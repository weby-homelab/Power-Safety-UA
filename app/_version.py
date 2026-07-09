import os

__version__ = "v3.9.2"


def get_version() -> str:
    version_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "VERSION")
    if os.path.exists(version_path):
        with open(version_path, "r") as f:
            return f.read().strip()
    return __version__
