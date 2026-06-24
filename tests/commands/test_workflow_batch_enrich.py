"""RED test for Issue #20: workflow enrich-list must use /append not O(n*types) sequential calls.

Problem: workflow_enrich_list calls business_profile + score + growth per domain.
  5 domains * 3 types = 15 API calls.
Solution: batch all domains via client.append() — 1 API call regardless of n*types.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from discolike.cli import cli
from tests.conftest import make_cli_runner

BASE_URL = "https://api.discolike.com/v1"

# Fake /append response for 2 domains
APPEND_RESPONSE = {
    "results": [
        {
            "domain": "alpha.com",
            "name": "Alpha Co",
            "score": 400,
            "digital_footprint_score": 400,
            "score_growth_3m": 5.2,
            "subdomain_growth_3m": 1.1,
        },
        {
            "domain": "beta.com",
            "name": "Beta Inc",
            "score": 350,
            "digital_footprint_score": 350,
            "score_growth_3m": 3.1,
            "subdomain_growth_3m": 0.5,
        },
    ]
}


class TestEnrichListUsesBatchAppend:
    """workflow enrich-list must use /append for all enrichment types."""

    @respx.mock
    def test_enrich_list_calls_append_not_per_domain_endpoints(
        self, tmp_path: Path
    ) -> None:
        """With 2 domains and all fields, only 1 POST to /append, no /bizdata /score /growth."""
        respx.post(f"{BASE_URL}/append").mock(
            return_value=httpx.Response(200, json=APPEND_RESPONSE)
        )

        input_file = tmp_path / "domains.txt"
        input_file.write_text("alpha.com\nbeta.com\n")
        output_file = tmp_path / "enriched.json"

        runner = make_cli_runner()
        result = runner.invoke(
            cli,
            [
                "workflow", "enrich-list",
                "--input", str(input_file),
                "-o", str(output_file),
                "--fields", "profile,score,growth",
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr}\noutput: {result.output}"

        urls = [str(c.request.url) for c in respx.calls]
        # Must use append, not per-domain endpoints
        append_calls = [u for u in urls if "/append" in u]
        bizdata_calls = [u for u in urls if "/bizdata" in u]
        score_calls = [u for u in urls if "/score" in u]
        growth_calls = [u for u in urls if "/growth" in u]

        assert len(append_calls) == 1, f"Expected 1 /append call, got {len(append_calls)}"
        assert len(bizdata_calls) == 0, f"Should not call /bizdata individually, got {len(bizdata_calls)}"
        assert len(score_calls) == 0, f"Should not call /score individually, got {len(score_calls)}"
        assert len(growth_calls) == 0, f"Should not call /growth individually, got {len(growth_calls)}"

    @respx.mock
    def test_enrich_list_batch_passes_all_domains_to_append(
        self, tmp_path: Path
    ) -> None:
        """The /append POST body must include all domains."""
        captured: list[dict] = []

        def capture_append(request: httpx.Request) -> httpx.Response:
            captured.append(json.loads(request.content))
            return httpx.Response(200, json=APPEND_RESPONSE)

        respx.post(f"{BASE_URL}/append").mock(side_effect=capture_append)

        input_file = tmp_path / "domains.txt"
        input_file.write_text("alpha.com\nbeta.com\n")
        output_file = tmp_path / "enriched.json"

        runner = make_cli_runner()
        result = runner.invoke(
            cli,
            [
                "workflow", "enrich-list",
                "--input", str(input_file),
                "-o", str(output_file),
                "--fields", "profile",
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert len(captured) == 1
        body = captured[0]
        assert set(body["domains"]) == {"alpha.com", "beta.com"}

    @respx.mock
    def test_enrich_list_batch_output_contains_results(
        self, tmp_path: Path
    ) -> None:
        """Output JSON must contain records from /append response."""
        respx.post(f"{BASE_URL}/append").mock(
            return_value=httpx.Response(200, json=APPEND_RESPONSE)
        )

        input_file = tmp_path / "domains.txt"
        input_file.write_text("alpha.com\nbeta.com\n")
        output_file = tmp_path / "enriched.json"

        runner = make_cli_runner()
        result = runner.invoke(
            cli,
            [
                "workflow", "enrich-list",
                "--input", str(input_file),
                "-o", str(output_file),
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr}"
        data = json.loads(output_file.read_text())
        assert data["count"] == 2
        domains = {r["domain"] for r in data["records"]}
        assert domains == {"alpha.com", "beta.com"}

    @respx.mock
    def test_enrich_list_batch_single_api_call_for_n_domains(
        self, tmp_path: Path
    ) -> None:
        """5 domains still results in exactly 1 API call, not 5*3=15."""
        five_domain_response = {
            "results": [
                {"domain": f"d{i}.com", "name": f"Co {i}", "score": 400}
                for i in range(5)
            ]
        }
        respx.post(f"{BASE_URL}/append").mock(
            return_value=httpx.Response(200, json=five_domain_response)
        )

        input_file = tmp_path / "domains.txt"
        input_file.write_text("\n".join(f"d{i}.com" for i in range(5)) + "\n")
        output_file = tmp_path / "enriched.json"

        runner = make_cli_runner()
        result = runner.invoke(
            cli,
            [
                "workflow", "enrich-list",
                "--input", str(input_file),
                "-o", str(output_file),
                "--fields", "profile,score,growth",
            ],
        )
        assert result.exit_code == 0, f"stderr: {result.stderr}"
        # Still just 1 call
        assert len(respx.calls) == 1
