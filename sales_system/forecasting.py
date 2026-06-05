from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sympy as sp

from .analytics import monthly_revenue


def forecast_sales(df: pd.DataFrame, periods: int = 3) -> pd.DataFrame:
    monthly = monthly_revenue(df)
    if len(monthly) < 2:
        raise ValueError("At least two months of sales data are required for forecasting.")

    y = monthly["total_revenue"].astype(float).to_numpy()
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, deg=1)

    future_x = np.arange(len(y), len(y) + periods, dtype=float)
    forecast_values = np.maximum(slope * future_x + intercept, 0)

    last_month = pd.Timestamp(monthly["date_of_transaction"].iloc[-1])
    forecast_dates = [last_month + pd.offsets.MonthBegin(index + 1) for index in range(periods)]

    return pd.DataFrame(
        {
            "month": forecast_dates,
            "predicted_revenue": np.round(forecast_values, 2),
            "trend_equation": [linear_equation_string(slope, intercept)] * periods,
        }
    )


def forecast_summary(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "3_month": forecast_sales(df, periods=3),
        "12_month": forecast_sales(df, periods=12),
    }


def linear_equation_string(slope: float, intercept: float) -> str:
    x = sp.Symbol("x")
    equation = sp.Eq(sp.Symbol("y"), sp.Float(slope, 6) * x + sp.Float(intercept, 6))
    return str(equation)


def save_forecast_chart(df: pd.DataFrame, forecast_df: pd.DataFrame, filename: str | Path) -> Path:
    monthly = monthly_revenue(df)
    output_path = Path(filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(monthly["date_of_transaction"], monthly["total_revenue"], marker="o", color="#1b5e20", label="Historical Revenue")
    ax.plot(forecast_df["month"], forecast_df["predicted_revenue"], marker="o", linestyle="--", color="#c62828", label="Forecast")
    ax.set_title("Revenue Forecast")
    ax.set_xlabel("Month")
    ax.set_ylabel("Revenue")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path
