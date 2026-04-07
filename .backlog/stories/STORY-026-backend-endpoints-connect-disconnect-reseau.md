# STORY-026 : Backend — Endpoints connect/disconnect réseau

**Statut :** TODO
**Epic Parent :** EPIC-009 — Refonte de la page ContainerDetail — Homogénéisation et édition complète

## Description

En tant qu'opérateur, je veux pouvoir connecter et déconnecter un container d'un réseau Docker à chaud (sans recréation ni redémarrage) afin de modifier la connectivité réseau d'un container en cours d'exécution.

## Contexte technique

Docker supporte nativement la connexion/déconnexion réseau à chaud via :
- `POST /v1.xx/networks/{id}/connect` (corps : `{"Container": "<id>"}`)
- `POST /v1.xx/networks/{id}/disconnect` (corps : `{"Container": "<id>", "Force": false}`)

Ces opérations ajoutent/retirent une interface réseau virtuelle dans le container **sans l'arrêter**. Elles peuvent échouer si :
- Le réseau est en mode `host` ou `none` (non supporté)
- Le container est arrêté (la déconnexion peut échouer silencieusement)
- Le réseau n'existe pas

**Fichiers backend à modifier** :
- `backend/app/schemas/docker.py` — ajouter `ContainerNetworkConnectRequest` et `ContainerNetworkDisconnectRequest`
- `backend/app/api/v1/docker.py` — ajouter les deux route handlers
- `backend/app/services/docker_client_service.py` — ajouter `connect_network()` et `disconnect_network()`

**Routes** :
- `POST /api/v1/docker/containers/{container_id}/networks/connect`
- `POST /api/v1/docker/containers/{container_id}/networks/disconnect`

**Schémas** :
```python
class ContainerNetworkConnectRequest(BaseModel):
    network_id: str                       # ID ou nom du réseau
    aliases: Optional[list[str]] = None   # Alias réseau dans ce réseau
    ipv4_address: Optional[str] = None    # IP fixe optionnelle

class ContainerNetworkDisconnectRequest(BaseModel):
    network_id: str
    force: bool = False                   # Force la déconnexion même si container arrêté
```

**Rate limit** : 30 requêtes/min.

## Critères d'acceptation (AC)

- [ ] AC 1 : `POST /docker/containers/{id}/networks/connect` connecte le container au réseau spécifié
- [ ] AC 2 : `POST /docker/containers/{id}/networks/disconnect` déconnecte le container du réseau spécifié
- [ ] AC 3 : Les deux endpoints retournent HTTP 204 (success, no content) en cas de succès
- [ ] AC 4 : Si le container n'existe pas → HTTP 404
- [ ] AC 5 : Si le réseau n'existe pas → HTTP 404
- [ ] AC 6 : Les deux endpoints sont documentés dans OpenAPI
- [ ] AC 7 : Tests unitaires couvrant les cas nominaux et d'erreur (≥ 80%)

## Dépendances

- Aucune dépendance sur d'autres stories de cette epic

## État d'avancement technique

- [ ] Ajouter `ContainerNetworkConnectRequest` et `ContainerNetworkDisconnectRequest` dans `backend/app/schemas/docker.py`
- [ ] Ajouter `connect_network()` et `disconnect_network()` dans `docker_client_service.py`
- [ ] Implémenter les deux handlers dans `backend/app/api/v1/docker.py`
- [ ] Écrire les tests unitaires

## Tâches d'implémentation détaillées

<!-- À remplir par analyse-story -->

## Tests à écrire

<!-- À remplir par analyse-story -->
