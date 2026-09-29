FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SAMPLE_DATA_DIR=/app/sample_data

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts
RUN pip install ".[postgres,aws]"

COPY sample_data ./sample_data

# Usuário sem privilégios de root
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
