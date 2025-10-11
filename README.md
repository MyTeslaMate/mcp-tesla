# Tesla Fleet API MCP Server

This workspace exposes a [Model Context Protocol](https://github.com/modelcontextprotocol/spec) server that wraps the
Tesla Fleet API, including vehicle endpoints, vehicle commands, energy endpoints (Powerwall/Solar), and charging endpoints. 
The implementation is modular and fully featured with **108 MCP tools**.

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

The server does **not** manage authentication. The bearer token must be provided
via the `Authorization` header when connecting to the MCP server. Configure your
MCP client to include:

```json
{
  "servers": {
    "tesla": {
      "url": "http://localhost:8000/sse",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN_HERE"
      }
    }
  }
}
```

The Tesla Fleet API base URL is read from the `TESLA_BASE_URL` environment
variable and falls back to `https://api.myteslamate.com` when unset.

## Installation

Install the Python dependencies once:

```bash
pip install -r requirements.txt
```

## Running the MCP server

```bash
python server.py
```

The server will start using Server-Sent Events (SSE). Connect your MCP-compatible
client (such as Cursor or VS Code with the MCP extension) and configure a server
entry that points to this script.

## Adding new modules

- Create a file under `tesla_mcp/modules/` inheriting from `TeslaModule`.
- Register the module in `tesla_mcp/modules/__init__.py`.
- Expose new MCP tools inside `server.py` that delegate to the module methods.

This structure keeps the MCP layer thin while centralising all Tesla Fleet API
logic in the `tesla_mcp` package.
