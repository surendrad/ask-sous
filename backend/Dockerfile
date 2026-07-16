FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
# Just enough of the package for setuptools to discover it during the
# editable install, so this layer only invalidates when pyproject.toml
# changes — not on every application code edit.
COPY app/__init__.py app/__init__.py
RUN pip install --no-cache-dir -e ".[dev]"
COPY app/ app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
