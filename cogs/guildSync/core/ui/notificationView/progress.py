from __future__ import annotations

import discord

from .message import MessageContainer


_DEFAULT_BAR_WIDTH = 20


class ProgressContainer(MessageContainer):
    def __init__(self, message: str, *, progress: float = 0.0) -> None:
        super().__init__(
            header="### Working... ⏳",
            body=message,
            accent=discord.Color.yellow(),
        )
        self._base_message = message
        self._percentage = 0.0
        self._bar_width = _DEFAULT_BAR_WIDTH
        self._bar_display = discord.ui.TextDisplay(self._format_bar())
        self.add_item(self._bar_display)
        self.set_progress(progress)

    def set_progress(self, percentage: float, *, message: str | None = None) -> None:
        clamped = max(0.0, min(percentage, 100.0))
        self._percentage = clamped

        active_message = message if message is not None else self._base_message
        self.body.value = active_message
        self._bar_display.value = self._format_bar()

    def _format_bar(self) -> str:
        filled_slots = int(round((self._percentage / 100) * self._bar_width))
        filled_slots = min(self._bar_width, max(0, filled_slots))
        empty_slots = self._bar_width - filled_slots
        bar = f"[{'#' * filled_slots}{'-' * empty_slots}]"
        if self._percentage in {0.0, 100.0}:
            percent_display = f"{int(self._percentage):3d}%"
        else:
            percent_display = f"{self._percentage:6.2f}%"
        return f"{bar} {percent_display}"


def create_progress_container(message: str, *, progress: float = 0.0) -> ProgressContainer:
    return ProgressContainer(message, progress=progress)
