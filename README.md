# Backend Moviebox Streaming API

Ce backend est une API RESTful construite avec **FastAPI** qui utilise le wrapper Python non officiel `moviebox-api` pour interagir avec les services de streaming de films et de séries. Il est conçu pour être facilement déployable sur **Render.com**.

## Fonctionnalités de l'API

| Endpoint | Méthode | Description | Paramètres de Requête |
| :--- | :--- | :--- | :--- |
| `/` | `GET` | Vérifie le statut de l'API. | Aucun |
| `/homepage` | `GET` | Récupère le contenu de la page d'accueil (Top Picks, etc.). | Aucun |
| `/trending` | `GET` | Récupère les contenus tendances. | `page` (int), `per_page` (int) |
| `/popular-searches` | `GET` | Récupère les recherches populaires. | Aucun |
| `/search` | `GET` | Recherche de films ou séries. | `query` (str), `subject_type` (int: 0=ALL, 1=MOVIE, 2=SERIES), `page` (int), `per_page` (int) |
| `/details/{subject_id}` | `GET` | Récupère les détails d'un contenu. | `type` (int: 1=MOVIE, 2=SERIES) |
| `/stream/{subject_id}` | `GET` | Récupère les liens de streaming. | `type` (int: 1=MOVIE, 2=SERIES), `season` (int), `episode` (int) |

La documentation interactive de l'API (Swagger UI) sera disponible à l'adresse `/docs` après le déploiement.

## Déploiement sur Render

Le déploiement est facilité par le fichier `render.yaml` (Render Blueprint).

### Prérequis

1.  Un compte **Render.com**.
2.  Un dépôt **Git** (GitHub, GitLab, Bitbucket) contenant les fichiers de ce projet (`main.py`, `requirements.txt`, `render.yaml`).

### Étapes de Déploiement

1.  **Créez un nouveau service Blueprint** sur Render.
2.  **Connectez votre dépôt Git** où se trouve ce projet.
3.  Render détectera automatiquement le fichier `render.yaml` et proposera de créer le service.
4.  **Confirmez les paramètres** :
    *   **Nom du service** : `moviebox-backend` (ou autre)
    *   **Type d'environnement** : Python
    *   **Commande de construction (`Build Command`)** : `pip install -r requirements.txt`
    *   **Commande de démarrage (`Start Command`)** : `uvicorn main:app --host 0.0.0.0 --port $PORT`
    *   **Variable d'environnement** : `MOVIEBOX_API_HOST` avec la valeur `h5.aoneroom.com` (ou un autre hôte fonctionnel de la liste `MIRROR_HOSTS` si celui-ci ne fonctionne plus).

### Note Importante sur le Streaming (Erreur 403)

L'API `moviebox-api` est un wrapper non officiel qui interagit avec un service tiers. L'accès aux liens de streaming est souvent soumis à des restrictions de sécurité (cookies, en-têtes `Referer`, ou blocage d'IP).

> **Problème connu** : Lors de l'accès à l'endpoint `/stream`, une erreur `403 Forbidden` peut survenir.

Le code a été conçu pour capturer cette erreur et vous en informer. Si cela se produit, vous devrez :
1.  **Changer la valeur de la variable d'environnement `MOVIEBOX_API_HOST`** sur Render pour essayer un autre miroir (par exemple, `moviebox.ph`).
2.  Si le problème persiste, cela indique que le service a renforcé ses mesures de sécurité, et une mise à jour du wrapper `moviebox-api` pourrait être nécessaire.

## Dépendances

Le fichier `requirements.txt` contient les dépendances nécessaires :

- `fastapi`
- `uvicorn`
- `httpx`
- `pydantic`
- `beautifulsoup4`
- `throttlebuster`
- `moviebox-api` (le wrapper analysé)

---
*Document préparé par **Manus AI***
