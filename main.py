import os
import uuid
import random
import asyncio
from datetime import date
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query
from pydantic import HttpUrl

# Importations Moviebox
from moviebox_api.requests import Session
from moviebox_api.core import Homepage, Search, Trending, MovieDetails, TVSeriesDetails, PopularSearch
from moviebox_api.stream import StreamFilesDetail
from moviebox_api.constants import SubjectType, MIRROR_HOSTS
from moviebox_api.models import SearchResultsItem, StreamFilesMetadata, ContentImageModel, OPS

# --- CONFIGURATION DES MIROIRS ---
# Liste fournie par l'utilisateur + dÃ©fauts du wrapper
CUSTOM_MIRRORS = [
    "v.moviebox.ph",
    "netnaija.video",
    "moviebox.id",
    "moviebox.ph",
    "movieboxapp.in",
    "moviebox.pk",
    "h5.aoneroom.com"
]

# --- CORRECTIFS ET PATCHES ---

# 1. Patch pour StreamFilesDetail (mÃ©thode abstraite manquante)
async def patched_get_content_model(self, season: int, episode: int) -> StreamFilesMetadata:
    contents = await self.get_content(season, episode)
    return StreamFilesMetadata(**contents)

StreamFilesDetail.get_content_model = patched_get_content_model

# 2. Gestion de la rotation des hÃ´tes
class MirrorRotator:
    def __init__(self, mirrors: List[str]):
        self.mirrors = mirrors
        self.current_index = 0

    def get_next_host(self):
        host = self.mirrors[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.mirrors)
        return host

    def shuffle(self):
        random.shuffle(self.mirrors)

rotator = MirrorRotator(CUSTOM_MIRRORS)
rotator.shuffle()

def set_moviebox_host(host: str):
    os.environ["MOVIEBOX_API_HOST"] = host
    # Note: Le wrapper lit cette variable au moment de l'import ou de l'init des constantes.
    # Pour que cela soit pris en compte dynamiquement, nous devons parfois forcer 
    # la mise Ã  jour des variables dans moviebox_api.constants si nÃ©cessaire.
    import moviebox_api.constants
    moviebox_api.constants.SELECTED_HOST = host
    moviebox_api.constants.HOST_URL = f"https://{host}/"

# --- APPLICATION FASTAPI ---

app = FastAPI(title="Moviebox Streaming API", description="Backend avec rotation de miroirs et correctifs")

async def get_session_with_retry():
    """Tente d'initialiser une session sur un hÃ´te fonctionnel"""
    for _ in range(len(CUSTOM_MIRRORS)):
        host = rotator.get_next_host()
        set_moviebox_host(host)
        try:
            session = Session()
            # Test rapide sur la homepage pour valider l'hÃ´te
            hp = Homepage(session)
            await hp.get_content()
            return session, host
        except Exception:
            continue
    # Si rien ne marche, on rend la derniÃ¨re session crÃ©Ã©e
    return Session(), CUSTOM_MIRRORS[0]

@app.get("/")
async def root():
    return {
        "message": "Moviebox API Backend is running",
        "mirrors_available": len(CUSTOM_MIRRORS),
        "current_host": os.environ.get("MOVIEBOX_API_HOST", "default")
    }

@app.get("/homepage")
async def get_homepage():
    session, _ = await get_session_with_retry()
    try:
        hp = Homepage(session)
        return await hp.get_content_model()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/trending")
async def get_trending(page: int = 0, per_page: int = 18):
    session, _ = await get_session_with_retry()
    try:
        trending = Trending(session, page=page, per_page=per_page)
        return await trending.get_content_model()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search")
async def search(query: str, subject_type: int = 0, page: int = 1):
    session, _ = await get_session_with_retry()
    try:
        s_type = SubjectType(subject_type)
        search_obj = Search(session, query, subject_type=s_type, page=page)
        return await search_obj.get_content_model()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/details/{subject_id}")
async def get_details(subject_id: str, type: int = 1):
    session, _ = await get_session_with_retry()
    try:
        # Correction de l'URL pour passer la validation VALID_ITEM_PAGE_URL_PATTERN
        # Le pattern attend : /detail/quelque-chose?id=NOMBRE_DE_17_CHIFFRES
        # On utilise un slug gÃ©nÃ©rique "item" qui match [\w-]+
        valid_path = f"/detail/item?id={subject_id}"
        
        if type == 1:
            details_provider = MovieDetails(valid_path, session)
        else:
            details_provider = TVSeriesDetails(valid_path, session)
            
        return await details_provider.get_content_model()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream/{subject_id}")
async def get_stream(subject_id: str, type: int = 1, season: int = 1, episode: int = 1):
    session, _ = await get_session_with_retry()
    try:
        mock_image = ContentImageModel(
            url="https://example.com/image.jpg", width=100, height=100, size=100, format="jpg",
            thumbnail="https://example.com/thumb.jpg", blurHash="", avgHueLight="", avgHueDark="", id="1"
        )
        
        # Correction du champ genre : passer une chaÃ®ne "Action" au lieu d'une liste ["Action"]
        # pour Ã©viter l'erreur 'list' object has no attribute 'split'
        mock_item = SearchResultsItem(
            subjectId=subject_id,
            subjectType=SubjectType(type),
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
    except Exception as e:
        if "403" in str(e):
            # En cas de 403, on pourrait tenter un autre miroir ici aussi
            raise HTTPException(status_code=403, detail="AccÃ¨s interdit (403) sur ce miroir.")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
