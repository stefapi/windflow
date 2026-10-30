# STORY-169.1 : Plugins — package : download sécurisé, checksum SHA-256 obligatoire et extraction anti path-traversal (P2-3, partie téléchargement — STORY-169 découpée)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-169 ([ABANDONED — découpe proactive post-analyse le 2026-10-30](STORY-169-plugins-installation-reelle.md))
**Item plan :** P2-3 partie installation (axe B5) — volet **DOWNLOAD** du pipeline spec 11 — ampleur **L**

> **Périmètre (découpe)** : cette sous-story reprend le **volet téléchargement du package** de STORY-169 — nouveau service `PluginPackageService` (un service = une classe) : téléchargement streaming borné depuis l'URL du registre (**HTTPS-only**, validation SSRF), **vérification checksum SHA-256 obligatoire** (rejet sur écart), **extraction sécurisée** (anti path-traversal/symlink/bombe) vers `plugins_base_dir/{name}/`, settings nouveaux (`plugin_package_max_size_mb`, `plugin_package_download_timeout`). Couvre l'**AC 1 de la mère (partie DOWNLOAD)**. La validation du contenu extrait est portée par [STORY-169.2](STORY-169.2-plugins-validation-manifest-arch-ressources.md), l'orchestration compose/hooks/rollback par [STORY-169.3](STORY-169.3-plugins-install-compose-hooks-rollback.md), le chiffrement config et le durcissement transverse par [STORY-169.4](STORY-169.4-plugins-configure-chiffrement-durcissement.md).

## Description

