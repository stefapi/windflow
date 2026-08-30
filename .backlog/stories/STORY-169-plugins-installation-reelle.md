# STORY-169 : Plugins — installation réelle — téléchargement du package, vérification checksum SHA-256, extraction, `docker compose up` du service et rollback sur échec (P2-3, partie installation — axes B5, C12)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-3 partie installation (axes B5, C12, rapports §10/§7) — ampleur **XL** (prévoir sous-découpe possible, plage réservée STORY-175-199)

## Description

En tant qu'administrateur WindFlow, je veux que l'installation d'un plugin effectue réellement le **téléchargement** du package depuis l'URL du registre, la **vérification du checksum SHA-256** (obligatoire, rejet en cas d'écart), l'**extraction** dans le répertoire des plugins, la validation du manifest, l'exécution des hooks lifecycle et le **`docker compose up`** du service pour les plugins service/hybrid — avec un **rollback complet** (DB + filesystem + conteneur) en cas d'échec à une étape — afin que l'installation ne soit plus un simple enregistrement en base sans effet.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §5, §14.1) : [`plugin_manager_service.py:27`](../../backend/app/services/plugin_manager_service.py:27) gère un cycle de vie de façade — install = enregistrement DB, **pas de download, pas de checksum SHA-256, pas de compose up, pas de rollback** (B5 : « plugins coquille vide ») ; le chiffrement `plugin_configs` si `encrypted` est à compléter (C12).

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- **Socle sain** (garde-fou §2.G) : le registre plugins (lecture, cache TTL via STORY-168 — [`plugin_registry_service.py:23`](../../backend/app/services/plugin_registry_service.py:23)) et la validation de manifest ([`plugin_manifest_service.py:21`](../../backend/app/services/plugin_manifest_service.py:21)) sont des bases saines à conserver ;
- **Pipeline d'installation spec 11** (étapes 1-5) : DOWNLOAD (télécharger depuis le registre, vérifier SHA-256, extraire dans le répertoire plugins) → VALIDATE (manifest, architecture, ressources, dépendances via [`plugin_dependency_service.py:54`](../../backend/app/services/plugin_dependency_service.py:54), conflits, version WindFlow minimale) → INSTALL (hook `on_install` si défini via [`plugin_lifecycle_service.py:40`](../../backend/app/services/plugin_lifecycle_service.py:40), `[Service/Hybrid]` déploiement du compose — pull images, network `windflow-plugin-{name}` si isolé, `docker compose up -d`, `[Extension/Hybrid]` chargement du code — routes STORY-170, hooks STORY-163) → CONFIGURE (wizard, valeurs en base **chiffrées si `password`/`encrypted`** via STORY-103, injection env/fichier, hook `on_configure`) → RUNNING ;
- **Rollback spec 11** : échec d'une étape → suppression des fichiers téléchargés (échec INSTALL), `docker compose down` + nettoyage (échec déploiement Docker), désenregistrement des routes partiellement chargées (échec extension), rollback complet (échec hook `on_install`) ; **l'utilisateur voit un message explicite avec la cause et la suggestion de résolution** ;
- **Volumes/networks conventionnés** : données persistantes dans `windflow-plugin-{name}-data`, network `windflow-plugin-{name}` — ces volumes sont **épargnés par le prune** (convention `windflow-plugin-*`, STORY-173 / spec 09 § prune) ;
- **Chiffrement `plugin_configs`** (C12) : `value` chiffrée quand `encrypted=true` (STORY-103) ; jamais exposée dans les logs ni les réponses API ;
- **Sécurité** (risque §7.3 : la story introduit de la surface d'attaque — download/exécution de hooks) : checksum **obligatoire** (installation refusée en cas d'écart, spec 15 § Vérifications à l'installation) ; sandboxing des hooks à documenter ; **audit trail branché avant** si possible (STORY-125) — `plugin.installed`/`plugin.removed` audités (spec 15 § Audit) ; événements bus `plugin.installed`/`plugin.removed` émis (STORY-162) ;
- Zones : [`plugin_manager_service.py:27`](../../backend/app/services/plugin_manager_service.py:27), [`plugin_registry_service.py:23`](../../backend/app/services/plugin_registry_service.py:23), [`plugin_manifest_service.py:21`](../../backend/app/services/plugin_manifest_service.py:21), [`plugin_lifecycle_service.py:40`](../../backend/app/services/plugin_lifecycle_service.py:40) ; endpoints `/plugins/install` (superadmin, RL 5/min) existants à faire piloter le vrai pipeline.

## Critères d'acceptation (AC)

- [ ] AC 1 : Le pipeline exécute download → checksum SHA-256 → extraction → validation manifest (arch/ressources/dépendances/conflits/version) — test : **install avec checksum invalide → rejet** avec message explicite ; install avec manifest invalide ou dépendance manquante → rejet à l'étape VALIDATE sans résidu filesystem.
- [ ] AC 2 : Pour un plugin service/hybrid, le `docker compose up -d` du service est effectué (test avec compose mocké/réel : conteneur créé, network/volumes conventionnés `windflow-plugin-{name}*`) ; le hook `on_install` est exécuté via le lifecycle service existant ; à l'issue, le plugin est `running` et l'événement `plugin.installed` est émis.
- [ ] AC 3 : **Échec de hook → rollback complet** (DB + filesystem + conteneur) : test simulé d'échec du hook `on_install` → fichiers supprimés, `docker compose down` effectué, aucune ligne d'état incohérente en base, message utilisateur explicite avec cause et suggestion ; idem pour un échec de déploiement Docker (rollback + nettoyage) et un échec de chargement d'extension (désenregistrement des routes partielles).
- [ ] AC 4 : `plugin_configs` : les valeurs de type `password`/`encrypted` sont **chiffrées en base** (STORY-103) — test : lecture directe en base ≠ valeur en clair ; jamais exposées dans les réponses API (masquage) ni les logs ; l'installation est **auditée** (ligne `plugin.installed` avec user/version — STORY-125 si fusionné, sinon tracée et le manque documenté).
- [ ] AC 5 : Tests de sécurité : `/plugins/install` reste superadmin (403 sinon), RL 5/min ; URLs de download validées (SSRF : schéma/host contrôlés) ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Plugin Manager / **Étapes d'installation** (pipeline 1-5 complet), § rollback (« Si une étape échoue… »), § Stockage des plugins (arborescence, volumes/networks conventionnés), § Manifest (compatibilité, ressources, dépendances, ports), § Sécurité des plugins (checksum SHA-256 au téléchargement, secrets chiffrés) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Sécurité des plugins (niveaux de confiance, **vérifications à l'installation** : checksum/signature/avertissements), § Audit trail (`plugin.installed`/`plugin.removed` loggés), § Chiffrement des secrets (`plugin_configs.value` quand `encrypted=true`) ;
- [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Plugin / PluginConfig (schémas, `encrypted`), § Données des plugins (tables préfixées, option PluginConfig) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Plugins `/api/v1/plugins/` (install, config, start/stop, RL 5/min sur install) ;
- [`12-marketplace.md`](../../docs/general_specs/12-marketplace.md) — (renvoi) format de package `{name}-{version}.tar.gz` + checksum ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-3, §2.B B5, §2.C C12, §7.3 (surface d'attaque, checksum obligatoire, sandboxing documenté, audit avant) ;
- [`backend_status.md`](../../docs/backend_status.md) — §5 (services plugin_*), §3.14 (endpoints plugins), §14.1 (coquille vide).

## Dépendances

- **STORY-103** (SecretManager — chiffrement `plugin_configs`, dépendance explicite du plan P2-3).
- Idéalement après **STORY-125** (audit branché — risque §7.3) ; interagit avec **STORY-163** (hooks événements au chargement), **STORY-170** (routes dynamiques, partie extension du pipeline), **STORY-162** (événements `plugin.*`), **STORY-168** (cache registry) et **STORY-173** (volumes `windflow-plugin-*` épargnés par le prune).

## Sous-stories

*(section réservée — story XL : `analyse-story` devra évaluer une découpe, ex. download+validation+extraction / compose+hooks+rollback ; plage réservée STORY-175-199)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
