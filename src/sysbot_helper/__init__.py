import argparse
import asyncio
import logging
from pathlib import Path

import yaml

from .bot import Bot
from .schedule import scheduled

__all__ = ["Bot", "scheduled"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def bot_main():
    parser = argparse.ArgumentParser(description="Multi functional bot originally developed to help sysbot helpers.")
    parser.add_argument(
        "config_file",
        nargs="+",
        type=Path,
        default="config.yml",
        help="Config file(s) to use for the bot.",
    )
    parser.add_argument(
        "--check",
        "-c",
        action="store_true",
        help="Validate the configuration file(s) and exit without starting services.",
    )
    parser.add_argument("--alembic", nargs=argparse.REMAINDER, help="Invoke alembic command.")

    # Run argument parser
    args = parser.parse_args()

    # Run configuration check and exit if requested
    if args.check:
        raise SystemExit(run_config_check(args.config_file))

    # Run alembic migration and exit if needed
    if args.alembic is not None:
        return run_alembic(args.config_file, args.alembic)

    try:
        asyncio.run(bot_start(args.config_file))
    except KeyboardInterrupt:
        log.info("Shutdown signal received (SIGINT). Exiting cleanly.")


def run_config_check(config_files: list[Path]) -> int:
    """Validate configuration files and return exit status code (0 for success, 1 for failure)."""
    has_errors = False
    for config_file in config_files:
        if not config_file.exists():
            log.error("[FAIL] Config file '%s' does not exist.", config_file)
            has_errors = True
            continue

        try:
            cogs = Bot.validate_file(config_file)
            log.info("[OK] Config file '%s' is valid (%d cogs loaded: %s)", config_file, len(cogs), ", ".join(cogs))
        except Exception as err:
            log.error("[FAIL] Config file '%s' validation error: %s: %s", config_file, type(err).__name__, err)
            has_errors = True

    return 1 if has_errors else 0


def run_alembic(config_files: list[Path], alembic_argv):
    from alembic.config import CommandLine, Config

    for config_file in config_files:
        with config_file.open(encoding="utf8") as f:
            config = yaml.safe_load(f)

        # Load database uri and create an engine
        database_url = config.pop("database_url")

        if not alembic_argv:
            alembic_argv = ["-h"]

        cmd = CommandLine()
        options = cmd.parser.parse_args(alembic_argv)

        config_file_path = options.config
        if isinstance(config_file_path, list):
            config_file_path = config_file_path[0] if config_file_path else "alembic.ini"
        elif config_file_path is None:
            config_file_path = "alembic.ini"

        cfg = Config(file_=config_file_path, ini_section=options.name, cmd_opts=options)
        cfg.set_main_option("sqlalchemy.url", database_url)
        return cmd.run_cmd(cfg, options)


async def bot_start(config_files):
    # Initialize and start all the bots
    futures = (Bot.from_file(config).start() for config in config_files)
    await asyncio.gather(*futures)
