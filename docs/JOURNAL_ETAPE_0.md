# Journal de conception — Étape 0 : Générateur de données SenMarket

**Projet :** SenMarket (fil rouge du programme Data Engineering, Big Data & DataOps)  
**Étape :** 0 — Le générateur de données  
**Objectif du document :** Décrire *ce qui a été fait*, *dans quel ordre*, et *pourquoi* — pour qu’un autre data engineer (ou le jury) comprenne les choix sans relire tout le code.

---

## 1. Contexte et contraintes

### 1.1 Ce que demande le programme

Le fil rouge SenMarket n’est pas une série d’exercices isolés : **chaque étape consomme la sortie de la précédente**. L’Étape 0 est donc le socle de toute la plateforme.

Exigences explicites de l’Étape 0 (document projets) :

| Exigence | Interprétation |
|----------|----------------|
| Dépôt Git (`src`, `tests`, `data`, README) | Structure professionnelle dès le jour 1 |
| Générateur (Faker, NumPy) | Clients, vendeurs, produits, commandes, paiements mobiles, avis, événements de navigation |
| Volumes réglables | De quelques milliers à plusieurs millions de lignes |
| Export CSV, JSON, Parquet | Trois formats, usages différents plus tard |
| Défauts réalistes | Doublons, valeurs manquantes, dates incohérentes |
| Nettoyage Pandas | Exercer le Module 0 (socle Python) |
| Logging + config `.env` | Pas de secrets / paramètres en dur |
| Tests pytest (dont cas d’erreur) | Qualité et “mettre à l’épreuve” |
| Fiche de décision formats | Justification écrite d’un choix technique |
| Livrable relançable + README | Reproductible par un tiers |

### 1.2 Ce que les étapes suivantes imposent déjà à l’Étape 0

On ne génère pas “des CSV au hasard”. On prépare des données qui devront :

| Étape ultérieure | Besoin sur les données de l’Étape 0 |
|------------------|-------------------------------------|
| **1 — Bases** | Relations clients ↔ commandes ↔ produits ; PostgreSQL relationnel ; Mongo (catalogue flexible, avis) ; Redis (sessions, top produits via events) |
| **2 — Spark** | Volumes multi-millions, Parquet, partitions par date |
| **3 — Ingestion** | Paiements type API (Wave / Orange Money) ; events pour Kafka |
| **4 — Lakehouse + dbt** | Bronze (brut) / Silver (nettoyé) ; schéma en étoile (fait ventes + dimensions) |
| **5+** | Pipelines idempotents, tests de qualité, orchestration |

**Conséquence :** les identifiants, les relations entre tables et les formats d’export sont des décisions d’architecture, pas des détails d’implémentation.

---

## 2. Démarche globale (ordre des travaux)

```
1. Lire le programme (modules + projets) et extraire les contraintes transverses
2. Définir le modèle de données logique (entités + relations)
3. Structurer le dépôt (src / tests / data / docs)
4. Config centralisée (.env) + logging
5. Générateur (avec défauts injectés)
6. Nettoyage Pandas
7. Export multi-format
8. CLI (main)
9. Tests (génération, erreurs, nettoyage, export, pipeline)
10. Fiche de décision formats + README + journal
11. Validation (pytest + run de bout en bout)
```

Chaque brique existe parce qu’elle répond à une exigence du programme **ou** à un besoin d’une étape future.

---

## 3. Modèle de données logique

### 3.1 Entités

| Dataset | Rôle métier | Clé | Sert surtout à… |
|---------|-------------|-----|------------------|
| `clients` | Acheteurs de la marketplace | `client_id` | PG (Étape 1), dim client (Étape 4) |
| `vendeurs` | Boutiques / marchands | `vendeur_id` | PG, dim vendeur |
| `produits` | Catalogue | `produit_id` | PG + Mongo (attributs variables), dim produit |
| `commandes` | En-tête de commande | `commande_id` | PG, fait ventes |
| `lignes_commande` | Détail produit × quantité | `ligne_id` | PG, grain du fait ventes |
| `paiements` | Wave / Orange Money / carte | `paiement_id` | PG, ingestion API (Étape 3) |
| `avis` | Notes et commentaires | `avis_id` | Mongo, qualité produit |
| `events` | Navigation (view, click, panier…) | `event_id` | Redis, Kafka streaming (Étape 3) |

