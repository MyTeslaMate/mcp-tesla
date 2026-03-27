# Tesla MCP Server: https://mcp.myteslamate.com/mcp

This repository provides a [Model Context Protocol](https://github.com/modelcontextprotocol/spec) server that wraps both the Tesla Fleet API and the TeslaMate API. It includes vehicle endpoints, vehicle commands, energy endpoints (Powerwall/Solar), and charging endpoints. The implementation is modular and fully featured, exposing **98 MCP tools** for the Tesla Fleet API and **9 MCP tools** for the TeslaMate API.

---

## ✨ What You Can Do

This isn't just remote control — it's a conversational interface to your entire Tesla ecosystem. **Express your use cases directly to your AI** — describe what you want in plain language and let it figure out which tools to call, in what order, and with what parameters. No app to open, no menu to navigate.

### ⚡ Energy Optimization

> *"My Powerwall is at 40%. Should I charge my car now or wait for solar production this afternoon?"*

> *"Analyze my last 30 days of energy data — am I losing money by exporting to the grid while paying to charge at night?"*

> *"Set the Powerwall backup reserve to 20% and schedule the car to charge from 2am to 6am at 16A."*

The AI can cross-reference your solar production, Powerwall state, grid rates, and vehicle battery level to give you a recommendation — and act on it immediately.

### 🚗 Smart Vehicle Management

> *"I have a road trip to Lyon next Thursday. Based on my usual efficiency, will I need to stop for charging? Find the best Supercharger on the route."*

> *"Compare my energy consumption this month vs last month. What changed?"*

> *"Pre-condition the car at 7:45am every weekday and set the charge limit back to 80% — it's currently at 100% from the trip."*

### 📊 Data & Insights (with TeslaMate API)

> *"What's my average km/kWh over the last 3 months? Is it getting worse?"*

> *"Show me my most expensive charging sessions this year and where they happened."*

> *"How many hours per week is the car sitting with climate running? What's the energy cost?"*

### 🔐 Security & Peace of Mind

> *"Is my car locked and is Sentry mode on? I forgot to check before my flight."*

> *"My car is parked downtown. Turn on Sentry mode and send me the current location."*

---

**Available capabilities** (98 tools for Tesla Fleet API + 9 for TeslaMate API):
- **Vehicle control**: lock/unlock, climate, trunk, windows, lights, horn
- **Charging**: start/stop, set limits, schedule, charging amps, charge history
- **Powerwall & Solar**: live status, energy history, backup reserve, storm mode, grid import/export, time-of-use settings
- **Navigation**: send destinations, find nearby Superchargers
- **Security**: Sentry mode, valet mode, speed limits, PIN to drive
- **Data & analytics**: vehicle data, trip history, drive statistics *(TeslaMate API)*

## 🔐 One-Click SSO — Connect with Your Tesla Account

The hosted server supports **OAuth 2.0 Single Sign-On** via Tesla's official authorization server. Compatible clients (ChatGPT, Claude.ai, VS Code…) trigger an automatic sign-in flow — **no token copy-paste required**.

```
MCP server URL: https://mcp.myteslamate.com/mcp
```

> The server proxies the OAuth flow to `auth.tesla.com`, then exchanges your Tesla token for a MyTeslaMate token transparently. Your Tesla credentials never touch this server.

---

### 🤖 Setup on ChatGPT (Apps / MCP Connector)

ChatGPT supports native MCP connectors via **Settings → Apps**.

1. In [chat.openai.com](https://chat.openai.com), open **Settings** → **Apps**.
2. Click **Create app**.
3. Enter the MCP server URL:
   ```
   https://mcp.myteslamate.com/mcp
   ```
4. ChatGPT will auto-discover the OAuth metadata and prompt you to **Connect**.
5. Sign in with your Tesla account — the authorization is handled automatically.
6. The connector appears in your **Enabled apps** list and is available in all your chats.

---

### 🧠 Setup on Claude.ai (MCP Connector)

1. Open [claude.ai](https://claude.ai) → **Settings** → **Connectors**.
2. Click **Add custom connector**.
3. Enter a name (e.g. `Tesla`) and the MCP server URL:
   ```
   https://mcp.myteslamate.com/mcp
   ```
4. Click **Add** — Claude will auto-discover the OAuth metadata and show a **Connect** button.
5. Click **Connect** — you'll be redirected to Tesla's login page.
6. After authorization, Claude will have access to all Tesla MCP tools.

> **Note:** OAuth-based SSO requires a MyTeslaMate account. The server validates your Tesla token and links it to your MTM subscription automatically.

---

## 🤖 Claude Code Skills

Ready-to-use Claude Code skills for this MCP server are available in **[myteslamate/tesla-skills](https://github.com/MyTeslaMate/tesla-skills)**.

Install the `/tesla` slash command in one step:

Then in Claude Code:
```
/tesla what is my battery level?
/tesla lock my car
/tesla how much did I charge last month?
```

---

## 🚀 Quick Start - Use Directly in VS Code, Claude Desktop, etc.

**No installation required!** Use the hosted MCP server directly. Two authentication options:

### Option A — SSO (Recommended for Claude.ai & ChatGPT)

Simply provide the server URL and let the client handle the OAuth flow automatically (see sections above).

### Option B — Manual Token (VS Code, Cursor, Claude Desktop)

For clients that don't support OAuth, use your MyTeslaMate API token directly in the `Authorization` header.

#### For VS Code / Cursor (with MCP Extension) and Other MCP Clients

Add both endpoints to your `.vscode/mcp.json` configuration to choose your preferred integration:

```json
{
  "servers": {
    "tesla": {
      "type": "http",
      "url": "https://mcp.myteslamate.com/mcp"
    }
  }
}
```

- Use `tesla_fleet_api` for direct access to Tesla's official Fleet API.
- Use `teslamate` for integration via TeslaMate API.

#### For Claude Desktop

Add endpoints in the MCP Connector configuration with the same URLs and headers as above.:

```bash
claude mcp add --transport http tesla-api "https://mcp.myteslamate.com/mcp"
```

Select the server according to your authentication method and API preference.


### 🔑 Getting Your Token (Manual Mode Only)
1. Visit [MyTeslaMate.com](https://myteslamate.com)
2. Sign in with your Tesla account
3. Navigate to the API section in your dashboard
4. Copy your personal API token
5. Use it in your MCP configuration


## 🔧 Self-Hosting (Advanced)

If you prefer to run your own instance, this repository also support TeslaMate API and Tesla Fleet API (Requires Tesla Developer Account and proper Fleet API registration).

## Features

- Modular package under `tesla_mcp` with a reusable `TeslaClient`.
- **Vehicle endpoints** (29 read-only endpoints):
  - **Core Vehicle Info**:
    - `GET /api/1/vehicles` - List vehicles
    - `GET /api/1/vehicles/{vehicle_tag}` - Get vehicle metadata
    - `GET /api/1/vehicles/{vehicle_tag}/vehicle_data` - Get live vehicle data
    - `POST /api/1/vehicles/{vehicle_tag}/wake_up` - Wake sleeping vehicle
    - `POST /api/1/vehicles/fleet_status` - Fleet status
    - `GET /api/1/vehicles/{vehicle_tag}/mobile_enabled` - Check mobile access
    - `GET /api/1/vehicles/{vehicle_tag}/nearby_charging_sites` - Nearby charging
    - `GET /api/1/vehicles/{vehicle_tag}/service_data` - Service data
    - `GET /api/1/vehicles/{vehicle_tag}/release_notes` - Firmware release notes
    - `GET /api/1/vehicles/{vehicle_tag}/recent_alerts` - Recent alerts
    - `GET /api/1/dx/vehicles/options?vin={vin}` - Vehicle options
    - `GET /api/1/dx/vehicles/upgrades/eligibility?vin={vin}` - Eligible upgrades
    - `GET /api/1/dx/vehicles/subscriptions/eligibility?vin={vin}` - Eligible subscriptions
  - **Drivers & Sharing** (6 endpoints):
    - `GET /api/1/vehicles/{vehicle_tag}/drivers` - List allowed drivers (owner only)
    - `DELETE /api/1/vehicles/{vehicle_tag}/drivers` - Remove driver access
    - `GET /api/1/vehicles/{vehicle_tag}/invitations` - List active share invites (paginated)
    - `POST /api/1/vehicles/{vehicle_tag}/invitations` - Create share invite (24hr expiry, single-use)
    - `POST /api/1/invitations/redeem` - Redeem share invite
    - `POST /api/1/vehicles/{vehicle_tag}/invitations/{id}/revoke` - Revoke share invite
  - **Fleet Telemetry** (4 endpoints):
    - `GET /api/1/vehicles/{vehicle_tag}/fleet_telemetry_config` - Get fleet telemetry config
    - `POST /api/1/vehicles/fleet_telemetry_config` - Configure self-hosted fleet-telemetry server
    - `DELETE /api/1/vehicles/{vehicle_tag}/fleet_telemetry_config` - Remove fleet telemetry config
    - `GET /api/1/vehicles/{vehicle_tag}/fleet_telemetry_errors` - Recent fleet telemetry errors
  - **Push Notification Subscriptions** (4 endpoints):
    - `GET /api/1/subscriptions` - Get subscriptions for mobile device
    - `POST /api/1/subscriptions` - Set subscriptions for mobile device
    - `GET /api/1/vehicle_subscriptions` - Get vehicle subscriptions
    - `POST /api/1/vehicle_subscriptions` - Set vehicle subscriptions
  - **Warranty & Signed Commands** (2 endpoints):
    - `GET /api/1/dx/warranty/details?vin={vin}` - Get warranty information
    - `POST /api/1/vehicles/{vehicle_tag}/signed_command` - Execute signed command (Tesla Vehicle Command Protocol)
- **Vehicle commands** (64 control endpoints):
  - **Doors & Access**: door_lock, door_unlock, actuate_trunk
  - **Climate**: auto_conditioning_start/stop, set_temps, set_climate_keeper_mode, set_bioweapon_mode, set_cabin_overheat_protection, set_cop_temp, set_preconditioning_max
  - **Seat & Steering**: remote_seat_heater_request, remote_seat_cooler_request, remote_auto_seat_climate_request, remote_steering_wheel_heater_request, remote_steering_wheel_heat_level_request, remote_auto_steering_wheel_heat_climate_request
  - **Charging**: charge_start, charge_stop, charge_port_door_open/close, set_charge_limit, charge_standard, charge_max_range, set_charging_amps, set_scheduled_charging, add/remove_charge_schedule, add/remove_precondition_schedule
  - **Windows & Sunroof**: window_control, sun_roof_control
  - **Lights & Horn**: flash_lights, honk_horn
  - **Media**: adjust_volume, media_toggle_playback, media_next/prev_track, media_next/prev_fav, media_volume_down
  - **Navigation**: navigation_request, navigation_gps_request, navigation_sc_request
  - **Security**: set_sentry_mode, set_valet_mode, reset_valet_pin, speed_limit_set_limit, speed_limit_activate/deactivate/clear_pin, speed_limit_clear_pin_admin, set_pin_to_drive, reset_pin_to_drive_pin, clear_pin_to_drive_admin
  - **Software**: schedule_software_update, cancel_software_update
  - **Misc**: remote_start_drive, trigger_homelink, remote_boombox, set_vehicle_name, guest_mode, erase_user_data
- **Energy endpoints** (12 endpoints for Powerwall/Solar control):
  - **Information**: energy_products (list all products), energy_site_info (site configuration), energy_live_status (real-time power/energy data)
  - **History**: energy_history (energy measurements over time), energy_backup_history (off-grid events), energy_charge_history (wall connector usage)
  - **Control**: energy_operation (set mode: autonomous/self_consumption), energy_backup (set backup reserve %), energy_off_grid_vehicle_charging_reserve (reserve for EV charging during outage)
  - **Grid Settings**: energy_storm_mode (enable/disable storm watch), energy_grid_import_export (control grid charging/exporting), energy_time_of_use_settings (configure utility rate plans)
- **Charging endpoints** (3 endpoints for charging history and invoices):
  - charging_history (paginated charging history with filters)
  - charging_invoice (download PDF invoice for a charging event)
  - charging_sessions (session information with pricing and energy data - business accounts only)
- Centralised error handling and basic logging so MCP clients surface useful
  diagnostics.

## Configuration


### API Endpoint Configuration

Configure the Tesla API base URL using the `TESLA_BASE_URL` environment variable:

#### For MyTeslaMate API (Default)
```bash
# No configuration needed - uses default
# Or explicitly set:
export TESLA_BASE_URL=https://api.myteslamate.com
```

#### For Tesla Fleet API (Official)
Choose your regional endpoint:

```bash
# North America, Asia-Pacific (excluding China)
export TESLA_BASE_URL=https://fleet-api.prd.na.vn.cloud.tesla.com

# Europe, Middle East, Africa  
export TESLA_BASE_URL=https://fleet-api.prd.eu.vn.cloud.tesla.com

# China
export TESLA_BASE_URL=https://fleet-api.prd.cn.vn.cloud.tesla.cn
```

**Note**: When using the official Tesla Fleet API, ensure you have:
- A registered Tesla Developer Account
- Proper Fleet API access permissions
- Valid OAuth 2.0 bearer tokens

## Installation

Install the Python dependencies once:

```bash
pip install -r requirements.txt
```

## Running the MCP server

You can start the server in multiple ways:

### Option 1: Using uvicorn (Recommended)
```bash
uvicorn tesla_mcp.app:app --host 0.0.0.0 --port 8000 --reload
```

### Option 2: Docker compose method
```bash
make up
```

### Option 3: Legacy method
```bash
python server.py
```

The server will start using HTTP Streaming on `http://0.0.0.0:8084`. Connect your MCP-compatible
client (such as Cursor or VS Code with the MCP extension) and configure a server
entry that points to this endpoint.

## Usage Examples

### Quick Start with MyTeslaMate
```bash
# 1. Start the server (uses MyTeslaMate API by default)
uvicorn tesla_mcp.app:app --host 0.0.0.0 --port 8000

# 2. Configure your MCP client with:
# URL: http://localhost:8000/sse
# Authorization: Bearer YOUR_MYTESLAMATE_TOKEN
```

### Using Tesla Fleet API (Official)
```bash
# 1. Set your regional endpoint
export TESLA_BASE_URL=https://fleet-api.prd.na.vn.cloud.tesla.com

# 2. Start the server
uvicorn tesla_mcp.app:app --host 0.0.0.0 --port 8000

# 3. Configure your MCP client with:
# URL: http://localhost:8000/sse  
# Authorization: Bearer YOUR_TESLA_FLEET_TOKEN
```

### Docker Usage
```bash
# Build the image
docker build -t tesla-mcp .

# Run with MyTeslaMate (default)
docker run -p 8000:8000 tesla-mcp

# Run with Tesla Fleet API
docker run -p 8000:8000 -e TESLA_BASE_URL=https://fleet-api.prd.na.vn.cloud.tesla.com tesla-mcp
```

## Adding new modules

- Create a file under `tesla_mcp/modules/` inheriting from `TeslaModule`.
- Register the module in `tesla_mcp/modules/__init__.py`.
- Expose new MCP tools inside `server.py` that delegate to the module methods.

This structure keeps the MCP layer thin while centralising all Tesla Fleet API
and TeslaMate API logic in the `tesla_mcp` package.
