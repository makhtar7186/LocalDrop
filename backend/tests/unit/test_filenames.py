import pytest
from hypothesis import given
from hypothesis import strategies as st

from localdrop.domain.transfers.filenames import (
    DEFAULT_NAME,
    MAX_NAME_LENGTH,
    candidate_name,
    sanitize_filename,
)

pytestmark = pytest.mark.unit

FORBIDDEN = set('<>:"/\\|?*')
RESERVED = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("photo.jpg", "photo.jpg"),
        ("../../Windows/System32/evil.dll", "evil.dll"),
        ("..\\..\\boot.ini", "boot.ini"),
        ("C:\\Users\\x\\note.txt", "note.txt"),
        ("rapport<final>?.pdf", "rapportfinal.pdf"),
        ("nom avec espaces .  ", "nom avec espaces"),
        ("CON", "_CON"),
        ("con.txt", "_con.txt"),
        ("Lpt1.log", "_Lpt1.log"),
        ("console.txt", "console.txt"),
        ("..", DEFAULT_NAME),
        ("", DEFAULT_NAME),
        ("\x00\x1f", DEFAULT_NAME),
        ("Cafe\u0301.txt", "Café.txt"),  # NFC
        ("été 🌞 مرحبا.png", "été 🌞 مرحبا.png"),
    ],
)
def test_FR_032_sanitize_filename(raw: str, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_long_names_keep_their_extension() -> None:
    result = sanitize_filename("a" * 500 + ".mp4")
    assert len(result) == MAX_NAME_LENGTH
    assert result.endswith(".mp4")


@given(st.text(max_size=400))
def test_FR_032_sanitized_name_is_always_safe(raw: str) -> None:
    name = sanitize_filename(raw)
    assert name
    assert len(name) <= MAX_NAME_LENGTH
    assert not FORBIDDEN & set(name)
    assert all(ch.isprintable() for ch in name)
    assert name not in {".", ".."}
    assert not name.endswith((".", " "))
    assert name.split(".", 1)[0].rstrip(" ").upper() not in RESERVED
    assert sanitize_filename(name) == name  # idempotent


@pytest.mark.parametrize(
    ("attempt", "expected"),
    [(0, "photo.jpg"), (1, "photo (1).jpg"), (12, "photo (12).jpg")],
)
def test_FR_028_collision_candidates(attempt: int, expected: str) -> None:
    assert candidate_name("photo.jpg", attempt) == expected


def test_collision_candidate_without_extension_and_too_long() -> None:
    assert candidate_name("README", 2) == "README (2)"
    long_name = "b" * MAX_NAME_LENGTH
    assert len(candidate_name(long_name, 3)) <= MAX_NAME_LENGTH
