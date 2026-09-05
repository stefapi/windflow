# STORY-103.2 : Chiffrement de Target.credentials + migration double lecture (P0-4b)

**Statut :** DONE
**Story Parente :** STORY-103 — SecretManager AES/Fernet — chiffrement au repos des credentials cibles et env vars de stacks (P0-4)
**Epic Parent :** EPIC-011 — P0 : Sécurité bloquante

## Description

En tant qu'administrateur sécurité de WindFlow, je veux que les credentials d'accès aux cibles (mots de passe SSH/sudo, clés privées) stockés dans `Target.credentials` soient chiffrés au repos via le `SecretManager`, afin que la compromission du fichier de base de données ne révèle aucun credential.

**Problème constaté** ([`backend_status.md`](../../../docs/backend_status.md) §6.2) : le modèle [`Target`](../../../backend/app/models/target.py) stocke ses `credentials` en **JSON en clair** dans la base. Cette sous-story branche le SecretManager (livré par STORY-103.1) sur toutes les écritures et lectures de ce champ, applique la **migration par double lecture** (ligne clair → lue → ré-encryptée au premier accès) et documente la procédure opérationnelle (backup, rotation de clé).

## Critères d'acceptation (AC)

- [x] AC 2 : Toute **écriture** de `Target.credentials` (création/modification de cible) passe par le SecretManager et stocke du JSON chiffré ; toute **lecture** (déploiement, scan, health-check, exécution SSH/sudo) déchiffre à la volée — les flux existants fonctionnent à l'identique pour l'utilisateur (non-régression des déploiements et du scan, garde-fous §2.G).
- [x] AC 4 : **Migration des données existantes par double lecture** : une ligne ancienne stockée en clair est lue avec succès puis **ré-encryptée au premier accès** ; test de migration dédié (fixture avec credential clair → accès → relecture chiffrée) ; documentation de la procédure (backup préalable, rotation de clé maîtresse).

## Contexte technique

- **Écritures** — [`target_service.py:70-115`](../../../backend/app/services/target_service.py:70) : `create()` sérialise via `to_storage_dict()` puis stocke ; `update()` passe par `_merge_credentials()` ([`target_service.py:330`](../../../backend/app/services/target_service.py:330)) — le JSON fusionné doit être chiffré avant persistance.
- **Lectures** :
  - Propriétés dérivées du modèle lisant `credentials` en direct : [`models/target.py:90-101`](../../../backend/app/models/target.py:90) (`auth_method`, `username`, `has_sudo`) — utilisées par la réponse API, doivent continuer à fonctionner (déchiffrement transparent ou propriété dédiée) ;
  - Scan : [`target_scanner_service.py:166-208`](../../../backend/app/services/target_scanner_service.py:166) lit username/password/clés au moment du scan ;
  - Exécution distante : `SSHCommandExecutor` consomme les credentials ([`services/commands.py`](../../../backend/app/services/commands.py:167)).
