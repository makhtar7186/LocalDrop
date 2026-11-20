import logging

import pytest

from localdrop.core.logging import REDACTED, RedactingFilter, redact


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "secret"),
    [
        ("Authorization: Bearer abc.DEF-123_xyz", "abc.DEF-123_xyz"),
        ("GET /download?ticket=T0k3nV4lue&x=1", "T0k3nV4lue"),
        ("http://192.168.1.10:8765/#/join?s=sess&k=Sup3rS3cret", "Sup3rS3cret"),
        ('{"secret": "hunter2hunter2"}', "hunter2hunter2"),
        ("device_token=zzzYYY", "zzzYYY"),
    ],
)
def test_redact_masks_secrets(raw: str, secret: str) -> None:
    result = redact(raw)
    assert secret not in result
    assert REDACTED in result


@pytest.mark.unit
def test_redact_keeps_ordinary_text() -> None:
    text = "Transfert 42 terminé : bank.pdf (12 Kio)"
    assert redact(text) == text


@pytest.mark.unit
def test_filter_redacts_formatted_arguments() -> None:
    record = logging.LogRecord(
        "t", logging.INFO, __file__, 1, "jeton reçu : token=%s", ("s3cr3tvalue",), None
    )
    assert RedactingFilter().filter(record) is True
    assert "s3cr3tvalue" not in record.getMessage()
