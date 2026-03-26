"""Config management commands."""

from __future__ import annotations

import os

import click

from discolike.config import get_config_path, load_config, mask_key, save_config


@click.group("config")
def config() -> None:
    """Manage DiscoLike configuration."""


@config.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Show current configuration."""
    cfg = load_config()
    env_key = os.environ.get("DISCOLIKE_API_KEY")

    click.echo("DiscoLike Configuration")
    click.echo("=" * 40)
    if env_key:
        click.echo(f"API Key: {mask_key(env_key)} (from env)")
    elif cfg.get("api_key"):
        click.echo(f"API Key: {mask_key(cfg['api_key'])} (from config)")
    else:
        click.echo("API Key: not set")

    click.echo(f"Config file: {get_config_path()}")
    for key in ["default_country", "default_fields", "output_dir"]:
        if key in cfg:
            click.echo(f"{key}: {cfg[key]}")

    # Cache stats if available
    cli_ctx = ctx.obj
    if cli_ctx and cli_ctx.cache:
        stats = cli_ctx.cache.stats()
        click.echo(f"\nCache: {stats['total_entries']} entries at {stats['db_path']}")
        for cat, count in stats.get("by_category", {}).items():
            click.echo(f"  {cat}: {count}")


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a configuration value."""
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
    display_value = mask_key(value) if key == "api_key" else value
    click.echo(f"Set {key} = {display_value}")


@config.command("clear")
@click.argument("key", required=False)
def config_clear(key: str | None) -> None:
    """Clear a config value, or all config if no key given."""
    if key:
        cfg = load_config()
        if key in cfg:
            del cfg[key]
            save_config(cfg)
            click.echo(f"Cleared {key}")
        else:
            click.echo(f"Key '{key}' not found in config")
    else:
        save_config({})
        click.echo("Cleared all configuration")
