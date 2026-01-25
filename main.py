from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import os
from moviebox_api import MovieClient, SeriesClient
from moviebox_api.models import SearchResult
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MovieBox Streaming API",
    description="Backend de streaming pour films et séries - Optimisé pour Render",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS - À configurer selon vos besoins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production : ["https://votre-app.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèles Pydantic
class SearchRequest(BaseModel):
    query: str
    year: Optional[int] = None

class StreamURLRequest(BaseModel):
    title: str
    year: Optional[int] = None
    quality: str = "best"
    subtitle_language: str = "English"

class SeriesStreamURLRequest(BaseModel):
    title: str
    season: int
    episode: int
    year: Optional[int] = None
    quality: str = "best"
    subtitle_language: str = "English"

# Health check pour Render
@app.get("/")
@app.get("/health")
async def health_check():
    """Health check endpoint pour Render"""
    return {
        "status": "online",
        "service": "MovieBox API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/api/v1/search/movies")
async def search_movies(
    query: str = Query(..., min_length=1, description="Terme de recherche"),
    year: Optional[int] = Query(None, description="Filtrer par année")
):
    """Rechercher des films"""
    try:
        logger.info(f"Recherche de films: {query}")
        client = MovieClient()
        results = await client.search(query)
        
        # Filtrer par année si spécifié
        if year:
            results = [r for r in results if r.release_year == year]
        
        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": [
                {
                    "id": r.id,
                    "title": r.title,
                    "year": r.release_year,
                    "thumbnail": r.thumbnail,
                    "rating": getattr(r, 'rating', None)
                } for r in results[:20]  # Limiter à 20 résultats
            ]
        }
    except Exception as e:
        logger.error(f"Erreur recherche films: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/api/v1/search/series")
async def search_series(
    query: str = Query(..., min_length=1, description="Terme de recherche"),
    year: Optional[int] = Query(None, description="Filtrer par année")
):
    """Rechercher des séries TV"""
    try:
        logger.info(f"Recherche de séries: {query}")
        client = SeriesClient()
        results = await client.search(query)
        
        if year:
            results = [r for r in results if r.release_year == year]
        
        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": [
                {
                    "id": r.id,
                    "title": r.title,
                    "year": r.release_year,
                    "thumbnail": r.thumbnail
                } for r in results[:20]
            ]
        }
    except Exception as e:
        logger.error(f"Erreur recherche séries: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/api/v1/movies/stream")
async def get_movie_stream(request: StreamURLRequest):
    """
    Obtenir l'URL de streaming pour un film
    ⚠️ L'URL générée expire après quelques heures - Régénérer si nécessaire
    """
    try:
        logger.info(f"Génération URL streaming pour: {request.title}")
        client = MovieClient()
        results = await client.search(request.title)
        
        if not results:
            raise HTTPException(status_code=404, detail="Film non trouvé")
        
        # Filtrer par année
        if request.year:
            results = [r for r in results if r.release_year == request.year]
            if not results:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Film '{request.title}' ({request.year}) non trouvé"
                )
        
        movie = results[0]
        details = await client.get_movie_details(movie)
        
        # Sélectionner la qualité
        quality_map = details.qualities
        stream_url = quality_map.get(request.quality)
        
        if not stream_url:
            # Fallback vers la meilleure qualité disponible
            stream_url = quality_map.get("best") or quality_map.get("1080p") or list(quality_map.values())[0]
        
        # Récupérer les sous-titres
        subtitles = []
        for sub in details.subtitles:
            if request.subtitle_language.lower() in sub.language.lower():
                subtitles.append({
                    "language": sub.language,
                    "url": sub.url,
                    "format": "srt"
                })
        
        return {
            "success": True,
            "data": {
                "title": details.title,
                "year": details.release_year,
                "stream_url": stream_url,
                "quality": request.quality,
                "available_qualities": list(quality_map.keys()),
                "subtitles": subtitles,
                "thumbnail": details.thumbnail,
                "duration": getattr(details, 'duration', None),
                "rating": getattr(details, 'rating', None),
                "synopsis": getattr(details, 'synopsis', None),
                "warning": "Cette URL expire après quelques heures. Régénérer si nécessaire."
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur génération stream: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/api/v1/series/stream")
async def get_series_stream(request: SeriesStreamURLRequest):
    """
    Obtenir l'URL de streaming pour un épisode de série
    ⚠️ L'URL générée expire après quelques heures - Régénérer si nécessaire
    """
    try:
        logger.info(f"Génération URL pour: {request.title} S{request.season}E{request.episode}")
        client = SeriesClient()
        results = await client.search(request.title)
        
        if not results:
            raise HTTPException(status_code=404, detail="Série non trouvée")
        
        if request.year:
            results = [r for r in results if r.release_year == request.year]
        
        series = results[0]
        details = await client.get_series_details(series)
        
        # Trouver la saison
        season = next((s for s in details.seasons if s.number == request.season), None)
        if not season:
            raise HTTPException(
                status_code=404, 
                detail=f"Saison {request.season} non trouvée"
            )
        
        # Trouver l'épisode
        episode = next((e for e in season.episodes if e.number == request.episode), None)
        if not episode:
            raise HTTPException(
                status_code=404, 
                detail=f"Épisode {request.episode} non trouvé"
            )
        
        # Obtenir les détails de l'épisode
        episode_details = await client.get_episode_details(episode)
        
        # Sélectionner la qualité
        quality_map = episode_details.qualities
        stream_url = quality_map.get(request.quality)
        
        if not stream_url:
            stream_url = quality_map.get("best") or list(quality_map.values())[0]
        
        # Sous-titres
        subtitles = []
        for sub in episode_details.subtitles:
            if request.subtitle_language.lower() in sub.language.lower():
                subtitles.append({
                    "language": sub.language,
                    "url": sub.url
                })
        
        return {
            "success": True,
            "data": {
                "series_title": details.title,
                "episode_title": f"S{request.season}E{request.episode}",
                "stream_url": stream_url,
                "quality": request.quality,
                "available_qualities": list(quality_map.keys()),
                "subtitles": subtitles,
                "thumbnail": episode_details.thumbnail,
                "warning": "Cette URL expire après quelques heures. Régénérer si nécessaire."
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur génération stream série: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/api/v1/series/{series_title}/seasons")
async def get_series_seasons(series_title: str, year: Optional[int] = None):
    """Obtenir la liste des saisons disponibles pour une série"""
    try:
        client = SeriesClient()
        results = await client.search(series_title)
        
        if not results:
            raise HTTPException(status_code=404, detail="Série non trouvée")
        
        if year:
            results = [r for r in results if r.release_year == year]
        
        series = results[0]
        details = await client.get_series_details(series)
        
        seasons = [
            {
                "season_number": season.number,
                "episode_count": len(season.episodes)
            }
            for season in details.seasons
        ]
        
        return {
            "success": True,
            "series_title": details.title,
            "total_seasons": len(seasons),
            "seasons": seasons
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Gestion des erreurs globale
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Erreur non gérée: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Erreur interne du serveur",
            "detail": str(exc)
        }
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
