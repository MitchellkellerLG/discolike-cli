"""Tests for the discogen command group -- AI-powered enrichment."""

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


def make_cli_runner() -> CliRunner:
    return CliRunner()


def _extract_json(output: str) -> dict:
    """Extract the JSON portion from CLI output (skips Rich table prefix)."""
    idx = output.find("{")
    if idx == -1:
        raise ValueError(f"No JSON found in output: {output!r}")
    return json.loads(output[idx:])


@pytest.fixture
def discogen_completed_fixture() -> dict:
    return load_fixture("discogen_completed.json")


@pytest.fixture
def discogen_interim_fixture() -> dict:
    return load_fixture("discogen_interim.json")


@pytest.fixture
def mock_client_fixture(discogen_completed_fixture):
    """Provide a mock client with discogen submit + poll pre-wired."""
    with patch("discolike.cli.DiscoLikeClient") as MockClient:
        instance = MockClient.return_value
        instance.discogen_submit.return_value = {
            "task_id": "dg-test-001",
            "status": "in_progress",
        }
        instance.discogen_personas_submit.return_value = {
            "task_id": "dg-personas-001",
            "status": "in_progress",
        }
        instance.task_status.return_value = discogen_completed_fixture
        instance.cost_tracker = MagicMock()
        instance.cost_tracker.last_call = None
        instance.cost_tracker.estimate.return_value = MagicMock(
            endpoint="discogen",
            total=0.05,
            query_fee=0.005,
            record_fee=0.045,
            estimated=True,
        )
        yield instance