### 3.2 Relations (intégrité référentielle logique)

Ordre de génération volontaire :

```
clients ──┐
           ├──► commandes ──► lignes_commande ──► produits ──► vendeurs
           │         │
           │         └──► paiements
           │
           ├──► avis ──► produits
           └──► events ──► produits (client optionnel = anonyme)
```

**Pourquoi c’est indispensable :**

- Sans FK logiques, l’Étape 1 (modèle relationnel + transaction “commande + paiement”) et l’Étape 4 (tests dbt `relationships`) cassent.
- Le générateur **ne crée pas** d’orphelins métier : un `produit` a toujours un `vendeur_id` existant, une `commande` un `client_id` existant, etc.
- Les **défauts** (doublons, nulls) sont ajoutés *après* pour simuler la réalité ; le cleaner les traite.

### 3.3 Ancrage sénégalais

Régions, villes, préfixes téléphoniques (`+221 77/76/70…`), moyens de paiement **Wave** et **Orange Money**, montants en **FCFA**.

**Pourquoi :** le sujet du fil rouge est une marketplace sénégalaise fictive ; des données génériques “US/EU” affaibliraient la cohérence métier et les questions analytiques (CA par région, etc.).

---

## 4. Structure du dépôt

```
SenMarket/
├── src/                    # Code applicatif uniquement
│   ├── config.py
│   ├── logging_config.py
│   ├── generator.py
│   ├── cleaner.py
│   ├── export.py
│   └── main.py
├── tests/                  # Tests isolés du code métier
├── data/
│   ├── raw/                # Bronze (brut, avec défauts)
│   └── cleaned/            # Base Silver locale
├── docs/                   # Décisions + journal
├── .env.example            # Contrat de configuration
├── .gitignore              # Ne pas versionner data / secrets / caches
├── requirements.txt
└── README.md
```

**Pourquoi cette découpe :**

| Choix | Motif |
|-------|--------|
| `src/` séparé de `tests/` | Standard Python, CI simple plus tard (Étape 8) |
| `data/raw` vs `data/cleaned` | Préfigure Bronze / Silver (Étape 4) sans lakehouse encore |
| Pas de données versionnées dans Git | Volumes variables, fichiers lourds ; `.gitignore` sur csv/json/parquet |
| `.env.example` sans secrets | Onversionne le *contrat*, pas les valeurs locales |
| `docs/` | Fiches de décision exigées à chaque étape du programme |

---

## 5. Configuration (`config.py` + `.env`)

### 5.1 Ce qui est configurable

- Volumes (`N_CLIENTS`, `N_COMMANDES`, …)
- Seed aléatoire (`RANDOM_SEED`)
- Chemins de sortie
- Formats d’export
- Probabilités de défauts (`P_MISSING`, `P_DUPLICATE`, `P_INCONSISTENT_DATE`)
- Niveau de log

### 5.2 Pourquoi

| Principe | Application |
|----------|-------------|
| **Pas de magie dans le code** | Un formateur / binôme change les volumes sans toucher à Python |
| **Reproductibilité** | Seed fixe → démos et tests stables |
| **Préparation DataOps** | Même idée que variables Airflow / secrets (Étapes 5, 8, 9) |
| **Validation explicite** | `validate()` refuse volumes ≤ 0, formats inconnus, probabilités hors [0, 1] |

Échec de config = message clair + code retour ≠ 0 (comportement “production-like”).

---

## 6. Générateur (`generator.py`)

