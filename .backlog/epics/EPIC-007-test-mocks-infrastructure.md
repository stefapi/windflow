# EPIC-007 : Infrastructure de Mocks pour Tests

**Statut :** TODO
**Priorité :** Haute
**Phase Roadmap :** Phase 1 — Infrastructure de base
**Version cible :** 0.1.0

## Vision

Créer une infrastructure de mocks centralisée pour isoler les tests unitaires et d'intégration des ressources physiques de la machine hôte (Docker, SSH, commandes shell, sockets). Cela permet d'exécuter les tests en toute sécurité sans risque de modification accidentelle de l'environnement réel.

### Valeur Business

- **Sécurité** : Évite les opérations destructrices sur la machine de développement/CI
- **Fiabilité** : Tests reproductibles avec des données constantes
- **Performance** : Pas d'appels système ni d'attente réseau
- **Portabilité** : Tests fonctionnant même si Docker/SSH ne sont pas disponibles

### Utilisateurs cibles

- Développeurs backend exécutant des tests unitaires
- Pipeline CI/CD nécessitant des tests isolés
- Équipe QA validant le comportement des services

## Contexte technique

### Services identifiés à mocker

| Service | Ressource physique | Risque |
|---------|-------------------|--------|
| `DockerClientService` | Socket Docker `/var/run/docker.sock` | Création/suppression de conteneurs |
| `CLIDockerExecutor` | Commandes `docker` CLI | Opérations destructrices sur conteneurs |
| `SocketDockerExecutor` | Socket Docker API REST | Idem via API REST |
| `ComposeExecutor` | Commandes `docker compose` | Déploiement de stacks |
| `TerminalService` | Exécution dans conteneurs | Commandes arbitraires |
| `TargetScannerService` | Commandes shell, SSH, socket libvirt | Scan système, connexion SSH |
| `LocalCommandExecutor` | Subprocess shell | Exécution de commandes locales |

### Architecture proposée

```
backend/tests/
├── mocks/
│   ├── __init__.py           # Exports centralisés
│   ├── docker_mock.py        # Mock du client Docker + réponses simulées
│   ├── executor_mock.py      # Mock des exécuteurs (CLI/Socket/Compose)
│   └── scan_mock.py          # Mock du scanner de targets
└── conftest.py               # Mise à jour avec nouvelles fixtures
```

## Contenu de l'Epic

### Module docker_mock.py
- [ ] Données de test statiques (MOCK_CONTAINERS, MOCK_IMAGES, MOCK_VOLUMES, MOCK_NETWORKS)
- [ ] Fixture `fake_docker_client` simulant DockerClientService
- [ ] Simulation de list_containers, list_images, get_container, etc.
- [ ] Simulation des opérations create/start/stop/remove

### Module executor_mock.py
- [ ] Fixture `fake_docker_executor` pour DockerExecutor
- [ ] Fixture `fake_compose_executor` pour ComposeExecutor
- [ ] Simulation des retours (success, error) configurables
- [ ] Support des scénarios d'erreur (timeout, connection refused)

### Module scan_mock.py
- [ ] Fixture `fake_target_scanner` pour TargetScannerService
- [ ] Fixture `fake_command_executor` pour LocalCommandExecutor/SSHCommandExecutor
- [ ] Données de scan prédéfinies (platform, os, docker, kubernetes)
- [ ] Simulation des réponses SSH sans connexion réelle

### Intégration conftest.py
- [ ] Fixture `mock_docker_env` désactivant l'accès aux ressources physiques
- [ ] Auto-use fixtures pour isolation par défaut
- [ ] Configuration des scénarios de test via paramétrage

## Liste des Stories liées
*À créer ultérieurement*

- [ ] STORY-XXX : Créer module docker_mock.py avec fixtures de base
- [ ] STORY-XXX : Créer module executor_mock.py pour exécuteurs Docker
- [ ] STORY-XXX : Créer module scan_mock.py pour scanner de targets
- [ ] STORY-XXX : Intégrer les mocks dans conftest.py

## Notes de conception

### Principes directeurs

1. **Aucune connexion réelle** : Les mocks ne doivent jamais tenter de se connecter aux ressources physiques
2. **Données réalistes** : Les données simulées doivent refléter les réponses réelles des API
3. **Configurabilité** : Permettre de simuler des scénarios de succès et d'échec
4. **Centralisation** : Un seul point de définition pour éviter la duplication

### Patterns utilisés

- **Fixture pattern** : Utilisation des fixtures pytest pour l'injection de dépendances
- **Builder pattern** : Construction configurable des réponses mockées
- **Strategy pattern** : Différentes stratégies de mock selon le contexte de test

## Critères de succès (Definition of Done)

- [ ] Tous les services Docker peuvent être testés sans Docker installé
- [ ] Les tests du scanner de targets fonctionnent sans SSH/socket
- [ ] Les mocks retournent des données cohérentes avec les schémas Pydantic
- [ ] Documentation d'utilisation des fixtures disponible
- [ ] Couverture de test des mocks ≥ 80%
- [ ] Aucune régression sur les tests existants

## Risques

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Données mockées obsolètes par rapport aux API réelles | Moyen | Versionner les données mock avec la doc API |
| Sur-mockage masquant des bugs réels | Élevé | Tests d'intégration séparés avec Docker réel |
| Complexité de maintenance des mocks | Moyen | Génération automatique depuis les schémas |

## Dépendances

- Aucune dépendance externe (tests existants utilisent déjà `unittest.mock`)
- Compatibilité avec pytest et pytest-asyncio existants
