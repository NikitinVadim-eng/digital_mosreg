from __future__ import annotations

import html
import re
from typing import Any

_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")

# Порядок колонок для Excel / таблицы GUI (все согласованные поля).
COLUMN_ORDER: tuple[str, ...] = (
    "ID",
    "URL",
    "Краткое название",
    "Полное название",
    "Единое название",
    "Статус публикации",
    "Статус эксплуатации",
    "Активно",
    "ИИ-рейтинг",
    "Цифровая практика",
    "Трансформационный проект",
    "Образец продвижения",
    "Категория",
    "Категория презентации",
    "Отрасль",
    "Тип кейса",
    "Уровень внедрения",
    "Регион",
    "Федеральный округ",
    "ОГВ",
    "ОМСУ",
    "Учреждение (заказчик)",
    "Сектор",
    "Структура",
    "Разработчик",
    "Провайдер",
    "Проблема",
    "Решение",
    "Цели создания",
    "Описание",
    "Описание презентации",
    "Эффект (метрики)",
    "Оценка эффектов",
    "Целевая аудитория",
    "Цена",
    "Срок внедрения",
    "Срок (месяцы)",
    "Число ОМСУ внедрения",
    "Требования",
    "Стоимость создания",
    "Стоимость эксплуатации",
    "Стоимость инфраструктуры",
    "Стоимость лицензий",
    "Сценарии ИИ (кастом)",
    "Сценарии ИИ",
    "Технологии",
    "Тиражирование",
    "Информационная безопасность",
    "Ссылка на проект",
    "Внешние ссылки",
    "Доступ",
    "Оценка кейса",
    "Контакт",
    "Связь / communication",
    "SEO",
    "Родитель",
    "Дата создания",
    "Дата обновления",
    "Дата регистрации",
    "Дата эксплуатации",
    "Дата вывода из эксплуатации",
    "Дата реализации",
    "Число изображений",
    "Число материалов",
)


