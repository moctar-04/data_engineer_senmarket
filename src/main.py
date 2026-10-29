#!/usr/bin/env python3
"""
Point d'entrée du générateur de données SenMarket (Étape 0).

Usage
-----
    python -m src.main                     # volumes par défaut (.env)
    python -m src.main --clients 1000      # override partiel
    python -m src.main --no-clean          # générer sans nettoyer
    python -m src.main --formats parquet   # un seul format

Le script :
  1. Charge la configuration (.env)
  2. Génère les données brutes (avec défauts réalistes)
  3. Les exporte (CSV / JSON / Parquet)
  4. Nettoie avec Pandas
  5. Exporte les versions nettoyées
  6. Affiche un rapport de nettoyage + comparaison de tailles
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permet d'exécuter depuis la racine du projet
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cleaner import clean_all, cleaning_report
from src.config import get_config, GeneratorConfig
from src.export import compare_format_sizes, export_all
from src.generator import SenMarketGenerator
from src.logging_config import setup_logging


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Générateur de données SenMarket — Étape 0"
    )
    p.add_argument("--clients", type=int, help="Nombre de clients")
    p.add_argument("--vendeurs", type=int, help="Nombre de vendeurs")
    p.add_argument("--produits", type=int, help="Nombre de produits")
    p.add_argument("--commandes", type=int, help="Nombre de commandes")
    p.add_argument("--avis", type=int, help="Nombre d'avis")
    p.add_argument("--events", type=int, help="Nombre d'événements")
    p.add_argument(
        "--formats",
        type=str,
        help="Formats d'export séparés par des virgules (csv,json,parquet)",
    )
    p.add_argument(
        "--no-clean",
        action="store_true",
        help="Ne pas exécuter l'étape de nettoyage",
    )
    p.add_argument(
        "--seed",
        type=int,
        help="Seed aléatoire (reproductibilité)",
    )
    return p.parse_args()


def apply_overrides(cfg: GeneratorConfig, args: argparse.Namespace) -> GeneratorConfig:
    """Applique les overrides CLI sur une config existante (via object.__setattr__ car frozen)."""
    # On reconstruit un GeneratorConfig non frozen pour simplicité
    from dataclasses import asdict, replace

    updates = {}
    if args.clients is not None:
        updates["n_clients"] = args.clients
    if args.vendeurs is not None:
        updates["n_vendeurs"] = args.vendeurs
    if args.produits is not None:
        updates["n_produits"] = args.produits
    if args.commandes is not None:
        updates["n_commandes"] = args.commandes
    if args.avis is not None:
        updates["n_avis"] = args.avis
    if args.events is not None:
        updates["n_events"] = args.events
    if args.formats is not None:
        updates["export_formats"] = [
            f.strip().lower() for f in args.formats.split(",") if f.strip()
        ]
    if args.seed is not None:
        updates["random_seed"] = args.seed

    if not updates:
        return cfg

    # GeneratorConfig est frozen → replace
    new_cfg = replace(cfg, **updates)
    new_cfg.validate()
    return new_cfg


def main() -> int:
    args = parse_args()

    try:
        cfg = get_config()
        cfg = apply_overrides(cfg, args)
    except ValueError as e:
        print(f"[ERREUR CONFIG] {e}", file=sys.stderr)
        return 1

    logger = setup_logging(cfg.log_level, cfg.log_file)
    logger.info("SenMarket Generator — démarrage")
    logger.info("Output brut  : %s", cfg.output_dir)
    logger.info("Output clean : %s", cfg.cleaned_dir)
    logger.info("Formats      : %s", cfg.export_formats)

    try:
        gen = SenMarketGenerator(cfg)
        raw = gen.generate_all()
    except Exception as e:
        logger.exception("Échec de la génération : %s", e)
        return 2

    # Export brut
    try:
        export_all(raw, cfg.output_dir, cfg.export_formats)
    except Exception as e:
        logger.exception("Échec de l'export brut : %s", e)
        return 3

    if not args.no_clean:
        try:
            cleaned = clean_all(raw)
            export_all(cleaned, cfg.cleaned_dir, cfg.export_formats)
            report = cleaning_report(raw, cleaned)
            logger.info("Rapport de nettoyage :\n%s", report.to_string(index=False))
        except Exception as e:
            logger.exception("Échec du nettoyage : %s", e)
            return 4

    # Comparaison de tailles (pour la fiche de décision)
    for name in ("clients", "commandes", "events"):
        sizes = compare_format_sizes(cfg.output_dir, name)
        if not sizes.empty:
            logger.info("Tailles [%s] :\n%s", name, sizes.to_string(index=False))

    logger.info("Terminé avec succès.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
