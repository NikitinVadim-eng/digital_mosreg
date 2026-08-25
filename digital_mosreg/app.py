from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import streamlit as st

from digital_mosreg.api_client import DigitalMosregApiError, collect_cases
from digital_mosreg.config import DEFAULT_CONFIG_PATH, load_digital_mosreg_config
from digital_mosreg.excel_export import rows_to_xlsx_bytes
from digital_mosreg.table_view import rows_to_arrow_safe_dataframe

VPN_WARNING = (
    "Перед запуском загрузки отключитесь от любых прокси и выключите VPN. "
    "Иначе портал может блокировать или искажать ответы."
)

LINK_COLUMNS = ("URL", "Ссылка на проект")
DEFAULT_UI_MAX_ITEMS = 1


def _progress_fraction(event: dict[str, Any]) -> float:
    done = event.get("items_done")
    total = event.get("items_total")
    if isinstance(done, int) and isinstance(total, int) and total > 0:
        return min(1.0, max(0.0, done / total))
    pages_total = event.get("pages_total")
    page = event.get("page")
    if isinstance(page, int) and isinstance(pages_total, int) and pages_total > 0:
        return min(1.0, max(0.0, (page - 1) / pages_total))
    return 0.0


def _column_config() -> dict[str, Any]:
    return {
        name: st.column_config.LinkColumn(name, display_text="Открыть") for name in LINK_COLUMNS
    }


def _init_session_state() -> None:
    if "rows" not in st.session_state:
        st.session_state.rows = []
    if "last_message" not in st.session_state:
        st.session_state.last_message = ""
    if "is_loading" not in st.session_state:
        st.session_state.is_loading = False
    if "load_requested" not in st.session_state:
        st.session_state.load_requested = False
    if "max_items_run" not in st.session_state:
        st.session_state.max_items_run = DEFAULT_UI_MAX_ITEMS


def render_app(*, config_path: Path | None = None) -> None:
    st.set_page_config(
        page_title="Цифровой регион — ИИ-решения",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.title("Цифровой регион: каталог ИИ-решений")
    st.warning(VPN_WARNING)

    config = load_digital_mosreg_config(config_path or DEFAULT_CONFIG_PATH)
    _init_session_state()

    max_items = st.number_input(
        "Количество карточек",
        min_value=0,
        max_value=10_000,
        value=DEFAULT_UI_MAX_ITEMS,
        step=1,
        disabled=st.session_state.is_loading,
        help=(
            "Сколько карточек загрузить за один запуск. "
            "По умолчанию 1 (тест). "
            "0 — весь каталог (долго: сотни запросов с паузами)."
        ),
    )

    st.caption(
        f"API: `{config.base_url}{config.cases_path}` · "
        f"задержка {config.delay_min_sec}–{config.delay_max_sec} с · "
        f"таймаут {config.timeout_sec}/{config.timeout_fallback_sec} с · "
        f"лимит карточек в форме: {max_items or 'все'} · "
        f"порт UI {config.streamlit_port}"
    )

    load_clicked = st.button(
        "Загрузить данные",
        type="primary",
        disabled=st.session_state.is_loading,
        help="Кнопка недоступна, пока идёт загрузка",
    )
    if load_clicked and not st.session_state.is_loading:
        st.session_state.max_items_run = int(max_items)
        st.session_state.load_requested = True
        st.session_state.is_loading = True
        st.rerun()

    if st.session_state.load_requested and st.session_state.is_loading:
        progress_bar = st.progress(0.0, text="Подготовка…")
        status = st.empty()
        run_config = replace(config, max_items=int(st.session_state.max_items_run))

        def on_progress(event: dict[str, Any]) -> None:
            message = str(event.get("message") or "")
            status.info(message)
            progress_bar.progress(_progress_fraction(event), text=message)

        try:
            result = collect_cases(run_config, progress=on_progress)
            st.session_state.rows = result.rows
            parts = [
                f"Загружено строк: {result.items_fetched}",
                f"страниц списка: {result.pages_fetched}",
                f"лимит: {run_config.max_items or 'все'}",
            ]
            if result.total_reported is not None:
                parts.append(f"всего по API: {result.total_reported}")
            if result.stopped_reason:
                parts.append(f"остановка: {result.stopped_reason}")
            st.session_state.last_message = "; ".join(parts)
            progress_bar.progress(1.0, text="Готово")
            status.success(st.session_state.last_message)
        except DigitalMosregApiError as exc:
            st.session_state.last_message = str(exc)
            status.error(f"Ошибка API: {exc}")
        except Exception as exc:  # noqa: BLE001 — показать пользователю в GUI
            st.session_state.last_message = str(exc)
            status.error(f"Ошибка загрузки: {exc}")
        finally:
            st.session_state.load_requested = False
            st.session_state.is_loading = False
            st.rerun()

    if st.session_state.last_message and not st.session_state.is_loading:
        st.info(st.session_state.last_message)

    rows: list[dict[str, Any]] = st.session_state.rows
    st.subheader(f"Данные ({len(rows)})")

    if not rows:
        st.write("Нажмите «Загрузить данные», чтобы получить каталог.")
        return

    frame = rows_to_arrow_safe_dataframe(rows)
    st.dataframe(
        frame,
        width="stretch",
        height=560,
        hide_index=True,
        column_config=_column_config(),
    )

    st.download_button(
        label="Скачать данные (XLSX)",
        data=rows_to_xlsx_bytes(rows),
        file_name="digital_mosreg_cases.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        disabled=st.session_state.is_loading,
    )


render_app()
