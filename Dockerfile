FROM python:3.11-slim
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

COPY src/ src/
COPY scripts/ scripts/
COPY infrastructure/cockroachdb/ca/root.crt /root/.postgresql/root.crt

RUN chmod +x scripts/entrypoint.sh

EXPOSE 8000

CMD ["/app/scripts/entrypoint.sh"]
