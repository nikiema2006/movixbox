import os
import json
import uuid
from typing import Optional
from datetime import date
from fastapi import FastAPI, HTTPException, Query
from moviebox_api.requests import Session
from moviebox_api.core import Homepage, Search, Trending, MovieDetails, TVSeriesDetails, PopularSearch
from moviebox_api.stream import StreamFilesDetail
from moviebox_api.constants import SubjectType, ITEM_DETAILS_PATH
from moviebox_api.models import SearchResultsItem, OPS

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
async def get_details(subject_id: str, type: int = Query(..., description="1 pour film, 2 pour série")):
    try:
        # CORRECTION: MovieDetails et TVSeriesDetails attendent une URL complète
        # Format attendu: "detail/item?id={subject_id}" ou juste "item?id={subject_id}"
        detail_path = f"item?id={subject_id}"
        
        if type == 1:  # Movie
            details_provider = MovieDetails(detail_path, session)
        elif type == 2:  # TV Series
            details_provider = TVSeriesDetails(detail_path, session)
        else:
            raise HTTPException(status_code=400, detail="Type doit être 1 (film) ou 2 (série)")
            
        content = await details_provider.get_content_model()
        return content
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream/{subject_id}")
async def get_stream(
    subject_id: str, 
    type: int = Query(..., description="1 pour film, 2 pour série"),
    season: int = Query(1, description="Numéro de saison (pour séries)"),
    episode: int = Query(1, description="Numéro d'épisode (pour séries)")
):
    try:
        # Validation du type
        if type not in [1, 2]:
            raise HTTPException(status_code=400, detail="Type doit être 1 (film) ou 2 (série)")
        
        # CORRECTION: Pydantic exige une URL valide pour cover.url
        # On utilise une URL placeholder valide
        mock_item = SearchResultsItem(
            subjectId=subject_id,
            subjectType=SubjectType(type),
            title="Stream Request",
            description="",
            releaseDate=date.today(),
            duration=0,
            genre="",
            cover={
                "url": "https://via.placeholder.com/300x450",  # URL valide requise
                "width": 300, 
                "height": 450, 
                "size": 1000, 
                "format": "jpg",
                "thumbnail": "https://via.placeholder.com/150x225",  # URL valide requise
                "blurHash": "", 
                "avgHueLight": "", 
                "avgHueDark": "", 
                "id": "placeholder"
            },
            countryName="",
            imdbRatingValue=0.0,
            detailPath=f"item?id={subject_id}",
            appointmentCnt=0,
            appointmentDate="",
            corner="",
            subtitles="",
            ops=json.dumps({"rid": str(uuid.uuid4()), "trace_id": ""}),
            hasResource=True
        )
        
        stream_provider = StreamFilesDetail(session, mock_item)
        
        # Différencier films et séries
        if type == 1:  # Film
            content = await stream_provider.get_content_model()
        else:  # Série
            content = await stream_provider.get_content_model(season=season, episode=episode)
        
        return content
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_stream: {str(e)}")
        if "403" in str(e):
            raise HTTPException(status_code=403, detail="Accès interdit par le serveur Moviebox")
        if "404" in str(e):
            raise HTTPException(status_code=404, detail="Contenu non trouvé sur Moviebox")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
