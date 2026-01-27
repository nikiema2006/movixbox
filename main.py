import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from moviebox_api.requests import Session
from moviebox_api.core import Homepage, Search, Trending, MovieDetails, TVSeriesDetails, PopularSearch
from moviebox_api.stream import StreamFilesDetail
from moviebox_api.constants import SubjectType
from moviebox_api.models import SearchResultsItem

app = FastAPI(title="Moviebox Streaming API", description="Backend pour application de streaming utilisant moviebox-api")

# Initialisation de la session globale
session = Session()

@app.get("/")
async def root():
    return {
        "message": "Moviebox API Backend is running",
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
    subject_type: int = 0, # 0: ALL, 1: MOVIES, 2: TV_SERIES
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
        # On crée un objet SearchResultsItem minimal pour MovieDetails/TVSeriesDetails
        # car ils attendent soit une URL soit un SearchResultsItem
        # L'URL de détail est généralement /detail/{subject_id}
        detail_path = f"detail/{subject_id}"
        
        if type == 1: # Movie
            details_provider = MovieDetails(detail_path, session)
        else: # TV Series
            details_provider = TVSeriesDetails(detail_path, session)
            
        content = await details_provider.get_content_model()
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream/{subject_id}")
async def get_stream(
    subject_id: str, 
    type: int = 1, 
    season: int = 1, 
    episode: int = 1
):
    try:
        # Création d'un item fictif pour StreamFilesDetail
        # subjectType est requis pour StreamFilesDetail
        from pydantic import HttpUrl
        from datetime import date
        from moviebox_api.models import ContentImageModel, OPS
        import uuid

        # Mock image
        mock_image = ContentImageModel(
            url="https://example.com/image.jpg",
            width=100, height=100, size=100, format="jpg",
            thumbnail="https://example.com/thumb.jpg",
            blurHash="", avgHueLight="", avgHueDark="", id="1"
        )
        
        mock_item = SearchResultsItem(
            subjectId=subject_id,
            subjectType=SubjectType(type),
            title="Unknown",
            description="",
            releaseDate=date(2000, 1, 1),
            duration=0,
            genre=["Action"],
            cover=mock_image,
            countryName="",
            imdbRatingValue=0.0,
            detailPath=f"detail/{subject_id}",
            appointmentCnt=0,
            appointmentDate="",
            corner="",
            subtitles=[],
            ops=OPS(rid=uuid.uuid4(), trace_id=""),
            hasResource=True
        )
        
        stream_provider = StreamFilesDetail(session, mock_item)
        content = await stream_provider.get_content_model(season, episode)
        return content
    except Exception as e:
        # Si 403, on renvoie une erreur explicite
        if "403" in str(e):
            raise HTTPException(status_code=403, detail="Accès interdit par le serveur Moviebox. Un changement d'hôte ou de cookies peut être nécessaire.")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
    
