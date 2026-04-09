"""Tests for the validate command -- ICP validation with sorted results."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from discolike.cli import cli

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    with open(FIXTURES / name) as f:
        return json.load(f)


def make_cli_runner(mix_stderr: bool = True) -> CliRunner:
    return CliRunner(mix_stderr=mix_stderr)


@pytest.fixture
def validate_fixture() -> dict:
    """Load the validate_completed.json fixture."""
    return load_fixture("validate_completed.json")


@pytest.fixture
def mock_client_fixture(validate_fixture):
    """Provide a mock client with validate submit + poll pre-wired."""
    with patch("discolike.cli.DiscoLikeClient") as MockClient:
        instance = MockClient.return_value
        instance.validate_icp_submit.return_value = {
            "task_id": "val-test-001",
            "status": "in_progress",
        }
        instance.task_status.return_value = validate_fixture
        instance.cost_tracker = MagicMock()
        instance.cost_tracker.last_call = None
        instance.cost_tracker.estimate.return_value = MagicMock(
            endpoint="validate/icp",
            total=0.01,
            query_fee=0.001,
            record_fee=0.009,
            estimated=True,
        )
        yield instance


class TestValidateSubmitAndPoll:
    """Test the submit -> poll lifecycle."""

    def test_submit_and_poll_lifecycle(self, mock_client_fixture, tmp_path) -> None:
        """validate --icp '...' --domain acme.com submits and polls."""
        runner = make_cli_runner()

        with patch("discolike.commands.validate.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "val-test-001",
                "status": "completed",
                "results": {
                    "gusto.com": {"Fit": "yes", "Confidence": "high", "Reasoning": "HR platform"},
                },
            }

            result = runner.invoke(
                cli,
                ["validate", "--icp", "HR software for SMBs", "--domain", "gusto.com", "--yes"],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        mock_client_fixture.validate_icp_submit.assert_called_once()
        call_params = mock_client_fixture.validate_icp_submit.call_args[0][0]
        assert call_params["icp_text"] == "HR software for SMBs"
        assert "gusto.com" in call_params["domains"]
        mock_mgr.poll.assert_called_once_with("val-test-001")

    def test_task_saved_to_cache_before_poll(self, mock_client_fixture, tmp_path) -> None:
        """validate saves task to cache before starting poll."""
        runner = make_cli_runner()
        save_task_calls: list[str] = []

        with patch("discolike.commands.validate.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "val-test-001",
                "status": "completed",
                "results": {"gusto.com": {"Fit": "yes", "Confidence": "high", "Reasoning": ""}},
            }

            # Capture save_task calls on the real CacheManager via cache module patch
            with patch("discolike.cache.CacheManager.save_task", side_effect=lambda tid, *a, **kw: save_task_calls.append(tid)):
                result = runner.invoke(
                    cli,
                    ["validate", "--icp", "HR tools", "--domain", "gusto.com", "--yes"],
                )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        # save_task should have been called with the task_id before poll
        assert any("val-test-001" in str(c) for c in save_task_calls), (
            f"Expected save_task('val-test-001') to be called, got: {save_task_calls}"
        )


def _extract_json(output: str) -> dict:
    """Extract the JSON portion from CLI output (skips Rich table prefix)."""
    # Find the first '{' which starts the JSON blob
    idx = output.find("{")
    if idx == -1:
        raise ValueError(f"No JSON found in output: {output!r}")
    return json.loads(output[idx:])


class TestValidateSortOrder:
    """Test that validate results are sorted correctly."""

    def test_yes_high_comes_first(self, mock_client_fixture) -> None:
        """First result after sort is yes+high."""
        runner = make_cli_runner()

        with patch("discolike.commands.validate.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = load_fixture("validate_completed.json")

            result = runner.invoke(
                cli,
                ["--json", "validate", "--icp", "HR tools", "--domain", "gusto.com", "--yes"],
            )

        assert result.exit_code == 0, f"Output: {result.output}"
        data = _extract_json(result.output)
        if isinstance(data, dict) and "records" in data:
            records = data["records"]
        else:
            records = data if isinstance(data, list) else []

        assert len(records) > 0, "Expected at least one record"
        first = records[0]
        assert first.get("Fit", "").lower() == "yes"
        assert first.get("Confidence", "").lower() == "high"

    def test_no_high_comes_last(self, mock_client_fixture) -> None:
        """Last result after sort is no+high."""
        runner = make_cli_runner()

        with patch("discolike.commands.validate.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = load_fixture("validate_completed.json")

            result = runner.invoke(
                cli,
                ["--json", "validate", "--icp", "HR tools", "--domain", "gusto.com", "--yes"],
            )

        assert result.exit_code == 0, f"Output: {result.output}"
        data = _extract_json(result.output)
        if isinstance(data, dict) and "records" in data:
            records = data["records"]
        else:
            records = data if isinstance(data, list) else []

        assert len(records) > 0, "Expected at least one record"
        last = records[-1]
        assert last.get("Fit", "").lower() == "no"
        assert last.get("Confidence", "").lower() == "high"


class TestValidateOptions:
    """Test command option behavior."""

    def test_context_mode_profile_passes_to_submit(self, mock_client_fixture) -> None:
        """--context-mode profile passes context_mode='profile' to submit params."""
        runner = make_cli_runner()

        with patch("discolike.commands.validate.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "val-001",
                "status": "completed",
                "results": {"gusto.com": {"Fit": "yes", "Confidence": "high", "Reasoning": ""}},
            }

            result = runner.invoke(
                cli,
                [
                    "validate",
                    "--icp", "HR tools",
                    "--domain", "gusto.com",
                    "--context-mode", "profile",
                    "--yes",
                ],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        call_params = mock_client_fixture.validate_icp_submit.call_args[0][0]
        assert call_params.get("context_mode") == "profile"

    def test_yes_flag_bypasses_confirm(self, mock_client_fixture) -> None:
        """--yes flag skips the confirmation prompt."""
        runner = make_cli_runner()

        with patch("discolike.commands.validate.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "val-001",
                "status": "completed",
                "results": {},
            }

            result = runner.invoke(
                cli,
                ["validate", "--icp", "HR tools", "--domain", "acme.com", "--yes"],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"

    def test_non_tty_without_yes_raises_usage_error(self, mock_client_fixture) -> None:
        """Non-interactive mode without --yes raises UsageError (exit 2)."""
        runner = make_cli_runner()

        # CliRunner simulates non-TTY by default
        with patch("discolike.commands.validate.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False

            result = runner.invoke(
                cli,
                ["validate", "--icp", "HR tools", "--domain", "acme.com"],
            )

        assert result.exit_code == 2, f"Output: {result.output}\nError: {result.stderr}"

    def test_web_search_flag_adds_param(self, mock_client_fixture) -> None:
        """--web-search passes web_search=True to submit params."""
        runner = make_cli_runner()

        with patch("discolike.commands.validate.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "val-001",
                "status": "completed",
                "results": {},
            }

            result = runner.invoke(
                cli,
                [
                    "validate",
                    "--icp", "HR tools",
                    "--domain", "acme.com",
                    "--web-search",
                    "--yes",
                ],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        call_params = mock_client_fixture.validate_icp_submit.call_args[0][0]
        assert call_params.get("web_search") is True

    def test_web_search_warns_for_many_domains(self, mock_client_fixture, tmp_path) -> None:
        """--web-search with >50 domains emits a warning to stderr."""
        domains_file = tmp_path / "many_domains.txt"
        domains_file.write_text("\n".join(f"domain{i}.com" for i in range(51)))

        runner = make_cli_runner()

        with patch("discolike.commands.validate.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "val-001",
                "status": "completed",
                "results": {},
            }

            result = runner.invoke(
                cli,
                [
                    "validate",
                    "--icp", "HR tools",
                    "--input", str(domains_file),
                    "--web-search",
                    "--yes",
                ],
            )

        assert result.exit_code == 0, f"Output: {result.output}"
        # Warning goes through Rich console (stderr), but CliRunner mixes by default
        assert "cost" in result.output.lower() or "web search" in result.output.lower()

    def test_input_file_reads_domains(self, mock_client_fixture, tmp_path) -> None:
        """--input FILE reads domains from the file."""
        domains_file = tmp_path / "domains.txt"
        domains_file.write_text("acme.com\nstripe.com\n")

        runner = make_cli_runner()

        with patch("discolike.commands.validate.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "val-001",
                "status": "completed",
                "results": {
                    "acme.com": {"Fit": "yes", "Confidence": "high", "Reasoning": ""},
                    "stripe.com": {"Fit": "no", "Confidence": "medium", "Reasoning": ""},
                },
            }

            result = runner.invoke(
                cli,
                ["validate", "--icp", "HR tools", "--input", str(domains_file), "--yes"],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        call_params = mock_client_fixture.validate_icp_submit.call_args[0][0]
        assert "acme.com" in call_params["domains"]
        assert "stripe.com" in call_params["domains"]


class TestValidateJsonOutput:
    """Test JSON output format."""

    def test_json_output_contains_meta(self, mock_client_fixture) -> None:
        """--json output contains _meta block."""
        runner = make_cli_runner()

        with patch("discolike.commands.validate.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "val-001",
                "status": "completed",
                "results": {
                    "gusto.com": {"Fit": "yes", "Confidence": "high", "Reasoning": "HR"},
                },
            }

            result = runner.invoke(
                cli,
                ["--json", "validate", "--icp", "HR tools", "--domain", "gusto.com", "--yes"],
            )

        assert result.exit_code == 0, f"Output: {result.output}"
        data = _extract_json(result.output)
        assert "_meta" in data, f"Expected _meta in JSON output, got keys: {list(data.keys())}"
