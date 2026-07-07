# Thin wrapper — logic moved to app/reports/text.py
if __name__ != "__main__":
    from app.reports.text import *  # noqa: F401, F403
else:
    import runpy

    runpy.run_module("app.reports.text", run_name="__main__")
