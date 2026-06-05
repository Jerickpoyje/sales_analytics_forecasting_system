from __future__ import annotations

import threading
from pathlib import Path
import tkinter as tk
import tkinter.scrolledtext as scrolled
from tkinter import messagebox, ttk
import customtkinter as ctk
from PIL import Image, ImageTk
import pandas as pd

from .app import SalesAnalyticsApp
from .config import DATASET_PATH, ensure_dataset_file, ensure_project_directories
from .data_loader import load_transactions, clean_transactions
from .analytics import category_summary, total_revenue, top_selling_items, save_visualizations
from .forecasting import forecast_summary, forecast_sales, save_forecast_chart


class SalesAnalyticsGUI(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Sales Analytics — GUI")
        self.geometry("1200x800")
        self.resizable(True, True)
        self.after(0, self._maximize_window)

        self.app = SalesAnalyticsApp()
        canonical_dataset = ensure_dataset_file()

        # Top frame for dataset controls
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", padx=12, pady=8)

        self.path_var = tk.StringVar(value=str(canonical_dataset))
        ctk.CTkLabel(top_frame, text="Dataset path:").pack(side="left", padx=(4, 8))
        self.path_entry = ctk.CTkEntry(top_frame, textvariable=self.path_var, width=560)
        self.path_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(top_frame, text="Load", command=self._threaded(self.load_dataset)).pack(side="left")

        # Buttons frame
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=12)

        ctk.CTkButton(btn_frame, text="Show Summary", command=self._threaded(self.show_summary)).pack(side="left", padx=6, pady=8)
        ctk.CTkButton(btn_frame, text="Clean Data", command=self._threaded(self.clean_data)).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Analytics", command=self._threaded(self.show_analytics)).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Products", command=self._open_product_management).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Forecasting", command=self._threaded(self.show_forecasting)).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Generate Charts", command=self._threaded(self.generate_charts)).pack(side="left", padx=6)

        # Output area
        out_frame = ctk.CTkFrame(self)
        out_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.output = scrolled.ScrolledText(out_frame, wrap="word")
        self.output.pack(fill="both", expand=True, padx=6, pady=6)

    def _maximize_window(self, window: tk.Misc | None = None) -> None:
        target = window or self
        try:
            target.state("zoomed")
        except Exception:
            try:
                target.attributes("-fullscreen", True)
            except Exception:
                pass

    def _threaded(self, fn):
        def wrapper():
            fn()

        return wrapper

    def _log(self, *parts: object) -> None:
        text = " ".join(str(p) for p in parts) + "\n"
        self.output.insert(tk.END, text)
        self.output.see(tk.END)

    def load_dataset(self) -> None:
        path = Path(self.path_var.get())
        try:
            df = load_transactions(path)
            self.app.raw_transactions = df
            self.app.catalog.load(self.app.raw_transactions)
            ensure_project_directories()
            self.app.catalog.save()
            self.app._sync_after_dataset_change()
            self._refresh_product_table()
            self._log(f"Loaded {len(df)} rows from {path}")
            self._log(f"Dataset writes are pinned to {DATASET_PATH}")
        except Exception as exc:
            self._log(f"Failed to load dataset: {exc}")

    def show_summary(self) -> None:
        frame = self.app.current_frame()
        if frame.empty:
            self._log("No data loaded.")
            return
        rows = len(frame)
        cols = len(frame.columns)
        try:
            date_min = frame["date_of_transaction"].min().date()
            date_max = frame["date_of_transaction"].max().date()
        except Exception:
            date_min = "n/a"
            date_max = "n/a"
        revenue = total_revenue(frame)
        self._log(f"Rows: {rows}, Columns: {cols}")
        self._log(f"Date range: {date_min} to {date_max}")
        self._log(f"Total revenue: {revenue:,.2f}")

    def clean_data(self) -> None:
        try:
            report = self.app.clean_data()
            self._log("Data cleaning completed and saved to dataset.")
            self._log(report)
            self._log(f"Cleaned rows: {len(self.app.raw_transactions)}")
            self._refresh_product_table()
        except Exception as exc:
            self._log(f"Data cleaning failed: {exc}")

    def show_analytics(self) -> None:
        frame = self.app.current_frame()
        if frame.empty:
            self._log("No data available for analytics.")
            return
        categories = category_summary(frame)
        top_items = top_selling_items(frame, metric="total_amount", limit=5)
        self._log("Category summary:")
        self._log(categories.to_string(index=False))
        self._log("Top products:")
        self._log(top_items.to_string(index=False))

    def show_forecasting(self) -> None:
        frame = self.app.current_frame()
        if frame.empty:
            self._log("No data available for forecasting.")
            return
        forecasts = forecast_summary(frame)
        self._log("3-month forecast:")
        self._log(forecasts["3_month"].to_string(index=False))
        self._log("12-month forecast:")
        self._log(forecasts["12_month"].to_string(index=False))

    def generate_charts(self) -> None:
        frame = self.app.current_frame()
        if frame.empty:
            self._log("No data available for charts.")
            return
        chart_paths = save_visualizations(frame, self.app.output_dir)
        forecast_df = forecast_sales(frame, periods=12)
        forecast_path = self.app._save_forecast_chart(frame, forecast_df)
        chart_paths.append(forecast_path)
        self._log("Charts generated:")
        for path in chart_paths:
            self._log(path)

        # Display images in the GUI — schedule on main thread
        try:
            self.after(0, lambda: self._show_image_gallery(chart_paths))
        except Exception:
            # Fall back to logging only
            pass

    # --- Product management UI ---
    def _open_product_management(self) -> None:
        if hasattr(self, "pm_window") and self.pm_window.winfo_exists():
            self.pm_window.lift()
            self._refresh_product_table()
            return

        self.pm_window = tk.Toplevel(self)
        self.pm_window.title("Product Management")
        self.pm_window.geometry("1400x860")
        self.pm_window.resizable(True, True)
        self.after(0, lambda: self._maximize_window(self.pm_window))

        left = ctk.CTkFrame(self.pm_window, width=340)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ctk.CTkFrame(self.pm_window)
        right.pack(side="right", fill="both", expand=True, padx=8, pady=8)

        # Product detail form
        ctk.CTkLabel(left, text="Product Details").pack(anchor="w", pady=(4, 6))
        form = tk.Frame(left)
        form.pack(fill="x", padx=6)

        tk.Label(form, text="Product ID:").grid(row=0, column=0, sticky="e", pady=4)
        self.pm_id = tk.StringVar()
        tk.Entry(form, textvariable=self.pm_id, state="readonly", width=28).grid(row=0, column=1, pady=4, sticky="w")

        tk.Label(form, text="Name:").grid(row=1, column=0, sticky="e", pady=4)
        self.pm_name = tk.StringVar()
        tk.Entry(form, textvariable=self.pm_name, width=28).grid(row=1, column=1, pady=4, sticky="w")

        tk.Label(form, text="Category:").grid(row=2, column=0, sticky="e", pady=4)
        self.pm_category = tk.StringVar()
        self.pm_category_combo = ttk.Combobox(form, textvariable=self.pm_category, state="readonly", width=26)
        self.pm_category_combo.grid(row=2, column=1, pady=4, sticky="w")

        tk.Label(form, text="Unit Price:").grid(row=3, column=0, sticky="e", pady=4)
        self.pm_price = tk.StringVar()
        tk.Entry(form, textvariable=self.pm_price, width=16).grid(row=3, column=1, pady=4, sticky="w")

        tk.Label(form, text="Quantity Sold:").grid(row=4, column=0, sticky="e", pady=4)
        self.pm_quantity_sold = tk.StringVar()
        tk.Entry(form, textvariable=self.pm_quantity_sold, width=16).grid(row=4, column=1, pady=4, sticky="w")

        tk.Label(form, text="Inventory Stock:").grid(row=5, column=0, sticky="e", pady=4)
        self.pm_stock = tk.StringVar()
        tk.Entry(form, textvariable=self.pm_stock, width=16).grid(row=5, column=1, pady=4, sticky="w")

        btn_frame = ctk.CTkFrame(left)
        btn_frame.pack(fill="x", pady=(10, 6))
        ctk.CTkButton(btn_frame, text="Refresh", command=self._refresh_product_table).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Save", command=self._save_catalog).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Clear", command=self._clear_product_form).pack(side="left", padx=6)

        action_frame = ctk.CTkFrame(right)
        action_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(action_frame, text="Add Product", command=self._add_product).pack(side="left", padx=6)
        ctk.CTkButton(action_frame, text="Update Product", command=self._update_product).pack(side="left", padx=6)
        ctk.CTkButton(action_frame, text="Delete Product", command=self._delete_product).pack(side="left", padx=6)

        filter_frame = ctk.CTkFrame(right)
        filter_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(filter_frame, text="Search").pack(side="left", padx=(6, 4))
        self.pm_search_var = tk.StringVar()
        self.pm_search_entry = tk.Entry(filter_frame, textvariable=self.pm_search_var, width=28)
        self.pm_search_entry.pack(side="left", padx=(0, 10), pady=6)
        self.pm_search_entry.bind("<KeyRelease>", lambda _event: self._refresh_product_table())

        ctk.CTkLabel(filter_frame, text="Category").pack(side="left", padx=(6, 4))
        self.pm_category_filter_var = tk.StringVar(value="All Categories")
        self.pm_category_filter = ttk.Combobox(filter_frame, textvariable=self.pm_category_filter_var, state="readonly", width=24)
        self.pm_category_filter.pack(side="left", padx=(0, 10), pady=6)
        self.pm_category_filter.bind("<<ComboboxSelected>>", lambda _event: self._refresh_product_table())
        ctk.CTkButton(filter_frame, text="Clear Filters", command=self._clear_product_filters).pack(side="left", padx=6)

        ctk.CTkLabel(right, text="Product Table").pack(anchor="w", pady=(4, 6))
        table_frame = ctk.CTkFrame(right)
        table_frame.pack(fill="both", expand=True)

        self.product_tree = ttk.Treeview(table_frame, columns=(), show="headings", selectmode="browse")
        self.product_tree.bind("<<TreeviewSelect>>", self._on_product_select)

        tree_scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.product_tree.yview)
        tree_scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.product_tree.xview)
        self.product_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.product_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self._refresh_category_options()
        self._refresh_product_table()

    def _clear_product_filters(self) -> None:
        if hasattr(self, "pm_search_var"):
            self.pm_search_var.set("")
        if hasattr(self, "pm_category_filter_var"):
            self.pm_category_filter_var.set("All Categories")
        self._refresh_product_table()

    def _refresh_category_options(self, current_selection: str | None = None) -> None:
        if hasattr(self, "pm_category_combo") and not self.pm_category_combo.winfo_exists():
            return
        if hasattr(self, "pm_category_filter") and not self.pm_category_filter.winfo_exists():
            return

        categories = []
        df = self._display_frame()
        if not df.empty and "product_category" in df.columns:
            categories = sorted({str(value) for value in df["product_category"].dropna().astype(str)})

        if hasattr(self, "pm_category_combo"):
            self.pm_category_combo["values"] = categories
            if current_selection and current_selection in categories:
                self.pm_category.set(current_selection)

        if hasattr(self, "pm_category_filter"):
            filter_values = ["All Categories"] + categories
            self.pm_category_filter["values"] = filter_values
            desired = current_selection if current_selection in filter_values else self.pm_category_filter_var.get().strip()
            if desired not in filter_values:
                desired = "All Categories"
            self.pm_category_filter_var.set(desired)

    def _display_frame(self) -> pd.DataFrame:
        return self.app.current_frame().reset_index(drop=True)

    def _tree_identifier_column(self, df: pd.DataFrame) -> str | None:
        for candidate in ("transaction_id", "product_id"):
            if candidate in df.columns:
                return candidate
        return df.columns[0] if len(df.columns) else None

    def _format_tree_value(self, value: object) -> object:
        if pd.isna(value):
            return ""
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        return value

    def _sync_tree_columns(self, df: pd.DataFrame) -> None:
        columns = list(df.columns)
        current_columns = list(self.product_tree["columns"])
        if current_columns != columns:
            self.product_tree["columns"] = columns

        for column in columns:
            heading_text = column.replace("_", " ").title()
            self.product_tree.heading(column, text=heading_text)

            lowered = column.lower()
            if lowered in {"transaction_id", "product_id"}:
                anchor = "w"
                width = 140
            elif "date" in lowered:
                anchor = "center"
                width = 130
            elif any(token in lowered for token in ("price", "amount", "quantity", "stock", "total")):
                anchor = "e"
                width = 120
            else:
                anchor = "w"
                width = max(120, min(260, len(heading_text) * 10))

            self.product_tree.column(column, width=width, anchor=anchor, stretch=True)

    def _filtered_product_frame(self) -> pd.DataFrame:
        df = self._display_frame()
        if df.empty:
            return df

        search_text = self.pm_search_var.get().strip().lower() if hasattr(self, "pm_search_var") else ""
        category_filter = self.pm_category_filter_var.get().strip() if hasattr(self, "pm_category_filter_var") else "All Categories"

        if search_text:
            text_frame = df.astype(str).apply(lambda column: column.str.lower())
            mask = text_frame.apply(lambda column: column.str.contains(search_text, na=False)).any(axis=1)
            df = df.loc[mask].copy()

        if category_filter and category_filter != "All Categories" and "product_category" in df.columns:
            df = df.loc[df["product_category"].astype(str).str.lower().eq(category_filter.lower())].copy()

        return df.reset_index(drop=True)

    def _refresh_category_filter_options(self, current_selection: str | None = None) -> None:
        self._refresh_category_options(current_selection=current_selection)

    def _refresh_product_table(self) -> None:
        if not hasattr(self, "product_tree") or not self.product_tree.winfo_exists():
            return

        self._refresh_category_options()
        selected_id = self.pm_id.get().strip() if hasattr(self, "pm_id") else ""
        for item in self.product_tree.get_children():
            self.product_tree.delete(item)

        df = self._filtered_product_frame()
        self._sync_tree_columns(df)
        identifier_column = self._tree_identifier_column(df)
        for _, row in df.iterrows():
            values = [self._format_tree_value(row[column]) for column in df.columns]
            row_identifier = str(row[identifier_column]) if identifier_column else str(len(self.product_tree.get_children()))
            self.product_tree.insert("", tk.END, iid=row_identifier, values=values)

        if selected_id and self.product_tree.exists(selected_id):
            self.product_tree.selection_set(selected_id)
            self.product_tree.see(selected_id)

    def _on_product_select(self, _event) -> None:
        if not hasattr(self, "product_tree"):
            return

        sel = self.product_tree.selection()
        if not sel:
            return

        selected_id = sel[0]
        df = self._display_frame().reset_index(drop=True)
        identifier_column = self._tree_identifier_column(df)
        if identifier_column is None:
            return

        row = df.loc[df[identifier_column].astype(str) == str(selected_id)]
        if row.empty:
            return
        row = row.iloc[0]
        if hasattr(self, "pm_id"):
            self.pm_id.set(str(row[identifier_column]))
        if hasattr(self, "pm_name"):
            self.pm_name.set(str(row["product_name"])) if "product_name" in row.index else self.pm_name.set("")
        if hasattr(self, "pm_category"):
            self.pm_category.set(str(row["product_category"])) if "product_category" in row.index else self.pm_category.set("")
        if hasattr(self, "pm_price"):
            if "unit_price" in row.index and pd.notna(row["unit_price"]):
                self.pm_price.set(f"{float(row['unit_price']):.2f}")
            else:
                self.pm_price.set("")
        if hasattr(self, "pm_quantity_sold"):
            if "quantity_sold" in row.index and pd.notna(row["quantity_sold"]):
                self.pm_quantity_sold.set(str(int(float(row["quantity_sold"]))))
            else:
                self.pm_quantity_sold.set("")
        if hasattr(self, "pm_stock"):
            if "inventory_stock" in row.index and pd.notna(row["inventory_stock"]):
                self.pm_stock.set(str(int(float(row["inventory_stock"]))))
            else:
                self.pm_stock.set("")

    def _clear_product_form(self) -> None:
        self.pm_id.set("")
        self.pm_name.set("")
        self.pm_category.set("")
        self.pm_price.set("")
        if hasattr(self, "pm_quantity_sold"):
            self.pm_quantity_sold.set("")
        self.pm_stock.set("")
        if hasattr(self, "product_tree"):
            self.product_tree.selection_remove(self.product_tree.selection())

    def _add_product(self) -> None:
        try:
            name = self.pm_name.get().strip()
            category = self.pm_category.get().strip()
            price = float(self.pm_price.get() or 0)
            quantity_sold = int(float(self.pm_quantity_sold.get() or 0))
            stock = int(float(self.pm_stock.get() or 0))
            if not name or not category:
                raise ValueError("Product name and category are required.")
            if price < 0 or quantity_sold < 0 or stock < 0:
                raise ValueError("Unit price, quantity sold, and inventory stock must be non-negative.")
            product = self.app.catalog.add_product(name, category, price, stock, quantity_sold)
            self.app._sync_after_dataset_change()
            self._refresh_product_table()
            self._log(f"Added product {product['product_id']} - {product['product_name']}")
            self._log(f"Saved to {self.app.catalog.storage_path}")
            messagebox.showinfo("Product Added", f"Added {product['product_name']} ({product['product_id']}).")
            self.pm_id.set(str(product["product_id"]))
        except PermissionError as exc:
            self._log(f"Failed to add product due to file permission error: {exc}")
            self._log("Ensure the dataset CSV is not open in Excel or another program, then try again.")
        except Exception as exc:
            self._log(f"Failed to add product: {exc}")

    def _update_product(self) -> None:
        try:
            identifier = self.pm_id.get().strip()
            if not identifier:
                raise ValueError("Select a product from the table before updating.")

            changes = {}
            name = self.pm_name.get().strip()
            category = self.pm_category.get().strip()
            price_text = self.pm_price.get().strip()
            quantity_text = self.pm_quantity_sold.get().strip() if hasattr(self, "pm_quantity_sold") else ""
            stock_text = self.pm_stock.get().strip()

            if name:
                changes["product_name"] = name
            if category:
                changes["product_category"] = category
            if price_text:
                changes["unit_price"] = float(price_text)
            if quantity_text:
                changes["quantity_sold"] = int(float(quantity_text))
            if stock_text:
                changes["inventory_stock"] = int(float(stock_text))

            if not changes:
                raise ValueError("Enter at least one field to update.")

            updated = self.app.catalog.update_product(identifier, **changes)
            self.app._sync_after_dataset_change()
            self._refresh_product_table()

            for key, value in changes.items():
                if key not in updated:
                    continue
                if key in {"unit_price"}:
                    if round(float(updated[key]), 2) != round(float(value), 2):
                        raise RuntimeError(f"Validation failed for {key}.")
                elif key in {"quantity_sold"}:
                    if int(updated[key]) != int(value):
                        raise RuntimeError(f"Validation failed for {key}.")
                elif key in {"inventory_stock"}:
                    if int(updated[key]) != int(value):
                        raise RuntimeError(f"Validation failed for {key}.")
                elif key in {"product_name", "product_category"}:
                    expected = str(value).strip().replace("  ", " ").title()
                    if str(updated[key]).strip() != expected:
                        raise RuntimeError(f"Validation failed for {key}.")
                elif str(updated[key]).strip() != str(value).strip():
                    raise RuntimeError(f"Validation failed for {key}.")

            self._log(f"Updated product {updated['product_id']} - {updated['product_name']}")
            self._log(f"Saved to {self.app.catalog.storage_path}")
            messagebox.showinfo("Product Updated", f"Updated {updated['product_name']} ({updated['product_id']}).")
        except PermissionError as exc:
            self._log(f"Failed to update product due to file permission error: {exc}")
            self._log("Ensure the dataset CSV is not open in Excel or another program, then try again.")
        except Exception as exc:
            self._log(f"Failed to update product: {exc}")

    def _delete_product(self) -> None:
        try:
            identifier = self.pm_id.get().strip()
            if not identifier:
                raise ValueError("Select a product from the table before deleting.")

            selected = self.app.catalog.list_products()
            match = selected.loc[selected["product_id"].astype(str) == identifier]
            if match.empty:
                raise ValueError(f"Product not found: {identifier}")

            product_name = str(match.iloc[0]["product_name"])
            if not messagebox.askyesno("Confirm Delete", f"Delete {product_name} ({identifier})?"):
                return

            deleted = self.app.catalog.delete_product(identifier)
            self.app._sync_after_dataset_change()
            self._refresh_product_table()
            self._clear_product_form()
            self._log(f"Deleted product {deleted['product_id']} - {deleted['product_name']}")
            self._log(f"Saved to {self.app.catalog.storage_path}")
            messagebox.showinfo("Product Deleted", f"Deleted {deleted['product_name']} ({deleted['product_id']}).")
        except PermissionError as exc:
            self._log(f"Failed to delete product due to file permission error: {exc}")
            self._log("Ensure the dataset CSV is not open in Excel or another program, then try again.")
        except Exception as exc:
            self._log(f"Failed to delete product: {exc}")

    def _save_catalog(self) -> None:
        try:
            self.app.catalog.save()
            self._log(f"Dataset saved to {self.app.catalog.storage_path}")
            self._refresh_product_table()
        except Exception as exc:
            if isinstance(exc, PermissionError):
                self._log(f"Failed to save catalog due to permission error: {exc}")
                self._log("Close any program using the CSV (Excel) and try again.")
            else:
                self._log(f"Failed to save catalog: {exc}")

    def _show_image_gallery(self, paths: list[Path]) -> None:
        if not paths:
            return

        gallery = tk.Toplevel(self)
        gallery.title("Generated Charts")
        gallery.geometry("1400x900")
        gallery.resizable(True, True)
        self._maximize_window(gallery)

        container = tk.Frame(gallery)
        container.pack(fill="both", expand=True)

        # Keep references to PhotoImage objects
        gallery._images = []
        controls = tk.Frame(gallery)
        controls.pack(fill="x", padx=12, pady=(0, 8))

        image_frame = tk.Frame(container, bd=1, relief="solid", padx=8, pady=8)
        image_frame.pack(fill="both", expand=True, padx=12, pady=12)
        image_frame.grid_rowconfigure(0, weight=1)
        image_frame.grid_columnconfigure(0, weight=1)

        page_size = 1
        total_pages = max(1, (len(paths) + page_size - 1) // page_size)
        gallery._page_index = 0

        page_label = tk.Label(controls, anchor="center")
        page_label.pack(side="left", expand=True)

        def _clear_tiles() -> None:
            for child in image_frame.winfo_children():
                child.destroy()
            gallery._images.clear()

        def _fit_image(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
            width, height = image.size
            width_scale = max_width / max(width, 1)
            height_scale = max_height / max(height, 1)
            scale = min(width_scale, height_scale)
            new_width = max(1, int(width * scale))
            new_height = max(1, int(height * scale))
            if new_width == width and new_height == height:
                return image
            return image.resize((new_width, new_height), Image.LANCZOS)

        def _render_page() -> None:
            _clear_tiles()
            gallery.update_idletasks()

            start = gallery._page_index * page_size
            page_items = paths[start : start + page_size]
            tile_width = max(640, gallery.winfo_width() - 60)
            tile_height = max(420, gallery.winfo_height() - controls.winfo_height() - 80)

            for p in page_items:
                try:
                    with Image.open(p) as img:
                        photo = ImageTk.PhotoImage(_fit_image(img, tile_width, tile_height))
                    label = tk.Label(image_frame, image=photo, text=p.name, compound="top", justify="center")
                    label.grid(row=0, column=0, sticky="nsew")
                    gallery._images.append(photo)
                except Exception as exc:
                    tk.Label(image_frame, text=f"Failed to load {p.name}: {exc}").grid(row=0, column=0, sticky="nsew")

            page_label.config(text=f"Page {gallery._page_index + 1} of {total_pages}")
            prev_button.config(state="normal" if gallery._page_index > 0 else "disabled")
            next_button.config(state="normal" if gallery._page_index < total_pages - 1 else "disabled")

        def _go_previous() -> None:
            if gallery._page_index > 0:
                gallery._page_index -= 1
                _render_page()

        def _go_next() -> None:
            if gallery._page_index < total_pages - 1:
                gallery._page_index += 1
                _render_page()

        prev_button = tk.Button(controls, text="Previous", command=_go_previous)
        prev_button.pack(side="left")
        next_button = tk.Button(controls, text="Next", command=_go_next)
        next_button.pack(side="right")

        def _schedule_render(_event: tk.Event | None = None) -> None:
            pending = getattr(gallery, "_gallery_render_job", None)
            if pending is not None:
                gallery.after_cancel(pending)
            gallery._gallery_render_job = gallery.after(120, _render_page)

        gallery.bind("<Configure>", _schedule_render)
        _render_page()


def run_gui() -> None:
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = SalesAnalyticsGUI()
    app.mainloop()
