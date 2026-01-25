from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import logging

# ✅ IMPORTS CORRECTS pour moviebox-api
from moviebox_api.models import SearchResult
from moviebox_api.core import Movie, Series

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MovieBox Streaming API",
    description="Backend de streaming pour films et séries - Hébergé sur Render",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèles Pydantic
class MovieSearchRequest(BaseModel):
    query: str
    year: Optional[int] = None

class SeriesSearchRequest(BaseModel):
    query: str
    year: Optional[int] = None

class MovieStreamRequest(BaseModel):
    title: str
    year: Optional[int] = None
    quality: str = "best"
    subtitle_language: str = "English"

class SeriesStreamRequest(BaseModel):
    title: str
    season: int
    episode: int
    year: Optional[int] = None
    quality: str = "best"
    subtitle_language: str = "English"

# Cache simple en mémoire
search_cache = {}

@app.get("/")
async def root():
    """Point d'entrée principal - Health check"""
    return {
        "status": "online",
        "service": "MovieBox Streaming API",
        "version": "1.0.0",
        "endpoints": {
            "documentation": "/docs",
            "search_movies": "/api/v1/search/movies?query=...",
            "search_series": "/api/v1/search/series?query=...",
            "movie_stream": "POST /api/v1/movies/stream",
            "series_stream": "POST /api/v1/series/stream"
        },
        "warning": "Les URLs de streaming expirent après 2-6h. Régénérer si nécessaire."
    }

@app.get("/health")
async def health_check():
    """Health check pour Render"""
    return {"status": "healthy", "service": "moviebox-api"}

@app.get("/api/v1/search/movies")
async def search_movies(
    query: str = Query(..., min_length=1, description="Terme de recherche"),
    year: Optional[int] = Query(None, description="Filtrer par année de sortie")
):
    """
    Rechercher des films
    
    Args:
        query: Titre ou mots-clés du film
        year: Année de sortie (optionnel)
    
    Returns:
        Liste des films trouvés avec leurs informations
    """
    try:
        logger.info(f"Recherche films: '{query}' (année: {year})")
        
        # Vérifier le cache
        cache_key = f"movie_{query}_{year}"
        if cache_key in search_cache:
            logger.info("Résultat depuis le cache")
            return search_cache[cache_key]
        
        # ✅ Utiliser la classe Movie correctement
        movie_client = Movie()
        results = await movie_client.search(query)
        
        if not results:
            return {
                "success": True,
                "query": query,
                "count": 0,
                "results": [],
                "message": "Aucun film trouvé"
            }
        
        # Filtrer par année si spécifié
        if year:
            results = [r for r in results if r.release_year == year]
        
        response_data = {
            "success": True,
            "query": query,
            "year_filter": year,
            "count": len(results),
            "results": [
                {
                    "id": r.id,
                    "title": r.title,
                    "year": r.release_year,
                    "thumbnail": r.thumbnail,
                } for r in results[:30]
            ]
        }
        
        search_cache[cache_key] = response_data
        return response_data
        
    except Exception as e:
        logger.error(f"Erreur recherche films: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Erreur lors de la recherche: {str(e)}"
        )

@app.get("/api/v1/search/series")
async def search_series(
    query: str = Query(..., min_length=1, description="Terme de recherche"),
    year: Optional[int] = Query(None, description="Filtrer par année")
):
    """Rechercher des séries TV"""
    try:
        logger.info(f"Recherche séries: '{query}' (année: {year})")
        
        cache_key = f"series_{query}_{year}"
        if cache_key in search_cache:
            return search_cache[cache_key]
        
        # ✅ Utiliser la classe Series correctement
        series_client = Series()
        results = await series_client.search(query)
        
        if not results:
            return {
                "success": True,
                "query": query,
                "count": 0,
                "results": [],
                "message": "Aucune série trouvée"
            }
        
        if year:
            results = [r for r in results if r.release_year == year]
        
        response_data = {
            "success": True,
            "query": query,
            "year_filter": year,
            "count": len(results),
            "results": [
                {
                    "id": r.id,
                    "title": r.title,
                    "year": r.release_year,
                    "thumbnail": r.thumbnail
                } for r in results[:30]
            ]
        }
        
        search_cache[cache_key] = response_data
        return response_data
        
    except Exception as e:
        logger.error(f"Erreur recherche séries: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.post("/api/v1/movies/stream")
async def get_movie_stream_url(request: MovieStreamRequest):
    """
    Générer l'URL de streaming pour un film
    
    ⚠️ IMPORTANT: Cette URL expire après 2-6 heures
    Il faut régénérer l'URL si elle ne fonctionne plus
    """
    try:
        logger.info(f"Génération URL streaming: '{request.title}' ({request.quality})")
        
        movie_client = Movie()
        results = await movie_client.search(request.title)
        
        if not results:
            raise HTTPException(
                status_code=404, 
                detail=f"Film '{request.title}' non trouvé"
            )
        
        # Filtrer par année
        if request.year:
            results = [r for r in results if r.release_year == request.year]
            if not results:
                raise HTTPException(
                    status_code=404,
                    detail=f"Film '{request.title}' ({request.year}) non trouvé"
                )
        
        movie = results[0]
        logger.info(f"Film trouvé: {movie.title} ({movie.release_year})")
        
        # Obtenir les détails complets
        details = await movie_client.get_details(movie)
        
        # Sélectionner la qualité
        available_qualities = details.qualities
        
        stream_url = None
        selected_quality = request.quality
        
        if request.quality in available_qualities:
            stream_url = available_qualities[request.quality]
        else:
            # Fallback
            priority = ["best", "1080p", "720p", "480p", "360p", "worst"]
            for q in priority:
                if q in available_qualities:
                    stream_url = available_qualities[q]
                    selected_quality = q
                    break
        
        if not stream_url and available_qualities:
            selected_quality = list(available_qualities.keys())[0]
            stream_url = available_qualities[selected_quality]
        
        if not stream_url:
            raise HTTPException(
                status_code=404,
                detail="Aucune URL de streaming disponible"
            )
        
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
                "quality_requested": request.quality,
                "quality_delivered": selected_quality,
                "available_qualities": list(available_qualities.keys()),
                "subtitles": subtitles,
                "thumbnail": details.thumbnail,
                "duration": getattr(details, 'duration', None),
                "rating": getattr(details, 'rating', None),
                "synopsis": getattr(details, 'synopsis', ''),
            },
            "metadata": {
                "generated_at": "now",
                "expires_in": "2-6 hours",
                "warning": "Cette URL expire. Régénérez-la si le streaming échoue."
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur génération stream film: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la génération: {str(e)}"
        )

