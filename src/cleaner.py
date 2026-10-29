"""Nettoyage des données brutes SenMarket avec Pandas.

Objectifs pédagogiques (Module 0) :
  - Gérer les valeurs manquantes
  - Supprimer les doublons
  - Corriger / filtrer les dates incohérentes
  - Typer correctement les colonnes
  - Produire un jeu propre réutilisable par les étapes suivantes
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

import pandas as pd

logger = logging.getLogger("senmarket.cleaner")


def _log_nulls(df: pd.DataFrame, name: str) -> None:
    nulls = df.isnull().sum()
    nulls = nulls[nulls > 0]
    if len(nulls):
        logger.info("[%s] Valeurs manquantes :\n%s", name, nulls.to_string())
    else:
        logger.info("[%s] Aucune valeur manquante", name)


def clean_clients(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Nettoyage clients (%s lignes)…", len(df))
    out = df.copy()
    before = len(out)

    # Doublons sur la clé métier
    out = out.drop_duplicates(subset=["client_id"], keep="first")
    logger.info("  Doublons clients supprimés : %s", before - len(out))

    # Emails et téléphones manquants : on garde la ligne mais on log
    _log_nulls(out, "clients")

    # Types
    out["date_inscription"] = pd.to_datetime(out["date_inscription"], errors="coerce")
    out["actif"] = out["actif"].astype("boolean")

    # Filtrer dates futures aberrantes
    now = pd.Timestamp.now()
    mask_future = out["date_inscription"] > now
    n_future = mask_future.sum()
    if n_future:
        logger.warning("  %s dates d'inscription futures → mises à NaT", n_future)
        out.loc[mask_future, "date_inscription"] = pd.NaT

    logger.info("  Clients nettoyés : %s lignes", len(out))
    return out.reset_index(drop=True)


def clean_vendeurs(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Nettoyage vendeurs (%s lignes)…", len(df))
    out = df.copy()
    before = len(out)
    out = out.drop_duplicates(subset=["vendeur_id"], keep="first")
    logger.info("  Doublons vendeurs supprimés : %s", before - len(out))
    out["date_inscription"] = pd.to_datetime(out["date_inscription"], errors="coerce")
    out["verifie"] = out["verifie"].astype("boolean")
    out["note_moyenne"] = pd.to_numeric(out["note_moyenne"], errors="coerce")
    return out.reset_index(drop=True)


def clean_produits(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Nettoyage produits (%s lignes)…", len(df))
    out = df.copy()
    before = len(out)
    out = out.drop_duplicates(subset=["produit_id"], keep="first")
    logger.info("  Doublons produits supprimés : %s", before - len(out))

    out["prix_fcfa"] = pd.to_numeric(out["prix_fcfa"], errors="coerce")
    out["stock"] = pd.to_numeric(out["stock"], errors="coerce").fillna(0).astype(int)
    out["date_ajout"] = pd.to_datetime(out["date_ajout"], errors="coerce")
    out["actif"] = out["actif"].astype("boolean")

    # Prix négatifs ou nuls → NaN (sera géré plus tard ou filtré)
    neg = (out["prix_fcfa"] <= 0).sum()
    if neg:
        logger.warning("  %s prix <= 0 → NaN", neg)
        out.loc[out["prix_fcfa"] <= 0, "prix_fcfa"] = pd.NA

    return out.reset_index(drop=True)


def clean_commandes(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Nettoyage commandes (%s lignes)…", len(df))
    out = df.copy()
    before = len(out)
    out = out.drop_duplicates(subset=["commande_id"], keep="first")
    logger.info("  Doublons commandes supprimés : %s", before - len(out))

    out["date_commande"] = pd.to_datetime(out["date_commande"], errors="coerce")
    out["montant_total_fcfa"] = pd.to_numeric(out["montant_total_fcfa"], errors="coerce")
    out["frais_livraison_fcfa"] = pd.to_numeric(
        out["frais_livraison_fcfa"], errors="coerce"
    ).fillna(0)

    now = pd.Timestamp.now()
    future = out["date_commande"] > now
    if future.any():
        logger.warning("  %s dates de commande futures → NaT (ligne conservée)", future.sum())
        out.loc[future, "date_commande"] = pd.NaT

    return out.reset_index(drop=True)


def clean_lignes_commande(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Nettoyage lignes_commande (%s lignes)…", len(df))
    out = df.copy()
    before = len(out)
    out = out.drop_duplicates(subset=["ligne_id"], keep="first")
    logger.info("  Doublons lignes supprimés : %s", before - len(out))
    out["quantite"] = pd.to_numeric(out["quantite"], errors="coerce").fillna(1).astype(int)
    out["prix_unitaire_fcfa"] = pd.to_numeric(out["prix_unitaire_fcfa"], errors="coerce")
    return out.reset_index(drop=True)


def clean_paiements(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Nettoyage paiements (%s lignes)…", len(df))
    out = df.copy()
    before = len(out)
    out = out.drop_duplicates(subset=["paiement_id"], keep="first")
    logger.info("  Doublons paiements supprimés : %s", before - len(out))

    out["date_paiement"] = pd.to_datetime(out["date_paiement"], errors="coerce")
    out["montant_fcfa"] = pd.to_numeric(out["montant_fcfa"], errors="coerce")

    now = pd.Timestamp.now()
    # Dates trop anciennes (> 5 ans) ou futures → on les met à NaT (on garde la ligne)
    too_old = out["date_paiement"] < (now - pd.Timedelta(days=5 * 365))
    future = out["date_paiement"] > now
    bad = too_old | future
    if bad.any():
        logger.warning(
            "  %s dates de paiement incohérentes → NaT (ligne conservée)", bad.sum()
        )
        out.loc[bad, "date_paiement"] = pd.NaT

    return out.reset_index(drop=True)


def clean_avis(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Nettoyage avis (%s lignes)…", len(df))
    out = df.copy()
    before = len(out)
    out = out.drop_duplicates(subset=["avis_id"], keep="first")
    logger.info("  Doublons avis supprimés : %s", before - len(out))
    out["note"] = pd.to_numeric(out["note"], errors="coerce")
    # Notes hors [1, 5]
    invalid = ~out["note"].between(1, 5) & out["note"].notna()
    if invalid.any():
        logger.warning("  %s notes hors [1,5] → NaN", invalid.sum())
        out.loc[invalid, "note"] = pd.NA
    out["date_avis"] = pd.to_datetime(out["date_avis"], errors="coerce")
    return out.reset_index(drop=True)


def clean_events(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Nettoyage events (%s lignes)…", len(df))
    out = df.copy()
    before = len(out)
    out = out.drop_duplicates(subset=["event_id"], keep="first")
    logger.info("  Doublons events supprimés : %s", before - len(out))
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    return out.reset_index(drop=True)


CLEANERS = {
    "clients": clean_clients,
    "vendeurs": clean_vendeurs,
    "produits": clean_produits,
    "commandes": clean_commandes,
    "lignes_commande": clean_lignes_commande,
    "paiements": clean_paiements,
    "avis": clean_avis,
    "events": clean_events,
}


def clean_all(datasets: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Applique le nettoyage adapté à chaque dataset."""
    logger.info("=== Début nettoyage ===")
    cleaned: Dict[str, pd.DataFrame] = {}
    for name, df in datasets.items():
        cleaner = CLEANERS.get(name)
        if cleaner is None:
            logger.warning("Pas de cleaner pour '%s' → copie brute", name)
            cleaned[name] = df.copy()
        else:
            cleaned[name] = cleaner(df)
    logger.info("=== Nettoyage terminé ===")
    return cleaned


def cleaning_report(
    raw: Dict[str, pd.DataFrame], cleaned: Dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Résumé avant/après pour le README / la fiche de décision."""
    rows = []
    for name in raw:
        r, c = raw[name], cleaned.get(name, raw[name])
        rows.append(
            {
                "dataset": name,
                "lignes_brutes": len(r),
                "lignes_nettoyees": len(c),
                "doublons_supprimes": len(r) - len(c),
                "nulls_restants": int(c.isnull().sum().sum()),
            }
        )
    return pd.DataFrame(rows)
