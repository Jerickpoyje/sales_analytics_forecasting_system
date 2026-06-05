from __future__ import annotations

from pathlib import Path

import pandas as pd

from .analytics import category_summary, cleaning_summary_text, save_visualizations, top_selling_items, total_revenue
from .catalog import ProductCatalog
from .config import DATASET_PATH, OUTPUT_DIR, PROJECT_ROOT, ensure_dataset_file, ensure_project_directories
from .data_loader import clean_transactions, load_transactions, save_transactions
from .forecasting import forecast_sales, forecast_summary, save_forecast_chart


class SalesAnalyticsApp:
    def __init__(self) -> None:
        self.project_root = PROJECT_ROOT
        self.data_dir = DATASET_PATH.parent
        self.output_dir = OUTPUT_DIR
        self.default_dataset = DATASET_PATH
        self.catalog_path = DATASET_PATH
        self.raw_transactions = pd.DataFrame()
        self.cleaned_transactions = pd.DataFrame()
        self.catalog = ProductCatalog(self.catalog_path)
        self.active_dataset_path = self.default_dataset

    def run(self) -> None:
        self._print_header()
        self._load_initial_data()

        while True:
            print()
            print("1. View dataset summary")
            print("2. Clean transaction data")
            print("3. Product management")
            print("4. Analytics module")
            print("5. Forecasting module")
            print("6. Generate all charts")
            print("0. Exit")

            choice = input("Select an option: ").strip()
            if choice == "1":
                self.show_dataset_summary()
            elif choice == "2":
                self.clean_data()
            elif choice == "3":
                self.product_management_menu()
            elif choice == "4":
                self.analytics_menu()
            elif choice == "5":
                self.forecasting_menu()
            elif choice == "6":
                self.generate_all_charts()
            elif choice == "0":
                print("Exiting system.")
                break
            else:
                print("Invalid choice. Please try again.")

    def _print_header(self) -> None:
        print("=" * 72)
        print("Terminal-Based Sales Analytics and Forecasting System")
        print("=" * 72)

    def _load_initial_data(self) -> None:
        ensure_dataset_file()
        while True:
            prompt = f"Enter dataset path [default: {self.default_dataset}]: "
            user_input = input(prompt).strip()
            source_dataset_path = Path(user_input) if user_input else self.default_dataset

            if not source_dataset_path.exists() and source_dataset_path == self.default_dataset:
                source_dataset_path = ensure_dataset_file()

            try:
                self.raw_transactions = load_transactions(source_dataset_path)
                self.cleaned_transactions = pd.DataFrame()
                self.catalog.load(self.raw_transactions)
                self._ensure_storage_dirs()
                self._sync_after_dataset_change()
                print(f"Loaded {len(self.raw_transactions)} transaction rows from {source_dataset_path}")
                print(f"Dataset writes are pinned to {self.active_dataset_path}")
                break
            except Exception as exc:
                print(f"Unable to load dataset: {exc}")
                retry = input("Try another path? (y/n): ").strip().lower()
                if retry != "y":
                    raise SystemExit("Cannot continue without a valid dataset.")

    def _ensure_storage_dirs(self) -> None:
        ensure_project_directories()
        self.catalog.save()

    def _sync_after_dataset_change(self) -> None:
        self.raw_transactions = self.catalog.dataset_frame.copy()
        self.cleaned_transactions = pd.DataFrame()
        self.active_dataset_path = self.catalog.storage_path

    def current_frame(self) -> pd.DataFrame:
        return self.cleaned_transactions if not self.cleaned_transactions.empty else self.raw_transactions

    def show_dataset_summary(self) -> None:
        frame = self.current_frame()
        print()
        print(f"Rows: {len(frame)}")
        print(f"Columns: {len(frame.columns)}")
        print(f"Date range: {frame['date_of_transaction'].min().date()} to {frame['date_of_transaction'].max().date()}")
        print(f"Total revenue: {total_revenue(frame):,.2f}")
        print()
        print(frame.head(5).to_string(index=False))

    def clean_data(self) -> None:
        cleaned, report = clean_transactions(self.raw_transactions)
        self.cleaned_transactions = cleaned

        # Save cleaned dataset back to active dataset path
        try:
            save_transactions(cleaned, self.active_dataset_path)
            # Update in-memory data so analytics sees the cleaned version immediately
            self.raw_transactions = cleaned.copy()
        except Exception as exc:
            print(f"Failed to save cleaned dataset: {exc}")

        print()
        print("Data cleaning completed.")
        print(cleaning_summary_text(report))
        # Add detailed duplicate counts if available
        if "txn_duplicates_removed" in report or "product_duplicates_removed" in report:
            print(f"Transaction ID duplicates removed: {report.get('txn_duplicates_removed', 0)}")
            print(f"Product-level duplicates removed: {report.get('product_duplicates_removed', 0)}")
        print(f"Cleaned dataset rows: {len(cleaned)}")
        return report

    def product_management_menu(self) -> None:
        while True:
            print()
            print("Product Management")
            print("1. View products")
            print("2. Add product")
            print("3. Update product")
            print("4. Delete product")
            print("5. Save catalog")
            print("0. Back")

            choice = input("Select an option: ").strip()
            if choice == "1":
                catalog = self.catalog.list_products()
                if catalog.empty:
                    print("No products available.")
                else:
                    print(catalog.to_string(index=False))
            elif choice == "2":
                self.add_product_flow()
            elif choice == "3":
                self.update_product_flow()
            elif choice == "4":
                self.delete_product_flow()
            elif choice == "5":
                self.catalog.save()
                print(f"Dataset saved to {self.catalog.storage_path}")
            elif choice == "0":
                break
            else:
                print("Invalid choice.")

    def add_product_flow(self) -> None:
        name = input("Product name: ").strip()
        category = input("Product category: ").strip()
        price = self._prompt_float("Unit price: ")
        stock = self._prompt_int("Inventory stock: ")
        product = self.catalog.add_product(name, category, price, stock)
        self._sync_after_dataset_change()
        print(f"Added product {product['product_id']} - {product['product_name']}")
        print(f"Saved to {self.active_dataset_path}")

    def update_product_flow(self) -> None:
        identifier = input("Enter product ID or row index: ").strip()
        print("Leave a field blank to keep the current value.")
        name = input("New product name: ").strip()
        category = input("New product category: ").strip()
        price_text = input("New unit price: ").strip()
        stock_text = input("New inventory stock: ").strip()

        changes: dict[str, object] = {}
        if name:
            changes["product_name"] = name
        if category:
            changes["product_category"] = category
        if price_text:
            changes["unit_price"] = float(price_text)
        if stock_text:
            changes["inventory_stock"] = int(stock_text)

        updated = self.catalog.update_product(identifier, **changes)
        self._sync_after_dataset_change()
        print(f"Updated product {updated['product_id']} - {updated['product_name']}")
        print(f"Saved to {self.active_dataset_path}")

    def delete_product_flow(self) -> None:
        identifier = input("Enter product ID or row index to delete: ").strip()
        confirm = input(f"Delete product {identifier}? (y/n): ").strip().lower()
        if confirm != "y":
            print("Deletion cancelled.")
            return

        deleted = self.catalog.delete_product(identifier)
        self._sync_after_dataset_change()
        print(f"Deleted product {deleted['product_id']} - {deleted['product_name']}")
        print(f"Saved to {self.active_dataset_path}")

    def analytics_menu(self) -> None:
        frame = self.current_frame()
        print()
        print(f"Total Revenue: {total_revenue(frame):,.2f}")
        print()
        categories = category_summary(frame)
        top_items = top_selling_items(frame, metric="total_amount", limit=3)
        print("Category summary:")
        print(categories.to_string(index=False))
        print()
        print("Top 3 best-selling products:")
        print(top_items.to_string(index=False))

    def forecasting_menu(self) -> None:
        frame = self.current_frame()
        print()
        forecasts = forecast_summary(frame)
        print("3-month forecast:")
        print(forecasts["3_month"].to_string(index=False))
        print()
        print("12-month forecast:")
        print(forecasts["12_month"].to_string(index=False))
        self._save_forecast_chart(frame, forecasts["12_month"])

    def generate_all_charts(self) -> None:
        frame = self.current_frame()
        if frame.empty:
            print("No data available for charts.")
            return

        chart_paths = save_visualizations(frame, self.output_dir)
        forecast_df = forecast_sales(frame, periods=12)
        forecast_path = self._save_forecast_chart(frame, forecast_df)
        chart_paths.append(forecast_path)

        print("Charts generated:")
        for path in chart_paths:
            print(path)

    def _save_forecast_chart(self, frame: pd.DataFrame, forecast_df: pd.DataFrame) -> Path:
        output_path = self.output_dir / "forecast_chart.png"
        save_forecast_chart(frame, forecast_df, output_path)
        return output_path

    @staticmethod
    def _prompt_float(prompt: str) -> float:
        while True:
            try:
                return float(input(prompt).strip())
            except ValueError:
                print("Please enter a valid number.")

    @staticmethod
    def _prompt_int(prompt: str) -> int:
        while True:
            try:
                return int(float(input(prompt).strip()))
            except ValueError:
                print("Please enter a valid whole number.")
