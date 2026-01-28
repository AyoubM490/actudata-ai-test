"""API FastAPI principale pour le système multi-tenant"""
import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("Démarrage de l'application FastAPI...")

try:
    from backend.auth import get_tenant_from_api_key
    from backend.document_store import document_store
    from backend.answer_generator import answer_generator
    from backend.config import API_PORT, API_HOST
    logger.info("Modules importés avec succès")
except Exception as e:
    logger.error(f"Erreur lors de l'importation des modules: {e}")
    raise

app = FastAPI(
    title="SaaS Multi-Tenant RAG API",
    description="API pour recherche dans les documents par tenant",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    """Modèle pour les requêtes de recherche"""
    query: str
    top_k: Optional[int] = 3


class DocumentResult(BaseModel):
    """Modèle pour un résultat de document"""
    filename: str
    content: str
    score: float


class QueryResponse(BaseModel):
    """Modèle pour la réponse de recherche"""
    tenant: str
    query: str
    answer: str  # Réponse textuelle générée
    found: bool
    message: Optional[str] = None


@app.get("/")
async def root():
    """Endpoint de santé"""
    return {
        "message": "SaaS Multi-Tenant RAG API",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Endpoint de santé détaillé"""
    return {
        "status": "healthy",
        "tenants_loaded": list(document_store.tenant_documents.keys())
    }


@app.post("/search", response_model=QueryResponse)
async def search_documents(
    request: QueryRequest,
    tenant_id: str = Depends(get_tenant_from_api_key)
):
    """
    Recherche dans les documents du tenant connecté.
    
    Le tenant est déterminé automatiquement depuis le header X-API-KEY.
    Les résultats sont strictement limités aux documents du tenant connecté.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La requête ne peut pas être vide"
        )
    
    # Recherche dans les documents du tenant uniquement
    results = document_store.search(tenant_id, request.query.strip(), request.top_k)
    
    if not results:
        return QueryResponse(
            tenant=tenant_id,
            query=request.query,
            answer=f"Je n'ai pas trouvé d'information pertinente dans les documents du client {tenant_id} pour répondre à votre question : '{request.query}'.",
            found=False,
            message=f"Aucune information pertinente trouvée dans les documents du client {tenant_id} pour cette requête."
        )
    
    # Générer une réponse textuelle basée sur les documents trouvés
    answer = answer_generator.generate_answer(
        query=request.query,
        documents=results,
        tenant_id=tenant_id
    )
    
    # Vérifier si la réponse indique qu'aucune information n'a été trouvée
    # (le générateur peut retourner un message d'absence d'info même avec des résultats)
    found = not any(phrase in answer.lower() for phrase in [
        "n'ai pas trouvé",
        "ne contiennent pas",
        "aucune information"
    ])
    
    return QueryResponse(
        tenant=tenant_id,
        query=request.query,
        answer=answer,
        found=found,
        message=None if found else "Aucune information pertinente trouvée."
    )


@app.get("/documents", response_model=List[DocumentResult])
async def list_documents(
    tenant_id: str = Depends(get_tenant_from_api_key)
):
    """
    Liste tous les documents disponibles pour le tenant connecté.
    """
    documents = document_store.get_all_documents(tenant_id)
    
    return [
        DocumentResult(
            filename=doc["filename"],
            content=doc["content"],
            score=1.0
        )
        for doc in documents
    ]


@app.on_event("startup")
async def startup_event():
    """Événement au démarrage de l'application"""
    logger.info("=" * 60)
    logger.info("Application démarrée avec succès!")
    logger.info(f"Tenants chargés: {list(document_store.tenant_documents.keys())}")
    logger.info(f"API disponible sur http://{API_HOST}:{API_PORT}")
    logger.info("=" * 60)

if __name__ == "__main__":
    logger.info(f"Démarrage du serveur sur {API_HOST}:{API_PORT}")
    uvicorn.run(app, host=API_HOST, port=API_PORT, log_level="info")

