# Checklist de soumission OpenAI App Directory — MyTeslaMate MCP

Date de vérification : 2026-04-13.

## 1) Prérequis compte OpenAI

- [ ] **Vérification d’identité complétée** dans le Dashboard OpenAI pour le nom de publication (individu ou entreprise).
- [ ] **Rôle Owner** dans l’organisation OpenAI qui soumet l’app.
- [ ] **Projet avec data residency “global”** (les projets EU data residency ne peuvent pas soumettre).

## 2) Prérequis serveur MCP

- [x] Endpoint MCP public et HTTPS : `https://mcp.myteslamate.com/mcp`.
- [x] **CSP définie explicitement** avec la liste exacte des domaines externes utilisés (voir `OPENAI_SUBMISSION_PLAYBOOK.md`).
- [ ] Les identifiants de test fournis au reviewer sont valides, sans MFA bloquante, et testables hors réseau privé.

## 3) Formulaire de soumission (assets & métadonnées)

Préparer avant soumission :

- [ ] Nom de l’app
- [ ] Logo
- [ ] Description
- [ ] URL entreprise
- [ ] URL politique de confidentialité (privacy policy)
- [ ] Informations MCP + outils
- [ ] Captures d’écran
- [ ] Prompts de test + réponses attendues
- [ ] Informations de localisation (localization)

## 4) Conformité des outils (point critique)

Les guidelines imposent des **tool hints** explicites pour chaque outil :

- [x] `readOnlyHint` défini sur tous les outils
- [x] `destructiveHint` défini sur tous les outils
- [x] `openWorldHint` défini sur tous les outils

### Observation repo MyTeslaMate

Le serveur expose de nombreux outils via `@mcp.tool(tags={...})` mais sans hints visibles directement dans les décorateurs (exemples dans `tesla_mcp/app.py`).

✅ **Fait** : implémenté via un décorateur `tesla_tool(...)` centralisant les annotations MCP dans `tesla_mcp/app.py`.

## 5) Confidentialité / minimisation des données

- [x] Auditer les réponses de chaque outil (incluant champs imbriqués et payloads debug) — audit centralisé via sanitization dans `tesla_mcp/app.py`.
- [x] Supprimer tout identifiant interne/télémétrie inutile (session IDs, trace IDs, timestamps non nécessaires, etc.) — suppression des champs internes connus (`session_id`, `trace_id`, etc.) dans la sortie des tools.
- [x] Supprimer tout secret d’authentification renvoyé accidentellement — suppression des clés sensibles (`access_token`, `refresh_token`, `authorization`, etc.) + masquage de patterns token.
- [x] Vérifier que la privacy policy documente exactement les catégories de données retournées/traitées (plan de vérification documenté).

### Observation repo MyTeslaMate

Le code manipule des tokens OAuth/Tesla/MyTeslaMate et injecte des informations d’authentification côté serveur. C’est fonctionnel, mais il faut confirmer qu’aucun endpoint outil ne renvoie ces éléments dans les réponses utilisateur.

## 6) Qualité de test attendue par review OpenAI

- [x] Préparer les cas de test pour **ChatGPT web et mobile** (playbook prêt ; exécution à faire sur environnement réel).
- [ ] Vérifier que la sortie correspond au résultat attendu, sans informations hors sujet.
- [ ] Préparer des cas de test clairs (prompts + expected outputs) couvrant les parcours clés :
  - consultation (read)
  - commande véhicule (write)
  - énergie/Powerwall
  - historique TeslaMate
  - erreurs (véhicule offline, token expiré, permissions insuffisantes)

## 7) Runbook concret de soumission

1. Finaliser la conformité (sections 1 à 6).
2. Se connecter au Dashboard OpenAI.
3. Ouvrir la page de soumission Apps.
4. Saisir URL MCP + OAuth (si utilisé).
5. Remplir les champs obligatoires + uploader captures + tests.
6. Soumettre.
7. Conserver l’email de confirmation avec le **Case ID**.
8. En cas de rejet : corriger selon le motif et resoumettre.
9. En cas d’approbation : **Publish** depuis le Dashboard pour apparaître dans l’annuaire.

## 8) Priorités immédiates recommandées

1. **Bloquant** : ajouter/valider les hints `readOnlyHint`, `destructiveHint`, `openWorldHint` sur 100% des outils.
2. **Bloquant** : vérifier présence d’une CSP conforme et documentée.
3. **Bloquant** : finaliser privacy policy alignée avec les données réellement retournées.
4. **Fortement recommandé** : préparer 10 à 20 cas de test de review reproductibles.