- **Double lecture** : détecter le ciphertext via le préfixe Fernet (`gAAAA...`, helper livré par STORY-103.1) ; si JSON clair → déchiffrer n/a, utiliser, puis **ré-encrypter au premier accès** (déchiffrement + re-persistance) ; les valeurs déchiffrées ne vivent qu'en mémoire.
- **Non-exposition API** : [`TargetResponse`](../../../backend/app/schemas/target.py:236) n'expose pas les credentials — à préserver.
- **Fixtures de test** : les fixtures cibles existantes (`credentials={}` — cf. [`conftest.py:319`](../../../backend/tests/conftest.py:319)) doivent continuer à fonctionner sans modification (le chiffrement d'un dict vide reste un cas valide).
- **Ne jamais logger de secrets** (masquage `***` déjà pratiqué par [`adoption_service.py:230`](../../../backend/app/services/adoption_service.py:230)).
- Audit trail : hors périmètre (STORY-125).

## Dépendances

- STORY-103.1 : SecretManager Fernet — socle config, dépendance et classe core (fournit `SecretManager` + helper détection ciphertext + settings clé maîtresse)

## Tâches d'implémentation détaillées

### Tâche 1 : Chiffrer à l'écriture dans `TargetService`
**Objectif :** Toute écriture de `Target.credentials` (`create`, `update`/`_merge_credentials`) stocke le JSON chiffré via le SecretManager au lieu du JSON clair.
**Fichiers :**
- `backend/app/services/target_service.py` — Modifier — `create()` (~ligne 76-83), `update()` (~ligne 107-115), `_merge_credentials()` (~ligne 330) : chiffrement du dict fusionné avant persistance
**Exigences sécurité :** les credentials ne transitent jamais en clair dans les logs ; le dict chiffré est opaque (une seule chaîne de ciphertext ou dict chiffré champ à champ selon le pattern spec — arbitrage à l'implémentation, documenté en note).
**Dépend de :** Aucune (dans cette sous-story)

### Tâche 2 : Déchiffrement à la volée + ré-encryptage au premier accès (double lecture)
**Objectif :** Centraliser la lecture des credentials : détection clair vs chiffré (préfixe `gAAAA`), déchiffrement transparent pour tous les lecteurs, et ré-encryptage + re-persistance de la ligne lors du premier accès si elle était encore en clair.
**Fichiers :**
- `backend/app/models/target.py` — Modifier — propriété d'accès déchiffrée (ex. `decrypted_credentials`) + adapter les propriétés dérivées `auth_method`/`username`/`has_sudo` (~lignes 90-101)
- `backend/app/services/target_scanner_service.py` — Modifier — lecteurs (~lignes 166-208, 330-335) consomment l'accès déchiffré
- `backend/app/services/commands.py` — Modifier — `SSHCommandExecutor` (~ligne 167) consomme l'accès déchiffré
**Exigences sécurité :** les valeurs déchiffrées ne vivent qu'en mémoire ; jamais de log des valeurs ; le ré-encryptage au premier accès doit être idempotent (pas de double chiffrement — le helper de détection garantit la détection).
**Dépend de :** Tâche 1

### Tâche 3 : Documenter la procédure opérationnelle (backup + rotation)
**Objectif :** Documenter la migration par double lecture, le backup de base préalable et la procédure de rotation de clé maîtresse (plan §7.1).
**Fichiers :**
- `docs/general_specs/16-deploiement.md` — Modifier — section dédiée : backup avant mise à jour, déroulé de la migration (progressive au fil des accès), procédure de rotation de la clé maîtresse (double lecture ancienne/nouvelle clé)
**Exigences sécurité :** la procédure de rotation ne doit jamais exiger d'écrire des secrets en clair sur disque.
**Dépend de :** Tâche 2

## Tests à écrire

### Backend
- `backend/tests/unit/test_services/test_target_service.py` (ou fichier dédié)
  - `test_create_stores_encrypted_credentials` — après `create()`, la colonne ne contient pas les valeurs en clair (ciphertext détecté)
  - `test_update_merge_reencrypts` — update partiel → credentials toujours chiffrés, fusion correcte
- `backend/tests/unit/test_models/test_target.py`
  - `test_double_reading_migrates_clear_row` — fixture credential **clair** → accès → relecture : la ligne est désormais chiffrée (préfixe `gAAAA`)
  - `test_derived_properties_still_work` — `auth_method`/`username`/`has_sudo` retournent les bonnes valeurs sur données chiffrées
  - `test_empty_credentials_roundtrip` — `credentials={}` inchangé côté fixtures (non-régression [`conftest.py:319`](../../../backend/tests/conftest.py:319))
- `backend/tests/unit/test_services/test_target_scanner_service.py`
  - `test_scan_reads_decrypted_credentials` — le scan reçoit les credentials déchiffrés (mock executor)

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_services/test_target_service.py backend/tests/unit/test_models/test_target.py -v
make backend-test-unit
```

## État d'avancement technique
- [x] Tâche 1 : Chiffrer à l'écriture dans `TargetService`
- [x] Tâche 2 : Déchiffrement à la volée + ré-encryptage au premier accès (double lecture)
- [x] Tâche 3 : Documenter la procédure opérationnelle (backup + rotation)
## Notes d'implémentation

**Date :** 2026-09-05

### Fichiers modifiés/créés

- `backend/app/models/target.py` : helpers module-level `encrypt_credentials_for_storage()` / `decrypt_credentials_from_storage()`, propriété `Target.decrypted_credentials` (double lecture + ré-encryptage dirty au premier accès), propriétés dérivées `auth_method`/`username`/`has_sudo` branchées sur l'accès déchiffré.
- `backend/app/services/target_service.py` : `create()` et `update()` chiffrent via `encrypt_credentials_for_storage()` ; `_merge_credentials()` opère sur les credentials **déchiffrés** puis le résultat est ré-encrypté avant persistance.
- `backend/app/services/target_scanner_service.py` : `_execute_full_scan()` consomme `target.decrypted_credentials` (les valeurs transitent déchiffrées vers `SSHCommandExecutor`).
- `docs/general_specs/16-deploiement.md` : nouvelle section « Chiffrement au repos des credentials cibles (SecretManager) » — backup préalable, déroulé de la migration progressive (double lecture), procédure de rotation de clé maîtresse (bascule one-shot en mémoire, jamais de secret en clair sur disque).
- `backend/tests/unit/test_models/test_target.py` : **créé** — 13 tests (helpers, migration double lecture, idempotence, propriétés dérivées, credentials vides, mauvaise clé).
- `backend/tests/unit/test_services/test_target_service.py` : **créé** — 5 tests (create chiffré, update merge + ré-encrypt, ligne legacy, update sans credentials, credentials LOCAL vides).
- `backend/tests/unit/test_services/test_target_scanner_service.py` : classe `TestScanReadsDecryptedCredentials` ajoutée (2 tests — lecture déchiffrée au scan, migration ligne legacy).

### Décisions techniques

- **Format de stockage** : dict opaque `{"_encrypted": "<token Fernet>"}` (une seule chaîne, JSON complet chiffré d'un bloc). Arbitrage demandé par la Tâche 1 : pas de fuite de structure (les noms de champs `password`/`ssh_private_key` n'apparaissent pas en base), une seule opération cryptographique par écriture/lecture, ré-encryptage atomique (impossible de migrer un champ sur deux).
- **Migration par dirty flag** : `decrypted_credentials` ré-assigne `self.credentials` quand la ligne est en clair → SQLAlchemy marque la colonne dirty, la migration est persistée par le commit de l'opération métier en cours (scan via `_persist_scan`, update via `update()`). Pas de commit caché dans le modèle.
- **Credentials vides (`{}`) non migrés** : aucun secret à protéger ; les fixtures existantes (`conftest.py:319`) restent inchangées et fonctionnelles.
- **Détecteur** : réutilisation stricte de `SecretManager.is_encrypted()` (préfixe `gAAAA`) livré par STORY-103.1 — jamais de ré-encryption d'un ciphertext (idempotence testée).

### Divergences par rapport à l'analyse

- **Tâche 2, `services/commands.py`** : l'analyse demandait d'adapter `SSHCommandExecutor` (~ligne 167). En réalité cette classe **ne lit jamais `target.credentials`** : elle reçoit `sudo_user`/`sudo_password` en paramètres constructeur, fournis par les appelants (scanner, connectivity, discovery) qui, eux, lisent la colonne. Le lecteur effectif à brancher était `_execute_full_scan` dans `target_scanner_service.py` — c'est ce qui a été fait. Aucune modification de `commands.py` n'était nécessaire ; en modifier l'API aurait élargi le périmètre sans bénéfice sécurité.
- **Tâche 3, rotation** : l'analyse mentionnait une « double lecture ancienne/nouvelle clé » (plan §7.1). Le SecretManager livré par 103.1 ne supporte qu'une seule clé maîtresse active (pas de clé précédente en settings). La procédure documentée est donc une bascule one-shot (déchiffrer avec l'ancienne clé → ré-encrypter avec la nouvelle, en mémoire, API arrêtée), équivalente en sécurité et sans secret en clair sur disque.

### Difficultés rencontrées

- `ruff format --check` échoue sur les fichiers existants (`target.py`, `target_service.py`, etc.) pour du code **préexistant** (style black antérieur — 24 fichiers du codebase seraient reformattés). Par respect du périmètre (diff minimal), seuls les nouveaux fichiers de test ont été formatés ; mes ajouts dans les fichiers existants suivent leur style actuel et `ruff check` passe sur l'ensemble.
- `mypy` et `bandit` sont **indisponibles** dans le venv actuel (Traceback à l'exécution) — non exécutés, remplacés par `ruff check` (passant).

### Tests ajoutés

- `backend/tests/unit/test_models/test_target.py` : 13 tests — couverture `app/models/target.py` **100%**.
- `backend/tests/unit/test_services/test_target_service.py` : 5 tests — toutes les nouvelles lignes de chiffrement de `target_service.py` couvertes (le reste du fichier est du code préexistant non couvert : health checks, capabilities).
- `backend/tests/unit/test_services/test_target_scanner_service.py` : +2 tests (`TestScanReadsDecryptedCredentials`).

### Résultats de validation

- Tests ciblés : **87 passed** (3 fichiers).
- Modules connexes (deployment, compute, secret manager, API) : **119 passed**.
- Suite unitaire complète : **909 passed, 41 failed** — les 41 échecs sont la baseline préexistante (`test_stacks_archive`, `test_stacks_duplicate`, `test_stack_actions`, `test_container_promote`), aucun lié à targets/credentials.
- `ruff check` : passant sur tous les fichiers modifiés/créés.

<!-- Ajoutées à la clôture par treat-story -->
