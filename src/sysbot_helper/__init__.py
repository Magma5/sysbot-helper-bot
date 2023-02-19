import argparse
import logging
import sys
from contextlib import suppress
from os import environ

import yaml

from .bot import Bot
from .schedule import scheduled

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger(__name__)


def bot_main():
    # Setting up the glorious argument parser
    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument(
        "config_file",
        nargs="?",
        default="config.yml",
        help="Config file to use for the bot",
    )

    # Parsing alembic args if needed
    argv = sys.argv[1:]
    alembic_argv = []

    with suppress(ValueError):
        idx = argv.index("alembic")
        argv, alembic_argv = argv[:idx], argv[idx + 1 :]

    # Run argument parser
    args = parser.parse_args(argv)

    # Load the glorious config file now
    with open(args.config_file, encoding="utf8") as f:
        config = yaml.safe_load(f)

    # Load database uri and create an engine
    database_url = config.pop("database_url", None)

    # Run alembic migration and exit if needed
    if alembic_argv:
        from alembic.config import CommandLine, Config

        cmd = CommandLine()
        options = cmd.parser.parse_args(alembic_argv)
        cfg = Config(file_=options.config, ini_section=options.name, cmd_opts=options)
        cfg.set_main_option("sqlalchemy.url", database_url)
        return cmd.run_cmd(cfg, options)

    # Read bot token
    config_token = config.pop("token", None)
    token = environ.get("TOKEN") or config_token

    # Initialize the bot
    helper_bot = Bot(config)

    if database_url:
        helper_bot.set_database(database_url)

    helper_bot.run(token)
