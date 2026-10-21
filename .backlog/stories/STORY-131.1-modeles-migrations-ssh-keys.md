# STORY-131.1 : Modèles & migrations — `ssh_keys`, `host_ssh_fingerprints` et data migration crypto (P1-9)

**Statut :** DONE
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Story Parent (split) :** STORY-131 ([ABANDONED — découpe proactive post-analyse le 2026-10-16](STORY-131-ssh-keys-empreintes-anti-mitm.md))
**Item plan :** P1-9 (axe A7, rapports §4/§7) — ampleur **M**

> **Périmètre (découpe)** : cette sous-story reprend le **volet modèles & migrations** (phase A de l'analyse STORY-131) — tâches 1→6 de la mère, couvrant l'AC 1 (et la partie validation de l'AC 5 limitée à ce périmètre). Le volet service/API de gestion est porté par [STORY-131.2](STORY-131.2-service-api-gestion-cles-ssh.md), le volet runtime anti-MITM par [STORY-131.3](STORY-131.3-anti-mitm-tofu-runtime.md) — **toutes deux dépendent de celle-ci**.

## Description

En tant qu'administrateur de cibles distantes WindFlow, je veux les entités **`ssh_keys`** (clé privée chiffrée au repos, partageable par N cibles) et **`host_ssh_fingerprints`** (empreintes de clés d'hôtes, socle de la politique TOFU) créées en base via migrations Alembic, avec **migration des credentials SSH existants sans perte**, afin de poser le socle de données des clés réutilisables et de l'anti-MITM (consommé par STORY-131.2 et STORY-131.3).

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §4, §7) : les credentials cibles sont stockés en **JSON en clair** dans `Target.connection_config` (chiffrement posé par STORY-103/EPIC-011) ; il n'existe ni entité `ssh_keys`, ni empreintes known_hosts.

## Contexte technique

> Extrait de l'analyse STORY-131 (2026-10-16, `analyse-story`) — volet phase A. Fondée sur le code réel du dépôt (fichiers et lignes cités). Aucun code modifié.

### Arbitrage F3 — correspondance spec ↔ code réel

L'entité « Host » des specs 06/15 **n'existe pas en base** : il n'y a pas de table `hosts` (cf. [`backend/app/models/`](../../backend/app/models/) — 15 modèles, aucun `host.py`). L'équivalent P1 est [`Target`](../../backend/app/models/target.py:68) (table `targets`). Le renommage/split `hosts` est porté par STORY-166 (EPIC-013, P2). **Conséquence directe : `host_ssh_fingerprints.host_id` référence `targets.id`** (arbitrage F3 « double nommage » documenté dans la story mère — la surface API réelle reste `/targets/*`).

### Patterns existants à réutiliser (directs)

- **Modèle avec secret chiffré** : [`api_key.py`](../../backend/app/models/api_key.py) (STORY-124.1) — UUID String(36), commentaires spec, `__repr__` sans secret ;
- **Migration additive** : [`2026_09_13_1241_api_keys_table.py`](../../backend/alembic/versions/2026_09_13_1241_api_keys_table.py) ; **data migration** (précédent établi) : [`2026_09_08_1213_migrate_users_org_to_associations.py`](../../backend/alembic/versions/2026_09_08_1213_migrate_users_org_to_associations.py) ;
- **Chiffrement au repos** : [`SecretManager`](../../backend/app/core/secret_manager.py) (STORY-103) — `get_secret_manager()`, `encrypt/decrypt`, `is_encrypted` ; pattern d'encapsulation crypto d'une colonne JSON : [`encrypt_credentials_for_storage`](../../backend/app/models/target.py:29) (et [`decrypt_credentials_from_storage`](../../backend/app/models/target.py:46)).

### Points d'intégration & contraintes

- **Empreinte normalisée** `SHA256:<base64nopad>` (asyncssh `key.fingerprint`, ~50 car.) → colonne `fingerprint` en `VARCHAR(100)` (spec 06 OK) ;
- **Data migration crypto** : l'extraction des clés existantes en migration Alembic requiert le SecretManager (settings) — vérifier que [`alembic/env.py`](../../backend/alembic/env.py) charge la config app ; sinon fallback = migration paresseuse au premier accès (pattern double lecture STORY-103.2 déjà éprouvé sur `decrypted_credentials`).

