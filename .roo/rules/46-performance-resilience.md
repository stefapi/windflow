# 46 — Performance et résilience

## 1. Objectifs de latence

95e centile, pile de production :

| Famille | Cible |
| --- | --- |
| Lecture d'une ressource (conteneur, host, stack) | moins de 300 ms |
| Liste paginée | moins de 500 ms |
| Tableau de bord | moins de 2 s |
| Opération de déploiement | tâche de fond avec suivi temps réel (`21`), jamais bloquante en requête synchrone |
| Scan / réconciliation de hosts | tâche planifiée ou déclenchée, avec progression |

Toute requête synchrone susceptible de dépasser 2 s devient une tâche de fond (`tasks/`) avec suivi par logs de déploiement ou événements temps réel.

## 2. Requêtes et charge

- Pas de requêtes N+1 : chargements explicites (`selectinload` / `joinedload`) SQLAlchemy 2.0 ; index sur toute colonne filtrée ou triée.
- Pagination systématique des listes API (`20` §2).
- Interface mise à jour par notification temps réel suivie d'une relecture (`21`), et relecture au retour sur l'onglet ; pas de polling périodique.

## 3. Patrons de résilience

| Patron | Outil | Règle |
| --- | --- | --- |
| Timeouts | aiohttp / docker SDK / asyncssh | Tout appel sortant a un délai ; jamais d'appel sans délai |
| Relances | `core/resilience.py` | Seulement pour une opération idempotente et une erreur transitoire ; attente exponentielle avec jigue ; nombre borné |
| Disjoncteur | `core/resilience.py` — câblé sur Docker, SSH et le registre de plugins (STORY-251) | Ouverture après échecs consécutifs, nouvel essai différé ; séries `windflow_circuit_breaker_*` |
| Rate limiting | fastapi-limiter (Redis, fallback mémoire STORY-102) | Entrant par endpoint ; sortant selon les quotas des providers |
| Cache | `get_cache()` (STORY-168) | Redis si configuré, sinon mémoire locale bornée avec fallback par opération ; invalidation explicite à la mise à jour |

## 4. Scalabilité

- Services stateless autant que possible ; déploiement single-worker assumé avec verrous anti-chevauchement du scheduler.
- Sessions et cache dans Redis quand il est configuré ; données métier en base ; fichiers temporaires effacés après usage.

## 5. Dégradation

| Dépendance indisponible | Comportement |
| --- | --- |
| Docker / SSH d'un host | Disjoncteur ouvert, host marqué injoignable, opération signalée ; les autres hosts restent opérationnels |
| Redis | Fallback mémoire process-local (cache, rate limiting) ; fonctionnalité dégradée signalée, pas d'erreur silencieuse |
| Provider IA (LiteLLM) | Relances puis bascule fournisseur selon la configuration (`25` §2) ; suggestion indisponible, jamais un résultat inventé |
| Flux temps réel | L'application fonctionne ; relecture au retour sur l'onglet |
| Base de données | Erreur explicite 503 ; aucune écriture partielle |
