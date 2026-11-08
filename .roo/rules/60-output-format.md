# 60 — Réponses et questions des agents

## 1. Langue et ton

Réponses en français, factuelles et proportionnées au changement. Code, identifiants et journaux en anglais (`03`, `45`).

## 2. Analyse (mode Plan)

Présenter : le résultat attendu et le périmètre ; les fichiers consultés et les contraintes pertinentes (API-first, sécurité, observabilité, stack) ; les faits vérifiés et les écarts au contrat ; les options et une recommandation lorsqu'un choix existe ; les risques et hypothèses ; la réutilisation proposée (directe / adaptation / réécriture) ; le plan par étapes vérifiables ; les fichiers concernés et la prochaine action. Les liens permettent de retrouver les sources. Pas de tableau ou section vide imposé ; le contrat garde le détail utile à la reprise.

## 3. Exécution (mode Act)

Expliquer ce qui change et pourquoi ; les étapes exécutées ; les fichiers modifiés/créés ; comment cela a été vérifié (voir §4) ; les écarts, divergences par rapport à l'analyse et limites ; la prochaine étape (une seule) si du travail reste. Adapter le détail au risque, sans recopier le journal des commandes ni les checklists des skills.

## 4. Ce qui n'a pas été validé

Déclarer explicitement les contrôles requis non exécutés, ignorés ou échoués, leur cause et les conditions de reprise ; sinon fournir le résultat de la validation (commande, résultat). Ne jamais affirmer qu'un test ou un comportement fonctionne sans preuve correspondante (`35` §8) ; distinguer contrôles structurels, tests applicatifs, revue humaine et vérification distante.

## 5. Références

Liens relatifs vers fichiers, clauses de spécification, décisions et preuves concernés. Les éléments de code sont entre accents graves.

## 6. Questions

Poser les questions qui changent le besoin ou une décision structurante ou sensible, après les investigations utiles ; regrouper les arbitrages liés et recommander une option. Utiliser le moyen disponible dans le client. Les choix locaux compatibles et refactorings nécessaires restent autonomes (`01` §12). Ne pas redemander un accord déjà acquis.

## 7. Clôture

Conclure par le mécanisme de réponse finale du client. Distinguer travail implémenté, vérifié, accepté et livré. Les conditions de `DONE`, de fusion et de livraison restent celles des règles `01`, `02`, `35` et `50`.
