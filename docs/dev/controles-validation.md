# Contrôles de validation et preuves

État du dépôt au 8 novembre 2026 (mise en place du harness aligné PreviImmo, EPIC-020). Cette matrice décrit la configuration locale ; elle n'atteste pas l'exécution distante des workflows Gitea Actions ni les protections de fusion de la forge.

| Contrôle | Commande locale | CI configurée | Portée et limites |
| --- | --- | --- | --- |
| Backlog | `make backlog-check` | Oui (job `harness-gates`) | Identifiants, statuts, registre, relations des contrats, cases et vue générée ; tests sur corpus temporaire (`make harness-test`). Aucune validation des AC ou du métier |
| Instructions partagées | `make check-harness` | Oui (job `harness-gates`) | Structure et liens locaux du corpus, présence des points d'entrée (AGENTS.md, CLAUDE.md, skills, règles de modes), frontmatter des skills, adaptateur `.claude/skills` et inventaire du corpus ; ni chargement réel des clients, ni comportement des agents certifiés (smoke tests : `docs/dev/harness.md`) |
| Lint et formatage | `make lint` | Oui (`.gitea/workflows/ci.yml`, `quality-gates.yml`) | black, isort, flake8, mypy, ESLint, Prettier, Stylelint |
| Types | `make typecheck` | Oui | mypy + tsc strict |
| Tests backend + couverture ≥ 80 % | `make ci-test-backend` | Oui (`test.yml`) | Vérifier les scénarios réellement collectés, les succès et les tests ignorés/skippés |
| Tests frontend | `make ci-test-frontend` | Oui | Vitest ; E2E Playwright séparés (`make frontend-test-e2e`) |
| Sécurité des dépendances | `make ci-security-backend` / `ci-security-frontend` | Oui | bandit + safety, pnpm audit ; les échecs sont actuellement tolérés (`|| true`) — à durcir avant livraison sensible |
| Migrations Alembic | Tests d'intégration round-trip (STORY-120.3) | Oui | Montée/descente sur base de test ; revue humaine obligatoire avant fusion (`02` §7) |
| Contrat d'API / client TS | `make generate-api` | Non (régénération locale) | Le client doit être régénéré dans le même changement que le contrat ; aucun contrôle automatique d'écart en CI aujourd'hui |
| Retour intermédiaire | `make ci-fast` | Non | Local seulement ; ne remplace aucune porte d'acceptation |
| Portes d'acceptation | `make check` | Partiellement (ci-full ≈ sous-ensemble) | `ci-full` + types + backlog + harness ; ajouter les contrôles requis par la tâche |
| Construction des images | `make ci-build-docker` | Oui (`build.yml`) | Aucune preuve de build déduite du lint |
| Déploiement | `make prod` / `make docker-prod` | `deploy.yml` | Accord explicite du propriétaire requis (`50` §2) |
| Revue, droits et fusion | Revue du contrat et du commit évalué | Configuration distante non inspectée | Propriétaire pour les zones sensibles (`02` §7) ; l'auteur agent ne peut pas s'accorder sa propre approbation |

`make check` regroupe les contrôles locaux actifs ; il ne certifie pas tous les critères d'acceptation d'une tâche. Les contrôles supplémentaires sont nommés dans le contrat avant réalisation. Un test absent, ignoré ou non exécuté reste non validé, même avec un code de sortie global nul. Une dérogation doit identifier décideur, justification, périmètre et expiration ; elle ne change pas le résultat du contrôle.

Pour chaque acceptation, conserver : identifiant du contrat, commit évalué et état de l'arbre, commande, environnement, résultats et lien de preuve. Après un changement, réexécuter les contrôles affectés. Pour un changement documentaire, une revue et les contrôles du corpus peuvent suffire ; les tests applicatifs sans rapport avec ce changement ne sont pas des preuves supplémentuelles utiles.
