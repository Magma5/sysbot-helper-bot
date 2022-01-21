from importlib import import_module
import logging

from .helpers import ConfigHelper


def setup(bot):
    # Load config file
    helper = ConfigHelper(bot)
    bot.helper = helper

    # Iterate through all defined cogs and load as extension
    for cog, config in helper.cogs_config.items():
        module = import_module('.' + cog, __name__)
        cls_cog = getattr(module, cog.capitalize())
        if hasattr(cls_cog, 'Config'):
            logging.info('Load cog with config: %s', cog)
            cls_config = getattr(cls_cog, 'Config')
            instance = cls_cog(bot, cls_config(**config))
        else:
            logging.info('Load cog: %s', cog)
            instance = cls_cog(bot)
        bot.add_cog(instance)
