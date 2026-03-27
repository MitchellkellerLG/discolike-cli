# Setup Guide

Get discolike-cli running from zero.

## Prerequisites

- **Python 3.11+** — check with `python --version`
- **pip** — included with Python 3.11+

## Install

**Development (recommended if you're working on the CLI):**

```bash
git clone <repo-url> && cd discolike-cli
pip install -e ".[dev]"
```

**User install (just want to use it):**

```bash
pip install .
```

**Verify:**

```bash
discolike --version
```

## Configure API Key

Get your API key from your [DiscoLike dashboard](https://api.discolike.com/v1/docs/). Keys start with `dk_`.

**Option 1: Environment variable (recommended for CI/agents)**

```bash
export DISCOLIKE_API_KEY="dk_your_key_here"
```

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.) to persist across sessions.

**Option 2: Config file (recommended for personal use)**

```bash
discolike config set api_key dk_your_key_here
```

Saves to `~/.discolike/config.yaml`. The env var takes priority if both are set.

**Verify:**

```bash
discolike config show
```

You should see your key (masked) and its source (env or file).

## Verify Setup

```bash
discolike account status
```

This confirms your key is valid and shows your plan, spend, and budget. If this works, you're good.

## Your First Commands

**Extract website text (free, cached):**

```bash
discolike extract example.com
```

**Count matching companies ($0.18, no records pulled):**

```bash
discolike count --domain example.com --country US
```

**Discover lookalikes (costs per record):**

```bash
discolike discover --domain example.com --country US --max-records 5
```

**Safe full workflow (count → validate → confirm → pull):**

```bash
discolike workflow discover --seed example.com --country US --max-records 50
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `python: command not found` | Install Python 3.11+. On Windows, try `py` instead of `python`. |
| `requires Python >=3.11` | Upgrade Python or use `pyenv` / `conda` to manage versions. |
| Exit code 2 (auth error) | Key missing or invalid. Run `discolike config show` to check. |
| Exit code 3 (rate limited) | Wait and retry. DiscoLike enforces per-minute rate limits. |
| Exit code 4 (plan gate) | Feature requires a higher plan tier (Team or Enterprise). |
| Exit code 5 (budget exceeded) | Monthly budget hit. Check with `discolike account usage`. |
| `ModuleNotFoundError: discolike` | Run `pip install -e .` from the repo root. |

## Config Reference

| Setting | Description | Default |
|---------|-------------|---------|
| `api_key` | DiscoLike API key (`dk_...`) | — |
| `default_country` | Default country filter | — |
| `default_fields` | Default output columns | all |
| `output_dir` | Default output directory | `.` |

**File locations:**

- Config: `~/.discolike/config.yaml`
- Cache: `~/.discolike/cache.db`

Manage with `discolike config show|set|clear`.
