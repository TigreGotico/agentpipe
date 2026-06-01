from agentpipe._types import (
    CommandSpec,
    GenerationResult,
    Provider,
    SessionInfo,
    ThinkingEvent,
    ToolCallEvent,
    ToolResultEvent,
    UsageEvent,
)


class TestProvider:
    def test_values(self):
        assert Provider.CLAUDE.value == "claude"
        assert Provider.GEMINI.value == "gemini"
        assert Provider.OPENCODE.value == "opencode"


class TestThinkingEvent:
    def test_frozen(self):
        e = ThinkingEvent(text="hello")
        assert e.text == "hello"


class TestToolCallEvent:
    def test_frozen_with_args(self):
        e = ToolCallEvent(tool="Bash", args={"cmd": "ls"}, tool_id="t1")
        assert e.tool == "Bash"
        assert e.args == {"cmd": "ls"}
        assert e.tool_id == "t1"

    def test_defaults(self):
        e = ToolCallEvent(tool="Read")
        assert e.args is None
        assert e.tool_id is None


class TestToolResultEvent:
    def test_frozen(self):
        e = ToolResultEvent(tool="Bash", output="file.txt", duration_ms=150.0)
        assert e.output == "file.txt"
        assert e.duration_ms == 150.0


class TestUsageEvent:
    def test_frozen(self):
        e = UsageEvent(input_tokens=100, output_tokens=50, cost_usd=0.05)
        assert e.input_tokens == 100
        assert e.cost_usd == 0.05

    def test_defaults(self):
        e = UsageEvent()
        assert e.input_tokens == 0
        assert e.cost_usd is None


class TestGenerationResult:
    def test_frozen(self):
        events = (ThinkingEvent(text="hi"),)
        e = GenerationResult(text="hi", events=events, returncode=0)
        assert e.text == "hi"
        assert e.events == events
        assert e.session_id is None
        assert e.usage is None


class TestSessionInfo:
    def test_default(self):
        s = SessionInfo()
        assert s.session_id is None

    def test_set(self):
        s = SessionInfo(session_id="abc")
        assert s.session_id == "abc"


class TestCommandSpec:
    def test_frozen(self):
        c = CommandSpec(argv=["echo", "hi"], stdin="", timeout=10.0)
        assert c.argv == ["echo", "hi"]
        assert c.timeout == 10.0
