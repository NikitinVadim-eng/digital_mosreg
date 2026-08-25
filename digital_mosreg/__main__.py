from __future__ import annotations

import sys
from pathlib import Path

from digital_mosreg.config import DEFAULT_CONFIG_PATH, load_digital_mosreg_config


def main() -> None:
    """Точка входа: Streamlit на 127.0.0.1 и порту из конфига (по умолчанию 8550)."""
    from streamlit.web import cli as stcli

    config = load_digital_mosreg_config(DEFAULT_CONFIG_PATH)
    app_path = str(Path(__file__).resolve().parent / "app.py")
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.port",
        str(config.streamlit_port),
        "--server.address",
        "127.0.0.1",
        "--browser.gatherUsageStats",
        "false",
    ]
    raise SystemExit(stcli.main())


if __name__ == "__main__":
    main()
