from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path("data/digital_mosreg_config.json")
DEFAULT_BASE_URL = "https://digital.mosreg.ru"
DEFAULT_CASES_PATH = "/api/cases"
DEFAULT_PAGE_LIMIT = 9
DEFAULT_MAX_PAGES = 0  # 0 = все страницы
DEFAULT_MAX_ITEMS = 0  # 0 = без лимита
DEFAULT_FETCH_DETAIL = True
DEFAULT_FILTER_AI = True
DEFAULT_FILTER_ALL_STATUS = 1
DEFAULT_DELAY_MIN_SEC = 1.5
DEFAULT_DELAY_MAX_SEC = 3.0
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_TIMEOUT_FALLBACK_SEC = 120
DEFAULT_CONNECT_TIMEOUT_SEC = 20
DEFAULT_STOP_ON_429 = True
DEFAULT_TRUST_ENV_PROXY = False  # игнорировать HTTP(S)_PROXY из окружения
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_STREAMLIT_PORT = 8550
DEFAULT_OUTPUT_XLSX = Path("data/digital_mosreg_cases.xlsx")


@dataclass(frozen=True)
class DigitalMosregConfig:
    base_url: str
    cases_path: str
    page_limit: int
    max_pages: int
    max_items: int
    fetch_detail: bool
    filter_ai: bool
    filter_all_status: int
    delay_min_sec: float
    delay_max_sec: float
    timeout_sec: int
    timeout_fallback_sec: int
    connect_timeout_sec: int
    stop_on_429: bool
    trust_env_proxy: bool
    user_agent: str
    streamlit_port: int
    output_xlsx: Path
    config_path: Path


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _float_value(value: Any, default: float) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


def _int_value(value: Any, default: int, *, minimum: int = 0) -> int:
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return default


def _bool_value(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def _env_is_set(name: str) -> bool:
    raw = os.environ.get(name)
    return raw is not None and raw.strip() != ""


def _pref_int(
    file_value: Any,
    env_name: str,
    default: int,
    *,
    minimum: int = 0,
) -> int:
    """Приоритет: переменная окружения → JSON → default (удобно для Docker)."""
    if _env_is_set(env_name):
        return _int_value(os.environ.get(env_name), default, minimum=minimum)
    if file_value is not None:
        return _int_value(file_value, default, minimum=minimum)
    return default


def _pref_float(file_value: Any, env_name: str, default: float) -> float:
    if _env_is_set(env_name):
        return _float_value(os.environ.get(env_name), default)
    if file_value is not None:
        return _float_value(file_value, default)
    return default


def _pref_bool(file_value: Any, env_name: str, default: bool) -> bool:
    if _env_is_set(env_name):
        return _bool_value(os.environ.get(env_name), default)
    if file_value is not None:
        return _bool_value(file_value, default)
    return default


def load_digital_mosreg_config(path: Path | str | None = None) -> DigitalMosregConfig:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    data: dict[str, Any] = {}
    if config_path.is_file():
        with config_path.open(encoding="utf-8") as file:
            data = _as_mapping(json.load(file))

    api = _as_mapping(data.get("api"))
    request = _as_mapping(data.get("request"))
    ui = _as_mapping(data.get("ui"))
    output = _as_mapping(data.get("output"))

    delay_min = _pref_float(
        request.get("delay_min_sec"),
        "DIGITAL_MOSREG_DELAY_MIN_SEC",
        DEFAULT_DELAY_MIN_SEC,
    )
    delay_max = _pref_float(
        request.get("delay_max_sec"),
        "DIGITAL_MOSREG_DELAY_MAX_SEC",
        DEFAULT_DELAY_MAX_SEC,
    )
    if delay_max < delay_min:
        delay_max = delay_min

    output_xlsx = Path(
        str(output.get("xlsx_path") or DEFAULT_OUTPUT_XLSX),
    )

    return DigitalMosregConfig(
        base_url=str(api.get("base_url") or DEFAULT_BASE_URL).rstrip("/"),
        cases_path=str(api.get("cases_path") or DEFAULT_CASES_PATH),
        page_limit=_pref_int(
            api.get("page_limit"),
            "DIGITAL_MOSREG_PAGE_LIMIT",
            DEFAULT_PAGE_LIMIT,
            minimum=1,
        ),
        max_pages=_pref_int(
            api.get("max_pages"),
            "DIGITAL_MOSREG_MAX_PAGES",
            DEFAULT_MAX_PAGES,
        ),
        max_items=_pref_int(
            api.get("max_items"),
            "DIGITAL_MOSREG_MAX_ITEMS",
            DEFAULT_MAX_ITEMS,
        ),
        fetch_detail=_pref_bool(
            api.get("fetch_detail"),
            "DIGITAL_MOSREG_FETCH_DETAIL",
            DEFAULT_FETCH_DETAIL,
        ),
        filter_ai=_bool_value(api.get("filter_ai"), DEFAULT_FILTER_AI),
        filter_all_status=_int_value(
            api.get("filter_all_status"),
            DEFAULT_FILTER_ALL_STATUS,
            minimum=0,
        ),
        delay_min_sec=delay_min,
        delay_max_sec=delay_max,
        timeout_sec=_pref_int(
            request.get("timeout_sec"),
            "DIGITAL_MOSREG_TIMEOUT_SEC",
            DEFAULT_TIMEOUT_SEC,
            minimum=1,
        ),
        timeout_fallback_sec=_pref_int(
            request.get("timeout_fallback_sec"),
            "DIGITAL_MOSREG_TIMEOUT_FALLBACK_SEC",
            DEFAULT_TIMEOUT_FALLBACK_SEC,
            minimum=1,
        ),
        connect_timeout_sec=_pref_int(
            request.get("connect_timeout_sec"),
            "DIGITAL_MOSREG_CONNECT_TIMEOUT_SEC",
            DEFAULT_CONNECT_TIMEOUT_SEC,
            minimum=1,
        ),
        stop_on_429=_pref_bool(
            request.get("stop_on_429"),
            "DIGITAL_MOSREG_STOP_ON_429",
            DEFAULT_STOP_ON_429,
        ),
        trust_env_proxy=_pref_bool(
            request.get("trust_env_proxy"),
            "DIGITAL_MOSREG_TRUST_ENV_PROXY",
            DEFAULT_TRUST_ENV_PROXY,
        ),
        user_agent=str(request.get("user_agent") or DEFAULT_USER_AGENT),
        streamlit_port=_pref_int(
            ui.get("streamlit_port"),
            "DIGITAL_MOSREG_STREAMLIT_PORT",
            DEFAULT_STREAMLIT_PORT,
            minimum=1,
        ),
        output_xlsx=output_xlsx,
        config_path=config_path,
    )
