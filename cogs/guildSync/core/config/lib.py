import json
import os
from typing import Any, Dict, Iterable, Optional, Set


CONFIG_DIR = os.path.join(os.path.dirname(__file__), "data")
GUILDS_FILE = os.path.join(CONFIG_DIR, "guilds.json")
COMMANDS_FILE = os.path.join(CONFIG_DIR, "commands.json")
UNMANAGED_FILE = os.path.join(CONFIG_DIR, "unmanaged.json")

_GUILDS_DEFAULT: Dict[str, int] = {}
_COMMANDS_DEFAULT: Dict[str, Any] = {"commands": {}}
_UNMANAGED_DEFAULT: Dict[str, Any] = {"suppressed": []}


def _ensure_config_dir() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)


def _load_json(path: str, default: Any) -> Any:
    _ensure_config_dir()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                pass

    with open(path, "w", encoding="utf-8") as file:
        json.dump(default, file, indent=4)

    # Return a deep copy of the default to avoid accidental mutation.
    return json.loads(json.dumps(default))


def _normalize_command_key(command_key: str) -> str:
    return command_key.replace(" ", ".").lower()


def _coerce_guild_list(raw: Any) -> Set[str]:
    if raw is None:
        return set()

    if isinstance(raw, dict):
        # Support compact structures like {"guilds": [...]} or {"include": [...]}.
        if "guilds" in raw:
            raw = raw.get("guilds")
        elif "include" in raw:
            raw = raw.get("include")
        else:
            return set()

    if raw == "*":
        return {"*"}

    if isinstance(raw, (list, tuple, set)):
        return {str(item) for item in raw}

    return {str(raw)}


_loaded_guilds: Dict[str, int] = _load_json(GUILDS_FILE, _GUILDS_DEFAULT)
loaded_guilds: Dict[str, int] = {
    name: int(guild_id)
    for name, guild_id in _loaded_guilds.items()
}

_loaded_command_scopes = _load_json(COMMANDS_FILE, _COMMANDS_DEFAULT)
command_scopes: Dict[str, Any] = {
    _normalize_command_key(command_key): value
    for command_key, value in _loaded_command_scopes.get("commands", {}).items()
}

_loaded_unmanaged = _load_json(UNMANAGED_FILE, _UNMANAGED_DEFAULT)
_suppressed_guilds: Set[str] = {
    str(guild_id) for guild_id in _loaded_unmanaged.get("suppressed", [])
}


def _save_unmanaged() -> None:
    with open(UNMANAGED_FILE, "w", encoding="utf-8") as file:
        json.dump({"suppressed": sorted(_suppressed_guilds)}, file, indent=4)


def is_guild_suppressed(guild_id: int) -> bool:
    return str(guild_id) in _suppressed_guilds


def suppress_guild(guild_id: int) -> None:
    key = str(guild_id)
    if key in _suppressed_guilds:
        return

    _suppressed_guilds.add(key)
    _save_unmanaged()


def clear_suppressed_guild(guild_id: int) -> None:
    key = str(guild_id)
    if key not in _suppressed_guilds:
        return

    _suppressed_guilds.remove(key)
    _save_unmanaged()


def _stringify_ids(ids: Iterable[Any]) -> Set[str]:
    return {str(item) for item in ids}


def _save_guilds() -> None:
    serializable = {
        name: int(guild_id)
        for name, guild_id in sorted(loaded_guilds.items(), key=lambda item: item[0].lower())
    }

    with open(GUILDS_FILE, "w", encoding="utf-8") as file:
        json.dump(serializable, file, indent=4)


def register_guild(guild_name: str, guild_id: int, *, overwrite: bool = False) -> bool:
    normalized_name = guild_name.strip()
    if not normalized_name:
        raise ValueError("Guild name cannot be empty.")

    existing = loaded_guilds.get(normalized_name)
    if existing == guild_id:
        return False

    if existing is not None and not overwrite:
        raise ValueError(
            f"Guild name '{normalized_name}' already maps to a different guild ({existing})."
        )

    loaded_guilds[normalized_name] = int(guild_id)
    clear_suppressed_guild(guild_id)
    _save_guilds()
    return True


