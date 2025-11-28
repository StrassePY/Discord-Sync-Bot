import discord
from discord import ui

class _SuccessContainer(ui.Container):
    def __init__(self, message: str) -> None:
        super().__init__(accent_color=discord.Color.green())
        header = ui.TextDisplay("### ✅ Success")
        body = ui.TextDisplay(message)
        section = ui.Section(header, body)
        self.add_item(section)

def create_success_container(message: str) -> _SuccessContainer:
    return _SuccessContainer(message)

