# Thin wrapper — logic moved to app/reports/daily.py
if __name__ != "__main__":
    from app.reports.daily import *  # noqa: F401, F403
else:
    import runpy

    runpy.run_module("app.reports.daily", run_name="__main__")
