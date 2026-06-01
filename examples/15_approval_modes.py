"""
Approval modes and budget caps — Claude-specific features.

Usage:
    python -m examples.15_approval_modes
"""

import asyncio

from agentpipe import Agent, ApprovalMode


async def main():
    # Plan mode — read-only, no tool execution
    plan_agent = Agent("claude-sonnet", approval_mode=ApprovalMode.PLAN)
    print(f"Plan agent: {plan_agent.provider}/{plan_agent.model}")
    print(f"Approval mode: {plan_agent.approval_mode}")

    # Auto-edit — auto-approve file edits, ask for shell commands
    edit_agent = Agent("claude-sonnet", approval_mode=ApprovalMode.AUTO_EDIT)
    print(f"\nAuto-edit agent: {edit_agent.approval_mode}")

    # Budget cap — stop after spending $1.00
    budget_agent = Agent("claude-sonnet", max_budget_usd=1.00)
    print(f"\nBudget agent: max ${budget_agent.max_budget_usd}")

    # Full auto (default) — uses --dangerously-skip-permissions
    auto_agent = Agent("claude-sonnet")
    print(f"\nAuto agent: approval_mode={auto_agent.approval_mode}")

    # Live call (requires Claude CLI):
    # result = await plan_agent.generate("Analyze this codebase without making changes")  # noqa: ERA001
    # print(result)  # noqa: ERA001


if __name__ == "__main__":
    asyncio.run(main())
