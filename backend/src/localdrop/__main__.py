"""Lancement du serveur seul : ``python -m localdrop``.

Le desktop (phase 8) embarquera le serveur dans un thread ; ce point d'entrée sert au
développement et aux tests manuels.
"""

from __future__ import annotations

import logging

import uvicorn

from localdrop.core.config import Settings
from localdrop.core.logging import setup_logging
from localdrop.main import create_app


def main() -> None:
    settings = Settings()
    setup_logging(settings)
    logging.getLogger(__name__).info(
        "Démarrage de LocalDrop sur http://%s:%d", settings.host, settings.port
    )
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        access_log=False,
        log_config=None,
        server_header=False,
    )


if __name__ == "__main__":
    main()
