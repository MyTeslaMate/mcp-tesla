"""TeslaMate Prefab UI sub-server.

Companion to ``teslamate_server`` — same module, but tools here render Prefab
UI components (cards, charts, tables) instead of returning raw JSON. Mounted
under the same ``namespace="teslamate"`` so they appear as
``teslamate_<name>`` from the parent server.
"""

from __future__ import annotations

from typing import Any, Optional

from fastmcp import Context, FastMCP
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Alert,
    AlertDescription,
    AlertTitle,
    Badge,
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    Column,
    DataTable,
    DataTableColumn,
    Grid,
    Heading,
    Metric,
    Muted,
    Progress,
    Row,
)
from prefab_ui.components.charts import BarChart, ChartSeries, LineChart

from ..auth_context import execute, make_tesla_tool, teslamate_auth_kwargs
from ..modules.teslamateapi import TeslaMateAPIModule


_TM_TAGS = {"teslamate", "ui"}


def _unwrap(payload: Any, *keys: str) -> Any:
    """Walk ``payload`` through TeslaMate's typical ``{"data": {...}}`` envelopes.

    Returns the inner value if the path matches; otherwise the original payload.
    """
    cur = payload
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return cur
    return cur


def _empty_app(title: str, message: str) -> PrefabApp:
    with Column(gap=4) as view:
        Heading(title, level=2)
        with Alert(variant="info"):
            AlertTitle("No data")
            AlertDescription(message)
    return PrefabApp(title=title, view=view)


def _records_table(
    title: str,
    records: list[dict[str, Any]],
    preferred_keys: list[tuple[str, str]],
) -> PrefabApp:
    """Build a ``DataTable`` from a list of dict rows.

    ``preferred_keys`` is ``[(key, header_label), ...]``. Keys that don't exist
    in any row are dropped; if no preferred key matches, falls back to all keys
    of the first row.
    """
    if not records:
        return _empty_app(title, "No records returned for this period.")

    available = set().union(*(r.keys() for r in records if isinstance(r, dict)))
    used: list[tuple[str, str]] = [(k, h) for k, h in preferred_keys if k in available]
    if not used:
        used = [(k, k.replace("_", " ").title()) for k in sorted(available)]

    columns = [DataTableColumn(key=k, header=h, sortable=True) for k, h in used]
    rows = [{k: r.get(k) for k, _ in used} for r in records if isinstance(r, dict)]

    with Column(gap=4) as view:
        Heading(title, level=2)
        Muted(f"{len(rows)} record(s)")
        DataTable(columns=columns, rows=rows, search=True, paginated=True, pageSize=15)
    return PrefabApp(title=title, view=view)


