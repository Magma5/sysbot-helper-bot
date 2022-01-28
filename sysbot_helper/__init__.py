from os import environ
from discord.ext import commands
import logging
import yaml
import argparse
from jinja2 import Environment, FileSystemLoader

from .helper import ConfigHelper
from .parser import DiscordTextParser
from importlib import import_module

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def bot_main():
    # Setting up the glorious argument parser
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('config_file', nargs='?', default='config.yml',
                        help='Config file to use for the bot')
    args = parser.parse_args()

    # Load the glorious config file now
    with open(args.config_file, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Initialize bot from config
    config_bot = config.pop('bot', {})
    bot = commands.Bot(**config_bot)
    token = config.pop('token', environ.get('TOKEN'))

    # Initialize config helper
    helper = ConfigHelper(bot, {
        'guilds': config.pop('guilds', {}),
        'channels': config.pop('channels', {})
    })

    # Initialize Jinja2 template environment
    template_env = Environment(
        loader=FileSystemLoader("templates"))

    # Setting up some variables to be available in bot and ctx
    bot.make_command = helper.make_command

    @bot.before_invoke
    async def _(ctx):
        ctx.template_variables = lambda: helper.template_variables(ctx)
        ctx.guild_config = lambda: helper.guild_config(ctx)
        ctx.channel_config = lambda: helper.channel_config(ctx)
        ctx.env = template_env
        ctx.DiscordTextParser = DiscordTextParser

    # Load the cogs from config file
    for pkg, configs in config.items():
        for cog_key, config in configs.items():
            module_name = f"{pkg}.{cog_key}"
            cls_name = ConfigHelper.cog_name(cog_key)

            module = import_module(module_name)
            if not hasattr(module, cls_name):
                log.warn('Unable to load cog %s from package %s!', cls_name, module_name)
                continue
            cls = getattr(module, cls_name)

            # Create a cog instance (with config) and add to the bot
            if hasattr(cls, 'Config'):
                log.info('Load cog with config: %s', cls_name)
                cls_config = getattr(cls, 'Config')
                instance = cls(bot, cls_config(**config))
            else:
                log.info('Load cog: %s', cls_name)
                instance = cls(bot)

            bot.add_cog(instance)
            helper.register_cog(cls_name)

    bot.run(token)
