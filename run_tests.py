"""Script pour tester automatiquement différentes requêtes"""
import requests
import time
from typing import Dict, List, Tuple

API_BASE_URL = "http://localhost:8000"

# Clés API
TENANT_KEYS = {
    "Client A": "tenantA_key",
    "Client B": "tenantB_key"
}

# Requêtes de test organisées par catégorie
TEST_QUERIES = {
    "Client A - Valides": [
        ("Comment résilier un contrat ?", True),
        ("Quelle est la procédure de résiliation ?", True),
        ("Qu'est-ce que la RC Pro A ?", True),
        ("Quelles sont les exclusions de la RC Pro ?", True),
    ],
    "Client A - Invalides (sinistre)": [
        ("Comment déclarer un sinistre ?", False),
        ("Procédure sinistre", False),
        ("Déclarer un sinistre", False),
    ],
    "Client A - Invalides (RC Pro B)": [
        ("Qu'est-ce que la RC Pro B ?", False),
    ],
    "Client A - Invalides (hors domaine)": [
        ("Comment se laver ?", False),
        ("Quelle est la météo ?", False),
        ("Comment cuisiner ?", False),
    ],
    "Client B - Valides": [
        ("Comment déclarer un sinistre ?", True),
        ("Quelle est la procédure pour déclarer un sinistre ?", True),
        ("Qu'est-ce que la RC Pro B ?", True),
        ("Quelles sont les exclusions ?", True),
    ],
    "Client B - Invalides (résiliation)": [
        ("Comment résilier un contrat ?", False),
        ("Procédure résiliation", False),
        ("Résilier contrat", False),
    ],
    "Client B - Invalides (RC Pro A)": [
        ("Qu'est-ce que la RC Pro A ?", False),
    ],
    "Client B - Invalides (hors domaine)": [
        ("Comment se laver ?", False),
        ("Quelle est la météo ?", False),
        ("Comment cuisiner ?", False),
    ],
}


def test_query(tenant_key: str, tenant_name: str, query: str, should_find: bool) -> Tuple[bool, str]:
    """
    Teste une requête.
    
    Args:
        tenant_key: Clé API du tenant
        tenant_name: Nom du tenant
        query: La requête à tester
        should_find: True si on s'attend à trouver une réponse, False sinon
        
    Returns:
        (success, message) où success indique si le test a réussi
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/search",
            json={"query": query, "top_k": 3},
            headers={"X-API-KEY": tenant_key},
            timeout=30
        )
        
        if response.status_code != 200:
            return False, f"Erreur HTTP {response.status_code}: {response.text}"
        
        result = response.json()
        found = result.get("found", False)
        answer = result.get("answer", "")
        
        # Vérifier si le résultat correspond aux attentes
        if should_find:
            if found and answer and len(answer) > 20:
                return True, f"✅ Trouvé: {answer[:100]}..."
            else:
                return False, f"❌ Attendu une réponse mais reçu: found={found}, answer='{answer[:50]}...'"
        else:
            if not found or "n'ai pas trouvé" in answer.lower() or "aucune information" in answer.lower():
                return True, f"✅ Correctement rejeté: {answer[:100]}..."
            else:
                return False, f"❌ Attendu un rejet mais reçu une réponse: {answer[:100]}..."
                
    except Exception as e:
        return False, f"❌ Erreur: {str(e)}"


def run_all_tests():
    """Exécute tous les tests"""
    print("=" * 80)
    print("🧪 TESTS AUTOMATIQUES DU SYSTÈME RAG MULTI-TENANT")
    print("=" * 80)
    print()
    
    # Vérifier que l'API est accessible
    try:
        health = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if health.status_code != 200:
            print("❌ L'API n'est pas accessible. Assurez-vous que le backend est démarré.")
            return
        print("✅ API accessible\n")
    except:
        print("❌ Impossible de se connecter à l'API. Assurez-vous que le backend est démarré sur http://localhost:8000")
        return
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    # Exécuter les tests par catégorie
    for category, queries in TEST_QUERIES.items():
        print(f"\n{'=' * 80}")
        print(f"📋 {category}")
        print(f"{'=' * 80}")
        
        # Déterminer le tenant
        if "Client A" in category:
            tenant_name = "Client A"
            tenant_key = TENANT_KEYS["Client A"]
        else:
            tenant_name = "Client B"
            tenant_key = TENANT_KEYS["Client B"]
        
        for query, should_find in queries:
            total_tests += 1
            print(f"\nTest {total_tests}: '{query}'")
            print(f"  Attendu: {'Réponse' if should_find else 'Rejet'}")
            
            success, message = test_query(tenant_key, tenant_name, query, should_find)
            
            if success:
                passed_tests += 1
                print(f"  {message}")
            else:
                failed_tests.append((category, query, message))
                print(f"  {message}")
            
            time.sleep(0.5)  # Petite pause entre les requêtes
    
    # Résumé
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 80)
    print(f"Total: {total_tests}")
    print(f"✅ Réussis: {passed_tests}")
    print(f"❌ Échoués: {len(failed_tests)}")
    print(f"Taux de réussite: {(passed_tests/total_tests)*100:.1f}%")
    
    if failed_tests:
        print("\n" + "=" * 80)
        print("❌ TESTS ÉCHOUÉS")
        print("=" * 80)
        for category, query, message in failed_tests:
            print(f"\n[{category}]")
            print(f"  Question: '{query}'")
            print(f"  {message}")
    else:
        print("\n🎉 Tous les tests sont passés avec succès!")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    run_all_tests()

