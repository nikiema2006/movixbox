import os
import uuid
from datetime import date
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import HttpUrl

# Importations Moviebox
from moviebox_api.requests import Session
from moviebox_api.core import Homepage, Search, Trending, MovieDetails, TVSeriesDetails, PopularSearch
from moviebox_api.stream import StreamFilesDetail
from moviebox_api.constants import SubjectType
from moviebox_api.models import SearchResultsItem, StreamFilesMetadata, ContentImageModel, OPS

# --- CORRECTIF POUR LA CLASSE ABSTRAITE ---
# Le wrapper original définit get_content_model comme une méthode abstraite 
# mais ne l'implémente pas dans StreamFilesDetail. Nous le corrigeons ici.
async def patched_get_content_model(self, season: int, episode: int) -> StreamFilesMetadata:
    contents = await self.get_content(season, episode)
    return StreamFilesMetadata(**contents)

StreamFilesDetail.get_content_model = patched_get_content_model
# ------------------------------------------

app = FastAPI(title="Moviebox Streaming API", description="Backend corrigé pour application de streaming")

# Initialisation de la session globale
session = Session()

@app.get("/")
async def root():
    return {
        "message": "Moviebox API Backend is running (Fixed Version)",
        "docs": "/docs",
        "status": "online"
    }

@app.get("/homepage")
async def get_homepage():
    try:
        hp = Homepage(session)
        content = await hp.get_content_model()
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/trending")
async def get_trending(page: int = 0, per_page: int = 18):
    try:
        trending = Trending(session, page=page, per_page=per_page)
        content = await trending.get_content_model()
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/popular-searches")
async def get_popular_searches():
    try:
        ps = PopularSearch(session)
        content = await ps.get_content_model()
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search")
async def search(
    query: str, 
    subject_type: int = 0, 
    page: int = 1, 
    per_page: int = 24
):
    try:
        s_type = SubjectType(subject_type)
        search_obj = Search(session, query, subject_type=s_type, page=page, per_page=per_page)
        content = await search_obj.get_content_model()
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/details/{subject_id}")
async def get_details(subject_id: str, type: int = 1):
    try:
        # Correction de l'URL : Le wrapper attend une URL relative qui sera combinée avec l'hôte.
        # L'erreur 404 venait d'un chemin incorrect. On utilise le format attendu par le wrapper.
        # Format type: "item?id=..."
        detail_path = f"item?id={subject_id}"
        
        if type == 1: # Movie
            details_provider = MovieDetails(detail_path, session)
        else: # TV Series
            details_provider = TVSeriesDetails(detail_path, session)
            
        content = await details_provider.get_content_model()
        return content
    except Exception as e:
        if "404" in str(e):
            raise HTTPException(status_code=404, detail=f"Contenu non trouvé. L'ID {subject_id} est peut-être invalide ou l'hôte a changé.")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream/{subject_id}")
async def get_stream(
    subject_id: str, 
    type: int = 1, 
    season: int = 1, 
    episode: int = 1
):
    try:
        # Mock image pour satisfaire le modèle Pydantic
        mock_image = ContentImageModel(
            url="https://example.com/image.jpg",
            width=100, height=100, size=100, format="jpg",
            thumbnail="https://example.com/thumb.jpg",
            blurHash="", avgHueLight="", avgHueDark="", id="1"
        )
        
        # Création d'un item pour StreamFilesDetail
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
            detailPath=f"item?id={subject_id}",
            appointmentCnt=0,
            appointmentDate="",
            corner="",
            subtitles=[],
            ops=OPS(rid=uuid.uuid4(), trace_id=""),
            hasResource=True
        )
        
        stream_provider = StreamFilesDetail(session, mock_item)
        # Utilisation de la méthode patchée
        content = await stream_provider.get_content_model(season, episode)
        return content
    except Exception as e:
        if "403" in str(e):
            raise HTTPException(status_code=403, detail="Accès interdit (403). Le serveur Moviebox bloque la requête. Essayez de changer MOVIEBOX_API_HOST.")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
