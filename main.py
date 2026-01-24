import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional

# Importation des composants de moviebox-api
from moviebox_api import Search, StreamFilesDetail, Session, SubjectType
from moviebox_api.models import SearchResultsItem, StreamFilesMetadata
from moviebox_api.exceptions import ZeroSearchResultsError

# --- Configuration de l'API ---
app = FastAPI(
    title="MovieBox API Bridge",
    description="Bridge API to expose moviebox-api functionality for React Native.",
    version="1.0.0"
)

# Configuration CORS pour permettre l'accès depuis l'application React Native
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À ajuster en production avec l'URL de votre app Expo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialisation de la session moviebox-api
# Nous utilisons une session globale pour la simplicité
# Dans une application plus complexe, on pourrait la gérer par requête.
moviebox_session = Session()

# --- Modèles de réponse pour l'API ---

class MovieItem(BaseModel):
    """Modèle simplifié pour un résultat de recherche."""
    subjectId: str
    title: str
    subjectType: str
    cover_url: str = Field(alias="coverUrl")
    detailPath: str

    @classmethod
    def from_search_result(cls, item: SearchResultsItem):
        return cls(
            subjectId=item.subjectId,
            title=item.title,
            subjectType=item.subjectType.name,
            coverUrl=str(item.cover.url),
            detailPath=item.detailPath
        )

class StreamInfo(BaseModel):
    """Modèle pour les informations de streaming."""
    stream_url: str
    resolution: int
    format: str

class StreamResponse(BaseModel):
    """Réponse complète pour le streaming."""
    best_stream: Optional[StreamInfo]
    all_streams: List[StreamInfo]

# --- Endpoints de l'API ---

@app.get("/")
async def root():
    return {"message": "MovieBox API Bridge is running. Use /search or /stream endpoints."}

@app.get("/search", response_model=List[MovieItem])
async def search_content(query: str, subject_type: str = "ALL"):
    """
    Recherche de contenu (films ou séries TV).
    subject_type peut être 'MOVIES', 'TV_SERIES' ou 'ALL'.
    """
    try:
        # Conversion du type de sujet
        subject_enum = SubjectType[subject_type.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid subject_type. Must be MOVIES, TV_SERIES, or ALL.")

    try:
        search_provider = Search(moviebox_session, query=query, subject_type=subject_enum)
        search_results = await search_provider.get_content_model()
        
        # Conversion des résultats en notre modèle simplifié
        items = [MovieItem.from_search_result(item) for item in search_results.items]
        
        return items
    except ZeroSearchResultsError:
        return []
    except Exception as e:
        # Log l'erreur pour le débogage côté serveur
        print(f"Erreur lors de la recherche: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during search.")

@app.get("/stream", response_model=StreamResponse)
async def get_stream_url(subject_id: str, detail_path: str, is_tv_series: bool = False, season: int = 0, episode: int = 0):
    """
    Récupère les liens de streaming directs pour un film ou un épisode de série TV.
    """
    # Recréer un SearchResultsItem minimal pour l'API moviebox-api
    # C'est une astuce pour éviter de refaire une recherche complète
    item = SearchResultsItem(
        subjectId=subject_id,
        title="", # Non utilisé ici
        subjectType=SubjectType.TV_SERIES if is_tv_series else SubjectType.MOVIES,
        detailPath=detail_path,
        # Les autres champs sont requis par le modèle Pydantic mais non utilisés par StreamFilesDetail
        description="", releaseDate="2000-01-01", duration=0, genre=[], cover={"url": "http://example.com", "width": 0, "height": 0, "size": 0, "format": "jpg", "thumbnail": "", "blurHash": "", "avgHueLight": "", "avgHueDark": "", "id": ""}, countryName="", imdbRatingValue=0.0, subtitles=[], ops={"rid": "00000000-0000-0000-0000-000000000000", "trace_id": ""}, hasResource=True, appointmentCnt=0, appointmentDate="", corner=""
    )

    try:
        stream_details_provider = StreamFilesDetail(moviebox_session, item)
        
        # Pour les films, season et episode sont 0. Pour les séries, ils sont requis.
        stream_metadata: StreamFilesMetadata = await stream_details_provider.get_modelled_content(
            season=season, episode=episode
        )

        all_streams = [
            StreamInfo(
                stream_url=str(s.url),
                resolution=s.resolutions,
                format=s.format
            ) for s in stream_metadata.streams
        ]

        best_stream_info = None
        if stream_metadata.best_stream_file:
            best_stream_info = StreamInfo(
                stream_url=str(stream_metadata.best_stream_file.url),
                resolution=stream_metadata.best_stream_file.resolutions,
                format=stream_metadata.best_stream_file.format
            )

        return StreamResponse(
            best_stream=best_stream_info,
            all_streams=all_streams
        )

    except Exception as e:
        print(f"Erreur lors de la récupération du stream: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during stream retrieval.")

# --- Point d'entrée pour le lancement local (non utilisé par Render) ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
