# STORY-447 : Vue ContainerDetail — Onglet Processus

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace
**Type :** Amélioration

## Description
En tant qu'utilisateur WindFlow, je veux voir la liste des processus running dans un container Docker afin de pouvoir surveiller et diagnostiquer l'activité du container.

### Contexte
Cette story améliore la vue `ContainerDetail.vue` en ajoutant un onglet "Processus" après l'onglet "Stats". Le container detail a déjà 4 onglets (Infos, Logs, Terminal, Stats), et cette amélioration ajoute un 5ème onglet.

### Comportement actuel
La vue ContainerDetail affiche 4 onglets : Infos, Logs, Terminal, Stats. Il n'y a pas de visibilité sur les processus running dans le container.

### Comportement attendu
Un nouvel onglet "Processus" affiche un tableau des processus avec :
- PID (Process ID)
- USER (Utilisateur)
- %CPU (Utilisation CPU)
- %MEM (Utilisation mémoire)
- TIME (Temps CPU)
- COMMAND (Commande)

## Critères d'acceptation (AC)
- [x] AC 1 : L'onglet "Processus" apparaît à droite de l'onglet "Stats" dans ContainerDetail
- [x] AC 2 : L'onglet affiche un tableau avec les colonnes PID, USER, CPU, MEM, TIME, COMMAND
- [x] AC 3 : L'onglet est désactivé si le container n'est pas en état "running"
- [x] AC 4 : Un bouton "Rafraîchir" permet de recharger la liste des processus
- [x] AC 5 : Un toggle "Auto-refresh" permet de rafraîchir automatiquement toutes les 3 secondes
- [x] AC 6 : L'API backend expose `GET /api/v1/docker/containers/{id}/top`
- [x] AC 7 : Les tests unitaires backend et frontend passent
- [x] AC 8 : L'amélioration ne casse pas les onglets existants (Infos, Logs, Terminal, Stats)

## État d'avancement technique
- [x] Analyse du code existant (faite)
- [x] Implémentation backend (schémas, service, endpoint)
- [x] Implémentation frontend (composable, composant, intégration)
- [x] Tests unitaires backend
- [x] Tests unitaires frontend
- [x] Vérification de non-régression

## Risques de régression

### Fichiers impactés
| Fichier | Impact | Action requise |
|---------|--------|----------------|
| `backend/app/schemas/docker.py` | Ajout de nouveaux schémas Pydantic | Aucun risque |
| `backend/app/services/docker_client_service.py` | Ajout méthode `list_processes()` | Aucun risque |
| `backend/app/api/v1/docker.py` | Ajout endpoint `GET /containers/{id}/top` | Aucun risque |
| `frontend/src/types/api.ts` | Ajout types TypeScript | Aucun risque |
| `frontend/src/composables/useContainerProcesses.ts` | Nouveau fichier | Aucun risque |
| `frontend/src/components/ContainerProcesses.vue` | Nouveau fichier | Aucun risque |
| `frontend/src/views/ContainerDetail.vue` | Ajout d'un onglet | Vérifier que les autres onglets fonctionnent |

### Fonctionnalités annexes vérifiées
- [x] Onglet Infos : Affichage des informations générales OK
- [x] Onglet Logs : Streaming des logs OK
- [x] Onglet Terminal : Connexion WebSocket OK
- [x] Onglet Stats : Streaming des stats OK

## Notes d'implémentation

### Fichiers créés
- `backend/app/schemas/docker.py` : Ajout `ContainerProcessResponse`, `ContainerProcessListResponse`
- `backend/app/services/docker_client_service.py` : Ajout méthode `list_processes()`
- `backend/app/api/v1/docker.py` : Ajout endpoint `GET /containers/{container_id}/top`
- `frontend/src/types/api.ts` : Ajout interfaces `ContainerProcess`, `ContainerProcessListResponse`
- `frontend/src/composables/useContainerProcesses.ts` : Nouveau composable
- `frontend/src/components/ContainerProcesses.vue` : Nouveau composant
- `backend/tests/unit/test_docker/test_container_processes.py` : Tests backend
- `frontend/tests/unit/components/ContainerProcesses.spec.ts` : Tests frontend

### Décisions techniques
1. **API Docker** : Utilisation de l'endpoint Docker `/containers/{id}/top?ps_args=aux` via le service `docker_client_service`
2. **Auto-refresh** : Intervalle de 3 secondes par défaut, configurable via le composable
3. **Parsing** : Les données brutes Docker (Titles + Processes array) sont parsées en objets structurés
4. **Désactivation** : L'onglet est désactivé visuellement si le container n'est pas "running"

### Tests
- **Backend** : Tests unitaires du service et de l'endpoint API
- **Frontend** : Tests du composant ContainerProcesses et du composable useContainerProcesses
- **Non-régression** : Vérification que les 4 autres onglets fonctionnent toujours
