from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from digital_mosreg.config import DigitalMosregConfig
from digital_mosreg.flatten import flatten_case


ProgressCallback = Callable[[dict[str, Any]], None]


class DigitalMosregApiError(RuntimeError):
    """Ошибка HTTP/API портала «Цифровой регион»."""


@dataclass(frozen=True)
class CollectResult:
    rows: list[dict[str, Any]]
    total_reported: int | None
    pages_fetched: int
    items_fetched: int
    stopped_reason: str | None


def _sleep_delay(config: DigitalMosregConfig) -> None:
    low = config.delay_min_sec
    high = config.delay_max_sec
    if high <= 0 and low <= 0:
        return
    if high < low:
        high = low
    time.sleep(random.uniform(low, high))


def build_list_params(config: DigitalMosregConfig, *, page: int) -> dict[str, Any]:
    params: dict[str, Any] = {
        "page": page,
        "limit": config.page_limit,
        "filter[title]": "",
    }
    if config.filter_ai:
        params["filter[ai]"] = "true"
    if config.filter_all_status is not None:
        params["filter[allStatus]"] = config.filter_all_status
    return params


def cases_list_url(config: DigitalMosregConfig) -> str:
    return f"{config.base_url}{config.cases_path}"


def case_detail_url(config: DigitalMosregConfig, case_id: int | str) -> str:
    return f"{config.base_url}{config.cases_path}/{case_id}"


def build_httpx_timeout(config: DigitalMosregConfig, *, read_sec: int | None = None) -> httpx.Timeout:
    read = float(config.timeout_sec if read_sec is None else read_sec)
    connect = float(config.connect_timeout_sec)
    return httpx.Timeout(connect=connect, read=read, write=read, pool=connect)


def create_http_client(
    config: DigitalMosregConfig,
    *,
    read_sec: int | None = None,
) -> httpx.Client:
    return httpx.Client(
        timeout=build_httpx_timeout(config, read_sec=read_sec),
        headers={"User-Agent": config.user_agent, "Accept": "application/json"},
        follow_redirects=True,
        # По умолчанию не берём HTTP(S)_PROXY / ALL_PROXY из окружения.
        trust_env=config.trust_env_proxy,
    )


def _raise_for_status(response: httpx.Response, *, stop_on_429: bool) -> None:
    if response.status_code == 429 and stop_on_429:
        raise DigitalMosregApiError("HTTP 429 Too Many Requests — остановка по политике stop_on_429")
    if response.status_code in {403, 401}:
        raise DigitalMosregApiError(f"HTTP {response.status_code}: доступ запрещён / блокировка")
    if response.status_code >= 400:
        body = response.text[:200]
        raise DigitalMosregApiError(f"HTTP {response.status_code}: {body}")


def _timeout_error_message(config: DigitalMosregConfig, *, retried: bool) -> str:
    fallback_note = (
        f" Повтор с {config.timeout_fallback_sec}с тоже не успел."
        if retried
        else f" Лимит ожидания: {config.timeout_sec}с."
    )
    return (
        "Таймаут соединения с digital.mosreg.ru."
        f"{fallback_note} "
        "Проверьте: VPN и прокси выключены; нет HTTP_PROXY/HTTPS_PROXY в окружении; "
        "сайт доступен из браузера на этой же машине."
    )


