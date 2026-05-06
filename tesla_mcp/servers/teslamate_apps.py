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
from prefab_ui.components.charts import BarChart, ChartSeries

from ..auth_context import execute, make_tesla_tool, teslamate_auth_kwargs
from ..modules.teslamateapi import TeslaMateAPIModule


_TM_TAGS = {"teslamate", "ui"}

# TeslaMate's API ignores the ``limit`` query param on /charges and /drives,
# so every UI tool also caps the returned list client-side.
_DEFAULT_TABLE_LIMIT = 50
_DEFAULT_CHART_LIMIT = 30
_DASHBOARD_RECENT_LIMIT = 5


def _unwrap(payload: Any, *keys: str) -> Any:
    """Walk ``payload`` through TeslaMate's typical ``{"data": {...}}`` envelopes."""
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


# === Field flattening (TeslaMate nests SoC, distance, ranges into sub-objects) ===


def _short_date(s: Any) -> Any:
    """Trim ISO timestamps down to ``YYYY-MM-DD HH:MM`` for compact tables."""
    if isinstance(s, str) and len(s) >= 16 and "T" in s:
        return s[:10] + " " + s[11:16]
    return s


def _round(v: Any, digits: int = 1) -> Any:
    if isinstance(v, (int, float)):
        return round(float(v), digits)
    return v


def _flatten_charge(r: dict[str, Any]) -> dict[str, Any]:
    bd = r.get("battery_details") or {}
    return {
        "start_date": _short_date(r.get("start_date")),
        "address": r.get("address"),
        "kwh": _round(r.get("charge_energy_added"), 2),
        "duration": r.get("duration_str") or r.get("duration_min"),
        "soc_start": bd.get("start_battery_level"),
        "soc_end": bd.get("end_battery_level"),
        "cost": _round(r.get("cost"), 2),
    }


def _flatten_drive(r: dict[str, Any]) -> dict[str, Any]:
    bd = r.get("battery_details") or {}
    od = r.get("odometer_details") or {}
    return {
        "start_date": _short_date(r.get("start_date")),
        "from": r.get("start_address"),
        "to": r.get("end_address"),
        "distance_km": _round(od.get("odometer_distance"), 1),
        "duration": r.get("duration_str") or r.get("duration_min"),
        "speed_avg": _round(r.get("speed_avg"), 0),
        "energy_kwh": _round(r.get("energy_consumed_net"), 2),
        "wh_per_km": _round(r.get("consumption_net"), 0),
        "soc_start": bd.get("start_battery_level"),
        "soc_end": bd.get("end_battery_level"),
    }


# === Generic table builder ===


