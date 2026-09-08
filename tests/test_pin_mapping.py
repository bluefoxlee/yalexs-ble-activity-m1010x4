"""Test PIN identifier/name mapping helpers."""

import pytest

from custom_components.yalexs_ble_activity.pin_mapping import (
    format_pin_names,
    normalize_pin_id,
    parse_pin_names,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0x22, "0x22"),
        ("22", "0x22"),
        ("0x1a", "0x1A"),
        (" 0Xee ", "0xEE"),
    ],
)
def test_normalize_pin_id(value, expected) -> None:
    """Normalize supported PIN identifier spellings."""
    assert normalize_pin_id(value) == expected


def test_parse_and_format_pin_names() -> None:
    """Parse editable text and format it in stable numeric order."""
    mapping = parse_pin_names(
        "# local names\n0xEE=Master PIN user\n0x1a = Person A\n0x22:Person B"
    )

    assert mapping == {
        "0x1A": "Person A",
        "0x22": "Person B",
        "0xEE": "Master PIN user",
    }
    assert format_pin_names(mapping) == (
        "0x1A=Person A\n0x22=Person B\n0xEE=Master PIN user"
    )


def test_parse_pin_names_rejects_invalid_line() -> None:
    """Reject a mapping line that cannot be interpreted safely."""
    with pytest.raises(ValueError, match="Line 1"):
        parse_pin_names("0x22")
