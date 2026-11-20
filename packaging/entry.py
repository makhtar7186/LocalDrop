"""Point d'entrée de l'exécutable Windows (PyInstaller exige un script)."""

import sys

from localdrop_desktop.application import main

if __name__ == "__main__":
    sys.exit(main())
