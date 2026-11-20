import pytest

import localdrop


@pytest.mark.unit
def test_package_exposes_version() -> None:
    assert localdrop.__version__ == "0.1.0"