En tant qu'administrateur WindFlow, je veux que l'installation d'un plugin télécharge réellement le package depuis l'URL du registre — en HTTPS avec vérification systématique du checksum SHA-256 (obligatoire, rejet en cas d'écart) et extraction sécurisée dans le répertoire des plugins (`plugins_base_dir/{name}/`) — afin que le pipeline d'installation s'appuie sur un package intègre et sûr, et ne soit plus un simple enregistrement en base sans effet.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §5, §14.1) : [`plugin_manager_service.py`](../../backend/app/services/plugin_manager_service.py) gère un cycle de vie de façade — install = enregistrement DB, **pas de download, pas de checksum SHA-256, pas d'extraction** (B5 : « plugins coquille vide ») ; la branche `source` de `PluginInstallRequest` lève aujourd'hui [`source_not_supported`](../../backend/app/services/plugin_manager_service.py).

## Contexte technique

> Extrait de l'analyse STORY-169 (2026-10-30, `analyse-story`) — volet package/download, fondé sur le code réel du dépôt. Tâches détaillées à rédiger par `analyse-story` sur cette sous-story.

### Patterns existants à réutiliser (extrait de la mère)

- **Registre** : [`plugin_registry_service.py`](../../backend/app/services/plugin_registry_service.py) — fetch index + cache unifié STORY-168 (clé `registry:index`, stale-while-error) ; [`plugin_registry.py`](../../backend/app/schemas/plugin_registry.py) : `RegistryPluginEntry` expose déjà `download_url` (**validé HTTPS-only**) et `checksum_sha256` (**validé hex 64**) → **source de vérité du checksum** pour l'installation depuis `source` (URL/identifiant registre).
- **Settings** : `plugins_base_dir` (`./data/plugins/`, cible d'extraction spec § Stockage), `plugin_registry_url/timeout/cache_ttl` existants dans [`config.py`](../../backend/app/config.py) ; **il manque taille max package + timeout download — à ajouter ici** (`plugin_package_max_size_mb`, `plugin_package_download_timeout`).
- **HTTP sortant** : `aiohttp ^3.11` déjà en dépendances — téléchargement **streaming** (jamais tout-en-mémoire), borné par les nouveaux settings.
- **Extraction** : `tarfile` stdlib — format de package `{name}-{version}.tar.gz` (spec 12) ; **nouveau code donc nouvelle surface** → couverture tests de sécurité requise (divergences n°8/9 ci-dessous).

### Divergences héritées de la mère — arbitrages délégués à cette sous-story

- **n°8 — Extraction sécurisée** : protection obligatoire path-traversal (membres `..`/chemins absolus rejetés) + **symlinks** contrôlés + **bombe** (limites taille totale/nombre de membres) — tout membre suspect → rejet sans écriture partielle ;
- **n°9 — SSRF download** : le schéma est déjà contraint HTTPS côté registre, mais le downloader doit **revalider** (pas de redirection vers IP privée, host contrôlé) — OWASP SSRF.

### Sécurité (règle 40 — extraits applicables à ce volet)

- Checksum **obligatoire** : installation refusée en cas d'écart (spec 15 § Vérifications à l'installation) — checksum absent du registre → rejet également ;
- Aucune donnée sensible dans les logs (jamais de contenu de package loggé) ;
- Erreurs typées depuis `core/exceptions.py` (jamais d'exception Python brute) ;
- Surface d'attaque nouvelle (download) → **tests de sécurité dédiés obligatoires** (risque §7.3) ;
- **Aucun résidu filesystem** en cas d'échec : fichiers temporaires purgés.

### Hors périmètre explicite

- Validation du manifest/architecture/ressources/dépendances (→ 169.2) ;
- Orchestration du pipeline, hooks, compose, rollback (→ 169.3) ;
- Chiffrement `config_values`, RL/RBAC, tests transverses globaux (→ 169.4).

## Critères d'acceptation (AC)

- [x] AC 1 *(extrait de l'AC 1 de la mère — partie DOWNLOAD)* : le package est téléchargé depuis l'URL du registre en **HTTPS** avec validation SSRF (schéma contrôlé, host validé, redirections vers IP privées rejetées) et téléchargement **streaming borné** par les settings — tests : URL non-HTTPS → rejet ; host non autorisé ou redirection vers IP privée → rejet ; dépassement taille max/timeout → rejet.
- [x] AC 2 *(extrait de l'AC 1 de la mère — partie DOWNLOAD)* : la vérification du **checksum SHA-256 est obligatoire**, sourcée depuis `RegistryPluginEntry.checksum_sha256` — tests : **install avec checksum invalide → rejet** avec message explicite ; checksum absent → rejet.
- [x] AC 3 *(extrait de l'AC 1 de la mère — partie DOWNLOAD)* : l'extraction vers `plugins_base_dir/{name}/` est **sécurisée** — tests : archive avec membre `..`/chemin absolu/symlink malveillant → rejet sans écriture ; bombe (taille/nombre de membres) → rejet ; **aucun résidu filesystem** sur échec (temporaires purgés).

## Références spécification

- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Étapes d'installation (étape 1 DOWNLOAD), § Stockage des plugins (arborescence `plugins_base_dir`), § Sécurité des plugins (checksum SHA-256 au téléchargement) ;
- [`12-marketplace.md`](../../docs/general_specs/12-marketplace.md) — format de package `{name}-{version}.tar.gz` + checksum ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Sécurité des plugins (vérifications à l'installation : checksum/signature), § Surface d'attaque plugins ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-3, §2.B B5, §7.3 (surface d'attaque download) ;
- [`backend_status.md`](../../docs/backend_status.md) — §5 (services plugin_*), §14.1 (coquille vide).

## Dépendances

- **Socle** : STORY-168 ✔ DONE (cache registry consommé par `plugin_registry_service`) — aucune dépendance bloquante.
- **Conditionne** [STORY-169.2](STORY-169.2-plugins-validation-manifest-arch-ressources.md) (validation testable sur le package extrait) puis [STORY-169.3](STORY-169.3-plugins-install-compose-hooks-rollback.md) (orchestration) — **première sous-story à traiter**.
- [STORY-169.4](STORY-169.4-plugins-configure-chiffrement-durcissement.md) reprend la validation SSRF dans ses tests transverses.
- Services externes : réseau sortant HTTPS vers `plugin_registry_url`. Aucun Redis/Vault requis.
- **Migrations DB : aucune.**

## État d'avancement technique

- 2026-10-30 (`analyse-story`) : exploration terminée — `## Tâches d'implémentation détaillées` et `## Tests à écrire` rédigées à partir du code réel (patterns ancrés : DI settings de [`plugin_registry_service.py`](../../backend/app/services/plugin_registry_service.py), mock aiohttp de [`test_plugin_registry_service.py`](../../backend/tests/unit/test_services/test_plugin_registry_service.py), branchement de la branche `source_not_supported` de [`plugin_manager_service.py`](../../backend/app/services/plugin_manager_service.py)). Complexité confirmée **L mais monotâche** (7 tâches séquentielles, un seul module nouveau) → pas de re-découpe. Statut inchangé (`TODO`), kanban/epic inchangés, aucun fichier de code modifié.
- 2026-10-30 (`treat-story`) : T1→T7 exécutées intégralement — settings (`plugin_package_max_size_mb=200`/`plugin_package_download_timeout=60`, ge=1), schéma `PluginPackageResult`, service `PluginPackageService` (SSRF complet + re-dir manuelle revalidée + streaming borné + `hmac.compare_digest` + extraction durcie pré-scan + staging/renommage atomique + purge `finally`), branchement manager (résolution registre, arbitrage n°1 `checksum_unavailable`→`plugin_not_in_registry`, purge sur manifest invalide). 61 tests ciblés verts (41 package + 20 manager), couverture `plugin_package_service` **92 %**, non-régression **2775 passed / 0 failed**, flake8/bandit/isort/black périmètre 0 erreur. Statut TODO→IN_PROGRESS→REVIEW→DONE.

*(coché pendant `treat-story` — voir `## Notes d'implémentation`)*

## Tâches d'implémentation détaillées

> Rédigées par `analyse-story` (2026-10-30) — exploration code réel, sans implémentation. **Ordre séquentiel strict** (chaque tâche s'appuie sur la précédente). Exigences sécurité ([`40-security.md`](../../.roo/rules/40-security.md)) intégrées dans chaque tâche. Aucune route API modifiée : le contrat `/plugins/install` (202, `require_admin`) est inchangé — seul le comportement backend devient réel (API-first respecté).

### Architecture cible (volet DOWNLOAD)

Nouveau service `PluginPackageService` (**un service = une classe**, DI `Settings` — pattern [`plugin_registry_service.py:42`](../../backend/app/services/plugin_registry_service.py)) consommé par `PluginManagerService` (branche `source`). Pipeline interne :

```mermaid
flowchart TD
    A[install source] --> B[Résolution entrée registre]
    B --> C[Validation SSRF de l'URL]
    C --> D[Download streaming borné + hash SHA-256]
    D --> E[Vérification checksum obligatoire]
    E -->|écart ou absent| R1[Rejet checksum_mismatch / checksum_missing]
    E -->|OK| F[Extraction durcie en staging]
    F -->|membre suspect ou bombe| R2[Rejet package_unsafe_member / package_bomb]
    F -->|OK| G[Renommage atomique vers plugins_base_dir/nom]
    G --> H[Purge staging en finally]
    R1 --> H
    R2 --> H
```

**Arbitrages pris par l'analyse** (complètent les divergences n°8/9 héritées) :

1. **Download réservé aux entrées du registre** : le checksum étant obligatoire et sourcé `RegistryPluginEntry.checksum_sha256`, une `source` qui ne se résout pas en entrée du registre (nom ou URL du `download_url`) est **rejetée** (`checksum_unavailable`) — pas de download d'URL arbitraire sans checksum ;
2. **Symlinks/hardlinks/devices/FIFO rejetés en bloc** à l'extraction (divergence n°8 « symlinks contrôlés » → politique la plus sûre : seuls fichiers réguliers et répertoires sont extraits) ;
3. **Extraction en staging puis renommage atomique** (même filesystem que `plugins_base_dir`) — aucun état partiel visible, cible finale créée en une opération ;
4. **Statuts inchangés dans 169.1** (pas de `downloading`/`validating`) — l'arbitrage des statuts intermédiaires appartient à 169.3 (orchestration) ;
5. **Re-directory manuelle** : `allow_redirects=False` + boucle bornée avec revalidation SSRF complète à chaque hop (OWASP — ne jamais laisser le client HTTP suivre une redirection non validée).

---

- [x] **T1 — Settings de bornage** ([`backend/app/config.py`](../../backend/app/config.py) + [`env.example`](../../env.example))

  Ajouter, juste après la section `# === Plugin Registry ===` (lignes ~522-534), deux settings :

  - `plugin_package_max_size_mb: int = Field(default=200, ge=1, description="Taille maximale en Mo d'un package plugin téléchargé — borne le streaming et l'archive")` ;
  - `plugin_package_download_timeout: int = Field(default=60, ge=1, description="Timeout total en secondes du téléchargement d'un package plugin")`.

  Défauts arbitraires documentés : 200 Mo (packages `{name}-{version}.tar.gz` spec 12, marge généreuse), 60 s (cohérent avec `plugin_registry_timeout=10` × marge download volumineux). Documenter les deux variables dans `env.example` (pydantic-settings les lit depuis l'environnement).

- [x] **T2 — Schéma de résultat** ([`backend/app/schemas/plugin_package.py`](../../backend/app/schemas/plugin_package.py), **nouveau**)

  `PluginPackageResult(BaseModel)` : `name: str`, `version: str`, `checksum_sha256: str`, `package_size_bytes: int`, `extracted_path: str`, `files_count: int` — contrat de sortie du service, consommé par 169.2 (validation sur le contenu extrait) et 169.3 (rollback filesystem), **non exposé en HTTP**. Docstring + `json_schema_extra` examples (convention des autres schémas, ex. [`plugin_registry.py`](../../backend/app/schemas/plugin_registry.py)). Champs non sensibles uniquement (pas d'URL complète ni de contenu — rules 40).

- [x] **T3 — `PluginPackageService` : validation SSRF + download streaming borné** ([`backend/app/services/plugin_package_service.py`](../../backend/app/services/plugin_package_service.py), **nouveau**)

  Classe unique `PluginPackageService` avec `__init__(self, settings: Settings)` (pattern DI du registry service). Constantes de classe documentées : `MAX_REDIRECTS = 5`, `CHUNK_SIZE = 64 * 1024`, `MAX_ARCHIVE_MEMBERS = 2000`, `MAX_EXTRACTION_FACTOR = 10` (borne décompressée = `plugin_package_max_size_mb` × 10 — anti-bombe). Méthode publique `async download_and_extract(self, entry: RegistryPluginEntry) -> PluginPackageResult` orchestrant T3+T4.

  **Validation SSRF** (divergence n°9) — méthode statique `_validate_url(url) -> yarl.URL` :
  - schéma `https` **strict** (rejet `http://` et tout autre schéma) → erreur typée `invalid_download_url` ;
  - host non vide, **pas de userinfo** (`user:pass@host` rejeté), pas de fragment ;
  - host littéral IP : rejet de toute adresse non publique via `ipaddress` (`is_private`, `is_loopback`, `is_link_local`, `is_reserved`, `is_multicast`, `is_unspecified`, y compris IPv4-mapped IPv6 — couvrir `169.254.169.254` metadata cloud) ;
  - méthode async `_assert_public_host(host)` : résolution `asyncio.get_running_loop().getaddrinfo(...)` → **toutes** les adresses résolues doivent être publiques, sinon erreur `ssrf_blocked` (anti DNS-rebinding partiel).

  **Download** — pattern [`_fetch_index_http`](../../backend/app/services/plugin_registry_service.py) adapté :
  - `aiohttp.ClientSession` avec `allow_redirects=False` ; sur 301/302/303/307/308 : lire `Location`, **revalider intégralement** (`_validate_url` + `_assert_public_host`) puis re-suivre, boucle ≤ `MAX_REDIRECTS` (dépassement → `too_many_redirects`) ;
  - timeout `aiohttp.ClientTimeout(total=settings.plugin_package_download_timeout)` ;
  - statut != 200 → `download_http_error` ;
  - **streaming** : `async for chunk in response.content.iter_chunked(CHUNK_SIZE)` — jamais tout-en-mémoire ; chaque chunk alimente `hashlib.sha256()` (checksum calculé pendant le téléchargement) + un compteur d'octets ; **dépassement `plugin_package_max_size_mb` → abandon immédiat** `package_too_large` (fermer la réponse proprement) ; écriture du chunk dans `staging/package.tar.gz` ;
  - exceptions : `asyncio.TimeoutError` → `download_timeout`, `aiohttp.ClientError` → `download_failed` (pattern registry) ;
  - staging : `Path(settings.plugins_base_dir) / ".staging" / f"{entry.name}-{secrets.token_hex(8)}"` — même filesystem que la cible finale (pré-requis du renommage atomique T4) ;
  - logs structurés (`plugin_package_download_started/completed/failed`) : host, taille, durée — **jamais de contenu du package ni de données sensibles** (rules 40).

- [x] **T4 — Checksum obligatoire + extraction durcie** (même fichier [`plugin_package_service.py`](../../backend/app/services/plugin_package_service.py))

  **Checksum** (AC 2) — `_verify_checksum(expected, actual_hex)` :
  - checksum absent/vide côté entrée → `checksum_missing` (défense en profondeur : le schéma registre le rend déjà requis, mais le downloader doit revalider) ;
  - comparaison en temps constant `hmac.compare_digest` ; écart → `checksum_mismatch` avec **message explicite** (attendu vs obtenu tronqués, cause + suggestion — AC 2).

  **Extraction** (AC 3, divergence n°8) — `_extract_package(archive_path, staging_dir, entry)` :
  - `tarfile.open(mode="r:gz")` ; **pré-scan de TOUS les membres avant toute écriture** :
    - types autorisés : fichiers réguliers (`REGTYPE`/`AREGTYPE`) et répertoires (`DIRTYPE`) uniquement — tout symlink/hardlink/device/FIFO → `package_unsafe_member`, **rejet sans écriture partielle** ;
    - noms : rejet de `..`, chemins absolus, backslashes ; containment vérifié par `os.path.realpath` + `os.path.commonpath` (la cible résolue doit rester sous le répertoire d'extraction) → `package_unsafe_member` ;
    - **bombe** : `len(members) > MAX_ARCHIVE_MEMBERS` → `package_bomb` ; `sum(member.size) > plugin_package_max_size_mb × MAX_EXTRACTION_FACTOR` → `package_bomb` ;
  - extraction via `extractall(path, members=validés, filter="data")` (PEP 706 — disponible Python 3.11.4+, **défense en profondeur en plus** des contrôles explicites ci-dessus, qui portent les messages d'erreur typés) ;
  - **install atomique** : cible `Path(settings.plugins_base_dir) / entry.name` — `entry.name` kebab-case déjà validé par le schéma registre (anti path-traversal natif) ; si la cible **existe déjà** → `target_exists` (l'upgrade/overwrite est arbitré en 169.3) ; sinon `extracted_dir.rename(target)` (atomique, même filesystem) ;
  - **purge du staging en `finally`** (`shutil.rmtree(..., ignore_errors=True)`) sur **tous** les chemins — succès comme échec : aucun résidu filesystem (AC 3).

- [x] **T5 — Branchement dans `PluginManagerService`** ([`backend/app/services/plugin_manager_service.py`](../../backend/app/services/plugin_manager_service.py))

  - `__init__(self, settings: Optional[Settings] = None)` : défaut `get_settings()` — **rétrocompatible** avec l'instanciation module-level du router ([`plugins.py:50`](../../backend/app/api/v1/plugins.py) `_plugin_service = PluginManagerService()` inchangé) ; instancier `self._package_service = PluginPackageService(settings or get_settings())` et `self._registry_service = PluginRegistryService(settings or get_settings())` (mockables en tests) ;
  - nouveau helper async `_resolve_registry_entry(source: str) -> RegistryPluginEntry` : si `source` commence par `https://` → chercher l'entrée du registre dont `download_url == source` (via `PluginRegistryService.list_plugins()`) ; sinon traiter comme identifiant nom → `get_plugin(source)` ; introuvable → `plugin_not_in_registry` ; **arbitrage n°1** : une URL ne correspondant à aucune entrée → rejet `checksum_unavailable` (download impossible sans checksum de registre) ;
  - **remplacer la branche [`source_not_supported`](../../backend/app/services/plugin_manager_service.py) (lignes 148-153)** par : `entry = await self._resolve_registry_entry(...)` → `result = await self._package_service.download_and_extract(entry)` → `manifest = self._manifest_service.validate_manifest_file(Path(result.extracted_path) / "windflow-plugin.yml")` (nom de fichier manifest standard, cf. [`plugin_manifest_service.py`](../../backend/app/services/plugin_manifest_service.py)) → **poursuite du flux existant à l'identique** (doublon, dépendances, création DB, hook, événements — rien ne change) ;
  - sur échec manifest après extraction réussie : **purger `plugins_base_dir/{name}` avant remontée** de l'erreur (wrap `manifest_invalid` — rejet sans résidu, périmètre download) ;
  - **statuts inchangés** (arbitrage n°4 : `downloading`/`validating` = 169.3) ; messages d'erreur typés `WindFlowException(details={"error_type": ...})` conformes au pattern du fichier.

- [x] **T6 — Tests** : implémenter la section `## Tests à écrire` ci-dessous (nouveau `test_plugin_package_service.py` + extensions `test_plugin_manager_service.py`). Mocks obligatoires : `aiohttp.ClientSession` patché au niveau du module (pattern [`test_plugin_registry_service.py:148`](../../backend/tests/unit/test_services/test_plugin_registry_service.py)), `getaddrinfo`, archives tar.gz construites dans `tmp_path`.

- [x] **T7 — Validation finale** : `make backend-lint` (isort + black + flake8 + mypy + bandit — bandit vérifiera l'usage `tarfile`), tests ciblés `poetry run pytest backend/tests/unit/test_services/test_plugin_package_service.py backend/tests/unit/test_services/test_plugin_manager_service.py -v --cov=app/services/plugin_package_service --cov-fail-under=80`, puis non-régression `make backend-test-unit`. Couverture ≥ 80 % du nouveau module (rules 35).

## Tests à écrire

> Conformes à [`35-testing-quality-gates.md`](../../.roo/rules/35-testing-quality-gates.md) — patterns AAA, docstrings cas nominal/erreur, mocks aiohttp par patch module. Localisation : `backend/tests/unit/test_services/`. Couverture cible ≥ 80 % de `plugin_package_service.py` (surface d'attaque nouvelle — risque §7.3).

### Fichier 1 : [`backend/tests/unit/test_services/test_plugin_package_service.py`](../../backend/tests/unit/test_services/test_plugin_package_service.py) (nouveau)

Fixtures : `Settings` avec `plugins_base_dir=tmp_path` (les nouveaux settings T1 testés au passage), helper local `_build_plugin_tar(dir, files)` pour générer des archives tar.gz légitimes, mock `aiohttp.ClientSession` (AsyncMock + réponse itérant des chunks — pattern registry), mock `loop.getaddrinfo` résolvant vers une IP publique (`203.0.113.10`, documentation TEST-NET).

**Cas nominaux**

- `test_download_and_extract_success` — archive valide + checksum correct → `PluginPackageResult` rempli, arborescence extraite sous `plugins_base_dir/{name}/`, staging **purgé** (AC 1/2/3) ;
- `test_download_follows_validated_redirect` — 301 vers URL publique (chaque hop revalidé) → succès ;
- `test_default_settings_bounds` — `plugin_package_max_size_mb=200`, `plugin_package_download_timeout=60` par défaut, `ge=1` respecté.

**Sécurité SSRF (AC 1)**

- `test_rejects_non_https_url` — `http://...` → `invalid_download_url` ;
- `test_rejects_private_ip_literal` — `https://127.0.0.1`, `https://10.0.0.1`, `https://169.254.169.254` → `ssrf_blocked`/`invalid_download_url` ;
- `test_rejects_host_resolving_to_private_ip` — `getaddrinfo` mocké → `192.168.1.1` → `ssrf_blocked` ;
- `test_rejects_redirect_to_private_ip` — 301 `Location: https://127.0.0.1/x.tar.gz` → rejet, **aucune seconde requête vers l'IP privée** ;
- `test_rejects_too_many_redirects` — boucle > `MAX_REDIRECTS` → `too_many_redirects` ;
- `test_rejects_userinfo_in_url` — `https://user:pass@host/...` → `invalid_download_url`.

**Checksum obligatoire (AC 2)**

- `test_rejects_checksum_mismatch` — contenu altéré → `checksum_mismatch` avec message explicite, staging purgé ;
- `test_rejects_missing_checksum` — entrée sans checksum (`model_construct` pour bypass la validation Pydantic) → `checksum_missing`.

**Streaming borné (AC 1)**

- `test_rejects_package_over_max_size` — settings `max=1` Mo + flux plus grand → `package_too_large`, purge, **arrêt avant la fin du flux** ;
- `test_rejects_download_timeout` — `asyncio.TimeoutError` mocké → `download_timeout` ;
- `test_rejects_http_error_status` — 404/500 → `download_http_error` ;
- `test_rejects_network_error` — `aiohttp.ClientError` → `download_failed`.

**Extraction durcie (AC 3, divergence n°8)**

- `test_rejects_path_traversal_member` — membres `../evil.sh`, `/etc/passwd`, `..\\win-path` → `package_unsafe_member` **sans aucune écriture hors staging** ;
- `test_rejects_symlink_and_special_members` — symlink, hardlink, device, FIFO → `package_unsafe_member` ;
- `test_rejects_member_count_bomb` — plus de `MAX_ARCHIVE_MEMBERS` membres → `package_bomb` ;
- `test_rejects_decompressed_size_bomb` — somme des tailles > borne → `package_bomb` ;
- `test_rejects_when_target_exists` — `plugins_base_dir/{name}` pré-créé → `target_exists`, contenu existant **intact** ;
- `test_no_residue_on_any_failure` — paramétré sur les rejets ci-dessus : `.staging` n'existe plus après l'appel (AC 3).

**Hygiène logs** : `test_logs_contain_no_package_content` — caplog : aucun chunk binaire ni donnée sensible dans les entrées loggées (rules 40).

### Fichier 2 : [`backend/tests/unit/test_services/test_plugin_manager_service.py`](../../backend/tests/unit/test_services/test_plugin_manager_service.py) (extension)

Mocks : `_package_service` et `_registry_service` injectés (entry registre + extraction simulée écrivant un `windflow-plugin.yml` valide dans `tmp_path`).

- `test_install_from_source_success` — source = nom registre → plugin créé, statut `installed`, manifest issu du package extrait ;
- `test_install_source_unknown_plugin_rejected` — registre ne connaît pas la source → `plugin_not_in_registry`, **aucune ligne Plugin en base** ;
- `test_install_source_checksum_mismatch_no_db_row` — package service lève `checksum_mismatch` → exception remontée, aucune ligne Plugin, **aucun résidu filesystem** ;
- `test_install_source_invalid_manifest_purges_extraction` — extraction OK puis manifest invalide → rejet `manifest_invalid` + `plugins_base_dir/{name}` purgé ;
- `test_install_manifest_yaml_path_unchanged` — non-régression : le chemin local `manifest_yaml` existant continue de fonctionner sans toucher au filesystem.

## Notes d'implémentation

**Date :** 2026-10-30 (`treat-story`) — T1→T7 exécutées séquentiellement, sans divergence de périmètre.

### Fichiers créés

- [`backend/app/schemas/plugin_package.py`](../../backend/app/schemas/plugin_package.py) — `PluginPackageResult` (T2) ;
- [`backend/app/services/plugin_package_service.py`](../../backend/app/services/plugin_package_service.py) — `PluginPackageService` complet (T3+T4) ;
- [`backend/tests/unit/test_services/test_plugin_package_service.py`](../../backend/tests/unit/test_services/test_plugin_package_service.py) — 41 tests (T6).

### Fichiers modifiés

- [`backend/app/config.py`](../../backend/app/config.py) — settings `plugin_package_max_size_mb=200` / `plugin_package_download_timeout=60` (`ge=1`) (T1) ;
- [`env.example`](../../env.example) — section `PLUGINS — PACKAGE` documentant les 2 variables (T1) ;
- [`backend/app/services/plugin_manager_service.py`](../../backend/app/services/plugin_manager_service.py) — DI settings (rétrocompatible), `_resolve_registry_entry`, `_install_from_source`, remplacement de la branche `source_not_supported` (T5) ;
- [`backend/tests/unit/test_services/test_plugin_manager_service.py`](../../backend/tests/unit/test_services/test_plugin_manager_service.py) — 6 nouveaux tests `TestInstallFromSource` + fixtures injectables (T6).

### Décisions techniques

- **Racine du contenu extrait** : les packages conventionnels enveloppent le contenu dans `{name}/` — le service détermine la racine utile (manifest à la racine OU sous `{name}/`) avant le renommage atomique, garantissant `plugins_base_dir/{name}/windflow-plugin.yml` dans les deux layouts (couvert par test).
- **Purge du staging en `finally`** sur tous les chemins + `rmdir` best-effort du parent `.staging` — aucun résidu, atomique préservée.
- **Re-dir manuelle** (`allow_redirects=False`) avec revalidation SSRF + DNS complète à chaque hop, `Location` absent → `download_http_error`.
- **Défense en profondeur checksum** : revalidation de l'absence (le schéma registre le rend déjà requis) + `hmac.compare_digest`.
- **Anti-bombe double borne** : 2000 membres max + taille décompressée totale ≤ `max_size_mb × 10`.
- **`filter="data"` (PEP 706)** : garde les bits de permission/mode sains en plus des contrôles explicites typés.

### Divergences par rapport à l'analyse

1. **`get_settings()` inexistant** : la story T5 mentionnait `get_settings()` — le module `config.py` exporte un singleton `settings` ; le défaut du constructeur utilise donc `settings or global_settings` (sémantique identique, rétrocompatible avec `_plugin_service = PluginManagerService()` du router).
2. **IP de test `203.0.113.10` remplacée** : les ranges de documentation TEST-NET (RFC 5737) sont classés `is_private` par `ipaddress` depuis Python 3.12.4+ (fix gh-113171) — l'IP publique simulée des tests est passée à `93.184.216.34` (commentaire explicite dans le fichier de tests). Aucun impact production.
3. **`checksum_unavailable` vs `plugin_not_in_registry`** : l'analyse T5 prévoyait `checksum_unavailable` pour une URL hors registre (arbitrage n°1) ; implémenté avec `plugin_not_in_registry` pour rester cohérent avec le message d'erreur existant du registre (un seul error_type pour "source inconnue", test dédié `test_install_source_url_not_in_registry_rejected`).
4. **Manifest de test `hybrid`→`extension`** : la cohérence du schéma `PluginManifest` exige `extensions` pour `hybrid` — le manifest factice des tests manager utilise `extension`+`api_module` (pattern des autres tests du fichier).

### Difficultés rencontrées

- Aucune bloquante. Nota : `make backend-lint` global échoue sur ~28 fichiers **préexistants** (isort/black sur HEAD, vérifié par `git stash`) — périmètre STORY-169.1 à 0 erreur (isort, black, flake8, bandit) ; mypy : 0 erreur directe sur les 3 fichiers modifiés/créés (15 erreurs préexistantes ailleurs, identiques sur HEAD).

### Validation (T7)

| Commande | Résultat |
|---|---|
| `poetry run pytest backend/tests/unit/test_services/test_plugin_package_service.py -v` | **41 passed** |
| `poetry run pytest backend/tests/unit/test_services/test_plugin_manager_service.py -v` | **20 passed** (14 existants + 6 nouveaux) |
| Couverture `plugin_package_service.py` | **92 %** (≥ 80 % requis) — schéma `plugin_package.py` 100 % |
| `poetry run flake8 <6 fichiers périmètre>` | 0 erreur |
| `poetry run bandit <périmètre> -ll` | 0 issue (tarfile durci couvert) |
| `cd backend && poetry run mypy <3 fichiers>` | 0 erreur directe (15 préexistantes ailleurs, inchangées vs HEAD) |
| `make backend-test-unit` (non-régression) | **2775 passed, 0 failed** |
