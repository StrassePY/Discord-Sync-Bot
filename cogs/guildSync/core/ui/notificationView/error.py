import discord

from .message import MessageContainer


class ErrorContainer(MessageContainer):
    def __init__(self, message: str) -> None:
        super().__init__(
            header="### Something Went Wrong ❌",
            body=message,
            accent=discord.Color.red(),
        )


def create_error_container(message: str) -> ErrorContainer:
    return ErrorContainer(message)
