# flake8: noqa
from discord import SlashCommand, ClientException


class MySlashCommand(SlashCommand):
    """Workaround for Pycord-Development/pycord#1393 until upstream is fixed.

    https://github.com/Pycord-Development/pycord/issues/1393
    Removed parameter checks if the function is inside a class.
    """

    def _check_required_params(self, params):
        params = iter(params.items())
        required_params = (
            ["self", "context"] if self.attached_to_group or self.cog else ["context"]
        )
        for p in required_params:
            try:
                next(params)
            except StopIteration:
                raise ClientException(
                    f'Callback for {self.name} command is missing "{p}" parameter.'
                )

        return params
