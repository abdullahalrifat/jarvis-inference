FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY inference ./inference
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["uvicorn", "inference.main:app", "--host", "0.0.0.0", "--port", "8080"]
