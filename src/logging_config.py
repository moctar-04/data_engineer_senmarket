"""Configuration du logging pour le générateur SenMarket."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> logging.Logger:
    """
    Configure le logger racine 'senmarket'.

    - Console (stdout) toujours active
    - Fichier optionnel (crée le dossier parent si besoin)
    """
    logger = logging.getLogger("senmarket")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Évite les handlers dupliqués si on appelle plusieurs fois
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
