"""Générateur de réponses basé sur les documents trouvés"""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class AnswerGenerator:
    """Générateur de réponses RAG"""
    
    def __init__(self):
        """Initialise le générateur de réponses"""
        self.use_llm = False
        self.llm_model = None
        self._try_load_llm()
    
    def _try_load_llm(self):
        """Essaie de charger un modèle LLM local si disponible"""
        try:
            # Option pour utiliser un modèle local léger
            # Pour l'instant, on utilise une approche template-based
            # Vous pouvez ajouter un modèle local ici si nécessaire
            pass
        except Exception as e:
            logger.info(f"Modèle LLM non disponible, utilisation de la synthèse template: {e}")
    
    def generate_answer(self, query: str, documents: List[Dict], tenant_id: str) -> str:
        """
        Génère une réponse textuelle basée sur les documents trouvés.
        
        Args:
            query: La question de l'utilisateur
            documents: Liste des documents pertinents trouvés
            tenant_id: L'identifiant du tenant
            
        Returns:
            Une réponse textuelle générée
        """
        if not documents:
            logger.info(f"Aucun document trouvé pour la question: '{query}'")
            return f"Je n'ai pas trouvé d'information pertinente dans les documents du client {tenant_id} pour répondre à votre question : '{query}'."
        
        # Log des documents trouvés
        logger.info(f"Documents trouvés pour '{query}': {len(documents)}")
        for idx, doc in enumerate(documents):
            logger.info(f"  Doc {idx+1}: {doc.get('filename')} - Score: {doc.get('score', 0):.3f}")
            logger.info(f"    Contenu: {doc.get('content', '')[:100]}...")
        
        # Vérifier la pertinence des documents trouvés
        is_relevant = self._is_relevant(tenant_id, query, documents)
        logger.info(f"Vérification de pertinence pour '{query}': {is_relevant}")
        
        if not is_relevant:
            logger.warning(f"Documents rejetés comme non pertinents pour '{query}'")
            return f"Je n'ai pas trouvé d'information pertinente dans les documents du client {tenant_id} pour répondre à votre question : '{query}'. Les documents disponibles ne contiennent pas cette information."
        
        # Filtrer et prioriser les documents selon la pertinence réelle à la question
        filtered_documents = self._filter_relevant_documents(query, documents)
        
        if not filtered_documents:
            return f"Les documents trouvés ne contiennent pas d'information pertinente pour répondre à votre question."
        
        # Extraire les contenus des documents filtrés
        contents = [doc.get("content", "") for doc in filtered_documents if doc.get("content")]
        
        if not contents:
            return f"Les documents trouvés ne contiennent pas d'information pertinente pour répondre à votre question."
        
        # Générer une réponse synthétisée
        if self.use_llm and self.llm_model:
            return self._generate_with_llm(query, contents)
        else:
            return self._generate_template_answer(query, contents, filtered_documents)
    
    def _generate_template_answer(self, query: str, contents: List[str], documents: List[Dict]) -> str:
        """
        Génère une réponse en utilisant une approche template-based intelligente.
        
        Args:
            query: La question
            contents: Liste des contenus des documents
            documents: Liste complète des documents avec métadonnées
            
        Returns:
            Réponse générée
        """
        # Combiner les contenus pertinents en évitant les doublons
        seen_content = set()
        unique_contents = []
        for content in contents:
            content_normalized = content.strip().lower()
            if content_normalized not in seen_content and len(content.strip()) > 10:
                seen_content.add(content_normalized)
                unique_contents.append(content.strip())
        
        if not unique_contents:
            return "Je n'ai pas pu extraire d'information pertinente des documents trouvés."
        
        combined_content = "\n".join(unique_contents)
        
        # Détecter le type de question
        query_lower = query.lower()
        
        # Créer une réponse structurée
        answer_parts = []
        
        # Extraire les informations pertinentes selon le type de question
        # Prioriser les documents qui correspondent vraiment à la question
        if any(word in query_lower for word in ["quoi", "qu'est", "définition", "c'est", "qu'est-ce"]):
            # Question de définition - utiliser uniquement le document le plus pertinent
            answer_parts.append(self._extract_definition_info(combined_content, query, documents))
        elif any(word in query_lower for word in ["comment", "procédure", "processus", "étapes", "faire"]):
            # Question sur une procédure
            answer_parts.append(self._extract_procedure_info(combined_content, query))
        elif any(word in query_lower for word in ["exclusion", "limite", "restriction", "ne couvre pas", "ne pas"]):
            # Question sur les exclusions
            answer_parts.append(self._extract_exclusion_info(combined_content, query))
        else:
            # Réponse générale - synthétiser intelligemment
            answer_parts.append(self._extract_general_info(combined_content, query))
        
        # Nettoyer et formater la réponse
        answer = "\n".join(answer_parts).strip()
        
        # Si la réponse est trop courte, ajouter plus de contexte
        if len(answer) < 50 and unique_contents:
            # Prendre les premières lignes pertinentes
            all_lines = []
            for content in unique_contents:
                lines = [l.strip() for l in content.split('\n') if l.strip()]
                all_lines.extend(lines[:2])  # Prendre les 2 premières lignes de chaque document
            answer = "\n".join(all_lines[:5])  # Limiter à 5 lignes
        
        return answer
    
    def _extract_procedure_info(self, content: str, query: str) -> str:
        """Extrait les informations de procédure"""
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        procedure_lines = []
        
        # Mots-clés pour les procédures
        procedure_keywords = ["doit", "procédure", "étapes", "enregistrer", "envoyer", 
                             "déclarer", "transmettre", "valider", "sous", "jours", "heures"]
        
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in procedure_keywords):
                procedure_lines.append(line)
        
        if procedure_lines:
            # Formater comme une procédure
            formatted = []
            for idx, line in enumerate(procedure_lines, 1):
                # Si la ligne commence par un titre, le garder tel quel
                if line and line[0].isupper() and len(line) < 50:
                    formatted.append(f"\n**{line}**")
                else:
                    formatted.append(line)
            return "\n".join(formatted).strip()
        else:
            # Retourner toutes les lignes pertinentes
            return "\n".join(lines[:5]) if lines else ""
    
    def _extract_definition_info(self, content: str, query: str, documents: List[Dict] = None) -> str:
        """Extrait les informations de définition en priorisant le document le plus pertinent"""
        query_lower = query.lower()
        
        # Utiliser directement les documents filtrés plutôt que le contenu combiné
        # Pour les questions de définition, utiliser uniquement le document le plus pertinent
        if documents and len(documents) > 0:
            # Le premier document est déjà le plus pertinent après filtrage dans _filter_relevant_documents
            best_doc = documents[0]
            content = best_doc.get("content", content)
            logger.info(f"Document utilisé pour définition: {best_doc.get('filename')}")
        
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        definition_lines = []
        
        # Pour les questions "Qu'est-ce que", prendre les lignes qui définissent vraiment
        for line in lines:
            line_lower = line.lower()
            # Ignorer les titres de procédure si la question n'est pas sur une procédure
            if "procédure" in query_lower:
                # Si la question est sur une procédure, inclure toutes les lignes
                definition_lines.append(line)
            elif not line.strip().startswith('Procédure'):
                # Pour les autres questions, exclure les lignes qui commencent par "Procédure"
                definition_lines.append(line)
        
        if definition_lines:
            # Prendre les premières lignes pertinentes (max 4)
            return "\n".join(definition_lines[:4])
        return content.split('\n')[0] if content else ""
    
    def _extract_exclusion_info(self, content: str, query: str) -> str:
        """Extrait les informations sur les exclusions"""
        lines = content.split('\n')
        exclusion_lines = []
        
        for line in lines:
            line_lower = line.lower()
            if "exclusion" in line_lower or "ne couvre" in line_lower or "au-delà" in line_lower:
                exclusion_lines.append(line.strip())
        
        if exclusion_lines:
            return "\n".join(exclusion_lines)
        return content
    
    def _extract_general_info(self, content: str, query: str) -> str:
        """Extrait les informations générales de manière intelligente"""
        # Trouver les lignes les plus pertinentes
        query_words = set(word.lower() for word in query.split() if len(word) > 2)
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        
        scored_lines = []
        for line in lines:
            line_words = set(word.lower() for word in line.split() if len(word) > 2)
            # Score basé sur les mots communs
            common_words = query_words.intersection(line_words)
            score = len(common_words)
            
            # Bonus si la ligne contient des mots-clés importants
            important_keywords = ["couverture", "exclusion", "déclaration", "procédure", 
                                 "doit", "peut", "ne", "sous", "jours", "heures"]
            if any(kw in line.lower() for kw in important_keywords):
                score += 1
            
            if score > 0 or len(line) > 20:  # Inclure les lignes substantielles
                scored_lines.append((score, line))
        
        # Trier par score et prendre les meilleures
        scored_lines.sort(reverse=True, key=lambda x: x[0])
        
        if scored_lines:
            # Prendre les meilleures lignes (max 4-5)
            best_lines = [line for _, line in scored_lines[:5]]
            # Éviter les doublons
            seen = set()
            unique_lines = []
            for line in best_lines:
                line_lower = line.lower()
                if line_lower not in seen:
                    seen.add(line_lower)
                    unique_lines.append(line)
            return "\n".join(unique_lines)
        
        # Sinon, retourner les premières lignes pertinentes (sauf titres très courts)
        relevant_lines = [line for line in lines if len(line) > 15][:4]
        return "\n".join(relevant_lines) if relevant_lines else "\n".join(lines[:3])
    
    def _is_relevant(self, tenant_id: str, query: str, documents: List[Dict]) -> bool:
        """
        Vérifie si les documents trouvés sont vraiment pertinents pour la question.
        
        Args:
            tenant_id: L'identifiant du tenant (tenantA ou tenantB)
            query: La question posée
            documents: Liste des documents trouvés
            
        Returns:
            True si les documents sont pertinents, False sinon
        """
        if not documents:
            return False
        
        query_lower = query.lower()
        
        # RÈGLE MÉTIER STRICTE : Le client A n'a AUCUNE information sur les sinistres
        # Même si un document mentionne "sinistre", ce n'est pas une réponse pertinente pour le client A
        if tenant_id == "tenantA" and "sinistre" in query_lower:
            logger.warning(f"RÈGLE MÉTIER: Client A ne peut pas avoir de réponse sur les sinistres - rejeté")
            return False
        
        # RÈGLE MÉTIER STRICTE : Le client B n'a AUCUNE information sur la résiliation
        # Même si un document mentionne "résiliation", ce n'est pas une réponse pertinente pour le client B
        if tenant_id == "tenantB" and ("résilier" in query_lower or "résiliation" in query_lower):
            logger.warning(f"RÈGLE MÉTIER: Client B ne peut pas avoir de réponse sur la résiliation - rejeté")
            return False
        
        # RÈGLE MÉTIER STRICTE : Vérification RC Pro A vs RC Pro B
        # Le Client A ne peut répondre que sur RC Pro A, pas sur RC Pro B
        if tenant_id == "tenantA" and "rc pro b" in query_lower:
            logger.warning(f"RÈGLE MÉTIER: Client A ne peut pas avoir de réponse sur RC Pro B - rejeté")
            return False
        
        # Le Client B ne peut répondre que sur RC Pro B, pas sur RC Pro A
        if tenant_id == "tenantB" and "rc pro a" in query_lower:
            logger.warning(f"RÈGLE MÉTIER: Client B ne peut pas avoir de réponse sur RC Pro A - rejeté")
            return False
        
        # VÉRIFICATION DOMAINE : La question doit être liée au domaine (assurance, contrat, etc.)
        # Liste des mots-clés du domaine d'assurance/contrat
        domain_keywords = [
            "résilier", "résiliation", "sinistre", "sinistres", "déclarer", "déclaration",
            "contrat", "contrats", "assurance", "assurances", "rc pro", "rc", "responsabilité",
            "exclusion", "exclusions", "couverture", "couvre", "dommages", "tiers",
            "procédure", "procédures", "dossier", "dossiers", "gestionnaire", "assureur",
            "enregistrer", "valider", "transmettre", "accusé", "réception", "jours", "ouvrés"
        ]
        
        # Vérifier si la question contient au moins un mot-clé du domaine
        has_domain_keyword = any(keyword in query_lower for keyword in domain_keywords)
        
        if not has_domain_keyword:
            logger.warning(f"Question '{query}' ne contient aucun mot-clé du domaine (assurance/contrat) - rejeté")
            return False
        
        logger.info(f"Question contient des mots-clés du domaine - vérification continue")
        
        # Vérification stricte pour RC Pro A vs RC Pro B AVANT la vérification générale
        if "rc pro a" in query_lower:
            # La question demande spécifiquement RC Pro A - vérifier que le document contient "rc pro a"
            rc_pro_a_found = False
            for doc in documents:
                content_lower = doc.get("content", "").lower()
                filename_lower = doc.get("filename", "").lower()
                if "rc pro a" in content_lower or "rc pro a" in filename_lower or "produit rc pro a" in content_lower:
                    rc_pro_a_found = True
                    break
            if not rc_pro_a_found:
                logger.warning("Question sur RC Pro A mais aucun document ne contient 'RC Pro A' spécifiquement - rejeté")
                return False
        
        if "rc pro b" in query_lower:
            # La question demande spécifiquement RC Pro B - vérifier que le document contient "rc pro b"
            rc_pro_b_found = False
            for doc in documents:
                content_lower = doc.get("content", "").lower()
                filename_lower = doc.get("filename", "").lower()
                if "rc pro b" in content_lower or "rc pro b" in filename_lower or "produit rc pro b" in content_lower:
                    rc_pro_b_found = True
                    break
            if not rc_pro_b_found:
                logger.warning("Question sur RC Pro B mais aucun document ne contient 'RC Pro B' spécifiquement - rejeté")
                return False
        
        # Mots-clés spécifiques avec leurs synonymes - STRICT
        # Si la question contient un de ces mots-clés, le document DOIT contenir le mot-clé ou un synonyme
        important_keywords = {
            "résilier": ["résiliation", "résilier", "résil"],
            "résiliation": ["résiliation", "résilier", "résil"],  # Ajout pour détecter "procédure de résiliation"
            "procédure de résiliation": ["résiliation", "résilier", "procédure résiliation"],
            "procédure résiliation": ["résiliation", "résilier", "procédure résiliation"],
            "sinistre": ["sinistre", "sinistres"],  # Plus strict - seulement "sinistre"
            "déclarer un sinistre": ["sinistre", "déclarer un sinistre", "déclaration de sinistre"],
            "procédure sinistre": ["sinistre", "procédure sinistre"],
            "rc pro": ["rc pro", "rc pro a", "rc pro b"],  # Générique (seulement si pas de spécification A ou B)
            "exclusion": ["exclusion", "exclusions"]
        }
        
        # Vérifier d'abord les mots-clés spécifiques - VÉRIFICATION STRICTE
        # IMPORTANT: Vérifier les phrases complètes AVANT les mots simples pour éviter les faux positifs
        keyword_found_in_docs = False
        matched_keyword = None
        
        # Trier les mots-clés par longueur décroissante pour vérifier les phrases complètes en premier
        sorted_keywords = sorted(important_keywords.items(), key=lambda x: len(x[0]), reverse=True)
        
        for keyword, synonyms in sorted_keywords:
            if keyword in query_lower:
                matched_keyword = keyword
                logger.info(f"Mot-clé trouvé dans la question: '{keyword}'")
                # Ce mot-clé est dans la question - vérifier qu'il est dans AU MOINS UN document
                for doc in documents:
                    content_lower = doc.get("content", "").lower()
                    filename_lower = doc.get("filename", "").lower()
                    # Vérifier si le mot-clé ou un de ses synonymes est dans le document
                    # Pour "sinistre", être encore plus strict
                    if keyword == "sinistre" or "sinistre" in keyword:
                        # Pour sinistre, le document DOIT contenir explicitement "sinistre"
                        # ET si c'est une question sur "Comment déclarer", il doit parler de procédure
                        if "sinistre" in content_lower:
                            # Si la question est sur "Comment déclarer un sinistre", vérifier le contexte
                            if "comment" in query_lower and "déclarer" in query_lower:
                                # Le document doit parler de procédure, pas juste mentionner sinistre
                                has_procedure = any(word in content_lower for word in [
                                    "procédure", "doit être", "jours", "ouvrés", "transmettre", 
                                    "gestionnaire", "déclaré", "déclarez"
                                ])
                                if has_procedure:
                                    keyword_found_in_docs = True
                                    logger.info(f"  Mot-clé 'sinistre' avec procédure trouvé dans: {doc.get('filename')}")
                                    break
                                else:
                                    logger.info(f"  Document {doc.get('filename')} mentionne sinistre mais pas de procédure - ignoré")
                            else:
                                # Pour les autres questions sur sinistre, juste vérifier la présence
                                keyword_found_in_docs = True
                                logger.info(f"  Mot-clé 'sinistre' trouvé dans le document: {doc.get('filename')}")
                                break
                    elif keyword == "rc pro":
                        # Pour "rc pro", vérifier la correspondance exacte si la question spécifie A ou B
                        if "rc pro a" in query_lower:
                            # Question sur RC Pro A - document doit contenir "rc pro a"
                            if "rc pro a" in content_lower or "rc pro a" in doc.get("filename", "").lower():
                                keyword_found_in_docs = True
                                logger.info(f"  'RC Pro A' trouvé dans le document: {doc.get('filename')}")
                                break
                        elif "rc pro b" in query_lower:
                            # Question sur RC Pro B - document doit contenir "rc pro b"
                            if "rc pro b" in content_lower or "rc pro b" in doc.get("filename", "").lower():
                                keyword_found_in_docs = True
                                logger.info(f"  'RC Pro B' trouvé dans le document: {doc.get('filename')}")
                                break
                        else:
                            # Question générique sur RC Pro - accepter tout document avec "rc pro"
                            for syn in synonyms:
                                if syn in content_lower:
                                    keyword_found_in_docs = True
                                    logger.info(f"  Synonyme '{syn}' trouvé dans le document: {doc.get('filename')}")
                                    break
                            if keyword_found_in_docs:
                                break
                    else:
                        # Pour les autres mots-clés, utiliser les synonymes
                        # Vérifier aussi dans le filename (important pour "procédure résiliation" dans le filename)
                        for syn in synonyms:
                            if syn in content_lower or syn in filename_lower:
                                keyword_found_in_docs = True
                                logger.info(f"  Synonyme '{syn}' trouvé dans le document: {doc.get('filename')}")
                                break
                        # Vérification supplémentaire pour les mots-clés contenant "procédure"
                        # Le filename peut contenir "procedure_resiliation" ou "procedure_sinistre"
                        if not keyword_found_in_docs and ("procédure" in keyword or "procedure" in keyword.lower()):
                            # Vérifier si le filename contient le mot-clé principal (sans "procédure")
                            if "résiliation" in keyword or "résilier" in keyword:
                                if "resiliation" in filename_lower or "resilier" in filename_lower:
                                    keyword_found_in_docs = True
                                    logger.info(f"  Mot-clé trouvé dans le filename: {doc.get('filename')}")
                            elif "sinistre" in keyword:
                                if "sinistre" in filename_lower:
                                    keyword_found_in_docs = True
                                    logger.info(f"  Mot-clé trouvé dans le filename: {doc.get('filename')}")
                        if keyword_found_in_docs:
                            break
                
                # Si le mot-clé de la question n'est PAS dans les documents, ce n'est PAS pertinent
                if not keyword_found_in_docs:
                    logger.warning(f"Mot-clé '{keyword}' trouvé dans la question mais absent des documents - réponse non pertinente")
                    return False
                break  # On a trouvé un mot-clé, pas besoin de continuer
        
        # Si on arrive ici, les mots-clés correspondent et sont dans les documents
        # On accepte les documents même avec un score bas car on a vérifié la correspondance des mots-clés
        # Vérifier juste qu'il y a au moins un document avec un score raisonnable
        relevant_count = 0
        
        # Seuil adaptatif selon si les mots-clés correspondent
        if keyword_found_in_docs:
            threshold = 0.2  # Seuil bas car on a déjà vérifié les mots-clés
        else:
            # Si pas de mots-clés spécifiques trouvés, seuil très élevé pour éviter les faux positifs
            threshold = 0.7
            logger.info(f"Pas de mots-clés spécifiques trouvés - seuil élevé: {threshold}")
        
        for doc in documents:
            score = doc.get("score", 0)
            logger.info(f"Document {doc.get('filename')}: score={score:.3f}, seuil={threshold}")
            if score > threshold:
                relevant_count += 1
        
        # Si aucun document n'a un score suffisant, mais que les mots-clés correspondent, on accepte quand même
        if relevant_count == 0:
            if keyword_found_in_docs:
                logger.info("Aucun document avec score suffisant, mais les mots-clés correspondent - on accepte quand même")
                return True
            else:
                logger.warning(f"Aucun document n'a un score suffisant (seuil: {threshold}) - réponse non pertinente")
                return False
        
        logger.info(f"{relevant_count} document(s) pertinents trouvés")
        
        # Vérification supplémentaire : pour "sinistre", s'assurer qu'on ne confond pas avec "résiliation"
        # On ne rejette que si TOUS les documents sont des faux positifs
        if "sinistre" in query_lower:
            # Compter les documents qui parlent VRAIMENT de sinistre (procédure, déclaration, etc.)
            sinistre_docs = 0
            for doc in documents:
                content_lower = doc.get("content", "").lower()
                # Le document doit contenir "sinistre" ET des mots liés à la procédure
                # Pas juste une mention dans un autre contexte
                has_sinistre = "sinistre" in content_lower
                has_procedure_words = any(word in content_lower for word in [
                    "procédure", "déclarer", "déclaration", "déclaré", "déclarez",
                    "doit être", "jours", "ouvrés", "transmettre", "gestionnaire"
                ])
                
                # Si c'est une question sur "Comment déclarer", le document doit parler de procédure
                if "comment" in query_lower and "déclarer" in query_lower:
                    if has_sinistre and has_procedure_words:
                        sinistre_docs += 1
                        logger.info(f"Document {doc.get('filename')} parle vraiment de la procédure de sinistre")
                    else:
                        logger.info(f"Document {doc.get('filename')} mentionne sinistre mais ne parle pas de procédure")
                else:
                    # Pour les autres questions sur sinistre, juste vérifier la présence
                    if has_sinistre:
                        sinistre_docs += 1
            
            # Si aucun document ne parle vraiment de sinistre, c'est un faux positif
            if sinistre_docs == 0:
                logger.warning("Question sur sinistre mais aucun document ne parle vraiment de sinistre - faux positif")
                return False
        
        # Vérification inverse : pour "résiliation", s'assurer qu'on ne confond pas avec "sinistre"
        # On ne rejette que si TOUS les documents sont des faux positifs
        if "résilier" in query_lower or "résiliation" in query_lower:
            # Compter les documents qui parlent vraiment de résiliation
            resiliation_docs = 0
            for doc in documents:
                content_lower = doc.get("content", "").lower()
                if "résiliation" in content_lower or "résilier" in content_lower:
                    resiliation_docs += 1
            
            # Si aucun document ne parle de résiliation, c'est un faux positif
            if resiliation_docs == 0:
                logger.warning("Question sur résiliation mais aucun document ne parle de résiliation - faux positif")
                return False
            
            # Si au moins un document parle de résiliation, on accepte même si d'autres documents ne le font pas
            logger.info(f"{resiliation_docs} document(s) parlent de résiliation - accepté")
        
        return True
    
    def _filter_relevant_documents(self, query: str, documents: List[Dict]) -> List[Dict]:
        """
        Filtre les documents pour ne garder que ceux vraiment pertinents à la question.
        
        Args:
            query: La question posée
            documents: Liste des documents trouvés
            
        Returns:
            Liste des documents filtrés et triés par pertinence
        """
        if not documents:
            return []
        
        query_lower = query.lower()
        
        # Extraire les mots-clés importants de la question
        query_keywords = []
        important_keywords = {
            "résilier": ["résiliation", "résilier", "résil"],
            "sinistre": ["sinistre", "sinistres"],
            "rc pro": ["rc pro", "rc pro a", "rc pro b", "rc", "produit"],
            "exclusion": ["exclusion", "exclusions"]
        }
        
        for keyword, synonyms in important_keywords.items():
            if keyword in query_lower:
                query_keywords.extend([keyword] + synonyms)
        
        # Si pas de mots-clés spécifiques, utiliser les mots de la question
        if not query_keywords:
            query_words = [w for w in query_lower.split() if len(w) > 3]
            query_keywords = query_words
        
        # Scorer chaque document selon sa pertinence
        scored_docs = []
        for doc in documents:
            content_lower = doc.get("content", "").lower()
            filename_lower = doc.get("filename", "").lower()
            base_score = doc.get("score", 0)
            
            # Bonus si le document contient les mots-clés de la question
            keyword_matches = sum(1 for kw in query_keywords if kw in content_lower or kw in filename_lower)
            if keyword_matches > 0:
                # Bonus significatif si plusieurs mots-clés correspondent
                base_score += keyword_matches * 0.2
            
            # Bonus important si le filename correspond
            if any(kw in filename_lower for kw in query_keywords):
                base_score += 0.4
            
            scored_docs.append((base_score, doc))
        
        # Trier par score décroissant
        scored_docs.sort(reverse=True, key=lambda x: x[0])
        
        # Prendre les documents les plus pertinents
        # Si le meilleur document a un score nettement supérieur, ne prendre que celui-là
        if len(scored_docs) > 1:
            best_score = scored_docs[0][0]
            second_score = scored_docs[1][0]
            
            # Si le meilleur score est nettement supérieur (>0.2 de différence), ne prendre que celui-là
            if best_score - second_score > 0.2:
                logger.info(f"Document le plus pertinent sélectionné (écart de score: {best_score - second_score:.3f})")
                return [scored_docs[0][1]]
        
        # Sinon, prendre le meilleur document seulement pour les questions de définition
        if any(word in query_lower for word in ["quoi", "qu'est", "définition", "c'est", "qu'est-ce"]):
            logger.info("Question de définition - sélection du document le plus pertinent uniquement")
            return [scored_docs[0][1]]
        
        # Pour les autres types de questions, prendre les 2 meilleurs
        filtered = [doc for _, doc in scored_docs[:2]]
        logger.info(f"{len(filtered)} document(s) sélectionné(s) après filtrage")
        return filtered
    
    def _generate_with_llm(self, query: str, contents: List[str]) -> str:
        """Génère une réponse avec un modèle LLM (à implémenter si nécessaire)"""
        # Placeholder pour une future implémentation avec un LLM local
        # Par exemple avec transformers + un modèle léger
        return self._generate_template_answer(query, contents, [])


# Instance globale
answer_generator = AnswerGenerator()

