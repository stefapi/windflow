# STORY-174 : Socle `WorkloadAdapter` + `DockerWorkloadAdapter` — abstraction encapsulant les services Docker existants et recreate sécurisé (rebase, rollback, masquage `***`) (P2-12 + P2-13 — axes D3, F7, C10)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-12 (axes D3, F7, arbitrage — rapports §5) + P2-13 (axe C10, rapport §5) — ampleur **L**

## Description

En tant que développeur backend WindFlow, je veux introduire l'abstraction **`WorkloadAdapter`** (contrat commun : identité `family()`/`profile()`, métriques/santé, ContextualActions, Mode Infra) et un **`DockerWorkloadAdapter`** (+ Compose) qui **encapsule les exécuteurs/services Docker existants** sans réécriture — le chemin de déploiement actuel passant par l'adapter — ainsi que le **recreate sécurisé** (capture de l'ancienne image avant pull, rebase par valeur des env/labels/cmd, rollback automatique sur échec, masquage des secrets `***` dans les aperçus), afin de poser le socle architectural spec 02 en préparant les adapters futurs (K8s/VM — **non implémentés ici**) et de fiabiliser le verbe Mettre à jour.

**Problème constaté** ([VIRTUALIZATION-SYSTEMS.md §6.3](../../docs/technical_specs/VIRTUALIZATION-SYSTEMS.md), [`backend_status.md`](../../docs/backend_status.md) §4) : aucun adapter n'existe — les services [`docker_service.py:20`](../../backend/app/services/docker_service.py) / [`docker_compose_service.py:20`](../../backend/app/services/docker_compose_service.py) / exécuteurs ([`docker_executor.py:26`](../../backend/app/services/docker_executor.py:26) `DockerExecutorBase`, [`DockerExecutor:680`](../../backend/app/services/docker_executor.py:680), [`ComposeExecutor:786`](../../backend/app/services/docker_executor.py:786)) en tiennent lieu ; le recreate existe (endpoint `POST /docker/containers/{id}/recreate`) mais C10 (rebase des modifications, rollback sur échec, secrets masqués `***` dans les aperçus) est incomplet.

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- **Arbitrage F7 (tranché)** : interface + adapter Docker **maintenant** — l'adapter **enveloppe** les exécuteurs existants sans réécriture ; les adapters K8s/Helm/Swarm **suivent la Roadmap** (arbitrage D4 : organisation modules limitée à ce que D3 introduit — pas de big-bang des ~36 services) ;
- **Contrat spec 02 § Interface WorkloadAdapter** : `WorkloadFamily` (app/machine/host/cluster), `family()`, `profile()`, `profile_label()`, `get_metrics()`, `health()`, `contextual_actions()`, `child_actions()`, `get_native_config()`, `get_technical_components()` — spécialisation **AppAdapter** (`get_open_url`, `list_services_or_pods`, verbes start/stop/restart/update/backup/configure/stream_logs/open_console) ; implémenter pour la famille Docker : `DockerContainerAdapter` (docker_container) et `ComposeStackAdapter` (docker_compose) ;
- **Recreate sécurisé — étapes spec 02 § Sémantique de mise à jour** : 1) **capture de l'ancienne image avant le pull** (env/labels/CMD par défaut — après un pull, l'ancien tag peut être détagué) ; 2) pull ; 3) arrêt (si running), **renommage** `<nom>-old`, déconnexion des réseaux ; 4) création du nouveau (passthrough inspection, image remplacée), reconnexion réseaux, démarrage si l'ancien tournait ; 5) suppression de l'ancien ; 6) **rollback automatique** en cas d'échec (renommage restauré, réseaux reconnectés, redémarrage) ;
- **Rebase par valeur** : env/label/cmd — valeur identique à l'ancienne image → suit la nouvelle image ; différente → conservée ; absente de l'ancienne image (ajout utilisateur) → conservée ; **secrets masqués `***`** : l'inspection masque les valeurs d'aspect secret (`*_PASSWORD`, `*_TOKEN`, `*_KEY`…), le formulaire renvoie `***` pour les valeurs inchangées et le backend **résout les placeholders** en relisant les valeurs réelles du container courant avant la recréation ;
- **Effet sur les mises à jour en attente** : une recréation réussie efface la « mise à jour en attente » du container (spec 03) ;
- **La gate pre-deploy s'applique au recreate** (STORY-170 — tous les chemins de déploiement) ; le chemin de déploiement existant ([`background_tasks.py:24`](../../backend/app/tasks/background_tasks.py:24) → DockerService/ComposeService) **passe par l'adapter** (test de non-régression complet des déploiements — critère P2-12) ;
- **Interface documentée spec 02** (critère de done) — annotation doc à coordonner avec P3-4 si non fusionnée ; la suppression du label `windflow.update=false` etc. reste hors périmètre (check-updates Roadmap) ;
- Localisation cible : nouveau `services/workloads/` (spec 04 § organisation cible — modeste) ;
- Garde-fous : module Docker intact (aucune suppression d'endpoint), recovery orchestrateur conservé.

## Critères d'acceptation (AC)

- [ ] AC 1 : L'interface `WorkloadAdapter` (+ `AppAdapter`) est définie conformément au contrat spec 02 (identité, métriques/santé, ContextualActions, Mode Infra) dans `services/workloads/` ; `DockerContainerAdapter` et `ComposeStackAdapter` l'implémentent en **enveloppant** les exécuteurs existants (`DockerExecutor`/`ComposeExecutor`/services actuels) — vérifié par revue : pas de duplication de logique Docker, les services existants restent la couche d'exécution.
- [ ] AC 2 : **Le chemin de déploiement existant passe par l'adapter** — test de non-régression complet des déploiements : déploiement de stack, démarrage/arrêt/redémarrage, logs, suppression… via l'adapter produisent les mêmes effets qu'avant (les tests existants du module Docker restent verts).
- [ ] AC 3 : **Recreate sécurisé complet** : capture de l'ancienne image **avant** le pull ; étapes arrêt→renommage `-old`→déconnexion réseaux→création→reconnexion→démarrage→suppression de l'ancien ; **rebase par valeur** vérifié par tests : env/label identique à l'ancienne image → suit la nouvelle ; modifié → conservé ; ajouté → conservé ; `command:` utilisateur survit.
- [ ] AC 4 : **Rollback sur échec** : un échec simulé à une étape (pull, création, démarrage) → retour à l'état antérieur (ancien container renommé restauré, réseaux reconnectés avec leurs réglages, redémarré si besoin) — testé ; **secrets masqués** : l'aperçu d'inspection masque `*_PASSWORD`/`*_TOKEN`/`*_KEY` en `***`, le backend résout les placeholders `***` en relisant les valeurs réelles avant recréation — test : recreate avec un env secret inchangé → la valeur réelle est préservée sans jamais apparaître en clair dans l'aperçu.
- [ ] AC 5 : Une recréation réussie efface la « mise à jour en attente » éventuelle (si la structure existe — sinon différé noté) ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [`02-familles-workloads.md`](../../docs/general_specs/02-familles-workloads.md) — **§ Interface WorkloadAdapter** (contrat commun + spécialisations), § Hiérarchie des adapters App (`DockerContainerAdapter`, `ComposeStackAdapter`), **§ Sémantique de mise à jour / recreate** (étapes 1-6, rebase par valeur, secrets `***`, effet mise à jour en attente), § Catalogue ContextualActions docker ;
- [VIRTUALIZATION-SYSTEMS.md](../../docs/technical_specs/VIRTUALIZATION-SYSTEMS.md) — §4.2 (services existants vs cible adapters), §6.3 (**écart explicite : aucun adapter n'existe — les services Docker en tiennent lieu**), §2.1 (correspondance moteur→adapter) ;
- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § Services core (App Service via adapters), § Organisation cible des modules (`workloads/adapters/`) ;
- [`03-modele-compute.md`](../../docs/general_specs/03-modele-compute.md) — § Mises à jour en attente (effacées à la recréation réussie) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Chiffrement des secrets / invariants (valeurs résolues jamais écrites dans un fichier, masquées `***` partout ailleurs) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Verbe Mettre à jour / batch update (le recreate est le mécanisme sous `POST /apps/{id}/update` futur) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-12 + P2-13, §2.D D3/D4, §3 F7, §6 (adapters non-Docker hors périmètre) ;
- [`backend_status.md`](../../docs/backend_status.md) — §4.2 (exécuteurs), §3.7 (endpoint recreate existant), §5 (docker/compose services).

## Dépendances

- **Aucune dépendance marquée par le plan** (P2-12 « dépend de : — » ; P2-13 dépend de P0-4 pour le masquage cohérent des secrets — STORY-103 recommandé).
- Prépare **P3-2** (CircuitBreaker câblé sur appels Docker distants — EPIC-014, dépend explicitement de P2-12) ; interagit avec **STORY-170** (gate sur le chemin de recreate) et **STORY-173** (browse/prune réutilisent les mêmes services encapsulés).

## Sous-stories

*(section réservée — story L : découpe possible interface+wrappers / recreate sécurisé ; plage réservée STORY-175-199)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
