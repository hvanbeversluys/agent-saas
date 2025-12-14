FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Installation des dépendances avec uv (ultra rapide)
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copie du code source
COPY . .

# Commande de démarrage
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
