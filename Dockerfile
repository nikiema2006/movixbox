# Utiliser une image Python officielle comme base
FROM python:3.11-slim

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Copier le fichier de dépendances et installer les dépendances
# Utiliser un fichier requirements.txt pour la gestion des dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste du code de l'application
COPY . .

# Commande pour lancer l'application avec Gunicorn et Uvicorn
# Gunicorn est un serveur WSGI/ASGI de production
# Uvicorn est le serveur ASGI qui exécute FastAPI
# --bind 0.0.0.0:$PORT est crucial pour Render, qui injecte le port via une variable d'environnement
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 4 --worker-class uvicorn.workers.UvicornWorker main:app
