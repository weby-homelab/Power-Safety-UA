# Thin wrapper — logic moved to app/reports/weekly.py
if __name__ != "__main__":
    from app.reports.weekly import *  # noqa: F401, F403
else:
    import runpy

    runpy.run_module("app.reports.weekly", run_name="__main__")