def _records_table(
    title: str,
    rows: list[dict[str, Any]],
    columns_spec: list[tuple[str, str]],
    *,
    pageSize: int = 15,
) -> PrefabApp:
    if not rows:
        return _empty_app(title, "No records returned for this period.")
    columns = [DataTableColumn(key=k, header=h, sortable=True) for k, h in columns_spec]
    with Column(gap=4) as view:
        Heading(title, level=2)
        Muted(f"{len(rows)} record(s)")
        DataTable(columns=columns, rows=rows, search=True, paginated=True, pageSize=pageSize)
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
        data = (
            _unwrap(payload, "data", "current_charge")
            or _unwrap(payload, "current_charge")
            or _unwrap(payload, "data")
            or payload
        )
        if not isinstance(data, dict) or not data:
            return _empty_app(f"Car #{car_id} – Charging", "Car is not charging right now.")

        bd = data.get("battery_details") or {}
        battery = bd.get("end_battery_level") or data.get("battery_level") or 0
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

    # === Battery health (scalar metrics, no timeseries) ===

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS, app=True)
    def battery_health_chart(car_id: int, ctx: Context) -> PrefabApp:
        """Render battery health KPIs (SoH, capacity, range).

        TeslaMate's ``/battery-health`` endpoint returns a flat snapshot, not a
        timeseries — so this is a Metric card, not a chart.

        Args:
            car_id: The TeslaMate car ID
        """
        payload = execute(
            teslamate_module.get_car_battery_health,
            car_id=car_id,
            **teslamate_auth_kwargs(ctx),
        )
        bh = _unwrap(payload, "data", "battery_health")
        units = _unwrap(payload, "data", "units")
        if not isinstance(bh, dict) or not bh:
            return _empty_app(f"Car #{car_id} – Battery health", "No battery health data available.")

        length_unit = (units or {}).get("unit_of_length", "km") if isinstance(units, dict) else "km"
        soh = bh.get("battery_health_percentage")
        max_cap = bh.get("max_capacity")
        cur_cap = bh.get("current_capacity")
        max_range = bh.get("max_range")
        cur_range = bh.get("current_range")
        capacity_loss_kwh = (
            round(float(max_cap) - float(cur_cap), 2)
            if isinstance(max_cap, (int, float)) and isinstance(cur_cap, (int, float))
            else None
        )

        title = f"Car #{car_id} – Battery health"
        with Column(gap=4) as view:
            Heading(title, level=2)
            if soh is not None:
                variant = "success" if soh >= 95 else "warning" if soh >= 90 else "destructive"
                Badge(f"State of health: {round(float(soh), 1)}%", variant=variant)
            with Grid(columns=2, gap=4):
                if cur_cap is not None and max_cap is not None:
                    Metric(
                        label="Capacity",
                        value=f"{round(float(cur_cap), 2)} kWh",
                        description=f"new: {round(float(max_cap), 2)} kWh",
                        delta=f"-{capacity_loss_kwh} kWh" if capacity_loss_kwh else None,
                        trend="down" if capacity_loss_kwh else None,
                        trendSentiment="negative" if capacity_loss_kwh else None,
                    )
                if cur_range is not None and max_range is not None:
                    Metric(
                        label=f"Range ({length_unit})",
                        value=round(float(cur_range), 0),
                        description=f"new: {round(float(max_range), 0)} {length_unit}",
                    )
                if bh.get("rated_efficiency") is not None:
                    Metric(label="Rated efficiency", value=f"{bh['rated_efficiency']} kWh/100{length_unit}")
        return PrefabApp(title=title, view=view)

    # === Charges ===

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS, app=True)
    def charges_table(
        car_id: int,
        ctx: Context,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = _DEFAULT_TABLE_LIMIT,
    ) -> PrefabApp:
        """Render charging sessions as a sortable, paginated table.

        Args:
            car_id: The TeslaMate car ID
            start_date: Optional RFC3339 start date
            end_date: Optional RFC3339 end date
            limit: Max sessions to display (default 50). The API ignores this,
                so slicing is enforced client-side.
        """
        payload = execute(
            teslamate_module.get_car_charges,
            car_id=car_id,
            start_date=start_date,
            end_date=end_date,
            **teslamate_auth_kwargs(ctx),
        )
        records = _extract_list(payload, ("data", "charges"), ("charges",))[: (limit or _DEFAULT_TABLE_LIMIT)]
        rows = [_flatten_charge(r) for r in records if isinstance(r, dict)]
        return _records_table(
            f"Car #{car_id} – Charging sessions",
            rows,
            columns_spec=[
                ("start_date", "Start"),
                ("address", "Location"),
                ("kwh", "kWh"),
                ("duration", "Duration"),
                ("soc_start", "SoC start"),
                ("soc_end", "SoC end"),
                ("cost", "Cost"),
            ],
        )

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS, app=True)
    def charges_summary_chart(
        car_id: int,
        ctx: Context,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = _DEFAULT_CHART_LIMIT,
    ) -> PrefabApp:
        """Render a bar chart of kWh per charging session + headline totals.

        Args:
            car_id: The TeslaMate car ID
            start_date: Optional RFC3339 start date
            end_date: Optional RFC3339 end date
            limit: Max sessions to chart (default 30, sliced client-side).
        """
        payload = execute(
            teslamate_module.get_car_charges,
            car_id=car_id,
            start_date=start_date,
            end_date=end_date,
            **teslamate_auth_kwargs(ctx),
        )
        records = _extract_list(payload, ("data", "charges"), ("charges",))[: (limit or _DEFAULT_CHART_LIMIT)]
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

        # Reverse so the chart reads left-to-right oldest → newest
        chart_rows.reverse()

        title = f"Car #{car_id} – Charging summary"
        with Column(gap=4) as view:
            Heading(title, level=2)
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
        return PrefabApp(title=title, view=view)

    # === Drives ===

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS, app=True)
    def drives_table(
        car_id: int,
        ctx: Context,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_distance: Optional[float] = None,
        max_distance: Optional[float] = None,
        limit: Optional[int] = _DEFAULT_TABLE_LIMIT,
    ) -> PrefabApp:
        """Render driving sessions as a sortable, paginated table.

        Args:
            car_id: The TeslaMate car ID
            start_date: Optional RFC3339 start date
            end_date: Optional RFC3339 end date
            min_distance: Optional minimum distance filter (TeslaMate units)
            max_distance: Optional maximum distance filter (TeslaMate units)
            limit: Max drives to display (default 50, sliced client-side).
        """
        payload = execute(
            teslamate_module.get_car_drives,
            car_id=car_id,
            start_date=start_date,
            end_date=end_date,
            min_distance=min_distance,
            max_distance=max_distance,
            **teslamate_auth_kwargs(ctx),
        )
        records = _extract_list(payload, ("data", "drives"), ("drives",))[: (limit or _DEFAULT_TABLE_LIMIT)]
        rows = [_flatten_drive(r) for r in records if isinstance(r, dict)]
        return _records_table(
            f"Car #{car_id} – Drives",
            rows,
            columns_spec=[
                ("start_date", "Start"),
                ("from", "From"),
                ("to", "To"),
                ("distance_km", "Distance"),
                ("duration", "Duration"),
                ("speed_avg", "Avg speed"),
                ("energy_kwh", "Energy (kWh)"),
                ("wh_per_km", "Wh/km"),
                ("soc_end", "SoC end"),
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
        recent_charges = execute(teslamate_module.get_car_charges, car_id=car_id, **kwargs)
        recent_drives = execute(teslamate_module.get_car_drives, car_id=car_id, **kwargs)

        status_data = (
            _unwrap(status, "data", "status")
            or _unwrap(status, "status")
            or _unwrap(status, "data")
            or status
        )
        current_data = (
            _unwrap(current, "data", "current_charge")
            or _unwrap(current, "current_charge")
            or _unwrap(current, "data")
            or current
        )
        bh = _unwrap(health, "data", "battery_health")
        units = _unwrap(health, "data", "units")
        length_unit = (units or {}).get("unit_of_length", "km") if isinstance(units, dict) else "km"

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

            # Top row: live status
            with Grid(columns=3, gap=4):
                Metric(label="Battery", value=f"{battery_pct}%" if battery_pct is not None else "—")
                Metric(label="State", value=str(charging_state or "—"))
                if isinstance(current_data, dict) and current_data:
                    pwr = current_data.get("charger_power") or current_data.get("power")
                    Metric(label="Charging power", value=f"{pwr} kW" if pwr is not None else "—")
                else:
                    Metric(label="Charging", value="Idle")

            # Battery health
            if isinstance(bh, dict) and bh:
                soh = bh.get("battery_health_percentage")
                cur_cap = bh.get("current_capacity")
                max_cap = bh.get("max_capacity")
                cur_range = bh.get("current_range")
                max_range = bh.get("max_range")
                with Card():
                    with CardHeader():
                        CardTitle("Battery health")
                    with CardContent():
                        with Grid(columns=3, gap=3):
                            if soh is not None:
                                Metric(label="State of health", value=f"{round(float(soh), 1)}%")
                            if cur_cap is not None and max_cap is not None:
                                Metric(
                                    label="Capacity",
                                    value=f"{round(float(cur_cap), 2)} kWh",
                                    description=f"new: {round(float(max_cap), 2)} kWh",
                                )
                            if cur_range is not None and max_range is not None:
                                Metric(
                                    label=f"Range ({length_unit})",
                                    value=round(float(cur_range), 0),
                                    description=f"new: {round(float(max_range), 0)}",
                                )

            # Recent charges + drives (top 5 each, flattened columns)
            charges = _extract_list(recent_charges, ("data", "charges"), ("charges",))[:_DASHBOARD_RECENT_LIMIT]
            drives = _extract_list(recent_drives, ("data", "drives"), ("drives",))[:_DASHBOARD_RECENT_LIMIT]

            with Grid(columns=2, gap=4):
                with Card():
                    with CardHeader():
                        CardTitle("Recent charges")
                    with CardContent():
                        _mini_table(
                            [_flatten_charge(r) for r in charges if isinstance(r, dict)],
                            [
                                ("start_date", "Start"),
                                ("address", "Where"),
                                ("kwh", "kWh"),
                                ("soc_end", "→ SoC"),
                            ],
                        )

                with Card():
                    with CardHeader():
                        CardTitle("Recent drives")
                    with CardContent():
                        _mini_table(
                            [_flatten_drive(r) for r in drives if isinstance(r, dict)],
                            [
                                ("start_date", "Start"),
                                ("to", "To"),
                                ("distance_km", "Distance"),
                                ("duration", "Duration"),
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


def _mini_table(rows: list[dict[str, Any]], columns_spec: list[tuple[str, str]]) -> None:
    """Render a small inline table (no pagination, no search) inside a Card."""
    if not rows:
        Muted("None.")
        return
    columns = [DataTableColumn(key=k, header=h, sortable=False) for k, h in columns_spec]
    DataTable(columns=columns, rows=rows, paginated=False)
