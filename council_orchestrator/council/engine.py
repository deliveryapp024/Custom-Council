"""Three-stage council orchestration."""

from __future__ import annotations

import asyncio
import os
import re
from collections import defaultdict
from typing import Any, Callable, Coroutine

from ..config import enabled_council_members
from ..engines import get_engine
from ..schemas import AggregateRanking, AppConfig, Stage1Result, Stage2Result

# Type alias for async callbacks
AsyncCallback = Callable[..., Coroutine[Any, Any, None]] | None


def build_generation_prompt(task: str) -> str:
    return f"""You are part of a council of senior software engineers.

Create an implementation plan for the following coding task.

Task:
{task}

Your plan should be concise but actionable. Use these sections:
1. Summary
2. Relevant files or code areas
3. Implementation steps
4. Testing plan
5. Risks or open questions
"""


def build_review_prompt(task: str, labeled_responses: list[tuple[str, str]]) -> str:
    responses_text = "\n\n".join(
        f"{label}:\n{response}" for label, response in labeled_responses
    )
    return f"""You are reviewing implementation plans for a coding task.

Task:
{task}

Here are the anonymized plans:

{responses_text}

Evaluate each plan for correctness, security, logic, and testability.
At the end, provide a final ranking in exactly this format:

FINAL RANKING:
1. Response A
2. Response B

Only rank the responses that were shown to you. Do not invent labels.
"""


def build_chairman_prompt(
    task: str,
    stage1_results: list[Stage1Result],
    stage2_results: list[Stage2Result],
    aggregate_rankings: list[AggregateRanking],
    feedback: str | None = None,
) -> str:
    stage1_text = "\n\n".join(
        f"Member: {result.member_name}\nModel: {result.model}\nPlan:\n{result.response}"
        for result in stage1_results
        if result.ok
    )
    stage2_text = "\n\n".join(
        f"Reviewer: {result.reviewer_name}\nRanking:\n{result.ranking_text}"
        for result in stage2_results
        if result.ok
    )
    aggregate_text = "\n".join(
        f"- {entry.member_name}: average rank {entry.average_rank} across {entry.rankings_count} reviews"
        for entry in aggregate_rankings
    )
    feedback_block = f"\nHuman feedback to incorporate:\n{feedback}\n" if feedback else ""
    return f"""You are the chairman of a coding council.

Task:
{task}

Stage 1 plans:
{stage1_text}

Stage 2 reviews:
{stage2_text}

Aggregate rankings:
{aggregate_text}
{feedback_block}
Produce one final implementation plan. Keep it actionable and concrete. Use these sections:
1. Summary
2. Files to change
3. Ordered implementation steps
4. Tests to run
5. Risks and follow-up checks
"""


async def run_stage1(
    task: str,
    config: AppConfig,
    on_member_done: AsyncCallback = None,
) -> list[Stage1Result]:
    prompt = build_generation_prompt(task)
    members = enabled_council_members(config)
    tasks_map: dict[asyncio.Task, str] = {}

    for member in members:
        engine = get_engine(member.engine)
        api_key = os.environ.get(member.api_key_env) if member.api_key_env else None
        t = asyncio.create_task(
            engine.generate(
                prompt,
                model=member.model,
                member_name=member.name,
                timeout=member.timeout_seconds,
                api_base=member.api_base,
                api_key=api_key,
            )
        )
        tasks_map[t] = member.name

    results: list[Stage1Result] = []
    for coro in asyncio.as_completed(list(tasks_map.keys())):
        response = await coro
        result = Stage1Result(
            member_name=response.member_name,
            engine=response.engine,
            model=response.model,
            ok=response.ok,
            response=response.text,
            error=response.error,
            duration_ms=response.duration_ms,
        )
        results.append(result)
        if on_member_done:
            await on_member_done(result)

    ok_count = sum(1 for r in results if r.ok)
    fail_count = len(results) - ok_count
    print(f"\nStage 1 complete: {ok_count} succeeded, {fail_count} failed")
    for r in results:
        status = "✓" if r.ok else "✗"
        print(f"  {status} {r.member_name} ({r.engine}/{r.model}) — {r.duration_ms}ms")

    if not any(result.ok for result in results):
        raise RuntimeError("All council members failed during Stage 1")

    return results