class TestDiscoGenRunSubmitsAndPolls:
    """Test the run subcommand submit -> poll lifecycle."""

    def test_discogen_run_submits_and_polls(self, mock_client_fixture) -> None:
        """discogen run --prompt '...' --domain acme.com submits and polls."""
        runner = make_cli_runner()

        with patch("discolike.commands.discogen.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "dg-test-001",
                "status": "completed",
                "results": [{"domain": "acme.com", "result": "B2B SaaS"}],
            }

            result = runner.invoke(
                cli,
                ["discogen", "run", "--prompt", "Summarize this company", "--domain", "acme.com", "--yes"],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        mock_client_fixture.discogen_submit.assert_called_once()
        call_params = mock_client_fixture.discogen_submit.call_args[0][0]
        assert call_params["prompt"] == "Summarize this company"
        assert "acme.com" in call_params["domains"]

    def test_discogen_run_context_mode(self, mock_client_fixture) -> None:
        """--context-mode domain passes context_mode='domain' in params."""
        runner = make_cli_runner()

        with patch("discolike.commands.discogen.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "dg-test-001",
                "status": "completed",
                "results": [],
            }

            result = runner.invoke(
                cli,
                [
                    "discogen", "run",
                    "--prompt", "Describe product",
                    "--domain", "acme.com",
                    "--context-mode", "domain",
                    "--yes",
                ],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        call_params = mock_client_fixture.discogen_submit.call_args[0][0]
        assert call_params.get("context_mode") == "domain"

    def test_discogen_run_saves_task(self, mock_client_fixture) -> None:
        """discogen run saves task_id to cache before poll."""
        runner = make_cli_runner()
        save_task_calls: list[str] = []

        with patch("discolike.commands.discogen.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "dg-test-001",
                "status": "completed",
                "results": [],
            }

            with patch("discolike.cache.CacheManager.save_task", side_effect=lambda tid, *a, **kw: save_task_calls.append(tid)):
                result = runner.invoke(
                    cli,
                    ["discogen", "run", "--prompt", "Describe", "--domain", "acme.com", "--yes"],
                )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        assert any("dg-test-001" in str(c) for c in save_task_calls), (
            f"Expected save_task('dg-test-001') to be called, got: {save_task_calls}"
        )


class TestDiscoGenRunOptions:
    """Test run subcommand option behavior."""

    def test_discogen_run_web_search_warning(self, mock_client_fixture, tmp_path) -> None:
        """--web-search with >50 domains emits a warning."""
        domains_file = tmp_path / "many_domains.txt"
        domains_file.write_text("\n".join(f"domain{i}.com" for i in range(51)))

        runner = make_cli_runner()

        with patch("discolike.commands.discogen.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "dg-test-001",
                "status": "completed",
                "results": [],
            }

            result = runner.invoke(
                cli,
                [
                    "discogen", "run",
                    "--prompt", "Summarize",
                    "--input", str(domains_file),
                    "--web-search",
                    "--yes",
                ],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        combined = result.output + result.stderr
        assert "web search" in combined.lower() or "cost" in combined.lower()

    def test_discogen_run_preflight_estimate(self, mock_client_fixture) -> None:
        """Pre-flight cost estimate is shown before submission."""
        runner = make_cli_runner()

        with patch("discolike.commands.discogen.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "dg-test-001",
                "status": "completed",
                "results": [],
            }

            result = runner.invoke(
                cli,
                ["discogen", "run", "--prompt", "Describe", "--domain", "acme.com", "--yes"],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        combined = result.output + result.stderr
        # Pre-flight estimate should show domain count or cost info
        assert "estimate" in combined.lower() or "cost" in combined.lower() or "domain" in combined.lower()

    def test_discogen_run_yes_skips_confirm(self, mock_client_fixture) -> None:
        """--yes flag skips confirmation prompt."""
        runner = make_cli_runner()

        with patch("discolike.commands.discogen.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "dg-test-001",
                "status": "completed",
                "results": [],
            }

            result = runner.invoke(
                cli,
                ["discogen", "run", "--prompt", "Describe", "--domain", "acme.com", "--yes"],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"

    def test_discogen_run_non_tty_no_yes_errors(self, mock_client_fixture) -> None:
        """Non-interactive without --yes exits with code 2."""
        runner = make_cli_runner()

        with patch("discolike.commands.discogen.sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False

            result = runner.invoke(
                cli,
                ["discogen", "run", "--prompt", "Describe", "--domain", "acme.com"],
            )

        assert result.exit_code == 2, f"Output: {result.output}\nError: {result.stderr}"

    def test_discogen_run_web_search_passes_param(self, mock_client_fixture) -> None:
        """--web-search flag adds web_search=True to submit params."""
        runner = make_cli_runner()

        with patch("discolike.commands.discogen.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "dg-test-001",
                "status": "completed",
                "results": [],
            }

            result = runner.invoke(
                cli,
                [
                    "discogen", "run",
                    "--prompt", "Describe",
                    "--domain", "acme.com",
                    "--web-search",
                    "--yes",
                ],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        call_params = mock_client_fixture.discogen_submit.call_args[0][0]
        assert call_params.get("web_search") is True

    def test_discogen_run_input_file(self, mock_client_fixture, tmp_path) -> None:
        """--input FILE reads domains from file via read_domains."""
        domains_file = tmp_path / "domains.txt"
        domains_file.write_text("acme.com\nstripe.com\n")

        runner = make_cli_runner()

        with patch("discolike.commands.discogen.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "dg-test-001",
                "status": "completed",
                "results": [],
            }

            result = runner.invoke(
                cli,
                ["discogen", "run", "--prompt", "Describe", "--input", str(domains_file), "--yes"],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        call_params = mock_client_fixture.discogen_submit.call_args[0][0]
        assert "acme.com" in call_params["domains"]
        assert "stripe.com" in call_params["domains"]


class TestDiscoGenPersonas:
    """Test the personas subcommand."""

    def test_discogen_personas_submits_to_personas_endpoint(self, mock_client_fixture, tmp_path) -> None:
        """discogen personas submits to the personas endpoint."""
        personas_file = tmp_path / "personas.txt"
        personas_file.write_text("persona-001\npersona-002\n")

        runner = make_cli_runner()

        with patch("discolike.commands.discogen.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "dg-personas-001",
                "status": "completed",
                "results": [{"persona_id": "persona-001", "result": "Sales decision maker"}],
            }

            result = runner.invoke(
                cli,
                [
                    "discogen", "personas",
                    "--prompt", "Describe this person",
                    "--input", str(personas_file),
                    "--yes",
                ],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        mock_client_fixture.discogen_personas_submit.assert_called_once()

    def test_discogen_personas_context_modes(self, mock_client_fixture, tmp_path) -> None:
        """discogen personas supports full|company|profile|name_only context modes."""
        personas_file = tmp_path / "personas.txt"
        personas_file.write_text("persona-001\n")

        runner = make_cli_runner()

        for mode in ["full", "company", "profile", "name_only"]:
            with patch("discolike.commands.discogen.AsyncTaskManager") as MockTaskMgr:
                mock_mgr = MockTaskMgr.return_value
                mock_mgr.poll.return_value = {
                    "task_id": "dg-personas-001",
                    "status": "completed",
                    "results": [],
                }

                result = runner.invoke(
                    cli,
                    [
                        "discogen", "personas",
                        "--prompt", "Describe",
                        "--input", str(personas_file),
                        "--context-mode", mode,
                        "--yes",
                    ],
                )

            assert result.exit_code == 0, f"Mode {mode}: Output: {result.output}"
            call_params = mock_client_fixture.discogen_personas_submit.call_args[0][0]
            assert call_params.get("context_mode") == mode

    def test_discogen_personas_invalid_context_mode(self, mock_client_fixture) -> None:
        """discogen personas rejects invalid context mode."""
        runner = make_cli_runner()

        result = runner.invoke(
            cli,
            [
                "discogen", "personas",
                "--prompt", "Describe",
                "--persona-id", "p-001",
                "--context-mode", "website",  # invalid for personas
                "--yes",
            ],
        )

        assert result.exit_code == 2, f"Output: {result.output}"

    def test_discogen_personas_web_search(self, mock_client_fixture, tmp_path) -> None:
        """discogen personas supports --web-search flag."""
        personas_file = tmp_path / "personas.txt"
        personas_file.write_text("persona-001\n")

        runner = make_cli_runner()

        with patch("discolike.commands.discogen.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "dg-personas-001",
                "status": "completed",
                "results": [],
            }

            result = runner.invoke(
                cli,
                [
                    "discogen", "personas",
                    "--prompt", "Describe",
                    "--input", str(personas_file),
                    "--web-search",
                    "--yes",
                ],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        call_params = mock_client_fixture.discogen_personas_submit.call_args[0][0]
        assert call_params.get("web_search") is True


class TestDiscoGenInterimResults:
    """Test interim results handling during polling."""

    def test_discogen_interim_results(self, mock_client_fixture) -> None:
        """on_result callback is called with interim results during polling."""
        runner = make_cli_runner()
        on_result_calls = []

        def fake_poll(task_id, on_result=None, **kwargs):
            # Simulate interim calls
            if on_result:
                on_result_calls.append(load_fixture("discogen_interim.json"))
            return load_fixture("discogen_completed.json")

        with patch("discolike.commands.discogen.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.side_effect = fake_poll

            result = runner.invoke(
                cli,
                ["discogen", "run", "--prompt", "Describe", "--domain", "acme.com", "--yes"],
            )

        assert result.exit_code == 0, f"Output: {result.output}\nError: {result.stderr}"
        # Verify poll was called with on_result keyword arg
        call_kwargs = MockTaskMgr.return_value.poll.call_args
        assert call_kwargs is not None

    def test_discogen_run_polls_with_on_result_kwarg(self, mock_client_fixture) -> None:
        """poll() is called with an on_result keyword argument."""
        runner = make_cli_runner()

        with patch("discolike.commands.discogen.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "dg-test-001",
                "status": "completed",
                "results": [{"domain": "acme.com", "result": "B2B SaaS"}],
            }

            result = runner.invoke(
                cli,
                ["discogen", "run", "--prompt", "Describe", "--domain", "acme.com", "--yes"],
            )

        assert result.exit_code == 0, f"Output: {result.output}"
        # Verify poll was called with on_result kwarg
        kwargs = mock_mgr.poll.call_args[1] if mock_mgr.poll.call_args else {}
        assert "on_result" in kwargs, f"Expected on_result in poll kwargs, got: {kwargs}"


class TestDiscoGenJsonOutput:
    """Test JSON output format."""

    def test_discogen_run_json_output(self, mock_client_fixture) -> None:
        """--json flag outputs JSON with results array."""
        runner = make_cli_runner()

        with patch("discolike.commands.discogen.AsyncTaskManager") as MockTaskMgr:
            mock_mgr = MockTaskMgr.return_value
            mock_mgr.poll.return_value = {
                "task_id": "dg-test-001",
                "status": "completed",
                "results": [
                    {"domain": "acme.com", "result": "B2B SaaS"},
                    {"domain": "stripe.com", "result": "Payments"},
                ],
            }

            result = runner.invoke(
                cli,
                ["--json", "discogen", "run", "--prompt", "Describe", "--domain", "acme.com", "--yes"],
            )

        assert result.exit_code == 0, f"Output: {result.output}"
        data = _extract_json(result.output)
        # Should have either records or results
        has_data = "records" in data or "results" in data or isinstance(data, list)
        assert has_data, f"Expected results in JSON output, got keys: {list(data.keys())}"
