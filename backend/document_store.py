"""Gestion du stockage et de la recherche des documents par tenant"""
import os
import re
import logging
from typing import List, Dict, Tuple
from pathlib import Path
from sentence_transformers import SentenceTransformer
import numpy as np
import pickle
import json

logger = logging.getLogger(__name__)


class DocumentStore:
    """Gestionnaire de documents avec recherche sémantique par tenant"""
    
    def __init__(self, documents_base_path: str = "."):
        """
        Initialise le store de documents.
        
        Args:
            documents_base_path: Chemin de base vers les dossiers des tenants
        """
        logger.info("Initialisation du DocumentStore...")
        self.documents_base_path = Path(documents_base_path)
        logger.info(f"Chemin de base des documents: {self.documents_base_path.absolute()}")
        
        from backend.config import FORCE_TEXT_SEARCH_ONLY
        
        self.model = None  # Chargé de manière lazy
        self.model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
        self.use_semantic_search = not FORCE_TEXT_SEARCH_ONLY  # Flag pour savoir si on utilise la recherche sémantique
        self.tenant_documents: Dict[str, List[Dict]] = {}
        self.tenant_embeddings: Dict[str, np.ndarray] = {}
        self._load_all_documents()
        
        if FORCE_TEXT_SEARCH_ONLY:
            logger.info("Mode recherche textuelle uniquement activé (pas de modèle sémantique)")
        
        logger.info(f"DocumentStore initialisé avec {len(self.tenant_documents)} tenant(s)")
    
    def _ensure_model_loaded(self) -> bool:
        """
        Charge le modèle SentenceTransformer de manière lazy.
        
        Returns:
            True si le modèle est chargé, False si on doit utiliser le fallback textuel
        """
        # Si le mode texte uniquement est activé, ne pas charger le modèle
        if not self.use_semantic_search:
            return False
            
        if self.model is None:
            try:
                logger.info("Chargement du modèle SentenceTransformer (peut prendre quelques minutes la première fois)...")
                logger.info("Note: Si vous n'avez pas de connexion internet, une recherche textuelle simple sera utilisée")
                self.model = SentenceTransformer(self.model_name)
                logger.info("Modèle SentenceTransformer chargé avec succès")
                self.use_semantic_search = True
                # Recréer les embeddings si nécessaire
                if self.tenant_documents and not self.tenant_embeddings:
                    logger.info("Création des embeddings pour les documents existants...")
                    for tenant_id, documents in self.tenant_documents.items():
                        texts = [doc["content"] for doc in documents]
                        embeddings = self.model.encode(texts, convert_to_numpy=True)
                        self.tenant_embeddings[tenant_id] = embeddings
                return True
            except KeyboardInterrupt:
                # Si l'utilisateur annule le téléchargement
                logger.warning("Téléchargement du modèle interrompu par l'utilisateur")
                logger.warning("Utilisation de la recherche textuelle simple comme fallback")
                self.use_semantic_search = False
                self.model = None
                return False
            except (Exception, RuntimeError, ConnectionError, OSError) as e:
                # Capturer toutes les erreurs possibles (réseau, timeout, etc.)
                error_type = type(e).__name__
                logger.warning(f"Impossible de charger le modèle SentenceTransformer ({error_type}): {str(e)}")
                logger.warning("Utilisation de la recherche textuelle simple comme fallback")
                logger.info("La recherche textuelle fonctionnera mais sera moins précise que la recherche sémantique")
                self.use_semantic_search = False
                self.model = None
                return False
        return self.use_semantic_search
    
    def _text_search(self, tenant_id: str, query: str, top_k: int = 3) -> List[Dict]:
        """
        Recherche textuelle simple basée sur les mots-clés (fallback).
        
        Args:
            tenant_id: L'identifiant du tenant
            query: La requête de recherche
            top_k: Nombre de résultats à retourner
            
        Returns:
            Liste de documents pertinents avec leur score
        """
        if tenant_id not in self.tenant_documents:
            return []
        
        documents = self.tenant_documents[tenant_id]
        if len(documents) == 0:
            return []
        
        # Normaliser la requête (minuscules, supprimer la ponctuation)
        query_normalized = re.sub(r'[^\w\s]', ' ', query.lower())
        query_words = [w for w in query_normalized.split() if len(w) > 2]  # Ignorer les mots trop courts
        
        if not query_words:
            # Si pas de mots valides, chercher la requête complète
            query_words = [query.lower()]
        
        # Mots-clés importants qui doivent être présents pour être pertinent - STRICT
        important_keywords = {
            "résilier": ["résiliation", "résilier", "résil"],
            "sinistre": ["sinistre", "sinistres"],  # Plus strict - seulement "sinistre"
            "déclarer un sinistre": ["sinistre", "déclarer un sinistre", "déclaration de sinistre"],
            "rc pro": ["rc pro", "rc pro a", "rc pro b"],
            "exclusion": ["exclusion", "exclusions"]
        }
        
        # Identifier les mots-clés de la requête
        query_keywords_found = []
        query_lower = query.lower()
        for keyword, synonyms in important_keywords.items():
            if keyword in query_lower:
                query_keywords_found.append((keyword, synonyms))
        
        results = []
        for doc in documents:
            content_normalized = re.sub(r'[^\w\s]', ' ', doc["content"].lower())
            content_words = set(content_normalized.split())
            content_lower = doc["content"].lower()
            
            # Vérifier la présence des mots-clés importants EN PREMIER - VÉRIFICATION STRICTE
            keyword_match = True
            if query_keywords_found:
                # Si la requête contient un mot-clé spécifique, vérifier qu'il est dans le document
                keyword_match = False
                for keyword, synonyms in query_keywords_found:
                    # Pour "sinistre", être encore plus strict - le document DOIT contenir "sinistre"
                    if keyword == "sinistre" or "sinistre" in keyword:
                        if "sinistre" in content_lower:
                            keyword_match = True
                            break
                    else:
                        # Pour les autres mots-clés, utiliser les synonymes
                        if any(syn in content_lower for syn in synonyms):
                            keyword_match = True
                            break
                # Si aucun mot-clé n'est trouvé, ce document n'est PAS pertinent - SKIP
                if not keyword_match:
                    logger.info(f"Document '{doc.get('filename', 'unknown')}' ne contient pas le mot-clé requis - ignoré")
                    continue
            
            # Compter le nombre de mots de la requête trouvés dans le document
            matches = sum(1 for word in query_words if word in content_words)
            
            # Vérifier aussi si la requête complète est dans le contenu (match exact)
            query_full = query.lower()
            exact_match = query_full in content_lower
            
            if matches > 0 or exact_match:
                # Score basé sur le nombre de correspondances
                if exact_match:
                    score = 1.0  # Score maximum pour match exact
                else:
                    score = matches / len(query_words) if query_words else 0
                    # Bonus si plusieurs mots correspondent
                    if matches == len(query_words):
                        score = min(0.9, score * 1.3)
                    # Bonus si les mots-clés importants correspondent
                    if keyword_match and query_keywords_found:
                        score = min(1.0, score * 1.2)
                
                results.append({
                    "document": doc,
                    "score": score,
                    "content": doc["content"],
                    "filename": doc["filename"]
                })
        
        # Trier par score décroissant
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # Retourner les top_k résultats avec un score minimum
        # Si les mots-clés importants correspondent, seuil plus bas (0.3)
        # Sinon, seuil plus élevé (0.4) pour éviter les faux positifs
        query_lower = query.lower()
        has_important_keyword = any(kw in query_lower for kw in ["résilier", "sinistre", "rc pro", "exclusion"])
        threshold = 0.3 if has_important_keyword else 0.4
        filtered_results = [r for r in results[:top_k] if r["score"] >= threshold]
        
        return filtered_results
    
    def _load_all_documents(self):
        """Charge tous les documents de tous les tenants"""
        from backend.config import TENANT_DOCUMENTS_PATH
        
        logger.info(f"Chargement des documents pour {len(TENANT_DOCUMENTS_PATH)} tenant(s)...")
        for tenant_id, tenant_path in TENANT_DOCUMENTS_PATH.items():
            tenant_dir = self.documents_base_path / tenant_path
            logger.info(f"Recherche de documents pour {tenant_id} dans {tenant_dir}")
            if tenant_dir.exists():
                logger.info(f"Dossier trouvé: {tenant_dir.absolute()}")
                self._load_tenant_documents(tenant_id, tenant_dir)
            else:
                logger.warning(f"Dossier non trouvé: {tenant_dir.absolute()}")
    
    def _load_tenant_documents(self, tenant_id: str, tenant_dir: Path):
        """Charge les documents d'un tenant spécifique"""
        documents = []
        
        txt_files = list(tenant_dir.glob("*.txt"))
        logger.info(f"Trouvé {len(txt_files)} fichier(s) .txt pour {tenant_id}")
        
        for file_path in txt_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        documents.append({
                            "filename": file_path.name,
                            "content": content,
                            "tenant": tenant_id
                        })
                        logger.info(f"Document chargé: {file_path.name}")
            except Exception as e:
                logger.error(f"Erreur lors du chargement de {file_path}: {e}")
        
        if documents:
            self.tenant_documents[tenant_id] = documents
            logger.info(f"Documents chargés pour {tenant_id} (embeddings créés lors de la première recherche)")
        else:
            logger.warning(f"Aucun document trouvé pour {tenant_id}")
    
    def search(self, tenant_id: str, query: str, top_k: int = 3) -> List[Dict]:
        """
        Recherche dans les documents d'un tenant spécifique.
        
        Utilise la recherche sémantique si disponible, sinon utilise une recherche textuelle simple.
        
        Args:
            tenant_id: L'identifiant du tenant (tenantA ou tenantB)
            query: La requête de recherche
            top_k: Nombre de résultats à retourner
            
        Returns:
            Liste de documents pertinents avec leur score de similarité
        """
        if tenant_id not in self.tenant_documents:
            return []
        
        documents = self.tenant_documents[tenant_id]
        if len(documents) == 0:
            return []
        
        # Essayer de charger le modèle, utiliser le fallback si échec
        if not self._ensure_model_loaded():
            logger.info("Utilisation de la recherche textuelle simple")
            return self._text_search(tenant_id, query, top_k)
        
        # Recherche sémantique avec embeddings
        try:
            # Créer les embeddings si nécessaire
            if tenant_id not in self.tenant_embeddings:
                logger.info(f"Création des embeddings pour {tenant_id}...")
                texts = [doc["content"] for doc in documents]
                embeddings = self.model.encode(texts, convert_to_numpy=True)
                self.tenant_embeddings[tenant_id] = embeddings
            
            embeddings = self.tenant_embeddings[tenant_id]
            
            # Encoder la requête
            query_embedding = self.model.encode(query, convert_to_numpy=True)
            
            # Calculer la similarité cosinus
            similarities = np.dot(embeddings, query_embedding) / (
                np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_embedding)
            )
            
            # Obtenir les top_k résultats
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                # Seuil de similarité plus élevé pour éviter les faux positifs
                # 0.5 est un seuil raisonnable pour la recherche sémantique
                if similarities[idx] > 0.5:  # Seuil de similarité minimum augmenté
                    results.append({
                        "document": documents[idx],
                        "score": float(similarities[idx]),
                        "content": documents[idx]["content"],
                        "filename": documents[idx]["filename"]
                    })
            
            return results
        except Exception as e:
            logger.warning(f"Erreur lors de la recherche sémantique, utilisation du fallback textuel: {e}")
            return self._text_search(tenant_id, query, top_k)
    
    def get_all_documents(self, tenant_id: str) -> List[Dict]:
        """
        Retourne tous les documents d'un tenant.
        
        Args:
            tenant_id: L'identifiant du tenant
            
        Returns:
            Liste de tous les documents du tenant
        """
        return self.tenant_documents.get(tenant_id, [])


# Instance globale du document store
document_store = DocumentStore()