def request_get_with_timeout_retry(
    client: httpx.Client,
    config: DigitalMosregConfig,
    url: str,
    *,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    """GET с одним fallback-retry при TimeoutException (если fallback > primary)."""
    try:
        return client.get(url, params=params)
    except httpx.TimeoutException as first_exc:
        fallback = config.timeout_fallback_sec
        primary = config.timeout_sec
        if fallback <= primary:
            raise DigitalMosregApiError(_timeout_error_message(config, retried=False)) from first_exc

        retry_client = create_http_client(config, read_sec=fallback)
        try:
            return retry_client.get(url, params=params)
        except httpx.TimeoutException as second_exc:
            raise DigitalMosregApiError(_timeout_error_message(config, retried=True)) from second_exc
        finally:
            retry_client.close()
    except httpx.RequestError as exc:
        raise DigitalMosregApiError(
            f"Сеть: {exc}. Проверьте VPN/прокси и доступность {config.base_url}."
        ) from exc


def fetch_cases_page(
    client: httpx.Client,
    config: DigitalMosregConfig,
    *,
    page: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    response = request_get_with_timeout_retry(
        client,
        config,
        cases_list_url(config),
        params=build_list_params(config, page=page),
    )
    _raise_for_status(response, stop_on_429=config.stop_on_429)
    payload = response.json()
    if not isinstance(payload, dict):
        raise DigitalMosregApiError("Список кейсов: неожиданный JSON")
    data = payload.get("data")
    if not isinstance(data, list):
        raise DigitalMosregApiError("Список кейсов: нет массива data")
    items = [item for item in data if isinstance(item, dict)]
    pagination = payload.get("pagination") if isinstance(payload.get("pagination"), dict) else {}
    return items, pagination


def fetch_case_detail(
    client: httpx.Client,
    config: DigitalMosregConfig,
    case_id: int | str,
) -> dict[str, Any]:
    response = request_get_with_timeout_retry(
        client,
        config,
        case_detail_url(config, case_id),
    )
    _raise_for_status(response, stop_on_429=config.stop_on_429)
    payload = response.json()
    if not isinstance(payload, dict):
        raise DigitalMosregApiError(f"Карточка {case_id}: неожиданный JSON")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise DigitalMosregApiError(f"Карточка {case_id}: нет объекта data")
    return data


def collect_cases(
    config: DigitalMosregConfig,
    *,
    progress: ProgressCallback | None = None,
    client: httpx.Client | None = None,
) -> CollectResult:
    """Собирает кейсы с пагинацией и опциональной детализацией."""
    own_client = client is None
    http_client = client or create_http_client(config)

    rows: list[dict[str, Any]] = []
    pages_fetched = 0
    total_reported: int | None = None
    stopped_reason: str | None = None

    def emit(**kwargs: Any) -> None:
        if progress is not None:
            progress(kwargs)

    try:
        page = 1
        count_pages: int | None = None

        while True:
            if config.max_pages > 0 and page > config.max_pages:
                stopped_reason = f"достигнут max_pages={config.max_pages}"
                break
            if count_pages is not None and page > count_pages:
                break

            emit(
                phase="list",
                page=page,
                pages_total=count_pages,
                items_done=len(rows),
                items_total=total_reported,
                message=f"Загрузка списка, страница {page}",
            )
            items, pagination = fetch_cases_page(http_client, config, page=page)
            pages_fetched += 1

            if total_reported is None:
                raw_count = pagination.get("count")
                if isinstance(raw_count, int):
                    total_reported = raw_count
            raw_pages = pagination.get("countPages")
            if isinstance(raw_pages, int):
                count_pages = raw_pages

            if not items:
                stopped_reason = "пустая страница списка"
                break

            for item in items:
                if config.max_items > 0 and len(rows) >= config.max_items:
                    stopped_reason = f"достигнут max_items={config.max_items}"
                    break

                case_id = item.get("id")
                if case_id is None:
                    continue

                _sleep_delay(config)

                if config.fetch_detail:
                    emit(
                        phase="detail",
                        page=page,
                        pages_total=count_pages,
                        items_done=len(rows),
                        items_total=total_reported,
                        case_id=case_id,
                        message=f"Карточка {case_id}",
                    )
                    detail = fetch_case_detail(http_client, config, case_id)
                else:
                    detail = item

                rows.append(flatten_case(detail, base_url=config.base_url))
                emit(
                    phase="row",
                    page=page,
                    pages_total=count_pages,
                    items_done=len(rows),
                    items_total=total_reported,
                    case_id=case_id,
                    message=f"Готово: {len(rows)}"
                    + (f" / {total_reported}" if total_reported else ""),
                )

            if stopped_reason:
                break
            if count_pages is not None and page >= count_pages:
                break
            if config.max_pages > 0 and page >= config.max_pages:
                stopped_reason = f"достигнут max_pages={config.max_pages}"
                break

            page += 1
            _sleep_delay(config)

        emit(
            phase="done",
            page=page,
            pages_total=count_pages,
            items_done=len(rows),
            items_total=total_reported,
            message=stopped_reason or "загрузка завершена",
        )
    finally:
        if own_client:
            http_client.close()

    return CollectResult(
        rows=rows,
        total_reported=total_reported,
        pages_fetched=pages_fetched,
        items_fetched=len(rows),
        stopped_reason=stopped_reason,
    )