### 6.1 Stack

- **Faker (`fr_FR`)** : noms, adresses, textes
- **NumPy** : tirages, volumes, seeds
- **uuid** : identifiants uniques préfixés (`cli_`, `cmd_`, …)

**Pourquoi pas seulement Faker :** les volumes et la reproductibilité statistique se pilotent mieux avec NumPy ; les IDs préfixés simplifient le debug et les jointures à l’œil.

### 6.2 Injection de défauts

| Défaut | Paramètre | Pourquoi |
|--------|-----------|----------|
| Valeurs manquantes | `P_MISSING` | Simuler APIs / fichiers sales ; exercer le nettoyage |
| Doublons sur clé métier | `P_DUPLICATE` | Cas réel d’exports mal dédupliqués ; tests `unique` plus tard |
| Dates incohérentes / futures | `P_INCONSISTENT_DATE` | Fraîcheur et contrôles qualité (Great Expectations, Étape 4/10) |

**Pourquoi injecter puis nettoyer plutôt que générer “propre” :**  
le Module 0 et l’Étape 0 exigent explicitement de *glisser des défauts puis les nettoyer avec Pandas*. C’est aussi le quotidien d’un data engineer.

### 6.3 Paiements mobiles

Champs : moyen (Wave, Orange Money, carte, espèces), statut, référence externe, téléphone payeur, lien `commande_id`.

**Pourquoi :** l’Étape 3 demande une ingestion depuis une API de paiements mobiles simulée ; le schéma est déjà aligné.

### 6.4 Événements de navigation

Types : `view`, `click`, `add_to_cart`, `remove_from_cart`, `search`, `checkout_start` + `session_id` + device.

**Pourquoi :** Redis (top produits, sessions) à l’Étape 1 ; Kafka (flux continu) à l’Étape 3.

---

## 7. Nettoyage (`cleaner.py`)

Un cleaner par dataset (pas un “clean_all générique aveugle”).

| Action | Motif pédagogique / métier |
|--------|----------------------------|
| `drop_duplicates` sur la clé métier | Restaurer une clé unique pour PG et dbt |
| Typage (`to_datetime`, `to_numeric`, booléens) | Éviter que tout reste en string (piège CSV) |
| Dates aberrantes → `NaT` (plutôt que supprimer la ligne) | Ne pas casser les FK en silence ; signaler le problème |
| Prix ≤ 0 → NaN | Règle métier simple, visible dans un rapport de qualité |
| Rapport avant/après | Preuve pour le README / la soutenance |

**Pourquoi ne pas tout supprimer d’un coup :**  
en production on préfère souvent *quarantine* ou *nullifier* plutôt que perdre des faits de vente entiers. L’Étape 10 parle explicitement de mise en quarantaine des données invalides.

---

## 8. Export (`export.py`)

### 8.1 Trois formats systématiques

| Format | Usage prévu dans le fil rouge |
|--------|-------------------------------|
| **Parquet** | Pipeline principal : Spark, zone brute, lakehouse, Athena/S3 |
| **CSV** | Debug, import manuel PostgreSQL, lisibilité |
| **JSON** | Illustration APIs / documents Mongo |

### 8.2 Décision documentée

Fiche dédiée : `docs/FICHE_DECISION_FORMATS.md`  
(exigence “justifier une décision” à chaque étape).

### 8.3 Détail technique Parquet

Écriture via **PyArrow direct** (`pq.write_table`) plutôt que seul `DataFrame.to_parquet`, pour robustesse sur l’environnement d’exécution.

**Pourquoi documenter ça :** un data engineer doit savoir que “le même appel pandas” n’est pas toujours fiable selon le filesystem / la version ; avoir un plan B fait partie du métier.

---

## 9. Point d’entrée (`main.py`)

Pipeline unique :

```
config → generate_all → export raw → clean_all → export cleaned → rapport
```

