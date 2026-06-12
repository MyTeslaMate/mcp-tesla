"""Interactive map Prefab UI sub-server.

Surfaces a single ``show_map`` tool that geocodes free-form addresses or
place names via OpenStreetMap Nominatim and renders them as an interactive
Leaflet map inside a Prefab UI Dashboard. Designed to be called whenever
the conversation needs to put TeslaMate locations (charging stops, trip
endpoints, geofences, …) on a map.

Mounted at the root of the MCP server (no namespace prefix) so the exposed
tool name stays ``show_map`` — short and discoverable for the LLM.
"""

from __future__ import annotations

from textwrap import dedent

import httpx
from fastmcp import Context, FastMCP
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge,
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    Dashboard,
    DashboardItem,
    DataTable,
    DataTableColumn,
    Label,
)

from ..auth_context import make_tesla_tool


# Includes `teslamate` so the tool flows through the existing
# `?tags=teslamate,generative` filter the Laravel bridge uses — without
# requiring callers to extend their tag query for one extra tool.
_MAP_TAGS = {"teslamate", "map", "ui", "geo"}
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def _geocode(query: str) -> dict | None:
    """Geocode a single query via OSM Nominatim (free, no key required).

    Returns ``None`` when Nominatim returns no result or the call fails —
    the caller surfaces a Badge for each failed lookup so the user can
    spot typos and the rest of the map keeps rendering.
    """
    try:
        resp = httpx.get(
            _NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "myteslamate-mcp/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
    except (httpx.HTTPError, ValueError):
        return None

    if not results:
        return None

    r = results[0]
    return {
        "name": r.get("display_name", query).split(",")[0],
        "address": query,
        "lat": float(r["lat"]),
        "lng": float(r["lon"]),
    }


def _build_map_html(locations: list[dict], zoom: int) -> str:
    """Build a sandboxed Leaflet page wired with one marker per location."""
    markers_js = ""
    for loc in locations:
        name = str(loc["name"]).replace("\\", "\\\\").replace("'", "\\'")
        markers_js += (
            f"L.marker([{loc['lat']}, {loc['lng']}]).addTo(map)"
            f".bindPopup('{name}');\n"
        )

    avg_lat = sum(loc["lat"] for loc in locations) / len(locations)
    avg_lng = sum(loc["lng"] for loc in locations) / len(locations)

    return dedent(
        f"""\
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8" />
            <link
                rel="stylesheet"
                href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
            />
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <style>
                body {{ margin: 0; }}
                #map {{ width: 100%; height: 100vh; }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <script>
                var map = L.map('map').setView([{avg_lat}, {avg_lng}], {zoom});
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    attribution: '&copy; OpenStreetMap contributors'
                }}).addTo(map);
                {markers_js}
            </script>
        </body>
        </html>
        """
    )


def build_map_apps_server(app_csp: dict | None = None) -> FastMCP:
    """FastMCP sub-server exposing ``show_map``.

    The ``app_csp`` argument matches the signature used by the other
    Prefab UI sub-servers so callers can pass through the shared CSP
    config from ``app.py``.
    """
    mcp = FastMCP("MyTeslaMate – Map")
    tesla_tool = make_tesla_tool(mcp, app_csp or {})

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_MAP_TAGS, app=True)
    def show_map(
        locations: list[str],
        ctx: Context,
        title: str = "Map",
        zoom: int = 6,
    ) -> PrefabApp:
        """Render an interactive map of geocoded addresses or place names.

        Call this whenever the conversation needs to put one or more
        locations on a map — typical use cases:

        - "Where are my last 10 charging stops?"  → pass charge.address
        - "Plot my trip from Paris to Lyon"        → pass start/end + via
        - "Where is the closest Supercharger to X?" → pass the candidates

        Args:
            locations: List of plain addresses, place names or landmarks.
                Each entry is geocoded via OpenStreetMap Nominatim. Failed
                lookups render as a Badge under the map so the user can
                spot typos without breaking the rest of the view.
            title: Card title shown above the map.
            zoom: Initial Leaflet zoom level (1 = world, 18 = building).
                Defaults to 6 (regional view).

        Returns a Dashboard wrapping a Card with the embedded Leaflet map
        and a DataTable listing every successfully geocoded location.
        """
        geocoded: list[dict] = []
        failed: list[str] = []
        for loc in locations or []:
            result = _geocode(loc)
            if result:
                geocoded.append(result)
            else:
                failed.append(loc)

        # Dashboard defaults to 12 columns and `row_height=120` px;
        # DashboardItem defaults to col_span=1, row_span=1 → 1/12 width
        # and a fixed 120 px row. Two side effects to neutralise:
        # 1. col_span=12 on each item so they take the full width.
        # 2. row_height="auto" on the Dashboard so the 500 px map iframe
        #    doesn't overflow into the row below where the DataTable
        #    sits (which was producing a stacked-overlay look).
        with PrefabApp() as app:
            with Dashboard(columns=12, row_height="auto", gap=4):
                with DashboardItem(col=1, row=1, col_span=12):
                    with Card():
                        with CardHeader():
                            CardTitle(title)
                            Label(f"{len(geocoded)} locations mapped")
                        with CardContent():
                            if geocoded:
                                from prefab_ui.components import Embed
                                Embed(
                                    html=_build_map_html(geocoded, zoom),
                                    width="100%",
                                    height="500px",
                                    sandbox="allow-scripts",
                                )
                            else:
                                Label("No location could be geocoded.")
                        for f in failed:
                            Badge(f"Could not find: {f}", variant="destructive")

                if geocoded:
                    with DashboardItem(col=1, row=2, col_span=12):
                        DataTable(
                            columns=[
                                DataTableColumn(key="name", header="Name", sortable=True),
                                DataTableColumn(key="address", header="Address", sortable=True),
                                DataTableColumn(key="lat", header="Latitude", sortable=True),
                                DataTableColumn(key="lng", header="Longitude", sortable=True),
                            ],
                            rows=geocoded,
                            search=True,
                        )

        return app

    return mcp
