"""Pydantic schemas for configuration and council results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


PlanningEngineName = Literal["litellm", "opencode_cli"]
ExecutionAgentName = Literal["opencode", "aider", "kilocode"]


class ProjectConfig(BaseModel):
    default_branch: str = "main"


class CouncilMember(BaseModel):
    name: str
    engine: PlanningEngineName
    model: str
    timeout_seconds: int = Field(default=120, ge=1)
    enabled: bool = True
    api_base: str | None = None         # custom API endpoint (e.g. Anthropic-compat)
    api_key_env: str | None = None      # env-var name holding the API key


class ChairmanConfig(CouncilMember):
    pass


class ExecutorConfig(BaseModel):
    agent: ExecutionAgentName
    model: str = "openai/gpt-4o"
    test_command: list[str]
    max_retries: int = Field(default=3, ge=1)
    auto_commit: bool = True
    auto_push: bool = False

    @field_validator("test_command")
    @classmethod
    def validate_test_command(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("executor.test_command must not be empty")
        return value


class AppConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    council_members: list[CouncilMember]
    chairman: ChairmanConfig
    executor: ExecutorConfig

    @field_validator("council_members")
    @classmethod
    def validate_council_members(cls, value: list[CouncilMember]) -> list[CouncilMember]:
        enabled = [member for member in value if member.enabled]
        if not enabled:
            raise ValueError("At least one enabled council member is required")
        return value


class Stage1Result(BaseModel):
    member_name: str
    engine: PlanningEngineName
    model: str
    ok: bool
    response: str = ""
    error: str | None = None
    duration_ms: int = 0


class Stage2Result(BaseModel):
    reviewer_name: str
    reviewer_engine: PlanningEngineName
    reviewer_model: str
    ok: bool
    ranking_text: str = ""
    parsed_ranking: list[str] = Field(default_factory=list)
    label_to_member: dict[str, str] = Field(default_factory=dict)
    duration_ms: int = 0
    error: str | None = None


class AggregateRanking(BaseModel):
    member_name: str
    average_rank: float
    rankings_count: int
