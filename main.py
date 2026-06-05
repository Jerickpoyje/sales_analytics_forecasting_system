from sales_system.app import SalesAnalyticsApp
from sales_system import gui


def main() -> None:
    # Offer GUI first; fall back to console if user prefers
    try:
        choice = input("Launch GUI? (Y/n): ").strip().lower()
    except Exception:
        choice = "y"

    if choice in ("", "y", "yes"):
        gui.run_gui()
    else:
        app = SalesAnalyticsApp()
        app.run()


if __name__ == "__main__":
    main()
