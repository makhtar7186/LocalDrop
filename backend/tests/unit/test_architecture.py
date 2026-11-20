"""Garde d'architecture : domain/ reste du Python pur (ADR-001)."""

import ast
from pathlib import Path

import pytest

import localdrop

FORBIDDEN_IN_DOMAIN = ("fastapi", "starlette", "sqlalchemy", "uvicorn", "localdrop.infrastructure")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.unit
def test_domain_does_not_import_frameworks_or_infrastructure() -> None:
    domain_dir = Path(localdrop.__file__).parent / "domain"
    violations = [
        f"{py.relative_to(domain_dir)} -> {module}"
        for py in domain_dir.rglob("*.py")
        for module in _imported_modules(py)
        if module.startswith(FORBIDDEN_IN_DOMAIN)
    ]
    assert violations == []
