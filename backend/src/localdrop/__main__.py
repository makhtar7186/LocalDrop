"""Lancement du serveur seul : ``python -m localdrop``.

Le QR Code et l'aide sont affichés dans le terminal (stdout, jamais dans les logs) ;
l'approbation se fait avec ``python -m localdrop.devtools``. Le desktop (phase 8)
réutilisera ``LocalServer`` dans un thread.
"""

from __future__ import annotations

import contextlib
import sys

from localdrop.core.config import Settings
from localdrop.core.logging import setup_logging
from localdrop.server import LocalServer, PortUnavailableError
from localdrop.services.container import build_services


def _print(text: str) -> None:
    print(text, flush=True)  # visible immédiatement même si stdout est redirigé


def main() -> None:
    with contextlib.suppress(AttributeError, ValueError):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    settings = Settings()
    setup_logging(settings)
    services = build_services(settings)
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    settings.admin_token_file.write_text(services.admin_token, encoding="utf-8")
    try:
        LocalServer(settings, services, output=_print).run()
    except PortUnavailableError as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        pass  # Ctrl+C : arrêt propre
    finally:
        services.close()
        settings.admin_token_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
