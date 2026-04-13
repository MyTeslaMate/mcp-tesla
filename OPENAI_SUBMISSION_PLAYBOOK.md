# OpenAI Submission Playbook — MyTeslaMate MCP

Date: 2026-04-13

Ce document implémente les 4 actions prioritaires de préparation à la soumission OpenAI.

---

## 1) Tool hints appliqués systématiquement

Le serveur MCP déclare désormais les hints sur **tous les tools** via un décorateur unique `tesla_tool(...)` qui injecte :

- `readOnlyHint`
- `destructiveHint`
- `openWorldHint`

### Règle actuellement appliquée

- Tools de lecture (`get_*`, `list_*`, `teslamate_get_*`, historiques/états) :
  - `readOnlyHint: true`
  - `destructiveHint: false`
  - `openWorldHint: true`
- Tools d’action/commande :
  - `readOnlyHint: false`
  - `destructiveHint: true`
  - `openWorldHint: true`

> Note: cette règle est volontairement conservatrice (`destructiveHint: true` pour les écritures) pour maximiser la sécurité en review.

---

## 2) CSP stricte (domaines exacts)

Pour la soumission OpenAI, utiliser une CSP **sans wildcard** et limiter aux domaines strictement nécessaires.

### Domaines runtime identifiés dans ce repo

- `https://mcp.myteslamate.com` (endpoint MCP public documenté)
- `https://fleet-auth.prd.vn.cloud.tesla.com` (authorize + token OAuth Tesla)
- `https://myteslamate.com` ou domaine API MTM exact configuré par `TESLA_OAUTH_MTM_BASE_URL`

### Exemple de politique CSP (à adapter exactement à l’infra prod)

```text
default-src 'none';
connect-src https://mcp.myteslamate.com https://fleet-auth.prd.vn.cloud.tesla.com https://myteslamate.com;
img-src 'self' data:;
style-src 'self';
script-src 'self';
frame-ancestors 'none';
base-uri 'none';
form-action 'none';
```

Checklist rapide CSP:

- Pas de `*`.
- Pas de domaine non utilisé.
- Aligner `connect-src` sur les domaines réellement appelés par le backend.

---

## 3) Privacy policy vs données réellement retournées

## Inventaire des catégories de données exposées par les tools

1. **Compte utilisateur**: infos profil, région, commandes/ordres.
2. **Véhicule**: état, position, sécurité, climat, charge, historique.
3. **Énergie**: Powerwall/solar, import/export réseau, réglages TOU.
4. **TeslaMate analytics**: trajets, charges, batterie, updates.

### Vérifications à faire avant soumission

- Confirmer que les réponses tools ne retournent **jamais**:
  - token Tesla,
  - token MyTeslaMate,
  - secrets OAuth,
  - identifiants internes non nécessaires.
- Aligner la privacy policy publique avec:
  - catégories de données collectées/traitées,
  - finalités,
  - durée de conservation,
  - sous-traitants,
  - contact suppression/export données.

### Texte minimum recommandé à couvrir dans la privacy policy

- "Nous traitons des données véhicule et énergie uniquement pour exécuter les commandes utilisateur demandées dans ChatGPT."
- "Nous ne partageons pas les tokens d’authentification dans les réponses utilisateurs."
- "Les utilisateurs peuvent demander suppression/export de leurs données via [canal support]."

---

## 4) Plan de tests review (web + mobile)

Préparer un fichier de test reproductible avec prompts et expected outputs.

## Cas de test recommandés

### A. Lecture (safe read)

1. Prompt: "Liste mes véhicules disponibles."
   - Expected: liste d’au moins un véhicule, sans token ni secret.

2. Prompt: "Donne-moi le niveau de batterie et l’autonomie estimée du véhicule principal."
   - Expected: valeurs batterie/autonomie, pas d’actions écriture.

3. Prompt: "Affiche la production solaire et le niveau Powerwall en temps réel."
   - Expected: données énergie actuelles.

### B. Commandes (write/open-world)

4. Prompt: "Active le mode sentinelle sur mon véhicule principal."
   - Expected: confirmation succès/échec explicite.

5. Prompt: "Régle la limite de charge à 80%."
   - Expected: commande exécutée + état final cohérent.

6. Prompt: "Démarre la climatisation maintenant."
   - Expected: action de commande et retour d’état.

### C. TeslaMate analytics

7. Prompt: "Montre mes 5 dernières sessions de charge et leur coût."
   - Expected: liste ordonnée, données agrégées claires.

8. Prompt: "Compare mon efficacité énergétique ce mois-ci vs mois dernier."
   - Expected: comparaison chiffrée + courte interprétation.

### D. Erreurs & robustesse

9. Prompt: "Réveille le véhicule puis verrouille-le."
   - Expected: gestion du cas véhicule offline/sleep si nécessaire.

10. Prompt: "Exécute une commande alors que la session est expirée."
    - Expected: message d’erreur actionnable (reconnexion), sans fuite sensible.

### Exécution attendue

- Exécuter ces cas sur **ChatGPT web** et **ChatGPT mobile**.
- Capturer pour chaque cas:
  - prompt,
  - résultat réel,
  - statut (PASS/FAIL),
  - capture d’écran.

