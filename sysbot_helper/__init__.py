from os import environ
import logging
import yaml
import argparse
from jinja2 import Environment, FileSystemLoader

from .helper import ConfigHelper
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
    config_token = config.pop('token', None)
    token = environ.get('TOKEN') or config_token

    # Initialize config helper
    helper = ConfigHelper(config)
    bot = helper.bot

    # Initialize Jinja2 template environment
    template_env = Environment(
        loader=FileSystemLoader("templates"))

    # Setting up some variables to be available in bot and ctx
    bot.make_command = helper.make_command
    bot.template_env = template_env
    bot.user_groups = helper.user_groups
    bot.channel_groups = helper.channel_groups
    bot.guild_config = helper.guild_config
    bot.channel_config = helper.channel_config
    bot.template_variables = helper.template_variables

    @bot.before_invoke
    async def _(ctx):
        ctx.template_variables = lambda: helper.template_variables(ctx)
        ctx.guild_config = helper.guild_config(ctx.guild)
        ctx.channel_config = helper.channel_config(ctx.channel)
        ctx.env = template_env
        ctx.user_groups = helper.user_groups()
        ctx.channel_groups = helper.channel_groups()

    # Load the cogs from config file
    for pkg, configs in helper.cog_config.items():
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