CLI : overrides de volumes, formats, seed, `--no-clean`.

**Pourquoi une CLI :**

- Même entrée pour un humain, un script shell, plus tard Airflow (`BashOperator` / TaskFlow)
- Codes retour distincts (config / génération / export / clean) → diagnostic rapide

---

## 10. Tests (`tests/test_generator.py`)

Couverture volontairement alignée sur le programme :

| Catégorie | Exemples | Pourquoi |
|-----------|----------|----------|
| Config | volumes invalides, formats inconnus | Échouer tôt |
| Génération | colonnes, volumes, `generate_all` | Non-régression du contrat de données |
| Relations / erreurs | produits sans vendeurs, commandes sans clients | **Mettre à l’épreuve** (exigence écrite) |
| Nettoyage | doublons supprimés | Preuve que le cleaner fait le job |
| Export | CSV + Parquet relus | Formats vraiment exploitables |
| Pipeline | bout-en-bout sur petit volume | Confiance avant de monter les volumes |

**Pourquoi des tests dès l’Étape 0 :**  
compétence transverse du programme (“tests unitaires et d’intégration — Modules 0, 4, 8”). On installe le réflexe avant dbt et la CI.

---

## 11. Ce qui a été volontairement *non* fait (et pourquoi)

| Non-fait | Raison |
|----------|--------|
| Vrais `FOREIGN KEY` SQL | Rôle de l’Étape 1 (PostgreSQL) |
| Docker Compose des bases | Fourni plus tard / reconstruit à l’Étape 7 |
| Partitionnement Spark / HDFS | Étape 2 |
| API HTTP réelle de paiements | Étape 3 (l’API sera “fournie”) |
| dbt / Great Expectations | Étape 4 |
| Classes OOP partout / asyncio | Marqués **optionnels** dans le module 0 |
| Polars / PyArrow côté nettoyage principal | Optionnel ; Pandas = priorité Module 0 |

Rester sur le **cœur** évite le survol d’outils — point explicitement demandé dans les retours du groupe.

---

## 12. Synthèse “quoi / pourquoi”

| Quoi | Pourquoi |
|------|----------|
| 8 datasets liés | Pipeline bout-en-bout jusqu’à la soutenance |
| Relations respectées à la génération | Modélisation PG + tests dbt `relationships` |
| Défauts puis nettoyage | Exigence pédagogique + réalisme |
| `raw` / `cleaned` | Prépare Bronze / Silver |
| CSV + JSON + Parquet | Usages distincts ; Parquet = standard lakehouse |
| Config `.env` + logging | Reproductibilité, bonne pratique DataOps |
| Tests d’erreur | Exigence “mettre à l’épreuve” |
| Fiche de décision formats | Exigence “justifier” à chaque étape |
| Ancrage Sénégal (régions, Wave, FCFA) | Cohérence du sujet SenMarket |

---

## 13. Comment relancer et vérifier

```bash
cd SenMarket
pip install -r requirements.txt
cp .env.example .env

python -m src.main
# ou volumes réduits :
python -m src.main --clients 200 --vendeurs 20 --produits 60 --commandes 300

pytest tests/ -v
```

Sorties attendues :

- `data/raw/*.{csv,json,parquet}` — avec défauts  
- `data/cleaned/*` — dédupliqué, typé  
- `logs/generator.log`  
- Rapport de nettoyage dans la console  

---

## 14. Suite directe

| Prochaine étape | Entrée issue de l’Étape 0 |
|-----------------|---------------------------|
| **Étape 1** | Datasets nettoyés → PostgreSQL / MongoDB / Redis + fiche “quelle base pour quelle donnée” |
| **Étape 2** | Monter `N_COMMANDES` (millions) + Parquet → PySpark |

---

*Document produit dans le cadre de la réalisation de l’Étape 0 du fil rouge SenMarket. Il complète le README et la fiche de décision formats ; il ne les remplace pas.*
