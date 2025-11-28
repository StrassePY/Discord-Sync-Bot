import discord
from discord import ui

class _MessageContainer(ui.Container):
    def __init__(self, header: str, message: str, accent: discord.Color) -> None:
        super().__init__(accent_color=accent)
        self.add_item(ui.TextDisplay(header))
        self.add_item(ui.TextDisplay(message))


class _SuccessContainer(_MessageContainer):
    def __init__(self, message: str) -> None:
        super().__init__("### Operation Successful ✅", message, discord.Color.green())


class _ProgressContainer(_MessageContainer):
    def __init__(self, message: str) -> None:
        super().__init__("### Working... ⏳", message, discord.Color.blurple())


def create_success_container(message: str) -> _SuccessContainer:
    return _SuccessContainer(message)


def create_progress_container(message: str) -> _ProgressContainer:
    return _ProgressContainer(message)

