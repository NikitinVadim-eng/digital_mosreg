from __future__ import annotations

from typing import Any

import pandas as pd

from digital_mosreg.flatten import COLUMN_ORDER


def cell_to_table_value(value: Any) -> str:
    """Единый тип ячейки для Streamlit/Arrow (иначе смесь int и '' ломает таблицу)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "да" if value else "нет"
    return str(value)


def rows_to_arrow_safe_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    records = [
        {name: cell_to_table_value(row.get(name)) for name in COLUMN_ORDER} for row in rows
    ]
    return pd.DataFrame(records, columns=list(COLUMN_ORDER))
