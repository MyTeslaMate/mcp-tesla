# Tesla MCP Server: https://mcp.myteslamate.com/mcp

This repository provides a [Model Context Protocol](https://github.com/modelcontextprotocol/spec) server that wraps both the Tesla Fleet API and the MyTeslaMate API. It includes vehicle endpoints, vehicle commands, energy endpoints (Powerwall/Solar), and charging endpoints. The implementation is modular and fully featured, exposing **98 MCP tools** for the Tesla Fleet API and **9 MCP tools** for the TeslaMate API.

## 🚀 Quick Start - Use Directly in VS Code, Claude, etc.

**No installation required!** Use the hosted MCP server directly for either Tesla Fleet API or MyTeslaMate API:

### For VS Code / Cursor (with MCP Extension) and Other MCP Clients

Add both endpoints to your `.vscode/mcp.json` configuration to choose your preferred integration:

```json
{
  "servers": {
    "tesla_fleet_api": {
      "type": "http",
      "url": "https://mcp.myteslamate.com/mcp?tags=tesla_fleet_api",
      "headers": {
        "Authorization": "Bearer YOUR_MYTESLAMATE_TOKEN"
      }
    },
    "teslamate": {
      "type": "http",
      "url": "https://mcp.myteslamate.com/mcp?tags=teslamate",
      "headers": {
        "X-Teslamate-EndPoint": "https://YOUR_MYTESLAMATE_API_ENDPOINT",
        "X-Teslamate-Authorization": "Bearer YOUR_MYTESLAMATE_TOKEN"
      }
    }
  }
}
```

- Use `tesla_fleet_api` for direct access to Tesla's official Fleet API.
- Use `teslamate` for integration via MyTeslaMate API.

### For Claude Desktop

Add both endpoints to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tesla_fleet_api": {
      "type": "http",
      "url": "https://mcp.myteslamate.com/mcp?tags=tesla_fleet_api",
      "headers": {
        "Authorization": "Bearer YOUR_MYTESLAMATE_TOKEN"
      }
    },
    "teslamate": {
      "type": "http",
      "url": "https://mcp.myteslamate.com/mcp?tags=teslamate",
      "headers": {
        "X-Teslamate-EndPoint": "https://YOUR_MYTESLAMATE_API_ENDPOINT",
        "X-Teslamate-Authorization": "Bearer YOUR_MYTESLAMATE_TOKEN"
      }
    }
  }
}
```

Select the server according to your authentication method and API preference.


### 🔑 Getting Your Token
1. Visit [MyTeslaMate.com](https://myteslamate.com)
2. Sign in with your Tesla account  
3. Navigate to the API section in your dashboard
4. Copy your personal API token
5. Use it in your MCP configuration (some clients handle authentication automatically)

## ✨ What You Can Do

Once configured, you can control your Tesla directly from your favorite MCP-enabled application:

- **🚗 Vehicle Control**: Lock/unlock, start climate, open trunk, flash lights *(Tesla Fleet API only)*
- **🔋 Charging**: Start/stop charging, set charge limits, schedule charging *(Tesla Fleet API only)*
- **📍 Location**: Get vehicle location, send navigation destinations *(Tesla Fleet API only)*
- **🌡️ Climate**: Set temperature, seat heaters, steering wheel heater *(Tesla Fleet API only)*
- **🛡️ Security**: Sentry mode, valet mode, speed limits *(Tesla Fleet API only)*
- **⚡ Energy**: Monitor Powerwall/Solar (if you have Tesla Energy products) *(Tesla Fleet API only)*
- **📊 Data**: Get vehicle data, charging history, energy usage

**With the TeslaMate API**, you can:
- View live and historical vehicle data (location, state, battery, climate, charging)
- Access charging history and energy usage
- Monitor trips and drive statistics
- Get notifications and alerts
- Integrate with your self-hosted TeslaMate instance for privacy and advanced analytics

Just ask in natural language: *"Lock my Tesla"*, *"Set the charge limit to 80%"*, *"Turn on the seat heater"*, etc.  
*(Note: Control commands and some endpoints are only available via the Tesla Fleet API. TeslaMate API focuses on data, history, and analytics.)*

## 🔧 Self-Hosting (Advanced)

If you prefer to run your own instance, this repository also support MyTeslaMate API and Tesla Fleet API (Requires Tesla Developer Account and proper Fleet API registration).

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

### Authentication (Tesla Fleet OAuth)

The server ships with a `TeslaFleetProvider` that proxies Tesla's OAuth flow via FastMCP. Provide your Tesla developer credentials and the public URL of this FastMCP server to enable interactive authentication:

```bash
export TESLA_MCP_AUTH_TESLA_FLEET_CLIENT_ID=your-client-id
export TESLA_MCP_AUTH_TESLA_FLEET_CLIENT_SECRET=your-client-secret
export TESLA_MCP_AUTH_TESLA_FLEET_BASE_URL=https://mcp.your-domain.com
# Optional overrides
export TESLA_MCP_AUTH_TESLA_FLEET_AUTH_BASE_URL=https://auth.tesla.com
export TESLA_MCP_AUTH_TESLA_FLEET_API_BASE_URL=$TESLA_BASE_URL
export TESLA_MCP_AUTH_TESLA_FLEET_REQUIRED_SCOPES="openid offline_access user_data vehicle_device_data vehicle_cmds"
export TESLA_MCP_AUTH_TESLA_FLEET_AUDIENCE=$TESLA_BASE_URL
export TESLA_MCP_AUTH_TESLA_FLEET_ALLOWED_CLIENT_REDIRECT_URIS='["http://localhost:*"]'
```

If these variables are not supplied, the server falls back to accepting raw `Authorization` headers as before.

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
