from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from digital_mosreg.api_client import (
    DigitalMosregApiError,
    build_list_params,
    case_detail_url,
    cases_list_url,
    create_http_client,
    request_get_with_timeout_retry,
)
from digital_mosreg.config import load_digital_mosreg_config
from digital_mosreg.excel_export import rows_to_xlsx_bytes
from digital_mosreg.flatten import COLUMN_ORDER, flatten_case, strip_html


def test_strip_html_br_and_entities() -> None:
    assert strip_html("A<br>B<br/>C") == "A\nB\nC"
    assert strip_html("a&amp;b") == "a&b"
    assert strip_html(None) == ""


def test_flatten_case_sample_card() -> None:
    data = {
        "id": 2304,
        "shortTitle": "ИИ РКЦ ЛО",
        "fullTitle": "Полное",
        "active": True,
        "aiRating": True,
        "digitalPractice": False,
        "transformationalProject": False,
        "promotionSample": False,
        "status": {"title": "Опубликовано"},
        "exploitationStatus": {"title": "Промышленная эксплуатация"},
        "category": {"name": "Государственное и муниципальное управление"},
        "region": {
            "name": "Ленинградская область",
            "district": {"name": "Северо-Западный федеральный округ"},
        },
        "institution": "ГКУ",
        "developer": {"name": "ООО «Уно-софт»"},
        "provider": {"name": "ООО «Уно-софт»"},
        "result": "Было:<br>1. вручную",
        "link": "https://ai.lenreg.ru/",
        "contact": "Иванов",
        "technologyCase": [{"technology": {"name": "Перспективные методы ИИ"}}],
        "circulationCase": [{"circulation": {"title": "Не тиражируемое решение"}}],
        "aiUsageScenario": [
            {"recommendedScenario": {"title": "Подготовка проектов ответов"}},
        ],
        "categoryEffectEstimation": [
            {
                "effectCategory": {"title": "Скорость"},
                "estimation": "в 8 раз",
            }
        ],
        "images": [{}],
        "materials": [],
    }
    row = flatten_case(data, base_url="https://digital.mosreg.ru")
    assert list(row.keys()) == list(COLUMN_ORDER)
    assert row["ID"] == 2304
    assert row["URL"] == "https://digital.mosreg.ru/ai-solutions-region/2304"
    assert row["Краткое название"] == "ИИ РКЦ ЛО"
    assert row["Эффект (метрики)"] == "Было:\n1. вручную"
    assert row["Технологии"] == "Перспективные методы ИИ"
    assert row["Сценарии ИИ"] == "Подготовка проектов ответов"
    assert "Скорость: в 8 раз" in row["Оценка эффектов"]
    assert row["Ссылка на проект"] == "https://ai.lenreg.ru/"
    assert row["Число изображений"] == 1
    assert row["Число материалов"] == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        ("", ""),
        ("plain", "plain"),
    ],
)
def test_strip_html_edge(value: str | None, expected: str) -> None:
    assert strip_html(value) == expected