@app.post("/api/v1/series/stream")
async def get_series_stream_url(request: SeriesStreamRequest):
    """
    Générer l'URL de streaming pour un épisode de série
    
    ⚠️ IMPORTANT: Cette URL expire après 2-6 heures
    """
    try:
        logger.info(
            f"Génération URL série: '{request.title}' "
            f"S{request.season}E{request.episode}"
        )
        
        series_client = Series()
        results = await series_client.search(request.title)
        
        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"Série '{request.title}' non trouvée"
            )
        
        if request.year:
            results = [r for r in results if r.release_year == request.year]
        
        series = results[0]
        logger.info(f"Série trouvée: {series.title} ({series.release_year})")
        
        # Obtenir les détails de la série
        details = await series_client.get_details(series)
        
        # Trouver la saison
        season = next(
            (s for s in details.seasons if s.number == request.season), 
            None
        )
        if not season:
            raise HTTPException(
                status_code=404,
                detail=f"Saison {request.season} non trouvée"
            )
        
        # Trouver l'épisode
        episode = next(
            (e for e in season.episodes if e.number == request.episode),
            None
        )
        if not episode:
            raise HTTPException(
                status_code=404,
                detail=f"Épisode {request.episode} non trouvé"
            )
        
        # Obtenir les détails de l'épisode
        episode_details = await series_client.get_episode_details(episode)
        
        # Sélectionner la qualité
        available_qualities = episode_details.qualities
        stream_url = None
        selected_quality = request.quality
        
        if request.quality in available_qualities:
            stream_url = available_qualities[request.quality]
        else:
            priority = ["best", "1080p", "720p", "480p", "360p", "worst"]
            for q in priority:
                if q in available_qualities:
                    stream_url = available_qualities[q]
                    selected_quality = q
                    break
        
        if not stream_url and available_qualities:
            selected_quality = list(available_qualities.keys())[0]
            stream_url = available_qualities[selected_quality]
        
        if not stream_url:
            raise HTTPException(
                status_code=404,
                detail="Aucune URL de streaming disponible"
            )
        
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
                "season": request.season,
                "episode": request.episode,
                "episode_title": getattr(episode_details, 'title', f"Episode {request.episode}"),
                "stream_url": stream_url,
                "quality_requested": request.quality,
                "quality_delivered": selected_quality,
                "available_qualities": list(available_qualities.keys()),
                "subtitles": subtitles,
                "thumbnail": episode_details.thumbnail,
            },
            "metadata": {
                "generated_at": "now",
                "expires_in": "2-6 hours",
                "warning": "Cette URL expire. Régénérez-la si le streaming échoue."
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur série stream: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/api/v1/series/{series_id}/info")
async def get_series_info(
    series_id: str,
    title: str = Query(..., description="Titre de la série")
):
    """Obtenir les informations sur les saisons disponibles"""
    try:
        series_client = Series()
        results = await series_client.search(title)
        
        if not results:
            raise HTTPException(status_code=404, detail="Série non trouvée")
        
        series = results[0]
        details = await series_client.get_details(series)
        
        seasons_info = []
        for season in details.seasons:
            seasons_info.append({
                "season_number": season.number,
                "episode_count": len(season.episodes),
                "episodes": [
                    {
                        "number": ep.number,
                        "title": getattr(ep, 'title', f"Episode {ep.number}")
                    } for ep in season.episodes
                ]
            })
        
        return {
            "success": True,
            "series_title": details.title,
            "year": details.release_year,
            "total_seasons": len(seasons_info),
            "seasons": seasons_info,
            "thumbnail": details.thumbnail
        }
        
    except Exception as e:
        logger.error(f"Erreur info série: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Gestionnaire d'erreurs global"""
    logger.error(f"Erreur non gérée: {str(exc)}", exc_info=True)
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
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
)
