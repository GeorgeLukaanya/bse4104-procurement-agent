"""Launch the optional Streamlit operator view."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .view import repo_root


def main() -> None:
    try:
        from streamlit.web.cli import main as stcli
    except ImportError:
        sys.stderr.write("error: Streamlit is not installed. Run: pip install -e '.[ui]'\n")
        raise SystemExit(2) from None

    root = repo_root()
    os.chdir(root)
    app = Path(__file__).resolve().parent / "app.py"
    extra = sys.argv[1:]
    sys.argv = [
        "streamlit",
        "run",
        str(app),
        "--browser.gatherUsageStats=false",
        "--theme.base=light",
        "--theme.primaryColor=#0B6B6B",
        "--theme.backgroundColor=#F4F5F7",
        "--theme.secondaryBackgroundColor=#FFFFFF",
        "--theme.textColor=#1B1F24",
        "--client.toolbarMode=viewer",
        *extra,
    ]
    stcli()


if __name__ == "__main__":
    main()
