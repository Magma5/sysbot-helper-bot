import argparse
import asyncio
import logging
from pathlib import Path

import yaml

from .bot import Bot
from .schedule import scheduled

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger(__name__)


def bot_main():
    parser = argparse.ArgumentParser(
        description="Multi functional bot originally developed to help sysbot helpers."
    )
    parser.add_argument(
        "config_file",
        nargs="+",
        type=Path,
        default="config.yml",
        help="Config file(s) to use for the bot.",
    )
    parser.add_argument(
        "--alembic", nargs=argparse.REMAINDER, help="Invoke alembic command."
    )

    # Run argument parser
    args = parser.parse_args()

    # Run alembic migration and exit if needed
    if args.alembic is not None:
        return run_alembic(args.config_file, args.alembic)

    asyncio.run(bot_start(args.config_file))


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
        cfg = Config(file_=options.config, ini_section=options.name, cmd_opts=options)
        cfg.set_main_option("sqlalchemy.url", database_url)
        return cmd.run_cmd(cfg, options)


async def bot_start(config_files):
    # Initialize and start all the bots
    futures = (Bot(config).start() for config in config_files)
    await asyncio.gather(*futures)
