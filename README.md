# 🔍 Système RAG Multi-Tenant SaaS

Application SaaS multi-tenant permettant à deux clients indépendants (Client A et Client B) d'interroger leurs propres documents via un système de recherche RAG (Retrieval-Augmented Generation).

## 💡 Approche et choix techniques

### Architecture Multi-Tenant

L'application utilise une **architecture multi-tenant stricte** où chaque client (tenant) possède ses propres données et ne peut accéder qu'à ses propres documents. La séparation est garantie au niveau serveur via :

- **Authentification par clé API** : Chaque requête est identifiée via le header `X-API-KEY`, jamais dans le body
- **Isolation des données** : Les documents sont stockés dans des dossiers séparés (`tenantA/` et `tenantB/`)
- **Filtrage strict** : La recherche est limitée aux documents du tenant authentifié avant même l'exécution de la requête

### Système RAG (Retrieval-Augmented Generation)

Le système implémente un pipeline RAG en deux étapes :

#### 1. Recherche sémantique avec fallback

- **Recherche sémantique** : Utilisation de `sentence-transformers` avec le modèle `paraphrase-multilingual-MiniLM-L12-v2` pour générer des embeddings et calculer la similarité cosinus
- **Lazy loading** : Le modèle est chargé uniquement lors de la première requête pour accélérer le démarrage
- **Fallback textuel** : Si le modèle ne peut pas être chargé (pas de connexion internet, erreur), le système bascule automatiquement sur une recherche par mots-clés
- **Seuils adaptatifs** : Les seuils de pertinence sont ajustés selon le type de recherche (sémantique : 0.5, textuelle : 0.4)

#### 2. Génération de réponse intelligente

- **Filtrage de pertinence** : Vérification stricte que les documents trouvés correspondent vraiment à la question
- **Règles métier** : 
  - Client A ne peut jamais répondre sur les sinistres
  - Client B ne peut jamais répondre sur la résiliation
  - Distinction stricte entre RC Pro A et RC Pro B
- **Vérification du domaine** : Rejet immédiat des questions hors domaine (assurance/contrat)
- **Synthèse contextuelle** : Génération d'une réponse textuelle structurée basée sur les documents pertinents, pas seulement une liste de documents

### Gestion de la pertinence

Le système implémente plusieurs couches de vérification pour garantir la pertinence :

1. **Vérification des mots-clés** : 
   - Détection des mots-clés importants (résiliation, sinistre, RC Pro, exclusion)
   - Vérification que les mots-clés de la question sont présents dans les documents
   - Tri par longueur pour vérifier les phrases complètes avant les mots simples

2. **Vérification du filename** : 
   - Utilisation du nom de fichier comme indicateur de pertinence
   - Bonus de score si le filename correspond aux mots-clés

3. **Filtrage adaptatif** : 
   - Pour les questions de définition, sélection du document le plus pertinent uniquement
   - Pour les procédures, combinaison intelligente de plusieurs documents

4. **Seuils de score** : 
   - Seuil élevé (0.7) si aucun mot-clé spécifique n'est trouvé
   - Seuil bas (0.2) si les mots-clés correspondent

### Sécurité et robustesse

- **Séparation stricte** : Aucune possibilité pour un client d'accéder aux données d'un autre client
- **Gestion des erreurs** : Messages d'erreur clairs sans révéler d'informations sensibles
- **Validation des entrées** : Vérification que les requêtes ne sont pas vides
- **Gestion des cas limites** : Retour explicite quand aucune information n'est trouvée plutôt qu'une réponse inventée

### Choix techniques

- **FastAPI** : Framework moderne et performant pour l'API REST
- **Streamlit** : Interface simple et rapide à développer pour les tests
- **Sentence-Transformers** : Modèle multilingue léger et efficace pour la recherche sémantique
- **Stockage fichier** : Approche simple et directe pour cette démonstration (facilement remplaçable par une base de données)
- **Python natif** : Pas de dépendance à des services externes, tout fonctionne localement

Cette approche garantit une **séparation stricte des données**, une **recherche pertinente** et une **génération de réponses fiables** sans invention d'information.

---

# 🚀 Démarrage rapide

## Cloner le dépôt

```bash
# Cloner le dépôt GitHub
git clone https://github.com/AyoubM490/actudata-ai-test.git

# Aller dans le dossier du projet
cd actudata-ai-test
```

## Installation (une seule fois)

```bash
# Créer un environnement virtuel (recommandé)
python -m venv venv

# Activer l'environnement
# Windows (plusieurs options selon votre terminal):

# Option 1: PowerShell (si politique d'exécution autorisée)
venv\Scripts\activate

# Option 2: PowerShell (si erreur de politique d'exécution)
# Méthode A: Activer temporairement pour cette session
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
venv\Scripts\activate

# Méthode B: Utiliser directement le script Python
venv\Scripts\python.exe

# Option 3: Utiliser CMD (Command Prompt) au lieu de PowerShell
# Dans CMD, tapez simplement:
venv\Scripts\activate.bat

# Option 4: Activer via Python directement (fonctionne toujours)
python -m venv venv
# Puis utilisez directement:
venv\Scripts\python.exe -m pip install -r requirements.txt

# Linux/Mac:
source venv/bin/activate

# Installer les dépendances
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## Lancement

### Terminal 1 - Backend
```bash
python run_backend.py
```

### Terminal 2 - Frontend
```bash
python run_frontend.py
```

## 🧪 Tests de séparation

### Test manuel rapide

**Client A :**
- ✅ "Comment résilier un contrat ?" → Doit retourner une réponse sur la résiliation
- ❌ "Comment déclarer un sinistre ?" → Doit retourner "Aucune information pertinente"
- ❌ "Comment se laver ?" → Doit retourner "Aucune information pertinente" (hors domaine)

**Client B :**
- ✅ "Comment déclarer un sinistre ?" → Doit retourner une réponse sur les sinistres
- ❌ "Comment résilier un contrat ?" → Doit retourner "Aucune information pertinente"
- ❌ "Comment cuisiner ?" → Doit retourner "Aucune information pertinente" (hors domaine)

### Tests automatiques

Un script de test automatique est disponible pour vérifier tous les scénarios :

```bash
python run_tests.py
```

Ce script teste automatiquement :
- ✅ Questions pertinentes pour chaque client
- ❌ Questions interdites (Client A sur sinistre, Client B sur résiliation)
- ❌ Questions hors domaine
- ❌ Questions sur le mauvais produit (Client A sur RC Pro B, Client B sur RC Pro A)
- ✅ Séparation stricte des données

## Test via l'API

```bash
# Client A
curl -X POST "http://localhost:8000/search" \
  -H "X-API-KEY: tenantA_key" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Comment résilier ?\", \"top_k\": 3}"

# Client B  
curl -X POST "http://localhost:8000/search" \
  -H "X-API-KEY: tenantB_key" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Comment déclarer un sinistre ?\", \"top_k\": 3}"
```

