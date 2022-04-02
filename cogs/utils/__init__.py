from .wait_tasks import wait_tasks_all, wait_tasks_any
from .parser import DiscordTextParser
from .discord_action import DiscordAction

__all__ = ['wait_tasks_any', 'wait_tasks_all', 'DiscordTextParser', 'DiscordAction']


def ensure_list(arg):
    if arg is None:
        return []
    if isinstance(arg, list):
        return arg
    return [arg]
