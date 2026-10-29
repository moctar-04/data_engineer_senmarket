"""Tests unitaires du générateur SenMarket (Étape 0).

Couvre :
  - génération des entités
  - présence des colonnes attendues
  - injection de défauts
  - cas d'erreur (config invalide, datasets vides)
  - nettoyage (doublons, types)
  - export
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from src.cleaner import clean_all, clean_clients, cleaning_report
from src.config import GeneratorConfig, get_config
from src.export import export_all, export_dataframe
from src.generator import SenMarketGenerator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def small_config(tmp_path: Path) -> GeneratorConfig:
    """Config légère pour des tests rapides."""
    return GeneratorConfig(
        n_clients=50,
        n_vendeurs=10,
        n_produits=30,
        n_commandes=80,
        n_avis=40,
        n_events=100,
        random_seed=42,
        output_dir=tmp_path / "raw",
        cleaned_dir=tmp_path / "cleaned",
        export_formats=["csv", "parquet"],
        p_missing=0.05,
        p_duplicate=0.05,
        p_inconsistent_date=0.05,
        log_level="WARNING",
        log_file=tmp_path / "test.log",
    )


@pytest.fixture
def generator(small_config: GeneratorConfig) -> SenMarketGenerator:
    return SenMarketGenerator(small_config)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def test_config_validate_ok(small_config: GeneratorConfig):
    small_config.validate()  # ne doit pas lever


def test_config_invalid_clients():
    with pytest.raises(ValueError, match="N_CLIENTS"):
        GeneratorConfig(n_clients=0).validate()


def test_config_invalid_format():
    with pytest.raises(ValueError, match="Formats non supportés"):
        GeneratorConfig(export_formats=["xml"]).validate()


def test_config_invalid_probability():
    with pytest.raises(ValueError, match="P_MISSING"):
        GeneratorConfig(p_missing=1.5).validate()


# ---------------------------------------------------------------------------
# Génération
# ---------------------------------------------------------------------------
def test_generate_clients(generator: SenMarketGenerator):
    df = generator.generate_clients()
    assert len(df) >= 50  # peut être plus à cause des doublons
    assert "client_id" in df.columns
    assert "email" in df.columns
    assert "region" in df.columns
    assert df["client_id"].notna().all()


def test_generate_vendeurs(generator: SenMarketGenerator):
    df = generator.generate_vendeurs()
    assert len(df) >= 10
    assert "vendeur_id" in df.columns
    assert "nom_boutique" in df.columns


def test_generate_produits(generator: SenMarketGenerator):
    vendeurs = generator.generate_vendeurs()
    produits = generator.generate_produits(vendeurs)
    assert len(produits) >= 30
    assert "produit_id" in produits.columns
    assert "prix_fcfa" in produits.columns
    # Les vendeur_id des produits existent dans les vendeurs (hors doublons injectés)
    valid_vendeurs = set(vendeurs["vendeur_id"].dropna())
    assert produits["vendeur_id"].isin(valid_vendeurs).all()


def test_generate_commandes(generator: SenMarketGenerator):
    clients = generator.generate_clients()
    vendeurs = generator.generate_vendeurs()
    produits = generator.generate_produits(vendeurs)
    commandes, lignes = generator.generate_commandes(clients, produits)
    assert len(commandes) >= 80
    assert len(lignes) >= 80  # au moins 1 ligne par commande
    assert "commande_id" in commandes.columns
    assert "montant_total_fcfa" in commandes.columns
    assert set(lignes["commande_id"]).issubset(set(commandes["commande_id"]))


def test_generate_all(generator: SenMarketGenerator):
    datasets = generator.generate_all()
    expected = {
        "clients",
        "vendeurs",
        "produits",
        "commandes",
        "lignes_commande",
        "paiements",
        "avis",
        "events",
    }
    assert set(datasets.keys()) == expected
    for name, df in datasets.items():
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0, f"{name} est vide"


def test_reproducibility(small_config: GeneratorConfig):
    """Même seed → même volume et mêmes colonnes (uuid4 n'est pas seedable)."""
    g1 = SenMarketGenerator(small_config)
    g2 = SenMarketGenerator(small_config)
    c1 = g1.generate_clients()
    c2 = g2.generate_clients()
    assert len(c1) == len(c2)
    assert list(c1.columns) == list(c2.columns)
    regions_ok = {
        "Dakar", "Thiès", "Saint-Louis", "Diourbel", "Kaolack", "Ziguinchor",
        "Louga", "Fatick", "Kolda", "Matam", "Kaffrine", "Kédougou",
        "Sédhiou", "Tambacounda",
    }
    assert set(c1["region"].dropna().unique()).issubset(regions_ok)


# ---------------------------------------------------------------------------
# Cas d'erreur
# ---------------------------------------------------------------------------
def test_produits_sans_vendeurs(generator: SenMarketGenerator):
    empty = pd.DataFrame(columns=["vendeur_id"])
    with pytest.raises(ValueError, match="Aucun vendeur"):
        generator.generate_produits(empty)


def test_commandes_sans_clients(generator: SenMarketGenerator):
    empty_cli = pd.DataFrame(columns=["client_id"])
    empty_prd = pd.DataFrame(columns=["produit_id", "prix_fcfa"])
    with pytest.raises(ValueError, match="Clients ou produits"):
        generator.generate_commandes(empty_cli, empty_prd)


# ---------------------------------------------------------------------------
# Nettoyage
# ---------------------------------------------------------------------------
def test_clean_clients_removes_duplicates(generator: SenMarketGenerator):
    raw = generator.generate_clients()
    # Forcer des doublons
    raw = pd.concat([raw, raw.iloc[:5]], ignore_index=True)
    cleaned = clean_clients(raw)
    assert cleaned["client_id"].is_unique
    assert len(cleaned) < len(raw)


def test_clean_all(generator: SenMarketGenerator):
    raw = generator.generate_all()
    cleaned = clean_all(raw)
    assert set(cleaned.keys()) == set(raw.keys())
    report = cleaning_report(raw, cleaned)
    assert "doublons_supprimes" in report.columns
    assert report["doublons_supprimes"].sum() >= 0


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def test_export_csv_and_parquet(generator: SenMarketGenerator, tmp_path: Path):
    df = generator.generate_clients()
    paths = export_dataframe(df, "clients", tmp_path, ["csv", "parquet"])
    assert "csv" in paths and paths["csv"].exists()
    assert "parquet" in paths and paths["parquet"].exists()
    # Relecture
    df_csv = pd.read_csv(paths["csv"])
    df_pq = pd.read_parquet(paths["parquet"])
    assert len(df_csv) == len(df)
    assert len(df_pq) == len(df)


def test_export_all(generator: SenMarketGenerator, tmp_path: Path):
    datasets = {"clients": generator.generate_clients()}
    result = export_all(datasets, tmp_path, ["csv"])
    assert "clients" in result
    assert result["clients"]["csv"].exists()


# ---------------------------------------------------------------------------
# Intégration légère : pipeline complet
# ---------------------------------------------------------------------------
def test_full_pipeline(small_config: GeneratorConfig):
    gen = SenMarketGenerator(small_config)
    raw = gen.generate_all()
    export_all(raw, small_config.output_dir, small_config.export_formats)
    cleaned = clean_all(raw)
    export_all(cleaned, small_config.cleaned_dir, small_config.export_formats)

    # Vérifier que les fichiers existent
    assert (small_config.output_dir / "clients.csv").exists()
    assert (small_config.cleaned_dir / "clients.parquet").exists()
    assert (small_config.cleaned_dir / "commandes.csv").exists()