def _save_command_scopes() -> None:
    serializable = {
        key: value
        for key, value in sorted(command_scopes.items())
    }

    with open(COMMANDS_FILE, "w", encoding="utf-8") as file:
        json.dump({"commands": serializable}, file, indent=4)


def get_guild_id(guild_name: str) -> Optional[int]:
    return loaded_guilds.get(guild_name)


def is_command_enabled_for_guild(command_key: str, guild_id: int) -> bool:
    normalized_key = _normalize_command_key(command_key)
    scope_definition = command_scopes.get(normalized_key)

    if scope_definition is None:
        return True

    if isinstance(scope_definition, dict):
        if "exclude" in scope_definition:
            excluded = _stringify_ids(scope_definition.get("exclude", []))
            return str(guild_id) not in excluded
        if "include" in scope_definition:
            included = _stringify_ids(scope_definition.get("include", []))
            return str(guild_id) in included
        if "guilds" in scope_definition:
            included = _stringify_ids(scope_definition.get("guilds", []))
            return str(guild_id) in included

    guilds = _coerce_guild_list(scope_definition)
    if not guilds:
        return False

    if "*" in guilds:
        return True

    return str(guild_id) in guilds


def disable_command_for_guild(command_key: str, guild_id: int) -> bool:
    normalized_key = _normalize_command_key(command_key)
    guild_str = str(guild_id)
    current = command_scopes.get(normalized_key)

    if current is None or current == "*":
        command_scopes[normalized_key] = {"exclude": [guild_str]}
        _save_command_scopes()
        return True

    if isinstance(current, dict) and "exclude" in current:
        excluded = _stringify_ids(current["exclude"])
        if guild_str in excluded:
            return False
        excluded.add(guild_str)
        command_scopes[normalized_key] = {"exclude": sorted(excluded)}
        _save_command_scopes()
        return True

    if isinstance(current, dict):
        included = _stringify_ids(
            current.get("include") or current.get("guilds") or []
        )
        if guild_str not in included:
            return False
        included.discard(guild_str)
        command_scopes[normalized_key] = sorted(included)
        _save_command_scopes()
        return True

    if isinstance(current, (list, tuple, set)):
        included = _stringify_ids(current)
        if guild_str not in included:
            return False
        included.discard(guild_str)
        command_scopes[normalized_key] = sorted(included)
        _save_command_scopes()
        return True

    return False


def enable_command_for_guild(command_key: str, guild_id: int) -> bool:
    normalized_key = _normalize_command_key(command_key)
    guild_str = str(guild_id)
    current = command_scopes.get(normalized_key)

    if current is None:
        return False

    if isinstance(current, dict) and "exclude" in current:
        excluded = _stringify_ids(current["exclude"])
        if guild_str not in excluded:
            return False
        excluded.discard(guild_str)
        if excluded:
            command_scopes[normalized_key] = {"exclude": sorted(excluded)}
        else:
            command_scopes.pop(normalized_key, None)
        _save_command_scopes()
        return True

    if isinstance(current, dict):
        included = _stringify_ids(
            current.get("include") or current.get("guilds") or []
        )
        if guild_str in included:
            return False
        included.add(guild_str)
        command_scopes[normalized_key] = sorted(included)
        _save_command_scopes()
        return True

    if isinstance(current, (list, tuple, set)):
        included = _stringify_ids(current)
        if guild_str in included:
            return False
        included.add(guild_str)
        command_scopes[normalized_key] = sorted(included)
        _save_command_scopes()
        return True

    if current == []:
        # Previously disabled globally – re-enable only for this guild.
        command_scopes[normalized_key] = [guild_str]
        _save_command_scopes()
        return True

    return False


def disable_command_globally(command_key: str) -> bool:
    normalized_key = _normalize_command_key(command_key)
    previous = command_scopes.get(normalized_key)
    if previous == []:
        return False
    command_scopes[normalized_key] = []
    _save_command_scopes()
    return True


def enable_command_globally(command_key: str) -> bool:
    normalized_key = _normalize_command_key(command_key)
    if normalized_key not in command_scopes:
        return False
    command_scopes.pop(normalized_key, None)
    _save_command_scopes()
    return True


def get_command_scope(command_key: str) -> Any:
    return command_scopes.get(_normalize_command_key(command_key))