def strip_html(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = _BR_RE.sub("\n", text)
    text = _TAG_RE.sub("", text)
    return html.unescape(text).strip()


def _join(parts: list[str], sep: str = "; ") -> str:
    return sep.join(p for p in parts if p)


def _title_of(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str | int | float | bool):
        return str(value)
    if isinstance(value, dict):
        for key in ("title", "name", "shortTitle", "fullTitle", "value"):
            if value.get(key) not in (None, ""):
                return str(value[key])
        return ""
    return str(value)


def _list_titles(value: Any, *, nested_keys: tuple[str, ...] = ()) -> str:
    if not isinstance(value, list):
        return _title_of(value)
    parts: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            title = _title_of(item)
            if title:
                parts.append(title)
            continue
        found = ""
        for key in nested_keys:
            nested = item.get(key)
            found = _title_of(nested)
            if found:
                break
        if not found:
            found = _title_of(item)
        if found:
            parts.append(found)
    return _join(parts)


def _effect_estimations(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    blocks: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        category = _title_of(item.get("effectCategory"))
        estimation = strip_html(item.get("estimation"))
        if category and estimation:
            blocks.append(f"{category}: {estimation}")
        elif estimation:
            blocks.append(estimation)
        elif category:
            blocks.append(category)
    return _join(blocks, sep="\n\n")


def _ai_scenarios(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        scenario = item.get("recommendedScenario")
        title = _title_of(scenario)
        if title:
            parts.append(title)
    return _join(parts)


def case_url(base_url: str, case_id: Any) -> str:
    return f"{base_url.rstrip('/')}/ai-solutions-region/{case_id}"


def flatten_case(data: dict[str, Any], *, base_url: str) -> dict[str, Any]:
    """Преобразует объект data из /api/cases/{id} в плоскую строку Excel/таблицы."""
    region = data.get("region") if isinstance(data.get("region"), dict) else {}
    district = region.get("district") if isinstance(region.get("district"), dict) else {}

    row = {
        "ID": data.get("id"),
        "URL": case_url(base_url, data.get("id")),
        "Краткое название": data.get("shortTitle") or "",
        "Полное название": data.get("fullTitle") or "",
        "Единое название": data.get("unifiedName") or "",
        "Статус публикации": _title_of(data.get("status")),
        "Статус эксплуатации": _title_of(data.get("exploitationStatus")),
        "Активно": data.get("active"),
        "ИИ-рейтинг": data.get("aiRating"),
        "Цифровая практика": data.get("digitalPractice"),
        "Трансформационный проект": data.get("transformationalProject"),
        "Образец продвижения": data.get("promotionSample"),
        "Категория": _title_of(data.get("category")),
        "Категория презентации": _title_of(data.get("presentationCategory")),
        "Отрасль": _title_of(data.get("industry")),
        "Тип кейса": _title_of(data.get("caseType")),
        "Уровень внедрения": strip_html(data.get("implementationLevel")),
        "Регион": _title_of(region) if region else _title_of(data.get("region")),
        "Федеральный округ": _title_of(district),
        "ОГВ": _title_of(data.get("ogv")),
        "ОМСУ": _title_of(data.get("omsu")),
        "Учреждение (заказчик)": strip_html(data.get("institution")),
        "Сектор": _title_of(data.get("sector")),
        "Структура": strip_html(data.get("structure")),
        "Разработчик": _title_of(data.get("developer")),
        "Провайдер": _title_of(data.get("provider")),
        "Проблема": strip_html(data.get("problem")),
        "Решение": strip_html(data.get("decision")),
        "Цели создания": strip_html(data.get("purpose")),
        "Описание": strip_html(data.get("description")),
        "Описание презентации": strip_html(data.get("presentationDescription")),
        "Эффект (метрики)": strip_html(data.get("result")),
        "Оценка эффектов": _effect_estimations(data.get("categoryEffectEstimation")),
        "Целевая аудитория": strip_html(data.get("contingent")),
        "Цена": data.get("price") if data.get("price") is not None else "",
        "Срок внедрения": data.get("timeframe") or "",
        "Срок (месяцы)": (
            data.get("timeframeMonth") if data.get("timeframeMonth") is not None else ""
        ),
        "Число ОМСУ внедрения": (
            data.get("implementationOmsuCount")
            if data.get("implementationOmsuCount") is not None
            else ""
        ),
        "Требования": strip_html(data.get("requirement")),
        "Стоимость создания": data.get("costCreation") or "",
        "Стоимость эксплуатации": data.get("costExploitation") or "",
        "Стоимость инфраструктуры": data.get("costInfrastructure") or "",
        "Стоимость лицензий": data.get("costLicense") or "",
        "Сценарии ИИ (кастом)": _list_titles(data.get("aiCustomUsageScenario")),
        "Сценарии ИИ": _ai_scenarios(data.get("aiUsageScenario")),
        "Технологии": _list_titles(data.get("technologyCase"), nested_keys=("technology",)),
        "Тиражирование": _list_titles(
            data.get("circulationCase"),
            nested_keys=("circulation",),
        ),
        "Информационная безопасность": _list_titles(
            data.get("informationSecurityCase"),
            nested_keys=("informationSecurity",),
        ),
        "Ссылка на проект": data.get("link") or "",
        "Внешние ссылки": _list_titles(data.get("externalLink")),
        "Доступ": _list_titles(data.get("access")),
        "Оценка кейса": _list_titles(data.get("caseScore")),
        "Контакт": strip_html(data.get("contact")),
        "Связь / communication": _title_of(data.get("communication")),
        "SEO": _title_of(data.get("seo")),
        "Родитель": _title_of(data.get("parent")),
        "Дата создания": data.get("dateCreate") or "",
        "Дата обновления": data.get("dateUpdate") or "",
        "Дата регистрации": data.get("dateRegistration") or "",
        "Дата эксплуатации": data.get("dateExploitation") or "",
        "Дата вывода из эксплуатации": data.get("dateOutExploitation") or "",
        "Дата реализации": data.get("dateRealization") or "",
        "Число изображений": (
            len(data["images"]) if isinstance(data.get("images"), list) else ""
        ),
        "Число материалов": (
            len(data["materials"]) if isinstance(data.get("materials"), list) else ""
        ),
    }
    # Гарантируем полный набор колонок в фиксированном порядке.
    return {name: row.get(name, "") for name in COLUMN_ORDER}


def rows_to_column_order(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{name: row.get(name, "") for name in COLUMN_ORDER} for row in rows]
