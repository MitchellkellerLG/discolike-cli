"""Configure LLM and search providers for DiscoLike.

Loads API keys from environment, then calls the discolike CLI
programmatically to set Serper (search) and DeepSeek (LLM) providers.

Usage: python scripts/configure_providers.py

Note: llm-providers API endpoint does not exist yet (2026-05-18).
The CLI wrapper is ready; DeepSeek config will work once the API ships.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from discolike.client import DiscoLikeClient
from discolike.cache import CacheManager
from discolike.cost import CostTracker


def _load_env():
    workspace = Path(__file__).resolve().parent.parent.parent.parent
    candidates = [workspace / ".env", workspace / ".claude" / ".env"]
    for env_path in candidates:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key and val and key not in os.environ:
                            os.environ[key] = val
            print(f"Loaded env from {env_path}")
            return True
    return False


def main():
    if not _load_env():
        print("Warning: No .env file found. Checking existing environment...")

    client = DiscoLikeClient(
        cache=CacheManager(),
        cost_tracker=CostTracker(),
    )

    configured = 0

    # --- Serper (search) ---
    serper_key = os.environ.get("SERPER_API_KEY")
    if serper_key:
        try:
            client.search_providers_set(
                "serper",
                {
                    "api_key": serper_key,
                    "integration_name": "Serper Dev",
                    "search_model": "serper/search",
                },
            )
            print("  Serper: configured (search_model: serper/search)")
            configured += 1
        except Exception as e:
            print(f"  Serper: FAILED — {e}")
    else:
        print("  Serper: SKIPPED — SERPER_API_KEY not set")
        print("    Add SERPER_API_KEY to .claude/.env")

    # --- DeepSeek (LLM) ---
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if deepseek_key:
        print("  DeepSeek: KEY FOUND but /llm-providers API endpoint not deployed yet.")
        print("    The CLI wrapper is ready. Until the API ships:")
        print("    Configure via DiscoLike web UI: https://app.discolike.com")
        print("    Or run once endpoint is live:")
        print("    discolike llm-providers set --provider deepseek --api-key $DEEPSEEK_API_KEY --model deepseek-flash --base-url https://api.deepseek.com/v1")
    else:
        print("  DeepSeek: SKIPPED — DEEPSEEK_API_KEY not set")
        print("    Add DEEPSEEK_API_KEY to .claude/.env")

    # --- Verify ---
    if configured > 0:
        print("\nVerifying configuration...")
        try:
            search = client.search_providers_list()
            if isinstance(search, dict):
                providers = search.get("providers", [])
                if isinstance(providers, list):
                    for p in providers:
                        print(f"  Search: {p.get('integration_name', '?')} ({p.get('provider', '?')}) model={p.get('search_model', '?')}")
                else:
                    print(f"  Search providers: {search}")
        except Exception as e:
            print(f"  Search list: {e}")

    print(f"\nDone. {configured}/1 providers configured (llm-providers API not yet deployed).")
    client.close()


if __name__ == "__main__":
    main()
