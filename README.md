# Terminal-Based Sales Analytics and Forecasting System

This project is a Python console application for the final project-based examination in numerical and symbolic computation and intelligent systems.

## Features

- Product management: add, update, view, and save products
- Data cleaning: handles missing values, duplicate records, invalid numbers, and date parsing
- Analytics: revenue, category grouping, and top-selling products
- Forecasting: 3-month and 12-month sales forecasts using trend analysis
- Visualization: bar charts, pie charts, line charts, and forecast charts saved with Matplotlib

## Dataset Note

The application now uses a single shared CSV source of truth at `data/retail_synthetic_dataset.csv` for product management, cleaning, analytics, forecasting, and charts.

## How to Run

1. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Run the application:

```bash
python main.py
```

## Default Dataset Path

The app looks for this file by default:

`c:\Users\Win11\Downloads\sales_analytics_forecasting_system\data\retail_synthetic_dataset.csv`

If you load a different source dataset, the app will still save product changes back to the shared file above.
