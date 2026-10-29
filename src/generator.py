"""Générateur de données réalistes pour la marketplace sénégalaise SenMarket.

Produit :
  - clients
  - vendeurs
  - produits
  - commandes (+ lignes de commande)
  - paiements mobiles (Wave, Orange Money)
  - avis clients
  - événements de navigation (vues, clics, ajouts panier)

Les données contiennent volontairement des défauts réalistes
(doublons, valeurs manquantes, dates incohérentes) pour exercer
le nettoyage Pandas (Module 0 / Étape 0).
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from faker import Faker

from src.config import GeneratorConfig

logger = logging.getLogger("senmarket.generator")

# Localisation sénégalaise (noms, villes, téléphones)
fake = Faker("fr_FR")

# --- Constantes métier Sénégal / marketplace ---------------------------------

REGIONS_SN = [
    "Dakar",
    "Thiès",
    "Saint-Louis",
    "Diourbel",
    "Kaolack",
    "Ziguinchor",
    "Louga",
    "Fatick",
    "Kolda",
    "Matam",
    "Kaffrine",
    "Kédougou",
    "Sédhiou",
    "Tambacounda",
]

VILLES_SN = {
    "Dakar": ["Dakar", "Pikine", "Guédiawaye", "Rufisque", "Bargny"],
    "Thiès": ["Thiès", "Mbour", "Tivaouane", "Joal"],
    "Saint-Louis": ["Saint-Louis", "Richard-Toll", "Dagana"],
    "Diourbel": ["Diourbel", "Touba", "Mbacké"],
    "Kaolack": ["Kaolack", "Nioro du Rip"],
    "Ziguinchor": ["Ziguinchor", "Bignona", "Oussouye"],
    "Louga": ["Louga", "Kébémer"],
    "Fatick": ["Fatick", "Foundiougne"],
    "Kolda": ["Kolda", "Vélingara"],
    "Matam": ["Matam", "Ourossogui"],
    "Kaffrine": ["Kaffrine", "Koungheul"],
    "Kédougou": ["Kédougou", "Saraya"],
    "Sédhiou": ["Sédhiou", "Bounkiling"],
    "Tambacounda": ["Tambacounda", "Bakel"],
}

CATEGORIES = {
    "Électronique": ["Téléphones", "Ordinateurs", "Accessoires", "TV & Audio"],
    "Mode": ["Homme", "Femme", "Enfant", "Chaussures", "Accessoires mode"],
    "Maison": ["Meubles", "Déco", "Électroménager", "Cuisine"],
    "Alimentation": ["Épicerie", "Boissons", "Produits frais", "Épices"],
    "Beauté": ["Soins", "Maquillage", "Parfums", "Cheveux"],
    "Sport": ["Fitness", "Football", "Running", "Outdoor"],
    "Livres": ["Roman", "Scolaire", "BD", "Religion"],
    "Autres": ["Bricolage", "Jardin", "Jouets", "Animaux"],
}

MOYENS_PAIEMENT = ["Wave", "Orange Money", "Carte bancaire", "Espèces à la livraison"]
STATUTS_COMMANDE = ["en_attente", "confirmee", "expediee", "livree", "annulee", "retournee"]
STATUTS_PAIEMENT = ["reussi", "echoue", "en_attente", "rembourse"]
EVENT_TYPES = ["view", "click", "add_to_cart", "remove_from_cart", "search", "checkout_start"]


class SenMarketGenerator:
    """Générateur principal de données SenMarket."""

    def __init__(self, config: GeneratorConfig):
        self.cfg = config
        self._rng = np.random.default_rng(config.random_seed)
        if config.random_seed is not None:
            random.seed(config.random_seed)
            Faker.seed(config.random_seed)
            np.random.seed(config.random_seed)
        logger.info(
            "Générateur initialisé | seed=%s | clients=%s vendeurs=%s produits=%s "
            "commandes=%s avis=%s events=%s",
            config.random_seed,
            config.n_clients,
            config.n_vendeurs,
            config.n_produits,
            config.n_commandes,
            config.n_avis,
            config.n_events,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    def _phone_sn(self) -> str:
        """Numéro sénégalais (77/76/70/78)."""
        prefix = random.choice(["77", "76", "70", "78", "75"])
        return f"+221{prefix}{random.randint(1000000, 9999999)}"

    def _region_ville(self) -> tuple[str, str]:
        region = random.choice(REGIONS_SN)
        ville = random.choice(VILLES_SN[region])
        return region, ville

    def _maybe_missing(self, value: Any, p: Optional[float] = None) -> Any:
        p = self.cfg.p_missing if p is None else p
        if self._rng.random() < p:
            return None
        return value

    def _inject_duplicates(self, df: pd.DataFrame, key_col: str) -> pd.DataFrame:
        """Duplique aléatoirement ~p_duplicate des lignes (même clé)."""
        n_dup = int(len(df) * self.cfg.p_duplicate)
        if n_dup == 0 or len(df) == 0:
            return df
        idx = self._rng.choice(df.index, size=n_dup, replace=True)
        dups = df.loc[idx].copy()
        # On garde la même clé pour créer de vrais doublons métier
        return pd.concat([df, dups], ignore_index=True)

    def _inject_inconsistent_dates(
        self, df: pd.DataFrame, date_col: str, ref_col: Optional[str] = None
    ) -> pd.DataFrame:
        """Met quelques dates dans le futur ou avant une date de référence."""
        n = int(len(df) * self.cfg.p_inconsistent_date)
        if n == 0 or len(df) == 0:
            return df
        idx = self._rng.choice(df.index, size=min(n, len(df)), replace=False)
        for i in idx:
            if ref_col and pd.notna(df.at[i, ref_col]):
                # Date antérieure à la référence (ex: paiement avant commande)
                ref = pd.to_datetime(df.at[i, ref_col])
                df.at[i, date_col] = ref - timedelta(days=random.randint(1, 30))
            else:
                # Date future (1 à 30 jours) — détectable, volume limité par p_inconsistent_date
                df.at[i, date_col] = datetime.now() + timedelta(days=random.randint(1, 30))
        return df

    # ------------------------------------------------------------------
    # Entités
    # ------------------------------------------------------------------
    def generate_clients(self) -> pd.DataFrame:
        logger.info("Génération de %s clients…", self.cfg.n_clients)
        rows: List[Dict[str, Any]] = []
        for _ in range(self.cfg.n_clients):
            region, ville = self._region_ville()
            created = fake.date_time_between(start_date="-3y", end_date="-1d")
            rows.append(
                {
                    "client_id": self._id("cli"),
                    "prenom": self._maybe_missing(fake.first_name()),
                    "nom": self._maybe_missing(fake.last_name()),
                    "email": self._maybe_missing(fake.email()),
                    "telephone": self._maybe_missing(self._phone_sn()),
                    "region": region,
                    "ville": ville,
                    "adresse": self._maybe_missing(fake.street_address()),
                    "date_inscription": created,
                    "actif": random.choices([True, False], weights=[0.92, 0.08])[0],
                }
            )
        df = pd.DataFrame(rows)
        df = self._inject_duplicates(df, "client_id")
        logger.info("Clients générés : %s lignes (dont doublons injectés)", len(df))
        return df

    def generate_vendeurs(self) -> pd.DataFrame:
        logger.info("Génération de %s vendeurs…", self.cfg.n_vendeurs)
        rows = []
        for _ in range(self.cfg.n_vendeurs):
            region, ville = self._region_ville()
            created = fake.date_time_between(start_date="-4y", end_date="-1d")
            rows.append(
                {
                    "vendeur_id": self._id("ven"),
                    "nom_boutique": self._maybe_missing(
                        fake.company() + " " + random.choice(["SN", "Market", "Shop", "Store"])
                    ),
                    "email": self._maybe_missing(fake.company_email()),
                    "telephone": self._maybe_missing(self._phone_sn()),
                    "region": region,
                    "ville": ville,
                    "note_moyenne": round(self._rng.uniform(2.5, 5.0), 2),
                    "nb_ventes": int(self._rng.integers(0, 5000)),
                    "date_inscription": created,
                    "verifie": random.choices([True, False], weights=[0.75, 0.25])[0],
                }
            )
        df = pd.DataFrame(rows)
        df = self._inject_duplicates(df, "vendeur_id")
        logger.info("Vendeurs générés : %s lignes", len(df))
        return df

    def generate_produits(self, vendeurs: pd.DataFrame) -> pd.DataFrame:
        logger.info("Génération de %s produits…", self.cfg.n_produits)
        vendeur_ids = vendeurs["vendeur_id"].dropna().unique().tolist()
        if not vendeur_ids:
            raise ValueError("Aucun vendeur disponible pour attacher les produits")

        rows = []
        for _ in range(self.cfg.n_produits):
            cat = random.choice(list(CATEGORIES.keys()))
            sous_cat = random.choice(CATEGORIES[cat])
            prix = round(float(self._rng.uniform(500, 500_000)), 0)  # FCFA
            rows.append(
                {
                    "produit_id": self._id("prd"),
                    "vendeur_id": random.choice(vendeur_ids),
                    "nom": self._maybe_missing(
                        f"{sous_cat} {fake.word().capitalize()} {random.randint(1, 999)}"
                    ),
                    "categorie": cat,
                    "sous_categorie": sous_cat,
                    "prix_fcfa": self._maybe_missing(prix),
                    "stock": int(self._rng.integers(0, 500)),
                    "description": self._maybe_missing(fake.sentence(nb_words=12)),
                    "poids_kg": round(float(self._rng.uniform(0.05, 25.0)), 2),
                    "date_ajout": fake.date_time_between(start_date="-2y", end_date="-1d"),
                    "actif": random.choices([True, False], weights=[0.9, 0.1])[0],
                }
            )
        df = pd.DataFrame(rows)
        df = self._inject_duplicates(df, "produit_id")
        logger.info("Produits générés : %s lignes", len(df))
        return df

    def generate_commandes(
        self, clients: pd.DataFrame, produits: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Retourne (commandes, lignes_commande)."""
        logger.info("Génération de %s commandes…", self.cfg.n_commandes)
        client_ids = clients["client_id"].dropna().unique().tolist()
        produit_ids = produits["produit_id"].dropna().unique().tolist()
        if not client_ids or not produit_ids:
            raise ValueError("Clients ou produits manquants pour générer les commandes")

        prix_map = (
            produits.dropna(subset=["produit_id", "prix_fcfa"])
            .set_index("produit_id")["prix_fcfa"]
            .to_dict()
        )

        commandes = []
        lignes = []
        for _ in range(self.cfg.n_commandes):
            cmd_id = self._id("cmd")
            client_id = random.choice(client_ids)
            created = fake.date_time_between(start_date="-18m", end_date="-2d")
            statut = random.choices(
                STATUTS_COMMANDE, weights=[0.08, 0.12, 0.15, 0.50, 0.10, 0.05]
            )[0]
            region, ville = self._region_ville()
            n_lignes = random.randint(1, 5)
            montant = 0.0
            for _ in range(n_lignes):
                pid = random.choice(produit_ids)
                qte = random.randint(1, 4)
                prix_u = float(prix_map.get(pid, 10_000))
                montant += prix_u * qte
                lignes.append(
                    {
                        "ligne_id": self._id("lig"),
                        "commande_id": cmd_id,
                        "produit_id": pid,
                        "quantite": qte,
                        "prix_unitaire_fcfa": prix_u,
                    }
                )
            commandes.append(
                {
                    "commande_id": cmd_id,
                    "client_id": client_id,
                    "date_commande": created,
                    "statut": statut,
                    "montant_total_fcfa": round(montant, 0),
                    "region_livraison": region,
                    "ville_livraison": ville,
                    "frais_livraison_fcfa": random.choice([0, 1000, 1500, 2000, 2500]),
                }
            )

        df_cmd = pd.DataFrame(commandes)
        df_lig = pd.DataFrame(lignes)
        df_cmd = self._inject_duplicates(df_cmd, "commande_id")
        df_cmd = self._inject_inconsistent_dates(df_cmd, "date_commande")
        logger.info(
            "Commandes : %s | Lignes : %s", len(df_cmd), len(df_lig)
        )
        return df_cmd, df_lig

    def generate_paiements(self, commandes: pd.DataFrame) -> pd.DataFrame:
        logger.info("Génération des paiements mobiles…")
        # Une commande livrée / confirmée / expédiée a en général un paiement réussi
        rows = []
        for _, row in commandes.iterrows():
            if pd.isna(row.get("commande_id")):
                continue
            # ~85 % des commandes ont un paiement
            if self._rng.random() > 0.85:
                continue
            moyen = random.choices(
                MOYENS_PAIEMENT, weights=[0.45, 0.35, 0.12, 0.08]
            )[0]
            statut = random.choices(
                STATUTS_PAIEMENT, weights=[0.82, 0.08, 0.06, 0.04]
            )[0]
            date_cmd = pd.to_datetime(row["date_commande"])
            date_pay = date_cmd + timedelta(
                minutes=random.randint(1, 60 * 24 * 3)
            )
            rows.append(
                {
                    "paiement_id": self._id("pay"),
                    "commande_id": row["commande_id"],
                    "montant_fcfa": row.get("montant_total_fcfa"),
                    "moyen": moyen,
                    "statut": statut,
                    "date_paiement": date_pay,
                    "reference_externe": f"{moyen[:3].upper()}-{uuid.uuid4().hex[:10].upper()}",
                    "telephone_payeur": self._maybe_missing(self._phone_sn()),
                }
            )
        df = pd.DataFrame(rows)
        df = self._inject_duplicates(df, "paiement_id")
        df = self._inject_inconsistent_dates(df, "date_paiement", ref_col=None)
        # Quelques paiements avec date clairement incohérente (trop ancienne)
        if len(df) > 0 and "date_paiement" in df.columns:
            n = max(1, int(len(df) * self.cfg.p_inconsistent_date))
            idx = self._rng.choice(df.index, size=min(n, len(df)), replace=False)
            for i in idx:
                # 5+ ans dans le passé → détectable par le cleaner
                df.at[i, "date_paiement"] = datetime(2018, 1, 1) + timedelta(days=int(self._rng.integers(0, 365)))
        logger.info("Paiements générés : %s", len(df))
        return df

    def generate_avis(
        self, clients: pd.DataFrame, produits: pd.DataFrame
    ) -> pd.DataFrame:
        logger.info("Génération de %s avis…", self.cfg.n_avis)
        client_ids = clients["client_id"].dropna().unique().tolist()
        produit_ids = produits["produit_id"].dropna().unique().tolist()
        rows = []
        for _ in range(self.cfg.n_avis):
            note = int(self._rng.integers(1, 6))
            rows.append(
                {
                    "avis_id": self._id("avi"),
                    "client_id": random.choice(client_ids),
                    "produit_id": random.choice(produit_ids),
                    "note": self._maybe_missing(note),
                    "titre": self._maybe_missing(fake.sentence(nb_words=4)),
                    "commentaire": self._maybe_missing(fake.paragraph(nb_sentences=2)),
                    "date_avis": fake.date_time_between(start_date="-12m", end_date="-1d"),
                    "utile": int(self._rng.integers(0, 50)),
                }
            )
        df = pd.DataFrame(rows)
        df = self._inject_duplicates(df, "avis_id")
        logger.info("Avis générés : %s", len(df))
        return df

    def generate_events(
        self, clients: pd.DataFrame, produits: pd.DataFrame
    ) -> pd.DataFrame:
        logger.info("Génération de %s événements de navigation…", self.cfg.n_events)
        client_ids = clients["client_id"].dropna().unique().tolist()
        produit_ids = produits["produit_id"].dropna().unique().tolist()
        # ~20 % d'événements anonymes
        rows = []
        for _ in range(self.cfg.n_events):
            etype = random.choices(
                EVENT_TYPES, weights=[0.45, 0.25, 0.12, 0.05, 0.08, 0.05]
            )[0]
            client = random.choice(client_ids) if self._rng.random() > 0.2 else None
            produit = (
                random.choice(produit_ids)
                if etype not in ("search",) and self._rng.random() > 0.1
                else None
            )
            rows.append(
                {
                    "event_id": self._id("evt"),
                    "client_id": client,
                    "produit_id": produit,
                    "event_type": etype,
                    "session_id": f"ses_{uuid.uuid4().hex[:10]}",
                    "timestamp": fake.date_time_between(start_date="-6m", end_date="-1h"),
                    "device": random.choice(["mobile", "desktop", "tablet"]),
                    "page_url": f"/p/{produit}" if produit else "/search",
                    "referrer": random.choice(
                        [None, "google", "facebook", "instagram", "direct", "whatsapp"]
                    ),
                }
            )
        df = pd.DataFrame(rows)
        logger.info("Événements générés : %s", len(df))
        return df

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    def generate_all(self) -> Dict[str, pd.DataFrame]:
        """Génère l'ensemble des datasets et retourne un dict nom → DataFrame."""
        logger.info("=== Début génération complète SenMarket ===")
        clients = self.generate_clients()
        vendeurs = self.generate_vendeurs()
        produits = self.generate_produits(vendeurs)
        commandes, lignes = self.generate_commandes(clients, produits)
        paiements = self.generate_paiements(commandes)
        avis = self.generate_avis(clients, produits)
        events = self.generate_events(clients, produits)

        datasets = {
            "clients": clients,
            "vendeurs": vendeurs,
            "produits": produits,
            "commandes": commandes,
            "lignes_commande": lignes,
            "paiements": paiements,
            "avis": avis,
            "events": events,
        }
        total = sum(len(d) for d in datasets.values())
        logger.info("=== Génération terminée : %s datasets, %s lignes au total ===", len(datasets), total)
        return datasets
