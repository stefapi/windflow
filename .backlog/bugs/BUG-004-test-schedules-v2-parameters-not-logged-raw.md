# BUG-004 : test_schedules_v2.py::test_parameters_not_logged_raw échoue sur main (echo SQL local)

**Statut :** DONE
**Gravité :** Majeur — *revalorisé à l'analyse (initialement Mineur) : le même mécanisme journalise le SQL avec paramètres bindés dans les logs applicatifs dès `LOG_LEVEL=INFO`, valeur par défaut du Settings et documentée en prod — cf. cause racine.*

## Reproduction

1. Lancer `poetry run pytest backend/tests/unit/test_api/test_schedules_v2.py -v` depuis le répertoire `backend/` (ou tout contexte où le `.env` racine n'est pas chargé, donc `LOG_LEVEL` par défaut INFO).
2. Le test [`test_parameters_not_logged_raw`](../../backend/tests/unit/test_api/test_schedules_v2.py:405) (classe `TestSecurity`) échoue : les paramètres SQL bruts apparaissent dans les logs capturés (`caplog`).

L'échec est **préexistant, confirmé sur main** sans les changements STORY-162 (vérifié par comparaison) — non lié au bus d'événements.

## Comportement attendu

Le test passe dans toutes les conditions d'exécution : les paramètres SQL (potentiellement sensitifs) ne doivent jamais être loggés en clair — l'echo SQL de SQLAlchemy doit rester désactivé quel que soit le niveau de log effectif pendant le test.

## Comportement actuel

Le test est sensible au répertoire de travail / au chargement du `.env` : lancé depuis `backend/`, le `env_file` résolu diffère, `LOG_LEVEL` retombe à INFO et l'echo SQL SQLAlchemy devient actif → les paramètres bruts fuient dans caplog → assertion d'échec. Depuis la racine (commande canonique), le test est vert. Phénomène identique documenté par STORY-160.2 pour `test_api_key_service.py::test_no_key_or_hash_in_logs` (même cause racine : herméticité cwd du settings Pydantic).

## Contexte

- Signalé lors de la clôture STORY-162 (échec relevé dans la suite de non-régression élargie, identifié préexistant).
- Piste de résolution : rendre le test (ou la fixture de settings) hermétique au cwd — forcer `LOG_LEVEL=WARNING` (ou désactiver l'echo SQL) explicitement dans la fixture du test, ou neutraliser l'echo SQL dans `conftest.py` pour les tests de sécurité logs — plutôt que de dépendre du `.env` racine.

---

## Cause racine identifiée (analyse)

**Défaillance d'herméticité en cascade : le niveau effectif du logger `sqlalchemy.engine` dépend du cwd de lancement, et ce logger à INFO journalise tout le SQL avec paramètres bindés — quel que soit le flag `echo` des engines.**

Chaîne exacte, confirmée à la lecture du code :

1. **`env_file` relatif au cwd** — [`Settings.model_config`](../../backend/app/config.py:520) déclare `env_file=".env"`, chemin relatif au répertoire courant. Lancé depuis `backend/`, le `.env` racine n'est pas résolu (aucun `backend/.env` n'existe) → `LOG_LEVEL` n'est jamais lu.
2. **Défaut INFO** — sans `.env`, [`settings.log_level`](../../backend/app/config.py:405) retombe à sa valeur par défaut `INFO`. Le `.env` racine fixe `LOG_LEVEL=WARNING` — d'où un test vert « par chance » depuis la racine uniquement.
3. **Echo SQL implicite activé à l'import** — [`conftest.py`](../../backend/tests/conftest.py:24) importe `app.main`, dont la ligne [`main.py:67`](../../backend/app/main.py:67) exécute `logging.getLogger("sqlalchemy.engine").setLevel(INFO)`. Or le logger `sqlalchemy.engine` à **INFO** émet chaque statement SQL **avec ses paramètres bindés**, et cela vaut pour *tout* engine du process : le flag [`echo=False`](../../backend/tests/conftest.py:191) de l'engine de test ne fait que s'abstenir de configurer le logger à la création — il n'empêche jamais les émissions d'un logger déjà positionné à INFO. Le commentaire [`main.py:65-67`](../../backend/app/main.py:65) documente d'ailleurs l'intention inverse de ce qu'il produit.
4. **Capture caplog** — [`test_parameters_not_logged_raw`](../../backend/tests/unit/test_api/test_schedules_v2.py:412) appelle `caplog.at_level(logging.INFO, logger="app.services.scheduler_service")`, ce qui abaisse également le handler caplog à INFO → les records INFO de `sqlalchemy.engine` (propagés au root) sont capturés. Le `POST /api/v1/schedules` déclenche l'`INSERT INTO scheduled_tasks` dont le paramètre bindé `parameters` contient le sentinel `tgt-TOPSECRET-42` → le sentinel apparaît dans `caplog.text` → l'assertion (ligne 424) échoue.

**Les logs applicatifs du domaine sont sains** : [`scheduler_service.py`](../../backend/app/services/scheduler_service.py:244) ne journalise que `name/action/trigger` (commentaires « Rules 40 » lignes 244 et 293) — la fuite provient exclusivement du logger `sqlalchemy.engine`, pas du code métier.

**Portée au-delà du test (découverte d'analyse — checklist sécurité `.roo/rules/40-security.md`)** : en production, `.env.prod.example` documente `LOG_LEVEL=INFO` et c'est le défaut du Settings → au démarrage, [`main.py:67`](../../backend/app/main.py:67) (complété par `logging.basicConfig(level=INFO)`, [`main.py:56-63`](../../backend/app/main.py:56)) active la journalisation de **tout le SQL avec paramètres bindés** : hash de mots de passe (`users`), `key_hash` des clés API, hash des refresh tokens, `parameters` des tâches planifiées, PEM chiffrés des clés SSH… Violation directe de « ne jamais logger de données sensibles » — d'où la revalorisation de la gravité.

### Sinks évalués systématiquement (rules 40)

| Sink | Verdict |
|------|---------|
| Logs applicatifs `scheduler_service` (create/update/toggle) | ✅ sains — jamais de `parameters` bruts ([`scheduler_service.py:244-246, 293-295, 319`](../../backend/app/services/scheduler_service.py:244)) |
| Events bus `scheduled_task.*` (payloads) | ✅ aucun emit ne porte `parameters` (seul [`scheduler_engine.py:651`](../../backend/app/services/scheduler_engine.py:651) émet `disabled_by_error_policy` avec `{"error": ...}`) |
| Réponses API `/schedules` | ✅ couvert par `test_no_sensitive_fields_in_responses` existant |
| Logger `sqlalchemy.engine` (SQL + paramètres bindés) | ❌ **cause de la fuite** — actif à INFO selon le cwd (test) **et par défaut en prod** |
| Tests caplog frères sans défense | ❌ [`test_api_key_service.py::test_no_key_or_hash_in_logs`](../../backend/tests/unit/test_services/test_api_key_service.py:357) (même piège documenté STORY-160.2 : `key_hash` transite dans l'INSERT bindé) et [`test_ssh_keys.py`](../../backend/tests/unit/test_api/test_ssh_keys.py:362) exposés au même échec depuis `backend/` |

## Contexte technique (analyse)

- **Pattern de défense établi** : deux tests posent déjà le bridage — [`test_api_keys.py:505-506`](../../backend/tests/unit/test_api/test_api_keys.py:505) et [`test_audit_emission.py:761-762`](../../backend/tests/unit/test_api/test_audit_emission.py:761) : `caplog.set_level(logging.WARNING, logger="sqlalchemy.engine")`, avec docstrings « exiger `LOG_LEVEL=WARNING` en tête de commande » (contournement manuel fragile que le présent correctif rend inutile).
- **Fixtures autouse existantes** dans [`conftest.py`](../../backend/tests/conftest.py:91) (`_reset_rate_limit_store`, `_reset_bruteforce_store`) : le pattern yield + restauration pour une hygiène transverse est déjà en place — la défense SQL s'y insère naturellement.
- **Engine de test** : créé `echo=False` ([`conftest.py:188-192`](../../backend/tests/conftest.py:188)) — correct mais insuffisant seul (cause racine point 3).
- **Commande canonique** : la cible [`backend-test-unit`](../../Makefile:151) du Makefile lance pytest depuis la racine (cwd où le `.env` charge) — c'est pourquoi la CI reste verte alors que le test échoue localement depuis `backend/`.
- **Pattern garde-fou structurel** : l'introspection de source est établie dans le projet ([`test_scheduler_engine.py:919-934`](../../backend/tests/unit/test_services/test_scheduler_engine.py:919), pattern `test_no_celery_residue`) — réutilisable pour verrouiller le bridage de `main.py`.
- **Absence de dépendance inverse** : aucun test n'attend la présence de SQL dans les logs (recherche exhaustive — les seules occurrences de `sqlalchemy.engine` dans les tests sont les 2 défenses WARNING) → le bridage global ne casse rien.

## Décision de résolution

**Défense en profondeur à 3 niveaux** (du plus local au plus structurel) :

1. **T1 — test auto-porteur** : le test signalé pose explicitement le bridage caplog (pattern des 2 tests existants). Objectif : le test documente et garantit son propre périmètre, indépendamment des autres niveaux.
2. **T2 — herméticité de suite (`conftest.py`)** : fixture autouse bridant `sqlalchemy.engine` à WARNING pour **tous** les tests (avec restauration du niveau initial). Objectif : immuniser les tests frères déjà exposés (`test_api_key_service`, `test_ssh_keys`) et tous les futurs tests caplog — y compris contre un `.env` local `LOG_LEVEL=DEBUG`, cas où T3 seul ne suffirait pas (`main.py` laisserait alors le logger à DEBUG).
3. **T3 — durcissement applicatif (`main.py`, rules 40)** : `sqlalchemy.engine` est bridé à WARNING sauf `LOG_LEVEL=DEBUG` (où l'echo SQL reste un choix de debug explicite via `echo=True` de [`database.py:88`](../../backend/app/database.py:88)). Objectif : le SQL avec paramètres bindés ne peut plus fuir dans les logs applicatifs en production à `LOG_LEVEL=INFO`.

Options écartées :

- **Résoudre `env_file` vers le `.env` racine quoi qu'il arrive** : changement global de comportement du Settings (risque large), déjà identifié comme dette STORY-160.2, et ne résoudrait ni le cas CI (sans `.env`) ni la fuite prod.
- **Forcer `LOG_LEVEL=WARNING` via pytest-env dans `pyproject.toml`** : neutraliserait l'environnement du développeur pour *tous* les aspects (pas seulement SQL) et masquerait le problème plutôt que de le corriger.

## Tâches d'implémentation détaillées

1. **Défense caplog dans le test signalé** — [`backend/tests/unit/test_api/test_schedules_v2.py`](../../backend/tests/unit/test_api/test_schedules_v2.py:405) : dans `TestSecurity.test_parameters_not_logged_raw`, ajouter `caplog.set_level(logging.WARNING, logger="sqlalchemy.engine")` (l'import `logging` existe déjà, ligne 16) et compléter la docstring avec le piège documenté (pattern [`test_api_keys.py:499-506`](../../backend/tests/unit/test_api/test_api_keys.py:499)). Objectif : le test passe quel que soit le cwd / `LOG_LEVEL` effectif.
2. **Fixture autouse de bridage SQL** — [`backend/tests/conftest.py`](../../backend/tests/conftest.py:108) : ajouter après `_reset_bruteforce_store` une fixture autouse `_silence_sqlalchemy_engine` qui sauvegarde le niveau courant de `logging.getLogger("sqlalchemy.engine")`, le force à `logging.WARNING`, `yield`, puis restaure le niveau sauvegardé. Docstring : défense rules 40 — les paramètres bindés (key_hash, hash de mots de passe, `parameters`…) ne fuient jamais dans caplog quelle que soit la config env locale. Objectif : herméticité de toute la suite, couvre les tests frères sans défense.
3. **Bridage applicatif de l'echo SQL** — [`backend/app/main.py`](../../backend/app/main.py:65) : remplacer `logging.getLogger("sqlalchemy.engine").setLevel(getattr(logging, settings.log_level))` par un bridage à `logging.DEBUG` si `settings.log_level == "DEBUG"`, sinon `logging.WARNING` ; réécrire le commentaire des lignes 65-67 (il documente aujourd'hui l'intention inverse de l'effet produit). Objectif rules 40 : plus aucun SQL avec paramètres bindés dans les logs applicatifs à `LOG_LEVEL=INFO` (défaut du Settings, valeur documentée `.env.prod.example`) ; echo conservé en DEBUG via `echo=True` de [`database.py:88`](../../backend/app/database.py:88).
4. **Actualiser les docstrings du contournement manuel** — [`backend/tests/unit/test_api/test_api_keys.py:499-503`](../../backend/tests/unit/test_api/test_api_keys.py:499) et [`backend/tests/unit/test_api/test_audit_emission.py:757-759`](../../backend/tests/unit/test_api/test_audit_emission.py:757) : les mentions « exiger LOG_LEVEL=WARNING en tête de commande » deviennent obsolètes (bridage désormais systématique — conftest + main) ; conserver les `caplog.set_level` explicites (auto-portance, pattern inchangé) mais reformuler la mention. Objectif : documentation exacte post-fix (même démarche que BUG-003, tâche 5).
5. **CHANGELOG** — entrée « Fixed » (BUG-004) dans [`CHANGELOG.md`](../../CHANGELOG.md) sous `[Unreleased]` : test rendu hermétique au cwd + arrêt de la journalisation SQL (paramètres bindés) pour `LOG_LEVEL >= INFO` — changement de comportement : l'echo SQL reste disponible en `LOG_LEVEL=DEBUG`.

## Tests à écrire

Backend — nouveau fichier `backend/tests/unit/test_core/test_sql_logging_hygiene.py` (introspection de source selon le pattern [`test_scheduler_engine.py:919`](../../backend/tests/unit/test_services/test_scheduler_engine.py:919) + assertion runtime) :

| Cas | Test | Attendu |
|-----|------|---------|
| Fixture conftest effective | `test_sqlalchemy_engine_bridged_to_warning_during_tests` | pendant l'exécution de tout test, `logging.getLogger("sqlalchemy.engine").level == logging.WARNING` (l'autouse de la tâche 2 est active) |
| Garde-fou structurel `main.py` | `test_main_bridges_sqlalchemy_engine_unless_debug` | le source de `main.py` ne contient plus le `setLevel(getattr(logging, settings.log_level))` inconditionnel et contient le bridage conditionnel vers `WARNING` (tâche 3 non régressable) |

Non-régression directe — le test corrigé est la preuve, à lancer **dans le contexte d'échec du signalement** (cwd `backend/`, `.env` non chargé, `LOG_LEVEL` défaut INFO) :

```bash
# contexte du signalement
cd backend && poetry run pytest tests/unit/test_api/test_schedules_v2.py -v

# tests frères exposés au même piège — même contexte
cd backend && poetry run pytest tests/unit/test_services/test_api_key_service.py tests/unit/test_api/test_ssh_keys.py tests/unit/test_api/test_api_keys.py tests/unit/test_api/test_audit_emission.py -v

# variante adversaire : un env local LOG_LEVEL=DEBUG ne doit rien casser (tâche 2 le garantit)
cd backend && LOG_LEVEL=DEBUG poetry run pytest tests/unit/test_api/test_schedules_v2.py -v

# nouveau fichier
cd backend && poetry run pytest tests/unit/test_core/test_sql_logging_hygiene.py -v
```

Commandes canoniques (Makefile = source de vérité) :

```bash
make backend-test-unit
make backend-lint && make backend-typecheck
```

Pas de test d'intégration requis : le mécanisme est purement logging/process, sans I/O externe.

## État d'avancement technique

- [x] T1. Défense caplog dans `test_parameters_not_logged_raw` (+ docstring)
- [x] T2. Fixture autouse `_silence_sqlalchemy_engine` dans `conftest.py`
- [x] T3. Bridage `sqlalchemy.engine` WARNING-sauf-DEBUG dans `main.py`
- [x] T4. Docstrings du contournement manuel actualisées (2 fichiers)
- [x] T5. CHANGELOG mis à jour
- [x] Nouveau `test_sql_logging_hygiene.py` (2 tests) verts
- [x] Suite ciblée verte depuis `backend/` **et** la racine + lint/typecheck

## Résolution

**Corrigé le 2026-10-23 (treat-story) — clôturé le 2026-10-23 (finalise-story) — statut DONE.**

### Fichiers modifiés/créés

- [`backend/app/main.py`](../../backend/app/main.py:65) (T3) : commentaire réécrit + bridage `logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG if settings.log_level == "DEBUG" else logging.WARNING)` — fin du `setLevel(getattr(logging, settings.log_level))` inconditionnel.
- [`backend/tests/conftest.py`](../../backend/tests/conftest.py:125) (T2) : import `logging` + fixture autouse `_silence_sqlalchemy_engine` — sauvegarde/force à WARNING/restaure les loggers de `_SQL_BINDING_LOGGERS = ("sqlalchemy.engine", "aiosqlite")`.
- [`backend/tests/unit/test_api/test_schedules_v2.py`](../../backend/tests/unit/test_api/test_schedules_v2.py:405) (T1) : `caplog.set_level(logging.WARNING, logger="sqlalchemy.engine")` + docstring du piège (pattern `test_api_keys.py`).
- [`backend/tests/unit/test_api/test_api_keys.py`](../../backend/tests/unit/test_api/test_api_keys.py:499) (T4) : docstring — mention « exiger LOG_LEVEL=WARNING » remplacée par le bridage systématique BUG-004 (conftest + main).
- [`backend/tests/unit/test_api/test_audit_emission.py`](../../backend/tests/unit/test_api/test_audit_emission.py:757) (T4) : idem.
- [`CHANGELOG.md`](../../CHANGELOG.md:57) (T5) : entrée « Fixed » BUG-004 sous `[Unreleased]` (cause, défense en profondeur, changement de comportement DEBUG).
- **Créé** [`backend/tests/unit/test_core/test_sql_logging_hygiene.py`](../../backend/tests/unit/test_core/test_sql_logging_hygiene.py) : `test_sqlalchemy_engine_bridged_to_warning_during_tests` (runtime) + `test_main_bridges_sqlalchemy_engine_unless_debug` (introspection de source, pattern `test_lifespan_wiring_and_existing_loops_preserved`).

### Décisions techniques

- Défense en profondeur implémentée exactement selon l'analyse (T1 locale, T2 suite, T3 applicatif) ; les `caplog.set_level` explicites des tests existants sont conservés (auto-portance).
- **Divergence documentée (T2, étendue en validation)** : la variante adversaire `LOG_LEVEL=DEBUG` a révélé un **sink adjacent non identifié à l'analyse** — le logger `aiosqlite` (driver SQLite) émet à DEBUG chaque opération SQL **avec ses arguments bindés** (fuite du `key_hash` constatée dans `test_no_key_or_hash_in_logs`) via le root abaissé par `basicConfig(DEBUG)`, indépendamment de `sqlalchemy.engine`. La fixture autouse bride donc les **deux** loggers (`_SQL_BINDING_LOGGERS`), ce qui satisfait le critère d'acceptation « la suite ciblée doit rester verte en DEBUG ». Le test d'hygiène runtime couvre les deux loggers.

### Validation exécutée

| Contexte | Commande | Résultat |
|----------|----------|----------|
| Signalement (cwd `backend/`, `.env` non chargé) | `pytest tests/unit/test_api/test_schedules_v2.py tests/unit/test_services/test_api_key_service.py tests/unit/test_api/test_ssh_keys.py -v` | **53 passed** |
| Adversaire (cwd `backend/`, `LOG_LEVEL=DEBUG`) | même suite + `test_sql_logging_hygiene.py` | **55 passed** |
| Canonique racine | `make backend-test-unit` | **2055 passed** (0 failed) |
| Nouveau fichier | `pytest tests/unit/test_core/test_sql_logging_hygiene.py -v` | **2 passed** |
| Lint | `black --check` + `isort --check-only` + `flake8` sur les 6 fichiers | **OK** |
| Typecheck | `mypy app/main.py` | 21 erreurs **préexistantes** (vérifiées par comparaison stash avant/après — aucune sur les lignes modifiées) |

### Difficultés rencontrées

- Fuite résiduelle `aiosqlite` à DEBUG découverte en validation adversaire (cf. divergence ci-dessus) — corrigée dans la foulée par l'extension de la fixture.
- `black` a reformatté le nouveau fichier de tests (guillemets/longueur de ligne) après écriture — corrigé avant le lint final.

## Definition of Done (clôture — finalise-story, 2026-10-23)

- [x] Bug reproduit et compris (échec préexistant confirmé sur main, cause racine en cascade identifiée)
- [x] Cause racine identifiée (`env_file` relatif au cwd → `LOG_LEVEL=INFO` → `main.py` forçait `sqlalchemy.engine` à INFO → SQL bindé dans caplog et logs prod)
- [x] Correction implémentée (défense en profondeur T1 caplog + T2 fixture autouse conftest `sqlalchemy.engine`/`aiosqlite` + T3 bridage `main.py` WARNING-sauf-DEBUG)
- [x] Tests de non-régression écrits (`test_sql_logging_hygiene.py` : 2 tests + défense caplog dans le test signalé)
- [x] Section « Résolution » présente (ci-dessus)

### Re-vérification de clôture (finalise-story)

| Contexte | Commande | Résultat |
|----------|----------|----------|
| Racine (canonique) | `poetry run pytest backend/tests/unit/test_api/test_schedules_v2.py backend/tests/unit/test_api/test_api_keys.py backend/tests/unit/test_api/test_audit_emission.py backend/tests/unit/test_core/test_sql_logging_hygiene.py -v` | **57 passed** |
| Adversaire (cwd `backend/`, `LOG_LEVEL=DEBUG`) | `pytest tests/unit/test_api/test_schedules_v2.py tests/unit/test_core/test_sql_logging_hygiene.py -v` | **22 passed** |
