from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

import pandas as pd


EXPECTED_COLUMNS = [
    "transaction_id",
    "product_name",
    "product_category",
    "quantity_sold",
    "unit_price",
    "date_of_transaction",
    "total_amount",
    "inventory_stock",
]

RENAME_MAP = {
    "transaction id": "transaction_id",
    "transaction_id": "transaction_id",
    "product name": "product_name",
    "product_name": "product_name",
    "product category": "product_category",
    "product_category": "product_category",
    "quantity sold": "quantity_sold",
    "quantity_sold": "quantity_sold",
    "unit price": "unit_price",
    "unit_price": "unit_price",
    "date of transaction": "date_of_transaction",
    "date_of_transaction": "date_of_transaction",
    "total amount": "total_amount",
    "total_amount": "total_amount",
    "inventory stock": "inventory_stock",
    "inventory_stock": "inventory_stock",
}


def _normalize_column_name(name: str) -> str:
    return str(name).strip().lower().replace("-", " ").replace("_", " ")


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    attempts: list[tuple[str, Callable[[], pd.DataFrame]]] = []

    if suffix in {".csv", ".txt", ".xls"}:
        attempts.append(("csv", lambda: pd.read_csv(path)))
    if suffix == ".tsv":
        attempts.append(("tsv", lambda: pd.read_csv(path, sep="\t")))

    if suffix in {".xls", ".xlsx"}:
        attempts.append(("excel-xlrd", lambda: pd.read_excel(path, engine="xlrd")))
        attempts.append(("excel-auto", lambda: pd.read_excel(path)))

    if not attempts:
        attempts.append(("csv", lambda: pd.read_csv(path)))
        attempts.append(("excel-auto", lambda: pd.read_excel(path)))

    errors: list[str] = []
    for label, reader in attempts:
        try:
            df = reader()
            if not df.empty:
                return df
        except Exception as exc:  # pragma: no cover - best effort readers
            errors.append(f"{label}: {exc}")

    raise ValueError("Unable to read dataset. Attempts failed: " + " | ".join(errors))


def load_transactions(path: str | Path) -> pd.DataFrame:
    source_path = Path(path)
    if not source_path.exists():
        raise FileNotFoundError(f"Dataset not found: {source_path}")

    print(f"[DEBUG] Reading dataset from: {source_path}")
    raw = _read_table(source_path)
    normalized_columns = {_normalize_column_name(column): column for column in raw.columns}

    renamed = {}
    for normalized_name, original_name in normalized_columns.items():
        if normalized_name in RENAME_MAP:
            renamed[original_name] = RENAME_MAP[normalized_name]

    df = raw.rename(columns=renamed).copy()

    missing = [column for column in EXPECTED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing)}")

    df = df[EXPECTED_COLUMNS].copy()

    string_columns: Iterable[str] = ["transaction_id", "product_name", "product_category"]
    for column in string_columns:
        non_missing = df[column].notna()
        df.loc[non_missing, column] = df.loc[non_missing, column].astype(str).str.strip()

    if "transaction_id" in df.columns:
        non_missing = df["transaction_id"].notna()
        df.loc[non_missing, "transaction_id"] = df.loc[non_missing, "transaction_id"].astype(str).str.upper()
    if "product_name" in df.columns:
        non_missing = df["product_name"].notna()
        df.loc[non_missing, "product_name"] = (
            df.loc[non_missing, "product_name"].astype(str).str.replace(r"\s+", " ", regex=True).str.title()
        )
    if "product_category" in df.columns:
        non_missing = df["product_category"].notna()
        df.loc[non_missing, "product_category"] = (
            df.loc[non_missing, "product_category"].astype(str).str.replace(r"\s+", " ", regex=True).str.title()
        )

    numeric_columns = ["quantity_sold", "unit_price", "total_amount", "inventory_stock"]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["date_of_transaction"] = pd.to_datetime(df["date_of_transaction"], errors="coerce")

    return df


