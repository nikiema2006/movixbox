import os
import uuid
import random
import asyncio
import logging
from datetime import date
from typing import Optional, List, Any
from fastapi import FastAPI, HTTPException, Query
from pydantic import HttpUrl

# Importations Moviebox
import moviebox_api.constants
from moviebox_api.requests import Session
from moviebox_api.core import Homepage, Search, Trending, MovieDetails, TVSeriesDetails, PopularSearch
from moviebox_api.stream import StreamFilesDetail
from moviebox_api.constants import SubjectType
from moviebox_api.models import SearchResultsItem, StreamFilesMetadata, ContentImageModel, OPS

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("moviebox-backend")

# --- CONFIGURATION DES MIROIRS ---
MIRRORS = [
    "v.moviebox.ph",
    "netnaija.video",
    "moviebox.id",
    "moviebox.ph",
    "movieboxapp.in",
    "moviebox.pk",
    "h5.aoneroom.com"
]

# --- CORRECTIFS ET PATCHES ---

# 1. Patch pour StreamFilesDetail (méthode abstraite manquante)
# Nous définissons une fonction qui sera injectée dans la classe
async def patched_get_content_model(self, season: int, episode: int) -> StreamFilesMetadata:
    contents = await self.get_content(season, episode)
    return StreamFilesMetadata(**contents)

# Injection du patch
StreamFilesDetail.get_content_model = patched_get_content_model

# 2. Gestion de la rotation des hôtes
class MirrorManager:
    def __init__(self, mirrors: List[str]):
        self.mirrors = mirrors
        self.current_mirror = mirrors[0]

    def rotate(self):
        self.current_mirror = random.choice(self.mirrors)
        self.apply_config(self.current_mirror)
        return self.current_mirror

    def apply_config(self, host: str):
        """Force la mise à jour des constantes du wrapper"""
        moviebox_api.constants.SELECTED_HOST = host
        moviebox_api.constants.HOST_URL = f"https://{host}/"
        # Mettre à jour les en-têtes par défaut qui dépendent de l'hôte
        moviebox_api.constants.DEFAULT_REQUEST_HEADERS["Host"] = host
        moviebox_api.constants.DEFAULT_REQUEST_HEADERS["Referer"] = moviebox_api.constants.HOST_URL
        logger.info(f"Switched to mirror: {host}")

mirror_manager = MirrorManager(MIRRORS)

# --- APPLICATION FASTAPI ---

app = FastAPI(title="Moviebox Streaming API", description="Backend avec rotation forcée et correctifs")

async def execute_with_retry(func, *args, **kwargs):
    """Exécute une fonction avec rotation automatique en cas d'échec"""
    last_error = None
    # On tente sur tous les miroirs disponibles
    available_mirrors = list(MIRRORS)
    random.shuffle(available_mirrors)
    
    for host in available_mirrors:
        mirror_manager.apply_config(host)
        try:
            # On recrée la session à chaque fois pour s'assurer que les nouveaux cookies/headers sont utilisés
            session = Session()
            # On injecte la session dans les arguments si nécessaire
            if 'session' in kwargs:
                kwargs['session'] = session
            
            return await func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Failed on {host}: {str(e)}")
            last_error = e
            continue
            
    raise HTTPException(status_code=500, detail=f"All mirrors failed. Last error: {str(last_error)}")

# --- WRAPPERS POUR LES APPELS API ---

async def fetch_homepage():
    session = Session()
    hp = Homepage(session)
    return await hp.get_content_model()

async def fetch_trending(page, per_page):
    session = Session()
    trending = Trending(session, page=page, per_page=per_page)
    return await trending.get_content_model()

async def fetch_search(query, subject_type, page):
    session = Session()
    s_type = SubjectType(subject_type)
    search_obj = Search(session, query, subject_type=s_type, page=page)
    return await search_obj.get_content_model()

async def fetch_details(subject_id, type_int):
    session = Session()
    # Format d'URL qui passe la validation regex du wrapper
    valid_path = f"/detail/item?id={subject_id}"
    if type_int == 1:
        details_provider = MovieDetails(valid_path, session)
    else:
        details_provider = TVSeriesDetails(valid_path, session)
    return await details_provider.get_content_model()

async def fetch_stream(subject_id, type_int, season, episode):
    session = Session()
    mock_image = ContentImageModel(
        url="https://example.com/image.jpg", width=100, height=100, size=100, format="jpg",
        thumbnail="https://example.com/thumb.jpg", blurHash="", avgHueLight="", avgHueDark="", id="1"
    )
    # Données brutes pour éviter les erreurs de validation Pydantic/split
    mock_item = SearchResultsItem(
        subjectId=subject_id,
        subjectType=SubjectType(type_int),
        title="Unknown",
        description="",
        releaseDate=date(2000, 1, 1),
        duration=0,
        genre="Action", 
        cover=mock_image,
        countryName="",
        imdbRatingValue=0.0,
        detailPath=f"detail/item?id={subject_id}",
        appointmentCnt=0,
        appointmentDate="",
        corner="",
        subtitles="en",
        ops='{"rid": "' + str(uuid.uuid4()) + '", "trace_id": ""}',
        hasResource=True
    )
    stream_provider = StreamFilesDetail(session, mock_item)
    return await stream_provider.get_content_model(season, episode)

# --- ROUTES ---

@app.get("/")
async def root():
    return {
        "message": "Moviebox API Backend is running",
        "current_mirror": moviebox_api.constants.SELECTED_HOST
    }

@app.get("/homepage")
async def get_homepage():
    return await execute_with_retry(fetch_homepage)

@app.get("/trending")
async def get_trending(page: int = 0, per_page: int = 18):
    return await execute_with_retry(fetch_trending, page, per_page)

@app.get("/search")
async def search(query: str, subject_type: int = 0, page: int = 1):
    return await execute_with_retry(fetch_search, query, subject_type, page)

@app.get("/details/{subject_id}")
async def get_details(subject_id: str, type: int = 1):
    return await execute_with_retry(fetch_details, subject_id, type)

@app.get("/stream/{subject_id}")
async def get_stream(subject_id: str, type: int = 1, season: int = 1, episode: int = 1):
    return await execute_with_retry(fetch_stream, subject_id, type, season, episode)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
