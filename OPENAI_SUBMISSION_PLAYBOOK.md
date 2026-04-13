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

### A. Reading (safe read)

**Case 1**
- **Scenario:** Enumerate the Tesla assets (vehicles + energy sites) linked to the authenticated account.
- **User prompt:** "List my available vehicles."
- **Tool triggered:** `list_vehicles_and_energy_sites`
- **Expected output:** A list of at least one vehicle (name/VIN-masked/ID) and, if applicable, energy sites. No tokens, refresh tokens, or raw credentials in the response.

**Case 2**
- **Scenario:** Check the current battery state and estimated range of the user's primary vehicle without issuing any write command.
- **User prompt:** "Give me the battery level and estimated range of the main vehicle."
- **Tool triggered:** `list_vehicles_and_energy_sites`, then `get_vehicle_data`
- **Expected output:** Numeric battery percentage and estimated range (km or mi), plus timestamp/unit. No actuation, no write tool called.

**Case 3**
- **Scenario:** Read real-time energy telemetry for a home Powerwall/solar site.
- **User prompt:** "Show solar production and Powerwall level in real time."
- **Tool triggered:** `list_vehicles_and_energy_sites`, then `energy_live_status`
- **Expected output:** Live solar power (kW), Powerwall state of charge (%), grid/load values with units and a timestamp.

### B. Commands (write/open-world)

**Case 4**
- **Scenario:** Enable Sentry Mode remotely on the primary vehicle.
- **User prompt:** "Enable sentry mode on my main vehicle."
- **Tool triggered:** `list_vehicles_and_energy_sites`, `wake_up_vehicle`, `set_sentry_mode`
- **Expected output:** Explicit success/failure confirmation with the resulting sentry state. No silent failure.

**Case 5**
- **Scenario:** Change the charging limit to a specific target and confirm the vehicle accepted it.
- **User prompt:** "Set the charge limit to 80%."
- **Tool triggered:** `wake_up_vehicle`, `set_charge_limit`, `get_vehicle_data`
- **Expected output:** Confirmation the command was executed, with a consistent final `charge_limit_soc = 80` read back from the vehicle.

**Case 6**
- **Scenario:** Pre-condition the cabin by starting HVAC remotely.
- **User prompt:** "Start the climate control now."
- **Tool triggered:** `wake_up_vehicle`, `auto_conditioning_start`
- **Expected output:** Command acknowledgement and a state signal indicating climate is running (e.g. `is_climate_on = true`).

### C. TeslaMate analytics

**Case 7**
- **Scenario:** Retrieve historical charging sessions with associated cost from the user's TeslaMate instance.
- **User prompt:** "Show my last 5 charging sessions and their cost."
- **Tool triggered:** `teslamate_get_cars`, `teslamate_get_car_charges` (fallback: `charging_history`, `charging_sessions`)
- **Expected output:** Ordered list of the 5 most recent sessions with date, energy added (kWh), and cost (currency), clearly aggregated.

**Case 8**
- **Scenario:** Compare energy efficiency between the current month and the previous month using historical drive + charge data.
- **User prompt:** "Compare my energy efficiency this month vs last month."
- **Tool triggered:** `teslamate_get_cars`, `teslamate_get_car_drives`, `teslamate_get_car_charges`
- **Expected output:** Quantified comparison (Wh/km or Wh/mi) for both periods, with a short natural-language interpretation of the delta.

### D. Errors & robustness

**Case 9**
- **Scenario:** Chain a wake-up with a lock command on a vehicle that may be asleep/offline.
- **User prompt:** "Wake up the vehicle then lock it."
- **Tool triggered:** `wake_up_vehicle`, then `door_lock`
- **Expected output:** Graceful handling of offline/sleep state (retry/wait or explicit message), followed by lock confirmation. No partial success without explanation.

**Case 10**
- **Scenario:** Attempt an authenticated call after the OAuth session has expired.
- **User prompt:** "Run a command while the session has expired."
- **Tool triggered:** Any authenticated tool (e.g. `get_vehicle_data`) — the call surfaces the auth error rather than executing.
- **Expected output:** Actionable error message prompting the user to reconnect/re-authenticate. No token, refresh token, or internal stack trace leaked.

### E. Negative test cases (app should NOT trigger)

**Case 11**
- **Scenario:** Financial/market question that mentions Tesla but does not concern the user's vehicle or energy account.
- **User prompt:** "What's the current stock price of Tesla (TSLA)?"
- **Tool triggered:** None. The MCP server should not be invoked.
- **Expected output:** The model answers from general knowledge (or declines) without calling any Tesla tool.

**Case 12**
- **Scenario:** Generic shopping/comparison request for a vehicle the user may not own.
- **User prompt:** "Compare the Tesla Model 3 and the Ford Mustang Mach-E for a potential purchase."
- **Tool triggered:** None. The MCP server should not be invoked.
- **Expected output:** The model provides a general comparison without calling any Tesla tool on the user's account.

**Case 13**
- **Scenario:** General science/knowledge question that mentions battery tech but requires no access to user data.
- **User prompt:** "How does a lithium-ion battery work?"
- **Tool triggered:** None. The MCP server should not be invoked.
- **Expected output:** The model explains the concept from general knowledge without calling any Tesla tool.

### Exécution attendue

- Exécuter ces cas sur **ChatGPT web** et **ChatGPT mobile**.
- Capturer pour chaque cas:
  - prompt,
  - résultat réel,
  - statut (PASS/FAIL),
  - capture d’écran.

---

## 5) UI widgets (OpenAI Apps SDK)

Le serveur expose désormais une **ressource MCP** HTML rendue inline par ChatGPT pour certains tools.

### Widget disponible

- **URI**: `ui://widget/vehicle-live.html`
- **Mime type**: `text/html+skybridge`
- **Source**: [tesla_mcp/widgets/vehicle_live.html](tesla_mcp/widgets/vehicle_live.html)
- **Rendu**: carte véhicule live (batterie + charge limit ring, autonomie estimée, état charge, lock, climat, sentry, température, odomètre, timestamp).
- **Interaction**: bouton `Refresh` qui re-déclenche `get_vehicle_data` via `window.openai.callTool`.
- **CSP**: widget 100 % self-contained (aucun fetch externe), compatible avec la CSP stricte existante — pas de domaine à ajouter.

### Tools qui rendent un widget

| Tool | Output template |
|---|---|
| `get_vehicle_data` | `ui://widget/vehicle-live.html` |

Le template est déclaré via `_meta["openai/outputTemplate"]` sur le tool (cf. décorateur `tesla_tool(..., output_template=...)` dans [tesla_mcp/app.py](tesla_mcp/app.py)). Le `structuredContent` retourné par le tool est la réponse Tesla Fleet API sanitizée — le widget lit `window.openai.toolOutput` et gère les champs manquants (états dégradés).

### Vérifications reviewer

- `resources/list` expose `ui://widget/vehicle-live.html`.
- `tools/list` inclut `openai/outputTemplate` sur `get_vehicle_data`.
- Dans ChatGPT: prompt "Show me my car" → carte rendue, bouton Refresh fonctionnel, pas d’erreur CSP en devtools.

