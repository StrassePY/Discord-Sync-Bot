import discord

from .message import MessageContainer


class SuccessContainer(MessageContainer):
    def __init__(self, message: str) -> None:
        super().__init__(
            header="### Operation Successful ✅",
            body=message,
            accent=discord.Color.green(),
        )


def create_success_container(message: str) -> SuccessContainer:
    return SuccessContainer(message)
