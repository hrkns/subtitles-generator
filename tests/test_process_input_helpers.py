import pytest

from process_input import (
    generate_segments_from_checkpoints,
    generate_time_checkpoints,
    is_pattern,
    parse_segments,
    validate_and_order_checkpoints,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("5s", True),
        ("10m", True),
        ("1h", True),
        ("05m", False),
        ("0s", False),
        ("abc", False),
        ("15", False),
    ],
)
def test_is_pattern(value, expected):
    assert bool(is_pattern(value)) is expected


def test_generate_time_checkpoints_builds_periodic_offsets():
    assert generate_time_checkpoints("30s", 65000) == [
        (30000, "0:00:30"),
        (60000, "0:01:00"),
    ]


def test_generate_time_checkpoints_uses_total_duration_when_shorter_than_interval():
    assert generate_time_checkpoints("5m", 120000) == [(120000, "0:02:00")]


def test_validate_and_order_checkpoints_sorts_values():
    assert validate_and_order_checkpoints("00:10,00:05", 20000) == ["00:05", "00:10"]


def test_validate_and_order_checkpoints_rejects_invalid_format():
    with pytest.raises(ValueError, match="Invalid time format"):
        validate_and_order_checkpoints("invalid", 20000)


def test_validate_and_order_checkpoints_rejects_out_of_bounds_values():
    with pytest.raises(ValueError, match="out of bounds"):
        validate_and_order_checkpoints("00:30", 20000)


def test_generate_segments_from_checkpoints_adds_leading_and_trailing_ranges():
    assert generate_segments_from_checkpoints("1m", 125000) == [
        (0, 60000),
        (60000, 120000),
        (120000, 125000),
    ]


def test_parse_segments_handles_opening_and_open_ended_ranges():
    assert parse_segments(":00:10,00:10-00:20,00:20", 30000) == [
        (0, 10000),
        (10000, 20000),
        (20000, 30000),
    ]


def test_parse_segments_rejects_malformed_middle_ranges():
    with pytest.raises(ValueError, match="malformed"):
        parse_segments("00:10,00:20-00:30", 40000)


def test_parse_segments_rejects_reversed_ranges():
    with pytest.raises(ValueError, match="invalid"):
        parse_segments("00:20-00:10", 40000)