### Risques identifiés

- **R1 — Data migration** : erreur de déchiffrement (clé maîtresse changée) → la migration doit être **tolérante** (target laissée intacte, warning loggé, pas d'échec du `upgrade head`).

### Points d'attention sécurité (checklist rules 40)

- **Aucune clé privée en clair en colonne** : `private_key_encrypted` contient exclusivement un token Fernet (`get_secret_manager().encrypt`) ;
- `__repr__` des modèles sans secret (id/name/fingerprint uniquement) ; logs de la data migration sans donnée sensible (les warnings R1 ne loggent jamais le contenu de credentials).

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend l'AC 1 de la story mère)* : Les tables `ssh_keys` et `host_ssh_fingerprints` existent via migration Alembic (STORY-120) conformément aux schémas spec 06 ; les cibles à accès SSH référencent une clé via FK ; migration des credentials existants **sans perte** (clés privées chiffrées via STORY-103, jamais en clair), **dédupliquées par fingerprint** (une `SSHKey` par clé unique — base de la réutilisabilité par N cibles, AC 2 mère) et **tolérantes aux échecs** de déchiffrement (R1 : le `upgrade head` ne doit jamais échouer).
- [x] AC 2 *(découpe locale de l'AC 5 de la mère, périmètre modèles)* : tests modèles + migration passants ; `make lint` vert ; couverture ≥ 80 % sur `backend/app/models/ssh_key.py` et `backend/app/models/host_ssh_fingerprint.py`.

## Références spécification

- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités d'accès distant (SSH) : `SSHKey` et `HostSSHFingerprint` (schémas SQL, relations) ;
- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) — § Sécurité réseau → Hosts distants (SSH) : clés réutilisables chiffrées au repos, empreintes known_hosts ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §4 (credentials JSON en clair sur `Target`), §7 (critique SSH) ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-9 (dépend de P1-1 et P0-4), §2.A A7, §3 F4 étape 1, §5 chaîne critique n°2.

## Dépendances

- **STORY-120** (Alembic — fait ✅ : baseline + migrations livrées, cf. [`backend/alembic/versions/`](../../backend/alembic/versions/)) ; **STORY-103** (EPIC-011 — fait ✅ : [`SecretManager`](../../backend/app/core/secret_manager.py) opérationnel sur `Target.credentials`).
- **Services externes** : aucun nouveau (asyncssh déjà en dépendance `^2.14.0`, utilisé par la data migration pour `import_private_key`/fingerprint). Aucune nouvelle variable de configuration requise (le SecretManager réutilise `SECRET_ENCRYPTION_KEY`/fallback JWT).
- **Conditionne** : [STORY-131.2](STORY-131.2-service-api-gestion-cles-ssh.md) (schémas/service/API consomment les modèles et la FK) et [STORY-131.3](STORY-131.3-anti-mitm-tofu-runtime.md) (le helper TOFU lit `HostSSHFingerprint` et `SSHKey.decrypted_private_key`) ; au-delà, STORY-164 (EPIC-013 — WS `ssh`) et STORY-174 (P2 — workload adapter).

## État d'avancement technique

*(cochage progressif pendant treat-story ; correspondance avec l'analyse mère — phase A — indiquée par tâche)*

- [x] Tâche 1 — *(mère : tâche 1 / A1)* Modèle `SSHKey` créé (`backend/app/models/ssh_key.py`)
- [x] Tâche 2 — *(mère : tâche 2 / A2)* Modèle `HostSSHFingerprint` créé (`backend/app/models/host_ssh_fingerprint.py`)
- [x] Tâche 3 — *(mère : tâche 3 / A3)* FK `targets.ssh_key_id` + relations ajoutées (`backend/app/models/target.py`)
- [x] Tâche 4 — *(mère : tâche 4 / A4)* Modèles enregistrés (`backend/app/models/__init__.py`)
- [x] Tâche 5 — *(mère : tâche 6)* Vérification `alembic/env.py` — **décision : data migration crypto directement dans Alembic** (`env.py` importe déjà `settings` + `models` avec `sys.path` résolu ; import applicatif paresseux dans la migration, garde offline-mode pour `--sql`) — aucun fallback paresseux requis
- [x] Tâche 6 — *(mère : tâche 5 / A5)* Migration Alembic livrée (`backend/alembic/versions/2026_10_16_1311_ssh_keys_and_fingerprints.py` — tables + FK + data migration tolérante R1 ; `alembic check` sans diff après upgrade)
- [x] Tests — *(mère : A6)* Tests modèles + migration passants (29 tests : familles 1-3, couverture 100 % sur les 2 modèles ; tests Alembic existants adaptés au pattern additive et repassés verts)

## Tâches d'implémentation détaillées

> Séquence reprise de la phase A de l'analyse STORY-131 (tâches 1→6 de la mère), renumérotée. Seul ajustement : la vérification `env.py` (tâche 6 de la mère) est traitée **avant** l'écriture de la migration — l'analyse exigeait explicitement que cette décision soit prise « au début de la tâche 5 ». Périmètre backend uniquement (API-first).

### Tâche 1 : Modèle `SSHKey`

*(mère : tâche 1)*

**Objectif :** créer l'entité des clés SSH réutilisables avec clé privée chiffrée au repos (AC 1).

**Fichiers :**
- `backend/app/models/ssh_key.py` — **Créer** (pattern [`api_key.py`](../../backend/app/models/api_key.py)) : classe `SSHKey`, table `ssh_keys` — `id` String(36) UUID PK, `name` String(100) UNIQUE NOT NULL, `key_type` String(20) NOT NULL default `"ssh-ed25519"`, `public_key` Text NOT NULL (consultable — déploiement `authorized_keys`), `private_key_encrypted` Text NOT NULL (token Fernet via `get_secret_manager().encrypt` — **jamais de clé en clair en colonne**), `fingerprint` String(100) NOT NULL + index `idx_ssh_keys_fingerprint`, `last_used_at` DateTime nullable, `created_at`. Ajouter une property `decrypted_private_key` (déchiffrement en mémoire uniquement, jamais loggée) et un `__repr__` sans secret (id/name/fingerprint uniquement). Conformité stricte spec 06 § SSHKey.

**Dépend de :** Aucune

### Tâche 2 : Modèle `HostSSHFingerprint`

*(mère : tâche 2)*

**Objectif :** créer l'entité des empreintes d'hôtes (socle TOFU, consommé par STORY-131.2/131.3).

**Fichiers :**
- `backend/app/models/host_ssh_fingerprint.py` — **Créer** : classe `HostSSHFingerprint`, table `host_ssh_fingerprints` — `id` String(36) PK, `host_id` String(36) **FK `targets.id` ON DELETE CASCADE** (adaptation F3 de `hosts.id`), `hostname` String(255) NOT NULL, `port` Integer default 22, `key_type` String(20) NOT NULL (algorithme de clé d'hôte), `fingerprint` String(100) NOT NULL, `accepted` Boolean default False (TRUE après acceptation explicite), `accepted_at` DateTime nullable, `created_at`, **`UniqueConstraint(host_id, hostname, port, key_type)`** + index `idx_host_ssh_fp_host`. Relation `target` (back_populates).

**Dépend de :** Tâche 1 (relation croisée `SSHKey.targets` ↔ `Target.ssh_key` posée tâche 3 ; les deux modèles vivent dans le même lot)

### Tâche 3 : FK `targets.ssh_key_id`

*(mère : tâche 3)*

**Objectif :** permettre à N cibles de référencer la même clé (AC 1/AC 2 mère).

**Fichiers :**
- `backend/app/models/target.py` — **Modifier** : ajouter `ssh_key_id` String(36) nullable + `ForeignKey("ssh_keys.id", ondelete="SET NULL")` + relationship `ssh_key` (et `targets` côté `SSHKey`). **Ne pas supprimer la colonne `credentials`** : `username`, `password` (auth password), `sudo_*` y restent chiffrés (STORY-103.2) ; seul `ssh_private_key` est migré vers l'entité.

**Dépend de :** Tâches 1-2

### Tâche 4 : Enregistrement des modèles

*(mère : tâche 4)*

**Objectif :** rendre les modèles découvrables par Alembic autogenerate et les imports applicatifs.

**Fichiers :**
- `backend/app/models/__init__.py` — **Modifier** : enregistrer `SSHKey` et `HostSSHFingerprint` (pattern des 15 modèles existants).

**Dépend de :** Tâches 1-3

### Tâche 5 : Vérification du contexte Alembic (décision préalable)

*(mère : tâche 6 — traitée en premier conformément à la note de l'analyse : « décision à prendre au début de la tâche 5 »)*

**Objectif :** statuer sur la faisabilité de la data migration crypto dans Alembic.

**Fichiers :**
- `backend/alembic/env.py` — **Vérifier (et modifier si besoin)** : le contexte doit permettre l'import du SecretManager (settings) pour la data migration ; sinon, basculer l'extraction en **migration paresseuse au premier accès** (pattern double lecture STORY-103.2). Décision à consigner en note d'implémentation.

**Dépend de :** Tâches 1-4

### Tâche 6 : Migration Alembic (tables + FK + data migration)

*(mère : tâche 5)*

**Objectif :** livrer le schéma et migrer les clés privées existantes sans perte (AC 1, risque R1).

**Fichiers :**
- `backend/alembic/versions/2026_10_XX_1311_ssh_keys_and_fingerprints.py` — **Créer** (patterns : additive de [`1241_api_keys`](../../backend/alembic/versions/2026_09_13_1241_api_keys_table.py), data migration de [`1213`](../../backend/alembic/versions/2026_09_08_1213_migrate_users_org_to_associations.py)) :
  - `upgrade()` : créer `ssh_keys` (+ index fingerprint), `host_ssh_fingerprints` (+ index host + unique constraint), ajouter colonne `ssh_key_id` nullable sur `targets` (batch_alter_table, FK SET NULL) ;
  - **Data migration** (AC 1 « sans perte ») : itérer les `targets` ; déchiffrer `credentials` via [`decrypt_credentials_from_storage`](../../backend/app/models/target.py:46) ; si `ssh_private_key` présent → `asyncssh.import_private_key` (passphrase depuis credentials le cas échéant) → fingerprint ; **déduplication par fingerprint** (une `SSHKey` par clé unique, réutilisée par N cibles — AC 2 mère) ; création avec `name` auto unique (ex. `imported-<fp8>`) et `private_key_encrypted` chiffrée ; setter `ssh_key_id` ; retirer `ssh_private_key` (et `ssh_private_key_passphrase`) du dict puis **ré-encrypter** `credentials`. Tolérance R1 : échec de déchiffrement/import → target inchangée + `logger.warning` (jamais d'échec du upgrade) ;
  - `downgrade()` : drop des contraintes/tables + colonne `ssh_key_id` (les clés importées ne sont pas re-inlinées — non destructif, documenté dans la docstring).

**Dépend de :** Tâches 1-5 (décision tâche 5 appliquée ici)

## Tests à écrire

> Règles 35/40. Cibles : `backend/tests/unit/`. Extrait de l'analyse STORY-131 — familles 1-3 (section « Modèles (Phase A) »).

### Backend — unitaires

1. **`backend/tests/unit/test_models/test_ssh_key.py`** : roundtrip chiffrement (colonne = token Fernet, clé privée jamais en clair — oracle `SecretManager.is_encrypted` + absence du PEM dans la valeur stockée, pattern [`test_target.py`](../../backend/tests/unit/test_models/test_target.py)) ; unicité `name` (IntegrityError) ; `decrypted_private_key` correct ; `__repr__` sans secret ; index fingerprint présent dans la migration.
2. **`backend/tests/unit/test_models/test_host_ssh_fingerprint.py`** : contrainte UNIQUE `(host_id, hostname, port, key_type)` (deux insertions identiques → IntegrityError ; key_type différent → OK, multi-algorithmes spec 06) ; cascade delete de la target ; défauts (`accepted=False`, port 22).
3. **`backend/tests/unit/test_migrations_131.py`** (pattern tests Alembic existants) : upgrade crée les 2 tables + FK `targets.ssh_key_id` ; **data migration** : target avec `ssh_private_key` chiffré → `ssh_keys` créée (fingerprint correct, private chiffrée) + FK settée + credentials ré-encryptés sans `ssh_private_key` ; deux targets partageant la même clé → **une seule** `SSHKey` (dédup, AC 2 mère) ; target sans clé → inchangée ; target illisible (mauvaise clé) → inchangée sans échec (R1) ; idempotence du re-run.

### Commandes de validation

```bash
poetry run pytest backend/tests/unit/test_models/test_ssh_key.py backend/tests/unit/test_models/test_host_ssh_fingerprint.py backend/tests/unit/test_migrations_131.py -v
make lint
```

## Notes d'implémentation

*(clôture treat-story — 2026-10-16)*

### Fichiers créés

- [`backend/app/models/ssh_key.py`](../../backend/app/models/ssh_key.py) — modèle `SSHKey` (spec 06 stricte) : `private_key_encrypted` Text (token Fernet exclusivement), propriété `decrypted_private_key` (mémoire seule), `__repr__` sans matériau de clé, relation `targets` ;
- [`backend/app/models/host_ssh_fingerprint.py`](../../backend/app/models/host_ssh_fingerprint.py) — modèle `HostSSHFingerprint` : FK `targets.id` ON DELETE CASCADE (arbitrage F3), `UniqueConstraint(host_id, hostname, port, key_type)` nommée `uq_host_ssh_fp_identity`, index `idx_host_ssh_fp_host`, défauts TOFU (`accepted=False`, `port=22`) ;
- [`backend/alembic/versions/2026_10_16_1311_ssh_keys_and_fingerprints.py`](../../backend/alembic/versions/2026_10_16_1311_ssh_keys_and_fingerprints.py) — révision `1311_ssh_keys` (down_revision `1251_audit_logs`) : création des 2 tables + index, `targets.ssh_key_id` nullable FK SET NULL (batch), data migration crypto tolérante R1, downgrade non destructif documenté ;
- [`backend/tests/unit/test_models/test_ssh_key.py`](../../backend/tests/unit/test_models/test_ssh_key.py) — 13 tests (roundtrip chiffrement, unicité name, défauts, `__repr__` sûr, structure, relation N↔1) ;
- [`backend/tests/unit/test_models/test_host_ssh_fingerprint.py`](../../backend/tests/unit/test_models/test_host_ssh_fingerprint.py) — 10 tests (UNIQUE 4 colonnes, multi-algorithmes, cascade, défauts, structure) ;
- [`backend/tests/unit/test_migrations_131.py`](../../backend/tests/unit/test_migrations_131.py) — 6 tests (schéma, data migration+dédup, sans clé, R1 illisible, rejouabilité, downgrade) — pattern subprocess des tests Alembic existants, seeds chiffrés via `SecretManager(MASTER_KEY)` explicite.

### Fichiers modifiés

- [`backend/app/models/target.py`](../../backend/app/models/target.py) — colonne `ssh_key_id` (FK `ssh_keys.id` SET NULL) + relations `ssh_key` / `ssh_fingerprints` ; `credentials` inchangé (username/password/sudo_* y restent) ;
- [`backend/app/models/__init__.py`](../../backend/app/models/__init__.py) — enregistrement `SSHKey` + `HostSSHFingerprint` ;
- [`backend/tests/unit/test_alembic_config.py`](../../backend/tests/unit/test_alembic_config.py), [`backend/tests/unit/test_database.py`](../../backend/tests/unit/test_database.py), [`backend/tests/integration/test_migrations.py`](../../backend/tests/integration/test_migrations.py) — maintenance liée (pattern établi « étendu à … par STORY-XXX ») : `EXPECTED_TABLES` + `ssh_keys`/`host_ssh_fingerprints`, `ADDITIVE_TABLES`, helper `_drop_targets_ssh_key_id` (rebuild batch Alembic — SQLite refuse `DROP COLUMN` sur colonne FK inline ; drop de la colonne **avant** `DROP TABLE ssh_keys` sinon FK dangling casse la réflexion).

### Décisions techniques

- **Tâche 5 (env.py)** : data migration crypto **directement dans Alembic** — `env.py` résout déjà `sys.path` et importe `settings`+`models` ; imports applicatifs (SecretManager, helpers STORY-103.2, asyncssh) **paresseux** dans la migration ; garde `is_offline_mode()` pour `--sql` (aucune donnée en offline). Aucune modification d'`env.py` requise.
- **Déduplication** : par fingerprint (asyncssh `get_fingerprint()`), inclut les lignes `ssh_keys` préexistantes (rejouabilité après `alembic stamp`) ; `name` auto `imported-<fp8>` avec anti-collision (`-2`, `-3`…).
- **Data migration** : retrait de `ssh_private_key` ET `ssh_private_key_passphrase` des credentials puis ré-encryption (les credentials chiffrés restent au format opaque STORY-103.2) ; `updated_at` rafraîchi.
- **asyncssh 2.21.1** (divergence mineure vs analyse) : `key.fingerprint` n'existe plus → `key.get_fingerprint()` (retourne bien `SHA256:<base64nopad>`) ; PEM via `export_private_key()`/`import_private_key()` (erreurs `KeyImportError`/`KeyEncryptionError` catchées par la tolérance R1 générique).
- **Échecs R1** : `except Exception` par cible (déchiffrement, PEM invalide, passphrase manquante) → `logger.warning` avec **id de ligne uniquement**, cible intégralement inchangée (vérifié byte-pour-byte par test).

### Divergences par rapport à l'analyse

- Aucune divergence structurelle. Seul ajustement : utilisation de `get_fingerprint()` (API asyncssh 2.21) au lieu de l'attribut `fingerprint` cité par l'analyse (supprimé dans cette version) — même format de sortie.
- Maintenance non prévue par la story mais nécessaire : adaptation des 3 fichiers de tests Alembic existants au pattern additive (suivant la pratique établie par 121.1/123.1/124.1/125.1).

### Difficultés rencontrées

- SQLite : `ALTER TABLE targets DROP COLUMN ssh_key_id` refusé (colonne référencée par FK inline) → le batch Alembic (rebuild de table) est la seule voie, y compris dans les helpers de tests legacy.
- `make backend-format` a reformaté 54 fichiers (dette de formatage préexistante sur `main`) → fichiers hors périmètre restaurés ; seuls les fichiers de la story sont livrés formatés.
- 35 échecs préexistants sur `main` (`test_stack_actions`, `test_stacks_archive`, `test_users`, `test_auth_isolation`, `test_debug_story1033`, `test_stacks_duplicate`) — **prouvés identiques sans les changements** (vérification `git stash`) : aucun lien avec 131.1.

### Validation (commandes et résultats)

- `poetry run pytest backend/tests/unit/test_migrations_131.py backend/tests/unit/test_models/test_ssh_key.py backend/tests/unit/test_models/test_host_ssh_fingerprint.py` → **29 passed** ;
- `poetry run pytest backend/tests/unit/test_alembic_config.py backend/tests/unit/test_database.py backend/tests/integration/test_migrations.py` → **38 passed, 1 skipped** (skip = PostgreSQL indisponible, préexistant) ;
- `make backend-test-unit` → 1690 passed / 35 failed **préexistants** (identiques sans les changements) ;
- `alembic upgrade head` + `alembic check` sur base vierge → **No new upgrade operations detected** (migration ≡ modèles) ;
- flake8 + isort + black sur les fichiers du périmètre → **verts** ; mypy : 0 erreur sur les fichiers du périmètre (2 erreurs préexistantes dans `docker_client_service.py`/`jwt.py`, non touchés) ; bandit (niveau low+) : aucun finding ;
- Couverture : `app/models/ssh_key.py` **100 %**, `app/models/host_ssh_fingerprint.py` **100 %** (AC 2 ≥ 80 % validé).

### Points d'attention pour STORY-131.2 / 131.3

- `SSHKey.decrypted_private_key` : déchiffrement mémoire seule — ne jamais l'exposer dans un schéma Response ni logger ;
- la dédup par fingerprint est une **invariant de service** (unicité applicative) : la contrainte DB porte sur `name` uniquement — 131.2 doit vérifier l'empreinte avant insertion ;
- `HostSSHFingerprint.accepted=False` par défaut : l'enregistrement sans acceptation explicite ne fait pas autorité (TOFU 131.3) ;
- les credentials `ssh_private_key` migrés ne reviennent jamais dans `credentials` (downgrade 1311 non réversible — documenté) ; 131.2 doit lire la clé via `Target.ssh_key_id` ;
- warning R1 : une cible dont les credentials sont illisibles (clé maîtresse changée) reste sur `auth_method` existant — 131.2 devrait proposer une voie de re-saisie.
