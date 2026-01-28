"""Gestion de l'authentification multi-tenant"""
from fastapi import Header, HTTPException, status
from typing import Optional
from backend.config import TENANT_KEYS


def get_tenant_from_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-KEY")) -> str:
    """
    Extrait le tenant depuis le header X-API-KEY.
    
    Args:
        x_api_key: La clé API depuis le header HTTP
        
    Returns:
        Le nom du tenant (tenantA ou tenantB)
        
    Raises:
        HTTPException: Si la clé API est invalide ou manquante
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-API-KEY manquant"
        )
    
    tenant = TENANT_KEYS.get(x_api_key)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide"
        )
    
    return tenant

