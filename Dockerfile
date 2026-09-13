FROM python:3.12-slim

WORKDIR /code

# Dependências de sistema para compilar psycopg2 (caso o binary wheel falhe)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render/Railway injetam a variável PORT — usamos ela se existir, senão 8000.
ENV PORT=8000
EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
