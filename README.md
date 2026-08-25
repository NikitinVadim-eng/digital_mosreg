# Цифровой регион — парсер ИИ-решений

Веб-приложение (Streamlit) для выгрузки каталога ИИ-решений с портала
[digital.mosreg.ru](https://digital.mosreg.ru/ai-solutions-region) в таблицу и Excel.

Данные загружаются через публичный API (`/api/cases`), без кликов по кнопке «Показать еще».

Репозиторий: https://github.com/NikitinVadim-eng/digital_mosreg

---

## Быстрый старт (Docker) — Windows / macOS / Linux

### Требования

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) (на Windows — с WSL2) **или** Docker Engine + Compose на Linux.
2. Git.
3. Браузер.

**Важно перед загрузкой данных:** выключите **Amnezia / любой VPN** и системный **прокси**.  
Иначе запросы из контейнера к порталу могут зависать по таймауту, хотя сайт в браузере открывается.

### 1. Клонировать репозиторий

```powershell
git clone https://github.com/NikitinVadim-eng/digital_mosreg.git
cd digital_mosreg
```

### 2. Собрать и запустить

```powershell
docker compose up --build
```

После обновления кода из GitHub всегда пересобирайте образ: `docker compose up --build` (не только `up`).

Дождитесь сообщения Streamlit о запуске (порт **8550**).

Остановка: `Ctrl+C`  
В фоне: `docker compose up --build -d`  
Логи: `docker compose logs -f`  
Остановить фон: `docker compose down`

### 3. Открыть интерфейс

В браузере: **http://127.0.0.1:8550**

1. Прочитайте предупреждение про VPN/прокси.
2. Нажмите **«Загрузить данные»** (кнопка блокируется на время загрузки).
3. Дождитесь прогресса — в таблице появятся строки.
4. При необходимости нажмите **«Скачать данные (XLSX)»**.

По умолчанию загружается **одна** карточка (`DIGITAL_MOSREG_MAX_ITEMS=1`) — быстрый тест.

---

## Полный каталог

В файле `docker-compose.yml` измените:

```yaml
DIGITAL_MOSREG_MAX_ITEMS: "1"
```

на:

```yaml
DIGITAL_MOSREG_MAX_ITEMS: "0"
```

(`0` = без лимита.) Перезапустите:

```powershell
docker compose up --build
```

Переменная окружения из compose имеет приоритет над `data/digital_mosreg_config.json`.

Полный обход занимает заметное время: между запросами есть паузы 1.5–3 с.

---

## Проверка сети (если таймаут)

В PowerShell при **выключенном VPN**:

```powershell
curl.exe -I "https://digital.mosreg.ru/api/cases?page=1&limit=1"
```

Ожидается быстрый ответ (HTTP 200 или редирект). Если команда «висит» — сначала сеть/VPN, потом снова Docker.

---

## Частые проблемы

| Симптом | Что сделать |
|---------|-------------|
| Таймаут при загрузке | Выключить VPN/прокси; проверить `curl` выше |
| http://127.0.0.1:8550 не открывается | Дождаться окончания сборки; `docker ps` — контейнер `digital-mosreg` |
| Порт 8550 занят | В compose: `"8551:8550"`, открыть http://127.0.0.1:8551 |
| Нужен весь каталог | `DIGITAL_MOSREG_MAX_ITEMS=0` |

---

## Структура проекта

| Путь | Назначение |
|------|------------|
| `digital_mosreg/` | Код парсера и Streamlit UI |
| `Dockerfile` | Образ приложения |
| `docker-compose.yml` | Запуск одной командой |
| `requirements.txt` | Зависимости образа |
| `data/digital_mosreg_config.json` | Настройки (лимиты, задержки) |
| `tests/` | Pytest |

---

## Конфигурация (кратко)

| Параметр / env | По умолчанию | Описание |
|----------------|--------------|----------|
| `DIGITAL_MOSREG_MAX_ITEMS` | `1` (в compose) | Лимит карточек; `0` = все |
| `DIGITAL_MOSREG_DELAY_MIN_SEC` / `MAX` | `1.5` / `3.0` | Пауза между запросами |
| `DIGITAL_MOSREG_TIMEOUT_SEC` | `60` | Таймаут чтения |
| `DIGITAL_MOSREG_TIMEOUT_FALLBACK_SEC` | `120` | Повтор при timeout |
| `ui.streamlit_port` | `8550` | Порт UI |

Пример JSON: `data/config.example.json`.

---

## Запуск без Docker (по желанию)

Нужны Python **3.14+** и [uv](https://docs.astral.sh/uv/):

```powershell
uv sync
uv run digital-mosreg
```

Открыть http://127.0.0.1:8550

Тесты:

```powershell
uv run pytest -q
```
