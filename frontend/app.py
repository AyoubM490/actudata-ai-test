"""Interface Streamlit pour tester le système multi-tenant"""
import streamlit as st
import requests
from typing import Optional

# Configuration
API_BASE_URL = "http://localhost:8000"

# Clés API pour les tenants
TENANT_KEYS = {
    "Client A": "tenantA_key",
    "Client B": "tenantB_key"
}


def search_documents(api_key: str, query: str, top_k: int = 3) -> Optional[dict]:
    """
    Effectue une recherche via l'API.
    
    Args:
        api_key: La clé API du tenant
        query: La requête de recherche
        top_k: Nombre de résultats
        
    Returns:
        La réponse JSON de l'API ou None en cas d'erreur
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/search",
            json={"query": query, "top_k": top_k},
            headers={"X-API-KEY": api_key},
            timeout=300  # 5 minutes pour permettre le téléchargement du modèle
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.warning("⏳ La requête prend plus de temps que prévu. "
                  "Si c'est la première utilisation, le modèle est peut-être en cours de téléchargement (471 MB). "
                  "Veuillez patienter ou réessayer dans quelques instants.")
        return None
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            st.warning("⏳ Timeout de la requête. Le modèle est peut-être en cours de téléchargement. "
                      "Veuillez patienter et réessayer.")
        else:
            st.error(f"Erreur lors de la requête: {error_msg}")
        return None


def list_documents(api_key: str) -> Optional[list]:
    """
    Liste tous les documents disponibles pour un tenant.
    
    Args:
        api_key: La clé API du tenant
        
    Returns:
        Liste des documents ou None en cas d'erreur
    """
    try:
        response = requests.get(
            f"{API_BASE_URL}/documents",
            headers={"X-API-KEY": api_key},
            timeout=30  # Timeout augmenté
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur lors de la requête: {str(e)}")
        return None


def main():
    st.set_page_config(
        page_title="SaaS Multi-Tenant RAG",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 Système RAG Multi-Tenant")
    st.markdown("---")
    
    # Sélection du client
    st.sidebar.header("Configuration")
    selected_client = st.sidebar.selectbox(
        "Sélectionner le client",
        options=list(TENANT_KEYS.keys()),
        help="Choisissez le client pour lequel vous souhaitez effectuer une recherche"
    )
    
    api_key = TENANT_KEYS[selected_client]
    
    # Afficher les informations du client
    st.sidebar.info(f"**Client connecté:** {selected_client}\n\n**Clé API:** `{api_key}`")
    
    # Vérifier la connexion à l'API
    try:
        health_response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if health_response.status_code == 200:
            st.sidebar.success("✅ API connectée")
        else:
            st.sidebar.error("❌ API non disponible")
    except:
        st.sidebar.error("❌ Impossible de se connecter à l'API")
        st.warning("⚠️ Assurez-vous que le backend FastAPI est démarré sur http://localhost:8000")
    
    # Onglets
    tab1, tab2 = st.tabs(["🔍 Recherche", "📄 Documents disponibles"])
    
    with tab1:
        st.header("Recherche dans les documents")
        st.markdown(f"**Client actuel:** {selected_client}")
        
        # Formulaire de recherche
        query = st.text_input(
            "Votre question",
            placeholder="Ex: Comment résilier un contrat ?",
            help="Posez une question sur les documents du client sélectionné"
        )
        
        if st.button("🔍 Rechercher", type="primary"):
            if query.strip():
                # Message informatif pour la première utilisation
                info_placeholder = st.empty()
                info_placeholder.info("💡 **Note:** Si c'est la première utilisation, le téléchargement du modèle peut prendre quelques minutes (471 MB). "
                                    "Les recherches suivantes seront beaucoup plus rapides.")
                
                with st.spinner("Recherche en cours... (cela peut prendre quelques minutes lors du premier téléchargement du modèle)"):
                    result = search_documents(api_key, query)
                    info_placeholder.empty()  # Supprimer le message info une fois la recherche terminée
                    
                    if result:
                        st.markdown("---")
                        
                        # Message si aucun résultat
                        if not result.get("found", False):
                            st.warning(f"⚠️ {result.get('message', 'Aucun résultat trouvé')}")
                        else:
                            # Afficher uniquement la réponse générée
                            answer = result.get("answer")
                            if answer:
                                st.markdown("### 💬 Réponse")
                                st.markdown(answer)
                            else:
                                st.info("Aucune réponse générée.")
            else:
                st.warning("Veuillez saisir une question")
    
    with tab2:
        st.header("Documents disponibles")
        st.markdown(f"**Client actuel:** {selected_client}")
        
        if st.button("🔄 Actualiser la liste", type="primary"):
            with st.spinner("Chargement des documents..."):
                documents = list_documents(api_key)
                
                if documents:
                    st.success(f"✅ {len(documents)} document(s) trouvé(s)")
                    
                    for idx, doc in enumerate(documents, 1):
                        with st.expander(f"📄 {doc.get('filename', 'Sans nom')}", expanded=False):
                            st.markdown("**Contenu complet:**")
                            st.text(doc.get("content", ""))
                else:
                    st.warning("Aucun document disponible pour ce client")


if __name__ == "__main__":
    main()