def build_teslamate_apps_server(
    teslamate_module: TeslaMateAPIModule,
    *,
    app_csp: dict[str, Any],
) -> FastMCP:
    """Build the TeslaMate Prefab UI sub-server."""
    mcp = FastMCP("MyTeslaMate – Apps")
    tesla_tool = make_tesla_tool(mcp, app_csp)

    # === Current charge ===

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS, app=True)
    def current_charge_card(car_id: int, ctx: Context) -> PrefabApp:
        """Render a live card for the currently active charging session.

        Args:
            car_id: The TeslaMate car ID
        """
        payload = execute(
            teslamate_module.get_car_charges_current,
            car_id=car_id,
            **teslamate_auth_kwargs(ctx),
        )
        data = _unwrap(payload, "data", "current_charge") or _unwrap(payload, "current_charge") or _unwrap(payload, "data") or payload

        if not isinstance(data, dict) or not data:
            return _empty_app(f"Car #{car_id} – Charging", "Car is not charging right now.")

        battery = data.get("battery_level") or data.get("usable_battery_level") or 0
        target = data.get("charge_limit_soc") or data.get("charge_limit") or 100
        power_kw = data.get("charger_power") or data.get("power")
        time_to_full = data.get("time_to_full_charge")
        added_kwh = data.get("charge_energy_added")

        with Column(gap=4) as view:
            with Card():
                with CardHeader():
                    CardTitle(f"Car #{car_id} – charging")
                    if power_kw is not None:
                        Muted(f"{power_kw} kW")
                with CardContent():
                    with Column(gap=3):
                        Progress(value=float(battery), max=float(target), variant="info")
                        with Row(gap=4):
                            Metric(label="Battery", value=f"{battery}%")
                            Metric(label="Target", value=f"{target}%")
                            if added_kwh is not None:
                                Metric(label="Added", value=f"{added_kwh} kWh")
                            if time_to_full is not None:
                                Metric(label="Time to full", value=f"{time_to_full} h")
        return PrefabApp(title=f"Car #{car_id} – charging", view=view)

    # === Battery health ===

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS, app=True)
    def battery_health_chart(car_id: int, ctx: Context) -> PrefabApp:
        """Render battery degradation over time as a line chart.

        Args:
            car_id: The TeslaMate car ID
        """
        payload = execute(
            teslamate_module.get_car_battery_health,
            car_id=car_id,
            **teslamate_auth_kwargs(ctx),
        )
        data = _unwrap(payload, "data") if isinstance(payload, dict) else payload
        series_data = (
            _unwrap(data, "battery_health")
            if isinstance(data, dict)
            else data if isinstance(data, list) else None
        )

        if not series_data or not isinstance(series_data, list):
            # Fallback: just show a summary card with whatever scalar fields exist
            scalar = data if isinstance(data, dict) else {}
            with Column(gap=4) as view:
                Heading(f"Car #{car_id} – Battery health", level=2)
                if not scalar:
                    Muted("No battery health data available.")
                else:
                    with Grid(columns=2, gap=4):
                        for k, v in scalar.items():
                            if isinstance(v, (int, float, str)):
                                Metric(label=k.replace("_", " ").title(), value=str(v))
            return PrefabApp(title=f"Car #{car_id} – Battery health", view=view)

        # Pick the first numeric key as the series. Date key autodetected.
        first = next((p for p in series_data if isinstance(p, dict)), {})
        date_key = next((k for k in ("date", "timestamp", "ts") if k in first), None)
        numeric_keys = [
            k for k, v in first.items()
            if k != date_key and isinstance(v, (int, float))
        ]
        if not numeric_keys:
            return _empty_app(f"Car #{car_id} – Battery health", "Unrecognized data shape.")

        latest = series_data[-1] if series_data else {}
        latest_value = latest.get(numeric_keys[0]) if isinstance(latest, dict) else None

        with Column(gap=4) as view:
            Heading(f"Car #{car_id} – Battery health", level=2)
            if latest_value is not None:
                Badge(f"Latest: {latest_value}", variant="info")
            LineChart(
                data=series_data,
                series=[ChartSeries(data_key=numeric_keys[0], label=numeric_keys[0])],
                x_axis=date_key or "date",
            )
        return PrefabApp(title=f"Car #{car_id} – Battery health", view=view)

    # === Charges ===

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS, app=True)
    def charges_table(
        car_id: int,
        ctx: Context,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = 100,
    ) -> PrefabApp:
        """Render charging sessions as a sortable, paginated table.

        Args:
            car_id: The TeslaMate car ID
            start_date: Optional RFC3339 start date
            end_date: Optional RFC3339 end date
            limit: Max sessions to fetch (default 100)
        """
        payload = execute(
            teslamate_module.get_car_charges,
            car_id=car_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            **teslamate_auth_kwargs(ctx),
        )
        records = _extract_list(payload, ("data", "charges"), ("charges",), ("data",))
        return _records_table(
            f"Car #{car_id} – Charging sessions",
            records,
            preferred_keys=[
                ("start_date", "Start"),
                ("end_date", "End"),
                ("charge_energy_added", "kWh"),
                ("charger_power", "Power (kW)"),
                ("start_battery_level", "SoC start"),
                ("end_battery_level", "SoC end"),
                ("cost", "Cost"),
                ("address", "Location"),
            ],
        )

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS, app=True)
    def charges_summary_chart(
        car_id: int,
        ctx: Context,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = 60,
    ) -> PrefabApp:
        """Render a bar chart of kWh per charging session + headline totals.

        Args:
            car_id: The TeslaMate car ID
            start_date: Optional RFC3339 start date
            end_date: Optional RFC3339 end date
            limit: Max sessions to chart (default 60)
        """
        payload = execute(
            teslamate_module.get_car_charges,
            car_id=car_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            **teslamate_auth_kwargs(ctx),
        )
        records = _extract_list(payload, ("data", "charges"), ("charges",), ("data",))
        if not records:
            return _empty_app(
                f"Car #{car_id} – Charging summary",
                "No charging sessions in this period.",
            )

        chart_rows: list[dict[str, Any]] = []
        total_kwh = 0.0
        total_cost = 0.0
        for r in records:
            if not isinstance(r, dict):
                continue
            kwh = _coerce_float(r.get("charge_energy_added"))
            cost = _coerce_float(r.get("cost"))
            label = (r.get("start_date") or "")[:10]
            if kwh is not None:
                total_kwh += kwh
                chart_rows.append({"date": label, "kwh": round(kwh, 2)})
            if cost is not None:
                total_cost += cost

        with Column(gap=4) as view:
            Heading(f"Car #{car_id} – Charging summary", level=2)
            with Row(gap=4):
                Metric(label="Sessions", value=len(records))
                Metric(label="Total kWh", value=round(total_kwh, 1))
                if total_cost:
                    Metric(label="Total cost", value=round(total_cost, 2))
            if chart_rows:
                BarChart(
                    data=chart_rows,
                    series=[ChartSeries(data_key="kwh", label="kWh")],
                    x_axis="date",
                )
        return PrefabApp(title=f"Car #{car_id} – Charging summary", view=view)

    # === Drives ===

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS, app=True)
    def drives_table(
        car_id: int,
        ctx: Context,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_distance: Optional[float] = None,
        max_distance: Optional[float] = None,
        limit: Optional[int] = 100,
    ) -> PrefabApp:
        """Render driving sessions as a sortable, paginated table.

        Args:
            car_id: The TeslaMate car ID
            start_date: Optional RFC3339 start date
            end_date: Optional RFC3339 end date
            min_distance: Optional minimum distance filter
            max_distance: Optional maximum distance filter
            limit: Max drives to fetch (default 100)
        """
        payload = execute(
            teslamate_module.get_car_drives,
            car_id=car_id,
            start_date=start_date,
            end_date=end_date,
            min_distance=min_distance,
            max_distance=max_distance,
            limit=limit,
            **teslamate_auth_kwargs(ctx),
        )
        records = _extract_list(payload, ("data", "drives"), ("drives",), ("data",))
        return _records_table(
            f"Car #{car_id} – Drives",
            records,
            preferred_keys=[
                ("start_date", "Start"),
                ("end_date", "End"),
                ("distance", "Distance"),
                ("duration_min", "Duration (min)"),
                ("consumption_kwh", "Energy (kWh)"),
                ("start_address", "From"),
                ("end_address", "To"),
            ],
        )

    # === Dashboard ===

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS, app=True)
    def dashboard(car_id: int, ctx: Context) -> PrefabApp:
        """Combined teslamate dashboard: status + battery + recent charges + drives.

        Args:
            car_id: The TeslaMate car ID
        """
        kwargs = teslamate_auth_kwargs(ctx)
        status = execute(teslamate_module.get_car_status, car_id=car_id, **kwargs)
        current = execute(teslamate_module.get_car_charges_current, car_id=car_id, **kwargs)
        health = execute(teslamate_module.get_car_battery_health, car_id=car_id, **kwargs)
        recent_charges = execute(
            teslamate_module.get_car_charges,
            car_id=car_id,
            limit=5,
            **kwargs,
        )
        recent_drives = execute(
            teslamate_module.get_car_drives,
            car_id=car_id,
            limit=5,
            **kwargs,
        )

        status_data = _unwrap(status, "data", "status") or _unwrap(status, "status") or _unwrap(status, "data") or status
        current_data = _unwrap(current, "data", "current_charge") or _unwrap(current, "current_charge") or _unwrap(current, "data") or current
        health_data = _unwrap(health, "data") if isinstance(health, dict) else health

        battery_pct = (
            (status_data or {}).get("battery_level")
            if isinstance(status_data, dict)
            else None
        )
        charging_state = (
            (status_data or {}).get("charging_state") or (status_data or {}).get("state")
            if isinstance(status_data, dict)
            else None
        )

        with Column(gap=6) as view:
            Heading(f"Car #{car_id} – Dashboard", level=1)

            # Top row: status metrics
            with Grid(columns=3, gap=4):
                Metric(label="Battery", value=f"{battery_pct}%" if battery_pct is not None else "—")
                Metric(label="State", value=str(charging_state or "—"))
                if isinstance(current_data, dict) and current_data:
                    pwr = current_data.get("charger_power") or current_data.get("power")
                    Metric(label="Charging power", value=f"{pwr} kW" if pwr is not None else "—")
                else:
                    Metric(label="Charging", value="Idle")

            # Battery health summary
            if isinstance(health_data, dict) and health_data:
                with Card():
                    with CardHeader():
                        CardTitle("Battery health")
                    with CardContent():
                        with Grid(columns=3, gap=3):
                            for k, v in list(health_data.items())[:6]:
                                if isinstance(v, (int, float, str)):
                                    Metric(label=k.replace("_", " ").title(), value=str(v))

            # Recent activity
            with Grid(columns=2, gap=4):
                charges = _extract_list(recent_charges, ("data", "charges"), ("charges",))
                drives = _extract_list(recent_drives, ("data", "drives"), ("drives",))

                with Card():
                    with CardHeader():
                        CardTitle("Recent charges")
                    with CardContent():
                        _mini_table(
                            charges,
                            [
                                ("start_date", "Start"),
                                ("charge_energy_added", "kWh"),
                                ("end_battery_level", "SoC end"),
                            ],
                        )

                with Card():
                    with CardHeader():
                        CardTitle("Recent drives")
                    with CardContent():
                        _mini_table(
                            drives,
                            [
                                ("start_date", "Start"),
                                ("distance", "Distance"),
                                ("consumption_kwh", "Energy"),
                            ],
                        )

        return PrefabApp(title=f"Car #{car_id} – Dashboard", view=view)

    return mcp


# === Helpers ===


def _extract_list(payload: Any, *paths: tuple[str, ...]) -> list[dict[str, Any]]:
    """Walk ``payload`` through any of the given key paths and return the first list found."""
    for path in paths:
        cur: Any = payload
        ok = True
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok and isinstance(cur, list):
            return cur
    if isinstance(payload, list):
        return payload
    return []


def _coerce_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _mini_table(records: list[dict[str, Any]], preferred_keys: list[tuple[str, str]]) -> None:
    """Render a small inline table (no pagination) inside a Card."""
    if not records:
        Muted("None.")
        return
    available: set[str] = set().union(*(r.keys() for r in records if isinstance(r, dict)))
    used = [(k, h) for k, h in preferred_keys if k in available] or [
        (k, k.replace("_", " ").title()) for k in sorted(available)
    ]
    columns = [DataTableColumn(key=k, header=h, sortable=False) for k, h in used]
    rows = [{k: r.get(k) for k, _ in used} for r in records if isinstance(r, dict)]
    DataTable(columns=columns, rows=rows, paginated=False)
