"""Tests for agentpipe.cli — the agentpipe console entry point."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from agentpipe._session import AgentSession
from agentpipe._types import GenerationResult, UsageEvent
from agentpipe.cli import _completed_ids, _load_batch_prompts, main


def _mock_generate(text="hello", usage=None):
    async def _gen(self_session, prompt, **kwargs):
        return GenerationResult(text=text, usage=usage, returncode=0)

    return _gen


class TestRun:
    def test_run_with_provider_prints_text(self, capsys):
        with patch.object(AgentSession, "generate_full", _mock_generate("the answer")):
            code = main(["run", "-p", "claude", "what is up"])
        assert code == 0
        assert "the answer" in capsys.readouterr().out

    def test_run_json_includes_usage(self, capsys):
        usage = UsageEvent(input_tokens=5, output_tokens=7, cost_usd=0.002)
        with patch.object(AgentSession, "generate_full", _mock_generate("ok", usage)):
            code = main(["run", "-p", "claude", "--json", "hi"])
        assert code == 0
        data = json.loads(capsys.readouterr().out)
        assert data["text"] == "ok"
        assert data["provider"] == "claude"
        assert data["cost_usd"] == 0.002

    def test_run_prompt_from_file(self, tmp_path, capsys):
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("file prompt")
        with patch.object(AgentSession, "generate_full", _mock_generate("from file")):
            code = main(["run", "-p", "claude", "-f", str(prompt_file)])
        assert code == 0
        assert "from file" in capsys.readouterr().out

    def test_run_provider_from_env(self, capsys, monkeypatch):
        monkeypatch.setenv("AGENTPIPE_PROVIDER", "claude")
        with patch.object(AgentSession, "generate_full", _mock_generate("env provider")):
            code = main(["run", "hi"])
        assert code == 0
        assert "env provider" in capsys.readouterr().out

    def test_run_failure_exits_nonzero(self, capsys):
        async def _boom(self_session, prompt, **kwargs):
            raise RuntimeError("nope")

        with patch.object(AgentSession, "generate_full", _boom):
            code = main(["run", "-p", "claude", "hi"])
        assert code == 1
        assert "nope" in capsys.readouterr().err


class TestLoadBatchPrompts:
    def test_plain_text_lines(self, tmp_path):
        f = tmp_path / "p.txt"
        f.write_text("first\nsecond\n\n")
        assert _load_batch_prompts(str(f), prompt_field="prompt", id_field="id") == [
            ("0", "first"),
            ("1", "second"),
        ]

    def test_jsonl_with_ids(self, tmp_path):
        f = tmp_path / "p.jsonl"
        f.write_text('{"id": "a", "prompt": "one"}\n{"prompt": "two"}\n')
        assert _load_batch_prompts(str(f), prompt_field="prompt", id_field="id") == [
            ("a", "one"),
            ("1", "two"),
        ]

    def test_jsonl_custom_fields(self, tmp_path):
        f = tmp_path / "p.jsonl"
        f.write_text('{"key": "k1", "question": "why?"}\n')
        assert _load_batch_prompts(str(f), prompt_field="question", id_field="key") == [("k1", "why?")]

    def test_missing_prompt_field_exits(self, tmp_path):
        f = tmp_path / "p.jsonl"
        f.write_text('{"id": "a"}\n')
        with pytest.raises(SystemExit):
            _load_batch_prompts(str(f), prompt_field="prompt", id_field="id")

    def test_empty_input_exits(self, tmp_path):
        f = tmp_path / "p.txt"
        f.write_text("\n\n")
        with pytest.raises(SystemExit):
            _load_batch_prompts(str(f), prompt_field="prompt", id_field="id")


class TestCompletedIds:
    def test_only_successful_ids_count(self, tmp_path):
        f = tmp_path / "out.jsonl"
        f.write_text(
            '{"id": "a", "text": "x", "error": null}\n'
            '{"id": "b", "text": null, "error": "boom"}\n'
            "not json\n"
        )
        assert _completed_ids(str(f)) == {"a"}

    def test_missing_file_is_empty(self, tmp_path):
        assert _completed_ids(str(tmp_path / "nope.jsonl")) == set()


class TestBatchCommand:
    def test_batch_writes_jsonl_and_reports(self, tmp_path, capsys):
        inp = tmp_path / "in.jsonl"
        inp.write_text('{"id": "q1", "prompt": "one"}\n{"id": "q2", "prompt": "two"}\n')
        out = tmp_path / "out.jsonl"

        with patch.object(AgentSession, "generate_full", _mock_generate("answer")):
            code = main(["batch", str(inp), "-o", str(out), "-p", "claude"])

        assert code == 0
        rows = [json.loads(line) for line in out.read_text().splitlines()]
        assert {r["id"] for r in rows} == {"q1", "q2"}
        assert all(r["ok"] for r in rows)
        assert "2 ok, 0 failed" in capsys.readouterr().err

    def test_batch_partial_failure_exits_1(self, tmp_path):
        inp = tmp_path / "in.txt"
        inp.write_text("good\nbad\n")
        out = tmp_path / "out.jsonl"

        async def _gen(self_session, prompt, **kwargs):
            if prompt == "bad":
                raise RuntimeError("kaboom")
            return GenerationResult(text="fine", returncode=0)

        with patch.object(AgentSession, "generate_full", _gen):
            code = main(["batch", str(inp), "-o", str(out), "-p", "claude"])

        assert code == 1
        rows = [json.loads(line) for line in out.read_text().splitlines()]
        failed = [r for r in rows if not r["ok"]]
        assert len(failed) == 1
        assert "kaboom" in failed[0]["error"]

    def test_batch_resume_skips_done(self, tmp_path, capsys):
        inp = tmp_path / "in.jsonl"
        inp.write_text('{"id": "a", "prompt": "one"}\n{"id": "b", "prompt": "two"}\n')
        out = tmp_path / "out.jsonl"
        out.write_text('{"id": "a", "text": "done", "error": null}\n')

        with patch.object(AgentSession, "generate_full", _mock_generate("answer")):
            code = main(["batch", str(inp), "-o", str(out), "-p", "claude", "--resume"])

        assert code == 0
        rows = [json.loads(line) for line in out.read_text().splitlines()]
        assert len(rows) == 2  # original line + the one new item
        assert "resuming: 1/2" in capsys.readouterr().err

    def test_batch_resume_without_output_errors(self, tmp_path, capsys):
        inp = tmp_path / "in.txt"
        inp.write_text("one\n")
        code = main(["batch", str(inp), "--resume", "-p", "claude"])
        assert code == 2


class TestProviders:
    def test_providers_json_lists_all(self, capsys):
        code = main(["providers", "--json"])
        assert code == 0
        rows = json.loads(capsys.readouterr().out)
        keys = {r["provider"] for r in rows}
        assert "claude" in keys
        assert "opencode-free" in keys
        assert all("installed" in r for r in rows)

    def test_providers_table(self, capsys):
        code = main(["providers"])
        assert code == 0
        assert "claude" in capsys.readouterr().out


class TestTiers:
    def test_tiers_json(self, capsys):
        code = main(["tiers", "--json"])
        assert code == 0
        data = json.loads(capsys.readouterr().out)
        assert "free" in data
        assert isinstance(data["free"], list)
