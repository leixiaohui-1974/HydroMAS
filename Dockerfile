FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install -e ".[web,alumina]" --no-cache-dir

COPY . .

EXPOSE 8000

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
