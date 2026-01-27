from fastapi import FastAPI, HTTPException, Query
from moviebox import MovieBox
from moviebox.details import MovieDetails, SeriesDetails
from moviebox.streamfiles import MovieStreamFiles, SeriesStreamFiles
import logging

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MovixBox API",
    description="API pour rechercher et streamer des films et séries",
    version="1.0.0"
)

# Vos autres endpoints (/, /search, /trending, /home) restent identiques...

@app.get("/details/{subject_id}")
async def get_details(
    subject_id: int,
    type: int = Query(..., description="Type de contenu: 1 pour série, 2 pour film")
):
    """
    Obtenir les détails d'un film ou d'une série
    
    - **subject_id**: ID du contenu
    - **type**: 1 = série, 2 = film
    """
    try:
        logger.info(f"Details request: subject_id={subject_id}, type={type}")
        
        # Validation du type
        if type not in [1, 2]:
            raise HTTPException(
                status_code=400, 
                detail="Le paramètre 'type' doit être 1 (série) ou 2 (film)"
            )
        
        # Utiliser la classe concrète appropriée
        if type == 1:
            details = SeriesDetails(subject_id)
        else:
            details = MovieDetails(subject_id)
        
        # Récupérer le contenu
        content = details.get_content_model()
        
        return content
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /details: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Erreur lors de la récupération des détails: {str(e)}"
        )


@app.get("/stream/{subject_id}")
async def get_stream(
    subject_id: int,
    type: int = Query(..., description="Type de contenu: 1 pour série, 2 pour film"),
    season: int = Query(None, description="Numéro de saison (requis pour les séries)"),
    episode: int = Query(None, description="Numéro d'épisode (requis pour les séries)")
):
    """
    Obtenir les liens de streaming d'un film ou d'une série
    
    - **subject_id**: ID du contenu
    - **type**: 1 = série, 2 = film
    - **season**: Numéro de saison (requis si type=1)
    - **episode**: Numéro d'épisode (requis si type=1)
    """
    try:
        logger.info(f"Stream request: subject_id={subject_id}, type={type}, season={season}, episode={episode}")
        
        # Validation du type
        if type not in [1, 2]:
            raise HTTPException(
                status_code=400, 
                detail="Le paramètre 'type' doit être 1 (série) ou 2 (film)"
            )
        
        # Pour les séries, vérifier que season et episode sont fournis
        if type == 1:
            if season is None or episode is None:
                raise HTTPException(
                    status_code=400,
                    detail="Les paramètres 'season' et 'episode' sont requis pour les séries (type=1)"
                )
            
            # Utiliser SeriesStreamFiles
            stream = SeriesStreamFiles(subject_id)
            content = stream.get_content(season=season, episode=episode)
        else:
            # Utiliser MovieStreamFiles pour les films
            stream = MovieStreamFiles(subject_id)
            content = stream.get_content_model()
        
        return content
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /stream: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Erreur lors de la récupération du streaming: {str(e)}"
        )