def test_load_config_defaults(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    config = load_digital_mosreg_config(missing)
    assert config.streamlit_port == 8550
    assert config.page_limit == 9
    assert config.delay_min_sec == 1.5
    assert config.fetch_detail is True
    assert config.timeout_sec == 60
    assert config.timeout_fallback_sec == 120
    assert config.trust_env_proxy is False


def test_load_config_from_file(tmp_path: Path) -> None:
    path = tmp_path / "cfg.json"
    path.write_text(
        json.dumps(
            {
                "api": {"max_items": 3, "page_limit": 5},
                "request": {"delay_min_sec": 2, "delay_max_sec": 1},
                "ui": {"streamlit_port": 8550},
            }
        ),
        encoding="utf-8",
    )
    config = load_digital_mosreg_config(path)
    assert config.max_items == 3
    assert config.page_limit == 5
    assert config.delay_min_sec == 2
    assert config.delay_max_sec == 2  # поднят до min


def test_env_overrides_json_max_items(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "cfg.json"
    path.write_text(
        json.dumps({"api": {"max_items": 1}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("DIGITAL_MOSREG_MAX_ITEMS", "0")
    config = load_digital_mosreg_config(path)
    assert config.max_items == 0


def test_build_list_params_and_urls() -> None:
    config = load_digital_mosreg_config(Path("/nonexistent-digital-mosreg.json"))
    params = build_list_params(config, page=2)
    assert params["page"] == 2
    assert params["limit"] == 9
    assert params["filter[ai]"] == "true"
    assert cases_list_url(config).endswith("/api/cases")
    assert case_detail_url(config, 2304).endswith("/api/cases/2304")


def test_create_http_client_ignores_env_proxy_by_default() -> None:
    config = load_digital_mosreg_config(Path("/nonexistent-digital-mosreg.json"))
    client = create_http_client(config)
    try:
        assert client.trust_env is False
    finally:
        client.close()


def test_request_get_timeout_without_retry() -> None:
    config = replace(
        load_digital_mosreg_config(Path("/nonexistent-digital-mosreg.json")),
        timeout_sec=10,
        timeout_fallback_sec=10,
    )

    class FakeClient:
        def get(self, *_args: object, **_kwargs: object) -> object:
            raise httpx.ReadTimeout("timed out")

    with pytest.raises(DigitalMosregApiError, match="Таймаут соединения"):
        request_get_with_timeout_retry(FakeClient(), config, "https://example.com")  # type: ignore[arg-type]


def test_request_get_timeout_then_retry_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    config = replace(
        load_digital_mosreg_config(Path("/nonexistent-digital-mosreg.json")),
        timeout_sec=5,
        timeout_fallback_sec=30,
    )

    class OkResponse:
        status_code = 200

    calls = {"n": 0}

    class PrimaryClient:
        def get(self, *_args: object, **_kwargs: object) -> object:
            raise httpx.ConnectTimeout("connect timed out")

    class RetryClient:
        def get(self, *_args: object, **_kwargs: object) -> object:
            calls["n"] += 1
            return OkResponse()

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "digital_mosreg.api_client.create_http_client",
        lambda *_a, **_k: RetryClient(),
    )
    response = request_get_with_timeout_retry(PrimaryClient(), config, "https://example.com")  # type: ignore[arg-type]
    assert response.status_code == 200
    assert calls["n"] == 1


def test_request_get_both_timeouts_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    config = replace(
        load_digital_mosreg_config(Path("/nonexistent-digital-mosreg.json")),
        timeout_sec=5,
        timeout_fallback_sec=30,
    )

    class PrimaryClient:
        def get(self, *_args: object, **_kwargs: object) -> object:
            raise httpx.ReadTimeout("timed out")

    class RetryClient:
        def get(self, *_args: object, **_kwargs: object) -> object:
            raise httpx.ReadTimeout("timed out again")

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "digital_mosreg.api_client.create_http_client",
        lambda *_a, **_k: RetryClient(),
    )
    with pytest.raises(DigitalMosregApiError, match="Повтор"):
        request_get_with_timeout_retry(PrimaryClient(), config, "https://example.com")  # type: ignore[arg-type]


def test_rows_to_xlsx_bytes_contains_sheet() -> None:
    rows = [
        flatten_case(
            {"id": 1, "shortTitle": "A", "link": "https://example.com"},
            base_url="https://digital.mosreg.ru",
        )
    ]
    payload = rows_to_xlsx_bytes(rows)
    assert payload[:2] == b"PK"
    assert len(payload) > 100


def test_arrow_safe_dataframe_mixed_int_and_empty() -> None:
    from digital_mosreg.table_view import cell_to_table_value, rows_to_arrow_safe_dataframe

    assert cell_to_table_value(None) == ""
    assert cell_to_table_value(True) == "да"
    assert cell_to_table_value(False) == "нет"
    assert cell_to_table_value(12) == "12"

    rows = [
        {"ID": 1, "Число ОМСУ внедрения": 3, "Активно": True},
        {"ID": 2, "Число ОМСУ внедрения": "", "Активно": False},
    ]
    frame = rows_to_arrow_safe_dataframe(rows)
    assert list(frame.columns) == list(COLUMN_ORDER)
    assert frame["Число ОМСУ внедрения"].tolist()[0] == "3"
    assert frame["Число ОМСУ внедрения"].tolist()[1] == ""
    assert frame["Активно"].tolist() == ["да", "нет"]
    assert all(frame[col].map(lambda v: isinstance(v, str)).all() for col in frame.columns)
