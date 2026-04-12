FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Install uv
RUN pip install uv

WORKDIR /app

# Copy dependency manifest and install dependencies
COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project

# Install Chromium for Playwright (browser binaries)
RUN uv run playwright install chromium

# Copy application source
COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "server.api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
