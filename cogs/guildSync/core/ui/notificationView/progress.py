import discord

from .message import MessageContainer


class ProgressContainer(MessageContainer):
    def __init__(self, message: str) -> None:
        super().__init__(
            header="### Working... ⏳",
            body=message,
            accent=discord.Color.blurple(),
        )


def create_progress_container(message: str) -> ProgressContainer:
    return ProgressContainer(message)
