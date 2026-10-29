"""Export multi-format des DataFrames SenMarket (CSV, JSON, Parquet)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

logger = logging.getLogger("senmarket.export")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def export_dataframe(
    df: pd.DataFrame,
    name: str,
    output_dir: Path,
    formats: Iterable[str],
) -> Dict[str, Path]:
    """
    Exporte un DataFrame dans les formats demandés.

    Returns
    -------
    dict format → chemin du fichier écrit
    """
    _ensure_dir(output_dir)
    written: Dict[str, Path] = {}

    # Normaliser les dtypes problématiques pour Parquet (boolean nullable, etc.)
    df_out = df.copy()
    for col in df_out.columns:
        if str(df_out[col].dtype) == "boolean":
            df_out[col] = df_out[col].astype(object).where(df_out[col].notna(), None)
        elif str(df_out[col].dtype).startswith("string"):
            df_out[col] = df_out[col].astype(object)

    for fmt in formats:
        fmt = fmt.lower().strip()
        path = output_dir / f"{name}.{fmt}"
        try:
            if fmt == "csv":
                df_out.to_csv(path, index=False, encoding="utf-8")
            elif fmt == "json":
                df_out.to_json(
                    path, orient="records", date_format="iso",
                    force_ascii=False, indent=2,
                )
            elif fmt == "parquet":
                # pyarrow direct (pandas.DataFrame.to_parquet peut produire
                # des fichiers vides sur certains filesystems du sandbox)
                import pyarrow as pa
                import pyarrow.parquet as pq
                table = pa.Table.from_pandas(df_out, preserve_index=False)
                pq.write_table(table, path, compression="snappy")
            else:
                logger.warning("Format ignoré (non supporté) : %s", fmt)
                continue
        except Exception:
            logger.exception("Échec export %s (%s)", name, fmt)
            raise

        size_kb = path.stat().st_size / 1024
        logger.info("  → %s (%s) — %.1f Ko", path.name, fmt, size_kb)
        if size_kb == 0 and len(df_out) > 0:
            logger.warning("Fichier vide alors que le DataFrame a %s lignes !", len(df_out))
        written[fmt] = path

    return written


def export_all(
    datasets: Dict[str, pd.DataFrame],
    output_dir: Path,
    formats: List[str],
) -> Dict[str, Dict[str, Path]]:
    """Exporte tous les datasets. Retourne {name: {fmt: path}}."""
    logger.info("Export vers %s | formats=%s", output_dir, formats)
    result: Dict[str, Dict[str, Path]] = {}
    for name, df in datasets.items():
        logger.info("Export '%s' (%s lignes)…", name, len(df))
        result[name] = export_dataframe(df, name, output_dir, formats)
    return result


def compare_format_sizes(output_dir: Path, name: str) -> pd.DataFrame:
    """Compare la taille des fichiers pour un même dataset (fiche de décision)."""
    rows = []
    for fmt in ("csv", "json", "parquet"):
        path = output_dir / f"{name}.{fmt}"
        if path.exists():
            rows.append(
                {
                    "dataset": name,
                    "format": fmt,
                    "taille_ko": round(path.stat().st_size / 1024, 1),
                    "chemin": str(path),
                }
            )
    return pd.DataFrame(rows)
