import discord
from discord import ui


class MessageContainer(ui.Container):
    def __init__(self, *, header: str, body: str, accent: discord.Color) -> None:
        super().__init__(accent_color=accent)
        self._header = ui.TextDisplay(header)
        self._body = ui.TextDisplay(body)
        self.add_item(self._header)
        self.add_item(self._body)

    @property
    def header(self) -> ui.TextDisplay:
        return self._header

    @property
    def body(self) -> ui.TextDisplay:
        return self._body
