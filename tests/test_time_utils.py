import pytest

from convert_hhmmss_to_ms import convert_hhmmss_to_ms
from format_ms_duration import format_ms_duration


@pytest.mark.parametrize(
    ("timestamp", "expected_ms"),
    [
        (None, None),
        ("5", 5000),
        ("01:05", 65000),
        ("01:02:03", 3723000),
        ("00:00:00", 0),
    ],
)
def test_convert_hhmmss_to_ms(timestamp, expected_ms):
    assert convert_hhmmss_to_ms(timestamp) == expected_ms


@pytest.mark.parametrize(
    ("milliseconds", "use_separator", "expected"),
    [
        (0, False, "000000"),
        (0, True, "00:00:00"),
        (3723000, False, "010203"),
        (3723000, True, "01:02:03"),
    ],
)
def test_format_ms_duration(milliseconds, use_separator, expected):
    assert format_ms_duration(milliseconds, use_separator=use_separator) == expected


def test_format_ms_duration_rejects_negative_values():
    with pytest.raises(ValueError, match="non-negative"):
        format_ms_duration(-1)