def save_transactions(df: pd.DataFrame, path: str | Path) -> Path:
    destination_path = Path(path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    import os
    from tempfile import NamedTemporaryFile

    destination_path = Path(destination_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[DEBUG] Writing dataset to: {destination_path}")

    # Write to a temp file in the same directory then atomically replace
    dirpath = str(destination_path.parent)
    with NamedTemporaryFile("w", delete=False, dir=dirpath, suffix=".tmp", newline="", encoding="utf-8") as tmp:
        tmp_name = tmp.name
        df.to_csv(tmp_name, index=False)

    try:
        os.replace(tmp_name, str(destination_path))
    except Exception:
        # Attempt a few recovery strategies for Windows "access denied" cases
        import time
        import stat

        replaced = False
        last_exc = None
        for attempt in range(3):
            try:
                time.sleep(0.25)
                os.replace(tmp_name, str(destination_path))
                replaced = True
                break
            except Exception as exc:
                last_exc = exc
                # Try clearing read-only bit on destination if it exists
                try:
                    if destination_path.exists():
                        current_mode = destination_path.stat().st_mode
                        destination_path.chmod(current_mode | stat.S_IWRITE)
                except Exception:
                    pass

        if not replaced:
            # Cleanup temp file if replace fails
            try:
                os.remove(tmp_name)
            except Exception:
                pass
            # Provide a clearer error message for the caller
            msg = (
                f"Unable to write dataset to {destination_path}. "
                "This may be because the file is open in another program (e.g., Excel) or you lack write permissions. "
                "Please close any programs locking the file and ensure you have write permission, then try again."
            )
            raise PermissionError(msg) from last_exc

    return destination_path


def clean_transactions(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    df = raw_df.copy()
    original_rows = int(len(df))

    # Treat empty strings and whitespace-only strings as missing values.
    object_columns = df.select_dtypes(include=["object", "string"]).columns.tolist()
    if object_columns:
        df[object_columns] = df[object_columns].replace(r"^\s*$", pd.NA, regex=True)

    important_columns = [
        "transaction_id",
        "product_name",
        "product_category",
        "quantity_sold",
        "unit_price",
        "date_of_transaction",
        "total_amount",
        "inventory_stock",
    ]
    present_important_columns = [column for column in important_columns if column in df.columns]
    missing_counts = {column: int(df[column].isna().sum()) for column in present_important_columns}

    print(f"[DEBUG] Missing values by column: {missing_counts}")

    for column in ["transaction_id", "product_name", "product_category"]:
        if column in df.columns:
            non_missing = df[column].notna()
            df.loc[non_missing, column] = df.loc[non_missing, column].astype(str).str.strip()

    if "transaction_id" in df.columns:
        df.loc[df["transaction_id"].notna(), "transaction_id"] = df.loc[df["transaction_id"].notna(), "transaction_id"].astype(str).str.upper()
    if "product_name" in df.columns:
        df.loc[df["product_name"].notna(), "product_name"] = (
            df.loc[df["product_name"].notna(), "product_name"].astype(str).str.replace(r"\s+", " ", regex=True).str.title()
        )
    if "product_category" in df.columns:
        df.loc[df["product_category"].notna(), "product_category"] = (
            df.loc[df["product_category"].notna(), "product_category"].astype(str).str.replace(r"\s+", " ", regex=True).str.title()
        )

    for column in ["quantity_sold", "unit_price", "total_amount", "inventory_stock"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df["date_of_transaction"] = pd.to_datetime(df["date_of_transaction"], errors="coerce")

    # Track missing values before applying fixes.
    missing_before_cleaning = int(df[present_important_columns].isna().any(axis=1).sum()) if present_important_columns else 0

    rows_imputed_due_to_missing = 0

    if "transaction_id" in df.columns:
        missing_mask = df["transaction_id"].isna()
        existing_ids = set(df.loc[~missing_mask, "transaction_id"].astype(str).str.upper())
        next_counter = len(existing_ids) + 1
        for idx in df.index[missing_mask]:
            candidate = f"TXN-AUTO-{next_counter:06d}"
            while candidate in existing_ids:
                next_counter += 1
                candidate = f"TXN-AUTO-{next_counter:06d}"
            df.at[idx, "transaction_id"] = candidate
            existing_ids.add(candidate)
            next_counter += 1
            rows_imputed_due_to_missing += 1

    if "product_name" in df.columns:
        missing_mask = df["product_name"].isna()
        if missing_mask.any():
            df.loc[missing_mask, "product_name"] = "Unknown Product"
            rows_imputed_due_to_missing += int(missing_mask.sum())

    if "product_category" in df.columns:
        missing_mask = df["product_category"].isna()
        if missing_mask.any():
            df.loc[missing_mask, "product_category"] = "Uncategorized"
            rows_imputed_due_to_missing += int(missing_mask.sum())

    if "quantity_sold" in df.columns:
        missing_mask = df["quantity_sold"].isna()
        if missing_mask.any():
            df.loc[missing_mask, "quantity_sold"] = 0
            rows_imputed_due_to_missing += int(missing_mask.sum())

    if "unit_price" in df.columns:
        missing_mask = df["unit_price"].isna()
        if missing_mask.any():
            df.loc[missing_mask, "unit_price"] = 0
            rows_imputed_due_to_missing += int(missing_mask.sum())

    if "inventory_stock" in df.columns:
        missing_mask = df["inventory_stock"].isna()
        if missing_mask.any():
            df.loc[missing_mask, "inventory_stock"] = 0
            rows_imputed_due_to_missing += int(missing_mask.sum())

    if "date_of_transaction" in df.columns:
        missing_mask = df["date_of_transaction"].isna()
        if missing_mask.any():
            df.loc[missing_mask, "date_of_transaction"] = pd.Timestamp.today().normalize()
            rows_imputed_due_to_missing += int(missing_mask.sum())

    if "total_amount" in df.columns:
        calculated_total = (df["quantity_sold"].fillna(0) * df["unit_price"].fillna(0)).round(2)
        total_missing_mask = df["total_amount"].isna()
        total_mismatch_mask = (~total_missing_mask) & ((df["total_amount"] - calculated_total).abs() > 0.01)
        total_fix_mask = total_missing_mask | total_mismatch_mask
        if total_fix_mask.any():
            df.loc[total_fix_mask, "total_amount"] = calculated_total[total_fix_mask]
            rows_imputed_due_to_missing += int(total_fix_mask.sum())

    print(f"[DEBUG] Rows imputed due to missing fields: {rows_imputed_due_to_missing}")

    calculated_total = (df["quantity_sold"].fillna(0) * df["unit_price"].fillna(0)).round(2)
    needs_recalc = df["total_amount"].isna() | ((df["total_amount"] - calculated_total).abs() > 0.01)
    df.loc[needs_recalc, "total_amount"] = calculated_total[needs_recalc]

    valid_rows = (
        df["transaction_id"].notna()
        & df["product_name"].notna()
        & df["product_category"].notna()
        & df["date_of_transaction"].notna()
        & df["quantity_sold"].notna()
        & df["unit_price"].notna()
        & df["total_amount"].notna()
        & (df["quantity_sold"] >= 0)
        & (df["unit_price"] >= 0)
        & (df["inventory_stock"].fillna(0) >= 0)
    )
    df = df.loc[valid_rows].copy()

    df["quantity_sold"] = df["quantity_sold"].astype(int)
    df["inventory_stock"] = df["inventory_stock"].fillna(0).astype(int)
    df["unit_price"] = df["unit_price"].round(2)
    df["total_amount"] = df["total_amount"].round(2)

    # First remove duplicate transaction IDs (keep first)
    txn_duplicate_mask = df.duplicated(subset=["transaction_id"], keep="first")
    txn_duplicates_removed = int(txn_duplicate_mask.sum())
    if txn_duplicates_removed:
        df = df.loc[~txn_duplicate_mask].copy()

    # Next: detect product-level duplicates.
    # Columns used to identify duplicate products (normalized):
    product_dup_cols = ["product_name", "product_category", "unit_price", "inventory_stock"]

    # Prepare a normalized view for duplicate detection
    dup_view = df.copy()
    for col in ["product_name", "product_category"]:
        if col in dup_view.columns:
            dup_view[col] = dup_view[col].astype(str).str.strip().str.lower()

    if "unit_price" in dup_view.columns:
        dup_view["unit_price"] = pd.to_numeric(dup_view["unit_price"], errors="coerce").fillna(0).round(2)
    if "inventory_stock" in dup_view.columns:
        dup_view["inventory_stock"] = pd.to_numeric(dup_view["inventory_stock"], errors="coerce").fillna(0).astype(int)

    product_duplicate_mask = dup_view.duplicated(subset=product_dup_cols, keep="first")
    product_duplicates_removed = int(product_duplicate_mask.sum())
    if product_duplicates_removed:
        df = df.loc[~product_duplicate_mask].copy()

    # Final dedupe and ordering
    df = df.sort_values("date_of_transaction").reset_index(drop=True)

    total_removed = int(original_rows - len(df))
    report = {
        "original_rows": original_rows,
        "cleaned_rows": int(len(df)),
        "removed_rows": total_removed,
        "duplicates_removed": txn_duplicates_removed + product_duplicates_removed,
        "txn_duplicates_removed": txn_duplicates_removed,
        "product_duplicates_removed": product_duplicates_removed,
        "missing_values_detected": missing_before_cleaning,
        "missing_values_removed": 0,
        "missing_values_fixed": rows_imputed_due_to_missing,
    }

    # Debugging output
    print(f"[DEBUG] Clean Data: original_rows={original_rows}, txn_dups={txn_duplicates_removed}, product_dups={product_duplicates_removed}, final_rows={len(df)}")

    return df, report