async def run_stage2(
    task: str,
    stage1_results: list[Stage1Result],
    config: AppConfig,
    on_review_done: AsyncCallback = None,
) -> tuple[list[Stage2Result], list[AggregateRanking]]:
    stage1_by_member = {result.member_name: result for result in stage1_results if result.ok}
    review_tasks_list = []

    for reviewer in enabled_council_members(config):
        reviewer_stage1 = stage1_by_member.get(reviewer.name)
        if reviewer_stage1 is None:
            continue

        candidates = [
            result
            for result in stage1_results
            if result.ok and result.member_name != reviewer.name
        ]
        if not candidates:
            continue

        labels = [f"Response {chr(65 + index)}" for index in range(len(candidates))]
        label_to_member = {
            label: candidate.member_name for label, candidate in zip(labels, candidates)
        }
        prompt = build_review_prompt(
            task,
            [(label, candidate.response) for label, candidate in zip(labels, candidates)],
        )
        review_tasks_list.append(
            asyncio.create_task(_run_single_review(reviewer, prompt, label_to_member))
        )

    print(f"\nPhase 2: Cross-reviewing plans ({len(review_tasks_list)} reviews)...")
    stage2_results: list[Stage2Result] = []
    for coro in asyncio.as_completed(review_tasks_list):
        result = await coro
        stage2_results.append(result)
        if on_review_done:
            await on_review_done(result)

    ok_count = sum(1 for r in stage2_results if r.ok)
    fail_count = len(stage2_results) - ok_count
    print(f"Stage 2 complete: {ok_count} succeeded, {fail_count} failed")
    aggregate_rankings = calculate_aggregate_rankings(stage2_results)
    return stage2_results, aggregate_rankings


async def _run_single_review(
    reviewer,
    prompt: str,
    label_to_member: dict[str, str],
) -> Stage2Result:
    engine = get_engine(reviewer.engine)
    api_key = os.environ.get(reviewer.api_key_env) if reviewer.api_key_env else None
    response = await engine.generate(
        prompt,
        model=reviewer.model,
        member_name=reviewer.name,
        timeout=reviewer.timeout_seconds,
        api_base=reviewer.api_base,
        api_key=api_key,
    )
    return Stage2Result(
        reviewer_name=response.member_name,
        reviewer_engine=response.engine,
        reviewer_model=response.model,
        ok=response.ok,
        ranking_text=response.text,
        parsed_ranking=parse_ranking_from_text(response.text),
        label_to_member=label_to_member,
        duration_ms=response.duration_ms,
        error=response.error,
    )


async def run_stage3(
    task: str,
    stage1_results: list[Stage1Result],
    stage2_results: list[Stage2Result],
    config: AppConfig,
    feedback: str | None = None,
) -> str:
    aggregate_rankings = calculate_aggregate_rankings(stage2_results)
    prompt = build_chairman_prompt(
        task,
        stage1_results,
        stage2_results,
        aggregate_rankings,
        feedback=feedback,
    )
    chairman = config.chairman
    print(f"\nPhase 3: Chairman synthesis ({chairman.name} via {chairman.engine})...")
    engine = get_engine(chairman.engine)
    response = await engine.generate(
        prompt,
        model=chairman.model,
        member_name=chairman.name,
        timeout=chairman.timeout_seconds,
    )
    if not response.ok:
        raise RuntimeError(f"Chairman synthesis failed: {response.error}")
    return response.text


def parse_ranking_from_text(ranking_text: str) -> list[str]:
    if "FINAL RANKING:" in ranking_text:
        _, ranking_section = ranking_text.split("FINAL RANKING:", maxsplit=1)
        numbered_matches = re.findall(r"\d+\.\s*Response [A-Z]", ranking_section)
        if numbered_matches:
            return [
                re.search(r"Response [A-Z]", match).group(0)
                for match in numbered_matches
                if re.search(r"Response [A-Z]", match)
            ]

        matches = re.findall(r"Response [A-Z]", ranking_section)
        if matches:
            return matches

    return re.findall(r"Response [A-Z]", ranking_text)


def calculate_aggregate_rankings(stage2_results: list[Stage2Result]) -> list[AggregateRanking]:
    positions: dict[str, list[int]] = defaultdict(list)

    for result in stage2_results:
        if not result.ok:
            continue
        for index, label in enumerate(result.parsed_ranking, start=1):
            member_name = result.label_to_member.get(label)
            if member_name:
                positions[member_name].append(index)

    aggregate = [
        AggregateRanking(
            member_name=member_name,
            average_rank=round(sum(ranks) / len(ranks), 2),
            rankings_count=len(ranks),
        )
        for member_name, ranks in positions.items()
        if ranks
    ]
    aggregate.sort(key=lambda item: (item.average_rank, item.member_name))
    return aggregate
