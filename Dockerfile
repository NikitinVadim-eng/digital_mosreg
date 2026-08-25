# Образ приложения «Цифровой регион» (Streamlit + API-парсер).
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    DIGITAL_MOSREG_STREAMLIT_PORT=8550 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY digital_mosreg /app/digital_mosreg
COPY data/digital_mosreg_config.json /app/data/digital_mosreg_config.json

EXPOSE 8550

CMD ["streamlit", "run", "digital_mosreg/app.py", \
     "--server.port=8550", \
     "--server.address=0.0.0.0", \
     "--browser.gatherUsageStats=false"]
