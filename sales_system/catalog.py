from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    from .data_loader import save_transactions
except ImportError:  # pragma: no cover - allows running this file directly
    from data_loader import save_transactions


CATALOG_COLUMNS = ["product_id", "product_name", "product_category", "quantity_sold", "unit_price", "inventory_stock", "date_of_transaction"]


class ProductCatalog:
    def __init__(self, storage_path: str | Path) -> None:
        self.storage_path = Path(storage_path)
        self.frame = pd.DataFrame(columns=CATALOG_COLUMNS)
        self.dataset_frame = pd.DataFrame()

    def load(self, source_transactions: pd.DataFrame | None = None) -> pd.DataFrame:
        if source_transactions is not None:
            self.dataset_frame = source_transactions.copy()
        elif self.storage_path.exists():
            try:
                from .data_loader import load_transactions
            except ImportError:  # pragma: no cover - allows running this file directly
                from data_loader import load_transactions

            self.dataset_frame = load_transactions(self.storage_path)
        else:
            self.dataset_frame = pd.DataFrame()

        self._rebuild_catalog_view()
        return self.frame.copy()

    def save(self) -> None:
        if self.dataset_frame.empty:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            if self.frame.empty:
                self.frame = pd.DataFrame(columns=CATALOG_COLUMNS)
            return

        save_transactions(self.dataset_frame, self.storage_path)

    def list_products(self) -> pd.DataFrame:
        return self.frame.copy().sort_values(["date_of_transaction", "product_category", "product_name"]).reset_index(drop=True)

    def add_product(
        self,
        product_name: str,
        product_category: str,
        unit_price: float,
        inventory_stock: int,
        quantity_sold: int = 1,
    ) -> dict[str, object]:
        product_id = self._next_transaction_id()
        product_name = self._clean_text(product_name)
        product_category = self._clean_text(product_category)
        created_at = pd.Timestamp.now().normalize()
        new_row = {
            "product_id": product_id,
            "product_name": product_name,
            "product_category": product_category,
            "quantity_sold": int(quantity_sold),
            "unit_price": round(float(unit_price), 2),
            "inventory_stock": int(inventory_stock),
            "date_of_transaction": created_at,
        }
        transaction_row = {
            "transaction_id": product_id,
            "product_name": product_name,
            "product_category": product_category,
            "quantity_sold": int(quantity_sold),
            "unit_price": round(float(unit_price), 2),
            "date_of_transaction": created_at,
            "total_amount": round(float(unit_price) * int(quantity_sold), 2),
            "inventory_stock": int(inventory_stock),
        }

        self.dataset_frame = pd.concat([self.dataset_frame, pd.DataFrame([transaction_row])], ignore_index=True)
        self._rebuild_catalog_view()
        self.save()
        return self._record_from_identifier(product_id)

    def update_product(self, identifier: str, **changes: object) -> dict[str, object]:
        if self.frame.empty:
            raise ValueError("Product catalog is empty.")

        row_index = self._resolve_row_index(identifier)
        product_id = str(self.frame.loc[row_index, "product_id"])
        updates = {}
        for key, value in changes.items():
            if key not in CATALOG_COLUMNS:
                continue
            if key == "product_id":
                continue
            if key in {"product_name", "product_category"} and value is not None:
                updates[key] = self._clean_text(str(value))
            elif key == "unit_price" and value is not None:
                updates[key] = round(float(value), 2)
            elif key == "quantity_sold" and value is not None:
                updates[key] = int(value)
            elif key == "inventory_stock" and value is not None:
                updates[key] = int(value)

        dataset_mask = self.dataset_frame["transaction_id"].astype(str).str.lower().eq(product_id.strip().lower())
        if not dataset_mask.any():
            raise ValueError(f"Product not found: {identifier}")

        for key, value in updates.items():
            dataset_key = "date_of_transaction" if key == "date_of_transaction" else key
            if dataset_key in self.dataset_frame.columns:
                self.dataset_frame.loc[dataset_mask, dataset_key] = value

        if {"quantity_sold", "unit_price"} & updates.keys():
            quantity_series = pd.to_numeric(self.dataset_frame.loc[dataset_mask, "quantity_sold"], errors="coerce").fillna(0)
            price_series = pd.to_numeric(self.dataset_frame.loc[dataset_mask, "unit_price"], errors="coerce").fillna(0)
            self.dataset_frame.loc[dataset_mask, "total_amount"] = (quantity_series * price_series).round(2)

        self._rebuild_catalog_view()
        self.save()

        updated_record = self._record_from_identifier(product_id)
        for key, value in updates.items():
            if key in updated_record and updated_record[key] != value:
                raise RuntimeError(f"Product update validation failed for {key}.")
        return updated_record

    def delete_product(self, identifier: str) -> dict[str, object]:
        if self.frame.empty:
            raise ValueError("Product catalog is empty.")

        row_index = self._resolve_row_index(identifier)
        product_id = str(self.frame.loc[row_index, "product_id"])
        deleted_record = self.frame.loc[row_index].to_dict()

        if not self.dataset_frame.empty and "transaction_id" in self.dataset_frame.columns:
            dataset_mask = self.dataset_frame["transaction_id"].astype(str).str.lower().eq(product_id.strip().lower())
            if not dataset_mask.any():
                raise ValueError(f"Product not found: {identifier}")
            self.dataset_frame = self.dataset_frame.loc[~dataset_mask].copy().reset_index(drop=True)

        self._rebuild_catalog_view()
        self.save()

        if self.frame["product_id"].astype(str).str.lower().eq(product_id.strip().lower()).any():
            raise RuntimeError("Product delete validation failed.")
        return deleted_record

    def _match_product(self, identifier: str) -> pd.Series:
        normalized = str(identifier).strip().lower()
        return (
            self.frame["product_id"].astype(str).str.lower().eq(normalized)
            | self.frame["product_name"].astype(str).str.lower().eq(normalized)
        )

    def _resolve_row_index(self, identifier: str) -> int:
        normalized = str(identifier).strip().lower()
        match = self._match_product(normalized)
        if match.any():
            return int(self.frame.index[match][0])

        if normalized.isdigit():
            row_index = int(normalized)
            if 0 <= row_index < len(self.frame):
                return row_index

        raise ValueError(f"Product not found: {identifier}")

    def _record_from_identifier(self, identifier: str) -> dict[str, object]:
        row_index = self._resolve_row_index(identifier)
        record = self.frame.loc[row_index].to_dict()
        if "date_of_transaction" in record and pd.notna(record["date_of_transaction"]):
            record["date_of_transaction"] = pd.to_datetime(record["date_of_transaction"]).date().isoformat()
        return record

    def _next_product_id(self) -> str:
        if self.frame.empty or "product_id" not in self.frame:
            return "PRD-0001"

        existing_numbers = []
        for value in self.frame["product_id"].astype(str):
            parts = value.split("-")
            if len(parts) == 2 and parts[1].isdigit():
                existing_numbers.append(int(parts[1]))

        next_number = max(existing_numbers, default=0) + 1
        return f"PRD-{next_number:04d}"

    def _next_transaction_id(self) -> str:
        if self.dataset_frame.empty or "transaction_id" not in self.dataset_frame:
            return "TXN-000001"

        existing_numbers = []
        for value in self.dataset_frame["transaction_id"].astype(str):
            digits = "".join(character for character in value if character.isdigit())
            if digits:
                existing_numbers.append(int(digits))

        next_number = max(existing_numbers, default=0) + 1
        return f"TXN-{next_number:06d}"

    def _rebuild_catalog_view(self) -> None:
        if self.dataset_frame.empty:
            self.frame = pd.DataFrame(columns=CATALOG_COLUMNS)
            return

        frame = self.dataset_frame.copy()
        for column in ["product_name", "product_category"]:
            if column in frame.columns:
                frame[column] = frame[column].astype(str).str.strip()

        if "product_name" in frame.columns:
            frame["product_name"] = frame["product_name"].str.replace(r"\s+", " ", regex=True).str.title()
        if "product_category" in frame.columns:
            frame["product_category"] = frame["product_category"].str.replace(r"\s+", " ", regex=True).str.title()

        for column in ["unit_price", "inventory_stock", "quantity_sold", "total_amount"]:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

        if "date_of_transaction" in frame.columns:
            frame["date_of_transaction"] = pd.to_datetime(frame["date_of_transaction"], errors="coerce")

        if "transaction_id" not in frame.columns:
            frame["transaction_id"] = [f"TXN-AUTO-{index + 1:06d}" for index in range(len(frame))]
        if "date_of_transaction" not in frame.columns:
            frame["date_of_transaction"] = pd.NaT

        catalog = frame[["transaction_id", "product_name", "product_category", "quantity_sold", "unit_price", "inventory_stock", "date_of_transaction"]].copy()
        catalog = catalog.rename(columns={"transaction_id": "product_id"})
        catalog = catalog.sort_values(["date_of_transaction", "product_category", "product_name", "product_id"]).reset_index(drop=True)
        self.frame = catalog[CATALOG_COLUMNS]

    @staticmethod
    def _clean_text(value: str) -> str:
        return str(value).strip().replace("  ", " ").title()
