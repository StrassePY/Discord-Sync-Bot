from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import discord
from discord.ext import commands

from interface.logger import Logger


@dataclass
class CollectionResult:
    resolved: Dict[int, discord.Guild]
    missing: List[Tuple[str, int]]


class ConfiguredGuildsCollector:
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def collect(self, configured: Dict[str, int]) -> CollectionResult:
        """Resolve configured guild ids into guild objects with logging."""
        resolved: Dict[int, discord.Guild] = {}
        missing: List[Tuple[str, int]] = []

        for guild_name, guild_id in configured.items():
            guild = await self._resolve_guild(guild_name, guild_id)
            if guild is None:
                missing.append((guild_name, guild_id))
                continue

            resolved[guild_id] = guild
            Logger.success(
                "GuildSyncEngine -",
                f"Synchronized guild {guild_name} ({guild_id}).",
            )

        return CollectionResult(resolved=resolved, missing=missing)

    async def _resolve_guild(self, guild_name: str, guild_id: int) -> Optional[discord.Guild]:
        guild = self.bot.get_guild(guild_id)
        if guild is not None:
            return guild

        try:
            return await self.bot.fetch_guild(guild_id)
        except discord.Forbidden:
            Logger.warning(
                "GuildSyncEngine -",
                f"Missing permissions to access guild {guild_name} ({guild_id}); cannot sync commands.",
            )
        except discord.NotFound:
            Logger.warning(
                "GuildSyncEngine -",
                f"Bot is not a member of guild {guild_name} ({guild_id}); cannot sync commands.",
            )
        except discord.HTTPException as exc:
            Logger.error(
                "GuildSyncEngine -",
                f"HTTP error while fetching guild {guild_name} ({guild_id}): {exc}.",
            )

        return None

    async def resolve_single(self, guild_id: int, label: Optional[str] = None) -> Optional[discord.Guild]:
        """Resolve a single guild id for ad-hoc additions."""
        name_hint = label or "<unknown>"
        guild = await self._resolve_guild(name_hint, guild_id)
        if guild is None:
            Logger.error(
                "GuildSyncEngine -",
                f"Failed to resolve guild {name_hint} ({guild_id}); commands will not be synced.",
            )
        return guild

    def report_missing(self, missing: List[Tuple[str, int]]) -> None:
        if not missing:
            Logger.success(
                "GuildSyncEngine -",
                "All configured guilds synchronized successfully.",
            )
            return

        for guild_name, guild_id in missing:
            Logger.warning(
                "GuildSyncEngine -",
                f"Guild {guild_name} ({guild_id}) could not be synchronized.",
            )

    def report_unmanaged(self, configured_ids: Iterable[int]) -> List[discord.Guild]:
        unmanaged = [guild for guild in self.bot.guilds if guild.id not in configured_ids]
        if not unmanaged:
            return []

        details = ", ".join(f"{guild.name} ({guild.id})" for guild in unmanaged)
        Logger.info(
            "GuildSyncEngine -",
            f"Bot is in guilds not present in config: {details}.",
        )
        return unmanaged
