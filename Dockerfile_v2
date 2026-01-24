# Utiliser une image Python officielle
FROM python:3.11-slim

# Installer les dépendances système nécessaires pour certaines libs Python (comme bs4 ou httpx)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier les fichiers de dépendances
COPY requirements.txt .

# Installer les dépendances avec une mise à jour de pip
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le code source
COPY . .

# S'assurer que le répertoire courant est dans le PYTHONPATH
ENV PYTHONPATH=/app

# Commande de lancement avec logs détaillés
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --worker-class uvicorn.workers.UvicornWorker --log-level debug main:app
