import json

from agentpipe._types import ApprovalMode, HttpMcpServer, StdioMcpServer
from agentpipe.providers.claude import ClaudeProvider


class TestClaudeMcpConfig:
    def test_http_mcp_in_command(self):
        p = ClaudeProvider(
            model="sonnet",
            mcp_servers=[
                HttpMcpServer(name="docs", url="http://localhost:9000/sse", headers={"X-Key": "val"}),
            ],
        )
        cmd = p.build_command("test")
        assert "--mcp-config" in cmd
        idx = cmd.index("--mcp-config")
        config_json = cmd[idx + 1]
        config = json.loads(config_json)
        assert "mcpServers" in config
        assert "docs" in config["mcpServers"]
        assert config["mcpServers"]["docs"]["type"] == "sse"
        assert config["mcpServers"]["docs"]["headers"] == {"X-Key": "val"}
        assert "--strict-mcp-config" in cmd

    def test_stdio_mcp_in_command(self):
        p = ClaudeProvider(
            model="sonnet",
            mcp_servers=[
                StdioMcpServer(
                    name="github",
                    command="npx",
                    args=["-y", "@mcp/server-github"],
                    env={"GITHUB_TOKEN": "ghp_x"},
                ),
            ],
        )
        cmd = p.build_command("test")
        idx = cmd.index("--mcp-config")
        config = json.loads(cmd[idx + 1])
        assert "github" in config["mcpServers"]
        assert config["mcpServers"]["github"]["command"] == "npx"
        assert config["mcpServers"]["github"]["env"] == {"GITHUB_TOKEN": "ghp_x"}

    def test_no_mcp_servers_no_flag(self):
        p = ClaudeProvider(model="sonnet")
        cmd = p.build_command("test")
        assert "--mcp-config" not in cmd


class TestClaudeApprovalMode:
    def test_default_skips_permissions(self):
        p = ClaudeProvider(model="sonnet")
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" in cmd

    def test_yolo_mode(self):
        p = ClaudeProvider(model="sonnet", approval_mode=ApprovalMode.YOLO)
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" in cmd

    def test_bypass_mode(self):
        p = ClaudeProvider(model="sonnet", approval_mode=ApprovalMode.BYPASS)
        cmd = p.build_command("test")
        assert "--dangerously-skip-permissions" in cmd

    def test_plan_mode(self):
        p = ClaudeProvider(model="sonnet", approval_mode=ApprovalMode.PLAN)
        cmd = p.build_command("test")
        assert "--permission-mode" in cmd
        assert "--dangerously-skip-permissions" not in cmd
        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "plan"

    def test_default_approval_mode(self):
        p = ClaudeProvider(model="sonnet", approval_mode=ApprovalMode.DEFAULT)
        cmd = p.build_command("test")
        assert "--permission-mode" in cmd
        idx = cmd.index("--permission-mode")
        assert cmd[idx + 1] == "default"


class TestClaudeBudgetCap:
    def test_budget_flag(self):
        p = ClaudeProvider(model="sonnet", max_budget_usd=1.0)
        cmd = p.build_command("test")
        assert "--max-budget-usd" in cmd
        idx = cmd.index("--max-budget-usd")
        assert cmd[idx + 1] == "1.0"

    def test_no_budget_no_flag(self):
        p = ClaudeProvider(model="sonnet")
        cmd = p.build_command("test")
        assert "--max-budget-usd" not in cmd
