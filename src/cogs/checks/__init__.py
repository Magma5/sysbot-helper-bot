from discord.ext.commands import NotOwner, check
from discord.ext.commands.errors import CheckFailure


def is_sudo():
    async def predicate(ctx):
        if not await ctx.bot.is_owner(ctx.author) and not ctx.user_groups.in_group(ctx.author.id, 'sudo'):
            raise NotOwner('You are not owner or sudo.')
        return True

    return check(predicate)


def is_in_any(*groups):
    async def predicate(ctx):
        if not ctx.user_groups.in_group_any(ctx.author.id, *groups):
            raise CheckFailure(f'You are not in any group: {",".join(groups)}')
        return True

    return check(predicate)
