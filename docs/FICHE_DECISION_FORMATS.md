# Fiche de décision — Formats de fichiers (Étape 0)

**Projet :** SenMarket  
**Module / Étape :** 0 — Générateur de données  
**Question :** Quel format de fichier (CSV, JSON, Parquet) pour quel usage ?

---

## Contexte

Le générateur produit 8 datasets (clients, vendeurs, produits, commandes, lignes, paiements, avis, events).  
Ils seront lus par :

- Pandas (nettoyage local, Module 0)
- PostgreSQL / MongoDB (Étape 1)
- Spark / PySpark (Étape 2) — volumes multi-millions
- dlt / Airbyte / zone brute (Étape 3)
- dbt + lakehouse Bronze/Silver/Gold (Étape 4)

Le format d’échange conditionne la performance, le coût de stockage et la compatibilité.

---

## Comparaison

| Critère              | CSV                         | JSON                              | Parquet                          |
|----------------------|-----------------------------|-----------------------------------|----------------------------------|
| **Lisibilité humaine** | Excellente                 | Bonne (si indenté)                | Nulle (binaire)                  |
| **Taille sur disque**  | Grande                     | Très grande (verbose)             | **Petite** (colonnes + compression) |
| **Vitesse de lecture** | Moyenne                    | Lente                             | **Rapide** (projection colonnes) |
| **Types de données**   | Tout est texte             | Types de base (pas de date native)| **Riches** (timestamp, decimal…) |
| **Schéma**             | Implicite                  | Implicite / flexible              | **Explicite** (embedded)         |
| **Évolution de schéma**| Fragile                    | Souple                            | Gérée (Iceberg/Delta plus tard)  |
| **Compatibilité**      | Universelle                | APIs, document stores             | Spark, Pandas, DuckDB, Athena…   |
| **Streaming / append** | Facile (ligne par ligne)   | Facile                            | Plus délicat (fichiers complets) |
| **Coût cloud (S3)**    | Élevé                      | Très élevé                        | **Faible**                       |

### Mesures observées (jeu de test ~20 k commandes + 50 k events)

Sur un run typique du générateur (seed=42) :

| Dataset   | CSV (Ko) | JSON (Ko) | Parquet (Ko) | Ratio CSV/Parquet |
|-----------|----------|-----------|--------------|-------------------|
| clients   | ~180     | ~320      | ~45          | ~4×               |
| commandes | ~900     | ~1 600    | ~180         | ~5×               |
| events    | ~3 500   | ~6 200    | ~700         | ~5×               |

*(Les chiffres exacts varient selon le volume ; le ratio 4–6× est stable.)*

---

## Décision retenue

| Usage                              | Format retenu | Justification |
|------------------------------------|---------------|---------------|
| **Debug / inspection manuelle**    | CSV           | Ouverture directe dans Excel, `head`, `csvkit`. |
| **Échange avec des APIs / outils légers** | JSON     | Format natif des API REST ; MongoDB. |
| **Zone brute (Bronze) & traitements** | **Parquet** | Standard de facto du lakehouse. Compression, types, lecture colonnaire → indispensable dès Spark (Étape 2) et dbt/Athena (Étapes 4–6–9). |
| **Tests unitaires / CI**           | Parquet + CSV | Parquet pour la fidélité des types ; CSV pour les asserts lisibles. |

**Règle du projet SenMarket :**

1. Le générateur écrit **toujours les trois formats** en `data/raw/` (pédagogie + flexibilité).
2. Le pipeline aval (Spark → Silver → Gold → cloud) **ne consomme que le Parquet**.
3. Le CSV sert uniquement au debug et aux imports manuels PostgreSQL (Étape 1).
4. Le JSON est conservé pour illustrer l’ingestion API / document (Étape 3).

---

## Ce qu’on ne fait pas

- Ne pas stocker l’historique multi-millions en CSV (coût + lenteur).
- Ne pas utiliser JSON comme format de lakehouse (taille + parsing).
- Ne pas versionner les fichiers de données dans Git (`.gitignore`).

---

## Révision

Cette décision sera réévaluée à l’Étape 4 (Iceberg / Delta Lake optionnels) et à l’Étape 9 (S3 + Athena), où le Parquet reste le format pivot.
