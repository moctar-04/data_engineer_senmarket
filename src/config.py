"""Configuration centralisée du générateur SenMarket.

Charge les variables d'environnement (fichier .env) avec des valeurs
par défaut sensées. Toute valeur sensible ou réglable passe par ici.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Charge .env s'il existe (ne plante pas sinon)
load_dotenv()

# Racine du projet (deux niveaux au-dessus de ce fichier : src/config.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


def _float(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)))


def _str(key: str, default: str) -> str:
    return os.getenv(key, default)


def _bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class GeneratorConfig:
    """Paramètres du générateur de données SenMarket."""

    # Volumes
    n_clients: int = field(default_factory=lambda: _int("N_CLIENTS", 5_000))
    n_vendeurs: int = field(default_factory=lambda: _int("N_VENDEURS", 200))
    n_produits: int = field(default_factory=lambda: _int("N_PRODUITS", 1_500))
    n_commandes: int = field(default_factory=lambda: _int("N_COMMANDES", 20_000))
    n_avis: int = field(default_factory=lambda: _int("N_AVIS", 8_000))
    n_events: int = field(default_factory=lambda: _int("N_EVENTS", 50_000))

    # Reproductibilité
    random_seed: int | None = field(
        default_factory=lambda: (
            int(os.getenv("RANDOM_SEED")) if os.getenv("RANDOM_SEED") else None
        )
    )

    # Chemins
    output_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / _str("OUTPUT_DIR", "data/raw")
    )
    cleaned_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / _str("CLEANED_DIR", "data/cleaned")
    )

    # Formats d'export
    export_formats: List[str] = field(
        default_factory=lambda: [
            f.strip().lower()
            for f in _str("EXPORT_FORMATS", "csv,json,parquet").split(",")
            if f.strip()
        ]
    )

    # Probabilités de défauts (réalistes pour un marketplace)
    p_missing: float = field(default_factory=lambda: _float("P_MISSING", 0.03))
    p_duplicate: float = field(default_factory=lambda: _float("P_DUPLICATE", 0.02))
    p_inconsistent_date: float = field(
        default_factory=lambda: _float("P_INCONSISTENT_DATE", 0.01)
    )

    # Logging
    log_level: str = field(default_factory=lambda: _str("LOG_LEVEL", "INFO"))
    log_file: Path = field(
        default_factory=lambda: PROJECT_ROOT / _str("LOG_FILE", "logs/generator.log")
    )

    def validate(self) -> None:
        """Vérifie la cohérence des paramètres. Lève ValueError si incohérent."""
        if self.n_clients < 1:
            raise ValueError("N_CLIENTS doit être >= 1")
        if self.n_vendeurs < 1:
            raise ValueError("N_VENDEURS doit être >= 1")
        if self.n_produits < 1:
            raise ValueError("N_PRODUITS doit être >= 1")
        if self.n_commandes < 1:
            raise ValueError("N_COMMANDES doit être >= 1")
        if not (0.0 <= self.p_missing <= 1.0):
            raise ValueError("P_MISSING doit être entre 0 et 1")
        if not (0.0 <= self.p_duplicate <= 1.0):
            raise ValueError("P_DUPLICATE doit être entre 0 et 1")
        allowed = {"csv", "json", "parquet"}
        unknown = set(self.export_formats) - allowed
        if unknown:
            raise ValueError(f"Formats non supportés : {unknown}. Autorisés : {allowed}")
        if not self.export_formats:
            raise ValueError("EXPORT_FORMATS ne peut pas être vide")


def get_config() -> GeneratorConfig:
    """Factory : charge et valide la configuration."""
    cfg = GeneratorConfig()
    cfg.validate()
    return cfg
