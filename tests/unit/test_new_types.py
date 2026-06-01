from agentpipe._types import (
    ApprovalMode,
    AuthStatus,
    HttpMcpServer,
    ModelInfo,
    SessionEntry,
    SessionUsage,
    StdioMcpServer,
    UsageEvent,
)


class TestApprovalMode:
    def test_values(self):
        assert ApprovalMode.DEFAULT.value == "default"
        assert ApprovalMode.AUTO_EDIT.value == "auto_edit"
        assert ApprovalMode.YOLO.value == "yolo"
        assert ApprovalMode.PLAN.value == "plan"
        assert ApprovalMode.BYPASS.value == "bypass"


class TestHttpMcpServer:
    def test_frozen(self):
        s = HttpMcpServer(name="docs", url="http://localhost:9000/sse")
        assert s.name == "docs"
        assert s.url == "http://localhost:9000/sse"
        assert s.headers == {}

    def test_headers(self):
        s = HttpMcpServer(name="api", url="http://localhost:8080", headers={"Auth": "Bearer x"})
        assert s.headers == {"Auth": "Bearer x"}


class TestStdioMcpServer:
    def test_frozen(self):
        s = StdioMcpServer(name="github", command="npx", args=["-y", "@modelcontextprotocol/server-github"])
        assert s.command == "npx"
        assert s.args == ["-y", "@modelcontextprotocol/server-github"]

    def test_env(self):
        s = StdioMcpServer(name="gh", command="npx", args=[], env={"GITHUB_TOKEN": "ghp_x"})
        assert s.env == {"GITHUB_TOKEN": "ghp_x"}


class TestSessionUsage:
    def test_add(self):
        usage = SessionUsage()
        usage.add(UsageEvent(input_tokens=100, output_tokens=50, cost_usd=0.05))
        assert usage.total_input_tokens == 100
        assert usage.total_output_tokens == 50
        assert usage.total_cost_usd == 0.05
        assert usage.turn_count == 1

    def test_accumulates(self):
        usage = SessionUsage()
        usage.add(UsageEvent(input_tokens=100, output_tokens=50, cost_usd=0.05))
        usage.add(UsageEvent(input_tokens=200, output_tokens=100, cost_usd=0.10))
        assert usage.total_input_tokens == 300
        assert usage.total_output_tokens == 150
        assert abs(usage.total_cost_usd - 0.15) < 0.001
        assert usage.turn_count == 2

    def test_cost_usd_none(self):
        usage = SessionUsage()
        usage.add(UsageEvent(input_tokens=100, output_tokens=50))
        assert usage.total_cost_usd == 0.0


class TestAuthStatus:
    def test_frozen(self):
        s = AuthStatus(authenticated=True, provider="claude", email="user@example.com")
        assert s.authenticated is True
        assert s.provider == "claude"


class TestSessionEntry:
    def test_frozen(self):
        s = SessionEntry(session_id="abc-123", provider="gemini")
        assert s.session_id == "abc-123"

    def test_defaults(self):
        s = SessionEntry(session_id="x")
        assert s.title is None
        assert s.provider is None


class TestModelInfo:
    def test_frozen(self):
        m = ModelInfo(id="sonnet", name="claude-sonnet-4", provider="claude")
        assert m.id == "sonnet"
        assert m.context_window is None

    def test_defaults(self):
        m = ModelInfo(id="test-model")
        assert m.name is None
        assert m.provider is None
