import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agentpipe import provision
from agentpipe.provision import CLI_SPECS, CliSpec, format_report, inspect, inspect_all


def _spec(**kw):
    base = {"binary": "kilo", "bundled": True}
    base.update(kw)
    return CliSpec(**base)


class TestSpecs(unittest.TestCase):
    def test_every_bundled_cli_is_covered(self):
        names = {s.binary for s in CLI_SPECS}
        self.assertTrue({"kilo", "opencode", "gemini", "aider", "vibe", "qodercli"} <= names)
        self.assertTrue({"claude", "agy", "mimo"} <= names)

    def test_only_kilo_and_opencode_claim_a_free_tier(self):
        free = {s.binary for s in CLI_SPECS if s.free_tier}
        self.assertEqual({"kilo", "opencode"}, free)

    def test_unbundled_clis_are_flagged(self):
        unbundled = {s.binary for s in CLI_SPECS if not s.bundled}
        self.assertEqual({"claude", "agy", "mimo"}, unbundled)


class TestInspect(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_missing_binary_is_not_usable(self):
        with patch.object(provision.shutil, "which", return_value=None):
            st = inspect(_spec(), home=self.home, environ={})
        self.assertFalse(st.installed)
        self.assertFalse(st.usable)
        self.assertIn("not installed", st.missing)

    def test_free_tier_cli_is_usable_with_no_credentials(self):
        with patch.object(provision.shutil, "which", return_value="/usr/bin/kilo"):
            st = inspect(_spec(free_tier=True), home=self.home, environ={})
        self.assertTrue(st.usable)
        self.assertFalse(st.has_credentials)
        self.assertEqual("", st.missing)

    def test_paid_cli_without_credentials_is_not_usable(self):
        spec = _spec(binary="vibe", free_tier=False, env_keys=("MISTRAL_API_KEY",))
        with patch.object(provision.shutil, "which", return_value="/usr/local/bin/vibe"):
            st = inspect(spec, home=self.home, environ={})
        self.assertFalse(st.usable)
        self.assertIn("MISTRAL_API_KEY", st.missing)

    def test_env_var_counts_as_a_credential(self):
        spec = _spec(binary="vibe", env_keys=("MISTRAL_API_KEY",))
        with patch.object(provision.shutil, "which", return_value="/usr/local/bin/vibe"):
            st = inspect(spec, home=self.home, environ={"MISTRAL_API_KEY": "sk-x"})
        self.assertTrue(st.usable)
        self.assertEqual(["MISTRAL_API_KEY"], st.env_found)

    def test_empty_env_var_is_not_a_credential(self):
        spec = _spec(binary="vibe", env_keys=("MISTRAL_API_KEY",))
        with patch.object(provision.shutil, "which", return_value="/usr/local/bin/vibe"):
            st = inspect(spec, home=self.home, environ={"MISTRAL_API_KEY": "   "})
        self.assertEqual([], st.env_found)
        self.assertFalse(st.usable)

    def test_mounted_credential_file_is_detected(self):
        (self.home / ".local" / "share" / "kilo").mkdir(parents=True)
        (self.home / ".local" / "share" / "kilo" / "auth.json").write_text('{"openrouter": {}}')
        spec = _spec(cred_globs=(".local/share/kilo/auth.json",))
        with patch.object(provision.shutil, "which", return_value="/usr/bin/kilo"):
            st = inspect(spec, home=self.home, environ={})
        self.assertEqual(1, len(st.creds_found))
        self.assertTrue(st.has_credentials)

    def test_empty_credential_file_does_not_count(self):
        (self.home / ".vibe").mkdir()
        (self.home / ".vibe" / ".env").write_text("")
        spec = _spec(binary="vibe", cred_globs=(".vibe/.env",))
        with patch.object(provision.shutil, "which", return_value="/usr/local/bin/vibe"):
            st = inspect(spec, home=self.home, environ={})
        self.assertEqual([], st.creds_found)

    def test_glob_credential_pattern_matches(self):
        (self.home / ".qoder").mkdir()
        (self.home / ".qoder" / "managed-token.json").write_text("{}")
        spec = _spec(binary="qodercli", cred_globs=(".qoder/*token*.json",))
        with patch.object(provision.shutil, "which", return_value="/usr/bin/qodercli"):
            st = inspect(spec, home=self.home, environ={})
        self.assertEqual(1, len(st.creds_found))


class TestDirectoryCreation(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_creates_missing_directories(self):
        spec = _spec(dirs=(".config/kilo", ".local/share/kilo"))
        with patch.object(provision.shutil, "which", return_value="/usr/bin/kilo"):
            st = inspect(spec, home=self.home, environ={})
        self.assertTrue((self.home / ".config" / "kilo").is_dir())
        self.assertEqual(2, len(st.created))

    def test_never_touches_an_existing_credential_file(self):
        target = self.home / ".local" / "share" / "kilo"
        target.mkdir(parents=True)
        auth = target / "auth.json"
        auth.write_text("SECRET-PAYLOAD")
        spec = _spec(dirs=(".local/share/kilo",), cred_globs=(".local/share/kilo/auth.json",))
        with patch.object(provision.shutil, "which", return_value="/usr/bin/kilo"):
            inspect(spec, home=self.home, environ={})
        self.assertEqual("SECRET-PAYLOAD", auth.read_text())

    def test_existing_directory_is_not_reported_as_created(self):
        (self.home / ".vibe").mkdir()
        spec = _spec(binary="vibe", dirs=(".vibe",))
        with patch.object(provision.shutil, "which", return_value="/usr/local/bin/vibe"):
            st = inspect(spec, home=self.home, environ={})
        self.assertEqual([], st.created)

    def test_nothing_is_created_for_a_missing_binary(self):
        spec = _spec(dirs=(".config/kilo",))
        with patch.object(provision.shutil, "which", return_value=None):
            st = inspect(spec, home=self.home, environ={})
        self.assertEqual([], st.created)
        self.assertFalse((self.home / ".config" / "kilo").exists())

    def test_dry_run_creates_nothing(self):
        spec = _spec(dirs=(".config/kilo",))
        with patch.object(provision.shutil, "which", return_value="/usr/bin/kilo"):
            st = inspect(spec, home=self.home, environ={}, dry_run=True)
        self.assertEqual(1, len(st.created))
        self.assertFalse((self.home / ".config" / "kilo").exists())

    def test_read_only_root_is_reported_not_raised(self):
        ro = self.home / "ro"
        ro.mkdir()
        os.chmod(ro, 0o500)
        self.addCleanup(os.chmod, ro, 0o700)
        spec = _spec(dirs=("kilo",))
        with patch.object(provision.shutil, "which", return_value="/usr/bin/kilo"):
            st = inspect(spec, home=ro, environ={})
        self.assertEqual([], st.created)
        self.assertEqual(1, len(st.unwritable))

    def test_existing_but_unwritable_directory_is_reported(self):
        d = self.home / ".vibe"
        d.mkdir()
        os.chmod(d, 0o500)
        self.addCleanup(os.chmod, d, 0o700)
        spec = _spec(binary="vibe", dirs=(".vibe",))
        with patch.object(provision.shutil, "which", return_value="/usr/local/bin/vibe"):
            st = inspect(spec, home=self.home, environ={})
        self.assertEqual([str(d)], st.unwritable)


class TestReport(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_report_never_prints_a_secret_value(self):
        with patch.object(provision.shutil, "which", return_value="/usr/bin/x"):
            statuses = inspect_all(home=self.home, environ={"MISTRAL_API_KEY": "sk-super-secret"})
        text = format_report(statuses)
        self.assertNotIn("sk-super-secret", text)
        self.assertIn("MISTRAL_API_KEY", text)

    def test_report_lists_every_cli(self):
        with patch.object(provision.shutil, "which", return_value=None):
            statuses = inspect_all(home=self.home, environ={})
        text = format_report(statuses)
        for spec in CLI_SPECS:
            self.assertIn(spec.binary, text)
        self.assertIn("Usable now: none", text)

    def test_report_mentions_unwritable_paths(self):
        os.chmod(self.home, 0o500)
        self.addCleanup(os.chmod, self.home, 0o700)
        with patch.object(provision.shutil, "which", return_value="/usr/bin/x"):
            statuses = inspect_all(home=self.home, environ={})
        text = format_report(statuses)
        self.assertIn("Read-only", text)

    def test_main_exits_zero_with_no_credentials(self):
        with patch.object(provision, "_home", return_value=self.home), \
                patch.dict(os.environ, {}, clear=True):
            self.assertEqual(0, provision.main(["--dry-run"]))

    def test_strict_flag_fails_when_nothing_is_usable(self):
        with patch.object(provision, "_home", return_value=self.home), \
                patch.object(provision.shutil, "which", return_value=None):
            self.assertEqual(1, provision.main(["--strict", "--dry-run"]))

    def test_help_exits_zero(self):
        self.assertEqual(0, provision.main(["--help"]))


if __name__ == "__main__":
    unittest.main()
