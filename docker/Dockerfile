FROM python:3.11-slim-bookworm@sha256:2333bd330d12de02514770b3585cad313644316047cdee24a7acfdece6de6efb

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONOPTIMIZE=2

WORKDIR /app
COPY pyproject.toml README.md ./
COPY inference ./inference
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"

CMD ["uvicorn", "inference.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log", "--timeout-keep-alive", "30"]
