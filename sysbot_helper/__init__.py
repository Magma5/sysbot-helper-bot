from discord.ext import commands
import logging
import yaml
import argparse


def bot_main():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('config_file', nargs='?', default='config.yml',
                        help='Config file to use for the bot')
    args = parser.parse_args()

    with open(args.config_file) as f:
        config = yaml.safe_load(f)

    bot = commands.Bot(**config['bot'])
    bot.config = config

    bot.load_extension('cogs')

    bot.run(config['token'])
