from os import environ
import logging
import yaml
import argparse
from .bot import Bot


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def bot_main():
    # Setting up the glorious argument parser
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('config_file', nargs='?', default='config.yml',
                        help='Config file to use for the bot')
    args = parser.parse_args()

    # Load the glorious config file now
    with open(args.config_file, encoding="utf8") as f:
        config = yaml.safe_load(f)

    # Read bot token
    config_token = config.pop('token', None)
    token = environ.get('TOKEN') or config_token

    # Initialize the bot
    bot = Bot(config)
    bot.helper.register_all_cogs()

    bot.run(token)
