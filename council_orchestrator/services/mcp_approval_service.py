"""Stored approval workflow for mutating MCP tool calls."""

from __future__ import annotations

from ..mcp.service import call_server_tool
from ..schemas import AppConfig, MCPApprovalRecord
from ..storage.repositories import mcp_approval_repository, new_id, utc_now_iso


def create_mcp_approval(
    *,
    project_path: str,
    server_id: str,
    tool_name: str,
    arguments: dict[str, object],
    notes: str = "",
) -> MCPApprovalRecord:
    record = MCPApprovalRecord(
        id=new_id("mcp"),
        project_path=project_path,
        server_id=server_id,
        tool_name=tool_name,
        arguments=arguments,
        notes=notes,
        created_at=utc_now_iso(),
    )
    return mcp_approval_repository.save(record)


def approve_mcp_request(record: MCPApprovalRecord, notes: str = "") -> MCPApprovalRecord:
    record.status = "approved"
    record.notes = notes or record.notes
    record.decided_at = utc_now_iso()
    return mcp_approval_repository.save(record)


def reject_mcp_request(record: MCPApprovalRecord, notes: str = "") -> MCPApprovalRecord:
    record.status = "rejected"
    record.notes = notes or record.notes
    record.decided_at = utc_now_iso()
    return mcp_approval_repository.save(record)


async def execute_approved_mcp_request(record: MCPApprovalRecord, config: AppConfig) -> tuple[MCPApprovalRecord, object]:
    result = await call_server_tool(
        record.project_path,
        record.server_id,
        record.tool_name,
        record.arguments,
        config,
    )
    record.status = "executed"
    record.executed_at = utc_now_iso()
    record.result_summary = str(result)[:500]
    return mcp_approval_repository.save(record), result


def fail_mcp_request(record: MCPApprovalRecord, message: str) -> MCPApprovalRecord:
    record.status = "failed"
    record.result_summary = message[:500]
    record.executed_at = utc_now_iso()
    return mcp_approval_repository.save(record)
