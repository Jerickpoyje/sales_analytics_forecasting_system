from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


def total_revenue(df: pd.DataFrame) -> float:
    return round(float(df["total_amount"].sum()), 2)


def category_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby("product_category", as_index=False)
        .agg(
            total_quantity=("quantity_sold", "sum"),
            total_revenue=("total_amount", "sum"),
            average_price=("unit_price", "mean"),
            product_count=("product_name", "nunique"),
        )
        .sort_values("total_revenue", ascending=False)
        .reset_index(drop=True)
    )
    summary["total_revenue"] = summary["total_revenue"].round(2)
    summary["average_price"] = summary["average_price"].round(2)
    return summary


def top_selling_items(df: pd.DataFrame, metric: str = "quantity_sold", limit: int = 3) -> pd.DataFrame:
    if metric not in {"quantity_sold", "total_amount", "total_revenue"}:
        raise ValueError("Metric must be 'quantity_sold', 'total_amount', or 'total_revenue'.")

    top_items = (
        df.groupby(["product_name", "product_category"], as_index=False)
        .agg(
            total_quantity=("quantity_sold", "sum"),
            total_amount=("total_amount", "sum"),
            average_price=("unit_price", "mean"),
        )
    )
    sort_column = "total_amount" if metric in {"total_amount", "total_revenue"} else "total_quantity"
    top_items = top_items.sort_values(sort_column, ascending=False).head(limit).reset_index(drop=True)
    top_items["total_revenue"] = top_items["total_amount"].round(2)
    top_items["average_price"] = top_items["average_price"].round(2)
    return top_items


def monthly_revenue(df: pd.DataFrame) -> pd.DataFrame:
    monthly = (
        df.set_index("date_of_transaction")
        .resample("MS")
        .agg(total_revenue=("total_amount", "sum"), total_quantity=("quantity_sold", "sum"))
        .reset_index()
    )
    monthly["total_revenue"] = monthly["total_revenue"].round(2)
    return monthly


def cleaning_summary_text(report: dict[str, int]) -> str:
    summary = (
        f"Rows before cleaning: {report['original_rows']}\n"
        f"Rows after cleaning: {report['cleaned_rows']}\n"
        f"Removed rows: {report['removed_rows']}\n"
        f"Duplicate rows removed: {report['duplicates_removed']}"
    )

    missing_detected = report.get("missing_values_detected")
    missing_removed = report.get("missing_values_removed")
    missing_fixed = report.get("missing_values_fixed")
    if missing_detected is not None:
        summary += f"\nMissing values detected: {missing_detected}"
    if missing_removed is not None:
        summary += f"\nRows removed due to missing critical fields: {missing_removed}"
    if missing_fixed is not None:
        summary += f"\nRows fixed due to missing non-critical fields: {missing_fixed}"

    return summary


def save_visualizations(df: pd.DataFrame, output_dir: str | Path) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    created_files: list[Path] = []

    categories = category_summary(df)
    top_items = top_selling_items(df, metric="total_amount", limit=3)
    monthly = monthly_revenue(df)

    created_files.append(_save_category_bar_chart(categories, output_path / "category_revenue_comparison.png"))
    created_files.append(_save_category_pie_chart(categories, output_path / "category_revenue_share.png"))
    created_files.append(_save_top_products_chart(top_items, output_path / "top_selling_products.png"))
    created_files.append(_save_revenue_trend_chart(monthly, output_path / "revenue_trend.png"))

    return created_files


def _save_category_bar_chart(categories: pd.DataFrame, filename: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(categories["product_category"], categories["total_revenue"], color="#1b5e20")
    ax.set_title("Revenue by Product Category")
    ax.set_xlabel("Product Category")
    ax.set_ylabel("Total Revenue")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(filename, dpi=180)
    plt.close(fig)
    return filename


def _save_category_pie_chart(categories: pd.DataFrame, filename: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(categories["total_revenue"], labels=categories["product_category"], autopct="%1.1f%%", startangle=140)
    ax.set_title("Category Revenue Share")
    fig.tight_layout()
    fig.savefig(filename, dpi=180)
    plt.close(fig)
    return filename


def _save_top_products_chart(top_items: pd.DataFrame, filename: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 6))
    labels = top_items["product_name"].astype(str) + "\n(" + top_items["product_category"].astype(str) + ")"
    ax.barh(labels, top_items["total_revenue"], color="#2e7d32")
    ax.set_title("Top 3 Best-Selling Products by Revenue")
    ax.set_xlabel("Revenue")
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(filename, dpi=180)
    plt.close(fig)
    return filename


def _save_revenue_trend_chart(monthly: pd.DataFrame, filename: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(monthly["date_of_transaction"], monthly["total_revenue"], marker="o", color="#0d47a1")
    ax.set_title("Monthly Revenue Trend")
    ax.set_xlabel("Month")
    ax.set_ylabel("Revenue")
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(filename, dpi=180)
    plt.close(fig)
    return filename
