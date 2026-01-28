"""Configuration de l'application"""
import os
from typing import Dict

# Clés API pour les tenants
TENANT_KEYS: Dict[str, str] = {
    "tenantA_key": "tenantA",
    "tenantB_key": "tenantB"
}

# Chemins des documents par tenant
TENANT_DOCUMENTS_PATH: Dict[str, str] = {
    "tenantA": "tenantA",
    "tenantB": "tenantB"
}

# Port du serveur FastAPI
API_PORT = 8000
API_HOST = "127.0.0.1"  # Utiliser localhost pour le développement local

# Option pour forcer l'utilisation de la recherche textuelle (sans modèle)
# Mettez à True si vous n'avez pas de connexion internet ou si le téléchargement échoue
FORCE_TEXT_SEARCH_ONLY = False

