"""Pydantic schemas for configuration, workflow state, and council results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


PlanningEngineName = Literal["litellm", "opencode_cli"]
ExecutionAgentName = Literal["opencode", "aider", "kilocode"]
MCPTransportName = Literal["stdio", "http"]
RunStatus = Literal[
    "created",
    "stage1",
    "stage2",
    "stage3",
    "awaiting_plan_approval",
    "plan_approved",
    "task_graph_ready",
    "awaiting_execution_approval",
    "executing",
    "awaiting_commit_approval",
    "qa_review",
    "awaiting_completion_approval",
    "completed",
    "rejected",
    "failed",
]
TaskStatus = Literal[
    "awaiting_assignment",
    "awaiting_execution_approval",
    "executing",
    "qa_review",
    "execution_retry_needed",
    "awaiting_completion_approval",
    "completed",
    "rejected",
    "failed",
]
ApprovalGate = Literal["plan", "execution", "completion"]
ApprovalDecision = Literal["approved", "rejected", "edited"]
AssignmentApprovalState = Literal["pending", "approved", "rejected"]
QASeverity = Literal["critical", "high", "medium", "low"]
QARecommendation = Literal["pass", "fail"]
MCPApprovalStatus = Literal["pending", "approved", "rejected", "executed", "failed"]


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


class SkillDefinition(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    prompt_preamble: str = ""
    allowed_agents: list[str] = Field(default_factory=list)
    instructions: str = ""
    source: str = ""
    source_path: str = ""
    mcp_actions: list["MCPActionDefinition"] = Field(default_factory=list)


class SkillSourceConfig(BaseModel):
    path: str
    source_name: str
    recursive: bool = True


class MCPActionDefinition(BaseModel):
    type: Literal["tool", "resource", "prompt"]
    server_id: str
    name: str
    description: str = ""
    mutating: bool = False


class MCPServerConfig(BaseModel):
    id: str
    display_name: str
    transport: MCPTransportName = "stdio"
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    project_ids: list[str] = Field(default_factory=list)
    requires_approval_for_tools: list[str] = Field(default_factory=list)
    required_env: list[str] = Field(default_factory=list)
    notes: str = ""


class ProjectProfile(BaseModel):
    id: str
    name: str
    root_paths: list[str] = Field(default_factory=list)
    enabled_mcp_servers: list[str] = Field(default_factory=list)
    default_skill_ids: list[str] = Field(default_factory=list)


class AgentProfile(BaseModel):
    id: str
    display_name: str
    executor_type: ExecutionAgentName
    model_override: str = ""
    enabled_skills: list[str] = Field(default_factory=list)
    allowed_workflows: list[str] = Field(default_factory=lambda: ["execute"])
    qa_capable: bool = False


class TaskGenerationConfig(BaseModel):
    max_tasks: int = Field(default=5, ge=1, le=20)
    sequential_only: bool = True


class QAConfig(BaseModel):
    reviewer_agent_id: str | None = None
    blocking_severities: list[QASeverity] = Field(
        default_factory=lambda: ["critical", "high"]
    )


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
    agents: list[AgentProfile] = Field(default_factory=list)
    skills: list[SkillDefinition] = Field(default_factory=list)
    skill_sources: list[SkillSourceConfig] = Field(default_factory=list)
    mcp_servers: list[MCPServerConfig] = Field(default_factory=list)
    project_profiles: list[ProjectProfile] = Field(default_factory=list)
    task_generation: TaskGenerationConfig = Field(default_factory=TaskGenerationConfig)
    qa: QAConfig = Field(default_factory=QAConfig)

    @field_validator("council_members")
    @classmethod
    def validate_council_members(cls, value: list[CouncilMember]) -> list[CouncilMember]:
        enabled = [member for member in value if member.enabled]
        if not enabled:
            raise ValueError("At least one enabled council member is required")
        return value

    @field_validator("agents")
    @classmethod
    def validate_agents(cls, value: list[AgentProfile]) -> list[AgentProfile]:
        ids = [agent.id for agent in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Agent ids must be unique")
        return value

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, value: list[SkillDefinition]) -> list[SkillDefinition]:
        ids = [skill.id for skill in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Skill ids must be unique")
        return value

    @field_validator("mcp_servers")
    @classmethod
    def validate_mcp_servers(cls, value: list[MCPServerConfig]) -> list[MCPServerConfig]:
        ids = [server.id for server in value]
        if len(ids) != len(set(ids)):
            raise ValueError("MCP server ids must be unique")
        return value

    @field_validator("project_profiles")
    @classmethod
    def validate_project_profiles(cls, value: list[ProjectProfile]) -> list[ProjectProfile]:
        ids = [profile.id for profile in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Project profile ids must be unique")
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


class TaskRecord(BaseModel):
    id: str
    run_id: str
    title: str
    description: str
    status: TaskStatus = "awaiting_assignment"
    priority: int = Field(default=3, ge=1, le=5)
    depends_on: list[str] = Field(default_factory=list)
    recommended_agent_id: str | None = None
    recommended_skills: list[str] = Field(default_factory=list)
    selected_agent_id: str | None = None
    selected_skills: list[str] = Field(default_factory=list)
    routing_reason: str | None = None
    created_at: str
    updated_at: str
    latest_attempt_id: str | None = None
    latest_qa_report_id: str | None = None
    worktree_path: str | None = None
    branch_name: str | None = None


class ApprovalRecord(BaseModel):
    id: str
    gate: ApprovalGate
    decision: ApprovalDecision
    run_id: str
    task_id: str | None = None
    attempt_id: str | None = None
    actor: str = "human"
    notes: str = ""
    created_at: str


class TaskAssignment(BaseModel):
    id: str
    task_id: str
    run_id: str
    agent_id: str
    selected_skills: list[str] = Field(default_factory=list)
    assigned_by: str = "human"
    assigned_at: str
    approval_state: AssignmentApprovalState = "approved"
    notes: str = ""


class ExecutionAttempt(BaseModel):
    id: str
    task_id: str
    run_id: str
    attempt_no: int
    agent_id: str
    prompt: str
    started_at: str
    finished_at: str | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    test_result: str = "not_run"
    logs_path: str | None = None


class MCPApprovalRecord(BaseModel):
    id: str
    project_path: str
    server_id: str
    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)
    status: MCPApprovalStatus = "pending"
    actor: str = "human"
    notes: str = ""
    result_summary: str = ""
    created_at: str
    decided_at: str | None = None
    executed_at: str | None = None


class QAFinding(BaseModel):
    title: str
    severity: QASeverity
    details: str
    suggested_fix: str = ""


class QAReport(BaseModel):
    id: str
    task_id: str
    run_id: str
    attempt_id: str | None = None
    agent_id: str
    summary: str
    findings: list[QAFinding] = Field(default_factory=list)
    recommendation: QARecommendation
    raw_output: str = ""
    created_at: str


class RunRecord(BaseModel):
    id: str
    task: str
    project_path: str
    created_at: str
    status: RunStatus
    stage1_results: list[Stage1Result] = Field(default_factory=list)
    stage2_results: list[Stage2Result] = Field(default_factory=list)
    aggregate_rankings: list[AggregateRanking] = Field(default_factory=list)
    chairman_output: str = ""
    duration_ms: int = 0
    error: str | None = None
    workspace_path: str | None = None
    branch_name: str | None = None
    task_ids: list[str] = Field(default_factory=list)


SkillDefinition.model_rebuild()
