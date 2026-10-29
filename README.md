# SenMarket — Générateur de données (Étape 0)

Marketplace sénégalaise **fictive** servant de fil rouge au programme  
**Data Engineering, Big Data & DataOps**.

Ce dépôt contient le **point de départ** de toute la plateforme : un générateur  
de données réalistes (clients, vendeurs, produits, commandes, paiements mobiles,  
avis, événements de navigation), avec défauts volontaires, nettoyage Pandas,  
tests et export multi-format.

---

## Structure du dépôt

```
SenMarket/
├── src/
│   ├── config.py          # Configuration (.env + validation)
│   ├── logging_config.py  # Logging console + fichier
│   ├── generator.py       # Génération des 8 datasets
│   ├── cleaner.py         # Nettoyage Pandas (doublons, nulls, types, dates)
│   ├── export.py          # Export CSV / JSON / Parquet
│   └── main.py            # Point d'entrée CLI
├── tests/
│   └── test_generator.py  # pytest (génération, erreurs, nettoyage, export)
├── data/
│   ├── raw/               # Données brutes (générées)
│   └── cleaned/           # Données nettoyées
├── docs/
│   └── FICHE_DECISION_FORMATS.md
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Prérequis

- Python ≥ 3.10
- (recommandé) environnement virtuel

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Configuration

```bash
cp .env.example .env
# Éditer .env si besoin (volumes, seed, formats, probabilités de défauts)
```

Variables principales :

| Variable        | Défaut     | Description                          |
|-----------------|------------|--------------------------------------|
| `N_CLIENTS`     | 5000       | Nombre de clients                    |
| `N_VENDEURS`    | 200        | Nombre de vendeurs                   |
| `N_PRODUITS`    | 1500       | Nombre de produits                   |
| `N_COMMANDES`   | 20000      | Nombre de commandes                  |
| `N_AVIS`        | 8000       | Nombre d'avis                        |
| `N_EVENTS`      | 50000      | Événements de navigation             |
| `RANDOM_SEED`   | 42         | Reproductibilité                     |
| `EXPORT_FORMATS`| csv,json,parquet | Formats écrits                  |
| `P_MISSING`     | 0.03       | Probabilité de valeur manquante      |
| `P_DUPLICATE`   | 0.02       | Probabilité de doublon injecté       |

---

## Lancer le générateur

```bash
# Volumes par défaut
python -m src.main

# Petit jeu de test
python -m src.main --clients 200 --vendeurs 20 --produits 100 --commandes 500 --avis 200 --events 1000

# Un seul format, sans nettoyage
python -m src.main --formats parquet --no-clean

# Seed fixe
python -m src.main --seed 123
```

Sorties :

- `data/raw/`     → fichiers bruts (avec défauts)
- `data/cleaned/` → fichiers nettoyés
- `logs/generator.log`

---

## Tests

```bash
pytest tests/ -v
```

Les tests couvrent :

1. **Génération** de chaque entité et du pipeline complet  
2. **Cas d’erreur** (config invalide, vendeurs/clients absents)  
3. **Nettoyage** (suppression des doublons, typage)  
4. **Export** CSV + Parquet et relecture  
5. **Pipeline bout-en-bout** sur un petit volume  

**Mettre à l’épreuve (exigence du programme) :**

```bash
# Corrompre un fichier d'entrée simulé : le script doit échouer proprement
python -c "
from src.config import GeneratorConfig
from src.generator import SenMarketGenerator
cfg = GeneratorConfig(n_clients=10, n_vendeurs=0, n_produits=5, n_commandes=5, n_avis=2, n_events=5, random_seed=1)
g = SenMarketGenerator(cfg)
# n_vendeurs=0 → generate_produits lèvera ValueError avec message clair
vendeurs = g.generate_vendeurs()  # DataFrame vide de vendeurs utiles
print(vendeurs)
" 
# Ou plus direct :
python -c "
from src.generator import SenMarketGenerator
from src.config import GeneratorConfig
import pandas as pd
g = SenMarketGenerator(GeneratorConfig(n_clients=5, n_vendeurs=5, n_produits=5, n_commandes=5, n_avis=2, n_events=5))
try:
    g.generate_produits(pd.DataFrame(columns=['vendeur_id']))
except ValueError as e:
    print('ÉCHEC ATTENDU:', e)
"
```

---

## Datasets produits

| Dataset            | Clé métier     | Contenu principal                                      |
|--------------------|----------------|--------------------------------------------------------|
| `clients`          | `client_id`    | Identité, contact, région/ville SN, date inscription   |
| `vendeurs`         | `vendeur_id`   | Boutique, note, nb ventes, région                      |
| `produits`         | `produit_id`   | Catalogue, catégorie, prix FCFA, stock, vendeur        |
| `commandes`        | `commande_id`  | Client, montant, statut, région livraison              |
| `lignes_commande`  | `ligne_id`     | Détail produits × quantités                            |
| `paiements`        | `paiement_id`  | Wave / Orange Money / carte, statut, référence         |
| `avis`             | `avis_id`      | Note 1–5, commentaire, produit, client                 |
| `events`           | `event_id`     | view / click / add_to_cart / search, session, device   |

Défauts injectés volontairement :

- Valeurs manquantes (`P_MISSING`)
- Doublons sur clé métier (`P_DUPLICATE`)
- Dates incohérentes / futures (`P_INCONSISTENT_DATE`)

---

## Décision technique — formats

Voir **[docs/FICHE_DECISION_FORMATS.md](docs/FICHE_DECISION_FORMATS.md)**.

**Résumé :** Parquet pour le pipeline (Bronze → cloud), CSV pour le debug,  
JSON pour illustrer les APIs. Les trois sont générés à cette étape.

---

## Suite du fil rouge

| Étape | Ce que SenMarket gagne                          |
|-------|-------------------------------------------------|
| 1     | Chaque donnée dans la bonne base (PG, Mongo, Redis) |
| 2     | Historique multi-millions traité avec Spark     |
| 3     | Ingestion batch + streaming (Kafka)             |
| 4     | Lakehouse Bronze / Silver / Gold + dbt          |
| 5     | Orchestration Airflow                           |
| …     | Docker, CI/CD, AWS, DataOps, soutenance         |

Les fichiers Parquet de `data/cleaned/` (ou `data/raw/`) alimentent directement  
les étapes 1 et 2.

---

## Livrable Étape 0

- [x] Dépôt Git structuré (`src`, `tests`, `data`, `docs`, README)
- [x] Générateur (Faker + NumPy) avec volumes réglables
- [x] Défauts réalistes + nettoyage Pandas
- [x] Logging + configuration `.env`
- [x] Tests pytest (y compris cas d’erreur)
- [x] Export CSV / JSON / Parquet
- [x] Fiche de décision formats
- [x] README

```bash
git init
git add .
git commit -m "Étape 0 : générateur de données SenMarket"
```
