"""Helpers for configuring local names for Yale credential identifiers."""

from __future__ import annotations

from collections.abc import Mapping
import re

_PIN_ID_PATTERN = re.compile(r"^(?:0[xX])?([0-9a-fA-F]{1,2})$")


def normalize_pin_id(pin_id: int | str | None) -> str | None:
    """Return a canonical hexadecimal representation of a PIN identifier."""
    if isinstance(pin_id, bool):
        return None

    if isinstance(pin_id, int):
        value = pin_id
    elif isinstance(pin_id, str):
        match = _PIN_ID_PATTERN.fullmatch(pin_id.strip())
        if match is None:
            return None
        value = int(match.group(1), 16)
    else:
        return None

    if not 0 <= value <= 0xFF:
        return None
    return f"0x{value:02X}"


def parse_pin_names(value: str | Mapping[object, object] | None) -> dict[str, str]:
    """Parse PIN identifier/name mappings from config-flow text or stored data.

    The text format intentionally keeps the mapping easy to edit in Home
    Assistant: one ``0xNN=Name`` entry per line. A colon is also accepted as a
    separator for convenience.

    Returns:
        A mapping with canonical hexadecimal identifiers.

    Raises:
        ValueError: If an identifier, name, or mapping line is invalid.
    """
    if value is None:
        return {}

    if isinstance(value, Mapping):
        items = value.items()
    elif isinstance(value, str):
        items = []
        for line_number, line in enumerate(value.splitlines(), start=1):
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("#"):
                continue
            separator = "=" if "=" in stripped_line else ":"
            if separator not in stripped_line:
                raise ValueError(  # noqa: TRY003
                    f"Line {line_number}: expected 0xNN=Name"
                )
            pin_id, name = stripped_line.split(separator, 1)
            items.append((pin_id, name))
    else:
        raise ValueError("PIN mappings must be text or a mapping")  # noqa: TRY003, TRY004

    parsed: dict[str, str] = {}
    for pin_id, name in items:
        normalized_pin_id = normalize_pin_id(pin_id)
        if normalized_pin_id is None:
            raise ValueError(f"Invalid PIN identifier: {pin_id}")  # noqa: TRY003
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Missing name for {normalized_pin_id}")  # noqa: TRY003
        parsed[normalized_pin_id] = name.strip()

    return dict(sorted(parsed.items(), key=lambda item: int(item[0], 0)))


def format_pin_names(value: str | Mapping[object, object] | None) -> str:
    """Format stored PIN mappings for the config-flow text field.

    Returns:
        One canonical mapping entry per line.
    """
    return "\n".join(
        f"{pin_id}={name}" for pin_id, name in parse_pin_names(value).items()
    )
