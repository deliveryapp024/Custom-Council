"""Discovery and normalization for external skill catalogs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .schemas import AppConfig, AgentProfile, SkillDefinition, SkillSourceConfig


def merge_discovered_skills(raw: dict[str, Any]) -> dict[str, Any]:
    merged = dict(raw)
    explicit_skills = [dict(item) for item in merged.get("skills", []) or []]
    skill_sources = [SkillSourceConfig.model_validate(item) for item in merged.get("skill_sources", []) or []]
    discovered = discover_skills(skill_sources)

    seen_ids: set[str] = set()
    merged_skills: list[dict[str, Any]] = []

    for skill in explicit_skills + [item.model_dump() for item in discovered]:
        skill_id = normalize_skill_id(skill.get("id") or skill.get("name") or "")
        if not skill_id or skill_id in seen_ids:
            continue
        skill["id"] = skill_id
        seen_ids.add(skill_id)
        merged_skills.append(skill)

    merged["skills"] = merged_skills
    if merged.get("agents"):
        all_skill_ids = [skill["id"] for skill in merged_skills]
        merged["agents"] = [
            expand_agent_skills(dict(agent), all_skill_ids)
            for agent in merged["agents"]
        ]
    return merged


def discover_skills(skill_sources: list[SkillSourceConfig]) -> list[SkillDefinition]:
    discovered: list[SkillDefinition] = []
    seen_ids: set[str] = set()

    for source in skill_sources:
        root = Path(source.path).expanduser()
        if not root.exists():
            continue
        pattern = "**/SKILL.md" if source.recursive else "*/SKILL.md"
        for skill_file in sorted(root.glob(pattern)):
            skill = load_skill_from_file(skill_file, source.source_name)
            if skill is None or skill.id in seen_ids:
                continue
            seen_ids.add(skill.id)
            discovered.append(skill)
    return discovered


def load_skill_from_file(path: Path, source_name: str) -> SkillDefinition | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter, body = split_frontmatter(content)
    metadata = yaml.safe_load(frontmatter) if frontmatter else {}
    if not isinstance(metadata, dict):
        metadata = {}

    name = str(metadata.get("name") or path.parent.name)
    description = str(metadata.get("description") or summarize_body(body))
    triggers = extract_triggers(metadata)
    prompt_preamble = summarize_body(body)

    return SkillDefinition(
        id=normalize_skill_id(name),
        name=name.replace("-", " ").title(),
        description=description,
        tags=triggers,
        prompt_preamble=prompt_preamble,
        allowed_agents=[],
        instructions=body.strip(),
        source=source_name,
        source_path=str(path),
    )


def split_frontmatter(content: str) -> tuple[str, str]:
    if not content.startswith("---"):
        return "", content

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", content, re.DOTALL)
    if not match:
        return "", content
    return match.group(1), match.group(2)


def extract_triggers(metadata: dict[str, Any]) -> list[str]:
    meta = metadata.get("metadata")
    if not isinstance(meta, dict):
        return []
    triggers = meta.get("triggers", "")
    if isinstance(triggers, list):
        return [str(item).strip().lower() for item in triggers if str(item).strip()]
    if isinstance(triggers, str):
        return [item.strip().lower() for item in triggers.split(",") if item.strip()]
    return []


def summarize_body(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped[:280]
    return "Imported skill instructions."


def normalize_skill_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized


def expand_agent_skills(agent: dict[str, Any], all_skill_ids: list[str]) -> dict[str, Any]:
    enabled = list(agent.get("enabled_skills", []) or [])
    if "*" in enabled:
        agent["enabled_skills"] = all_skill_ids
    return agent


def agent_skill_ids(agent: AgentProfile, config: AppConfig) -> set[str]:
    if "*" in agent.enabled_skills:
        return {skill.id for skill in config.skills}
    return set(agent.enabled_skills)
