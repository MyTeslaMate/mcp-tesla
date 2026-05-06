"""PV-follow smart charging module.

Continuously matches Tesla charging amps to the solar surplus reported by the
Powerwall (`grid_power` from live_status). Designed to be driven as a FastMCP
background Task, with state read back via separate status tool calls.

The pure helpers (`compute_surplus_w`, `compute_target_amps`, `decide_action`)
are kept side-effect-free so they can be unit-tested without mocking Tesla.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Dict, Optional

from ..base import TeslaClient, TeslaModule


DEFAULT_DATA_DIR = "./data"
CONFIG_FILENAME = "pv_follow_config.json"

CHARGING_STATES_ACTIVE = {"Charging", "Starting"}
CHARGING_STATES_TERMINAL = {"Disconnected", "Complete"}


@dataclass
class PVFollowConfig:
    """Per-vehicle smart charging configuration."""

    energy_site_id: Optional[str] = None
    min_amps: int = 5
    max_amps: int = 16
    interval_s: int = 30
    min_pw_soc_percent: int = 50
    start_hysteresis_s: int = 120
    stop_hysteresis_s: int = 180
    target_soc_percent: Optional[int] = None
    voltage_v: Optional[int] = None
    phases: Optional[int] = None
    max_consecutive_errors: int = 5

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PVFollowConfig":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def merged_with(self, overrides: Optional[Dict[str, Any]]) -> "PVFollowConfig":
        if not overrides:
            return self
        data = asdict(self)
        for k, v in overrides.items():
            if k in data and v is not None:
                data[k] = v
        return PVFollowConfig.from_dict(data)


@dataclass
class PVFollowState:
    """Live state of a session, exposed via pv_follow_status."""

    vehicle_tag: str
    energy_site_id: str
    started_at: float
    last_tick_at: Optional[float] = None
    last_action: str = "pending"
    last_error: Optional[str] = None
    surplus_w: int = 0
    target_amps: int = 0
    pw_soc_percent: Optional[float] = None
    vehicle_soc_percent: Optional[float] = None
    charging_state: Optional[str] = None
    voltage_v: Optional[int] = None
    phases: Optional[int] = None
    consecutive_errors: int = 0
    terminated: bool = False
    terminate_reason: Optional[str] = None


@dataclass
class TickResult:
    """Outcome of one control loop iteration."""

    surplus_w: int
    target_amps: int
    pw_soc_percent: Optional[float]
    vehicle_soc_percent: Optional[float]
    charging_state: Optional[str]
    action: str
    terminate: bool = False
    terminate_reason: Optional[str] = None


# === Pure helpers ===========================================================


def compute_surplus_w(grid_power: float) -> int:
    """Convert raw grid_power (W, negative = export) into a non-negative surplus.

    A negative grid_power means energy is being exported to the grid — that's
    the surplus we can divert to the car. Positive (importing) yields 0.
    """
    surplus = -float(grid_power)
    return max(0, int(surplus))


def compute_target_amps(
    surplus_w: int,
    voltage_v: int,
    phases: int,
    min_amps: int,
    max_amps: int,
) -> int:
    """Translate a solar surplus (W) into an integer charging current (A).

    Below the minimum-amp threshold the answer is 0 (don't charge) so the
    caller can apply hysteresis on a clean boolean signal.
    """
    if voltage_v <= 0 or phases <= 0 or surplus_w <= 0:
        return 0
    raw = surplus_w // (voltage_v * phases)
    if raw < min_amps:
        return 0
    if raw > max_amps:
        return max_amps
    return raw


def decide_action(
    *,
    target_amps: int,
    current_amps: int,
    charging_state: Optional[str],
    vehicle_soc: Optional[float],
    target_soc: Optional[float],
    above_since: Optional[float],
    below_since: Optional[float],
    now: float,
    start_hysteresis_s: int,
    stop_hysteresis_s: int,
    min_amps: int,
) -> tuple[str, Optional[str]]:
    """Decide what to do at this tick.

    Returns (action, terminate_reason). Action is one of:
        "terminate" | "start" | "stop" | "adjust" | "hold"
    """
    if charging_state in CHARGING_STATES_TERMINAL:
        return "terminate", f"charging_state={charging_state}"

    if (
        target_soc is not None
        and vehicle_soc is not None
        and vehicle_soc >= target_soc
    ):
        return "terminate", f"target_soc_reached ({vehicle_soc}>={target_soc})"

    is_charging = charging_state in CHARGING_STATES_ACTIVE
    has_surplus = target_amps >= min_amps

    if is_charging:
        if not has_surplus:
            if below_since is not None and (now - below_since) >= stop_hysteresis_s:
                return "stop", None
            return "hold", None
        if target_amps != current_amps:
            return "adjust", None
        return "hold", None

    if has_surplus:
        if above_since is not None and (now - above_since) >= start_hysteresis_s:
            return "start", None
    return "hold", None


# === Session ================================================================


class PVFollowSession:
    """One PV-follow session tied to a single vehicle.

    Holds live state, reads Powerwall + vehicle, drives the car commands.
    Cancellation is signalled via ``request_stop()`` which sets an asyncio
    event; the loop wakes between ticks and exits cleanly.
    """

    def __init__(
        self,
        *,
        vehicle_tag: str,
        config: PVFollowConfig,
        bearer_token: str,
        energy_module: Any,
        commands_module: Any,
        vehicle_module: Any,
        logger: Optional[logging.Logger] = None,
    ):
        if not config.energy_site_id:
            raise ValueError("energy_site_id is required (set via config or override)")
        self.vehicle_tag = vehicle_tag
        self.config = config
        self.bearer_token = bearer_token
        self.energy_module = energy_module
        self.commands_module = commands_module
        self.vehicle_module = vehicle_module
        self.logger = logger or logging.getLogger("tesla_mcp.pv_follow")
        self.state = PVFollowState(
            vehicle_tag=vehicle_tag,
            energy_site_id=config.energy_site_id,
            started_at=time.time(),
            voltage_v=config.voltage_v,
            phases=config.phases,
        )
        self._stop_event = asyncio.Event()
        self._above_since: Optional[float] = None
        self._below_since: Optional[float] = None

    def request_stop(self) -> None:
        self._stop_event.set()

    @property
    def stop_requested(self) -> bool:
        return self._stop_event.is_set()

    def _detect_voltage_phases(self) -> tuple[int, int]:
        if self.config.voltage_v and self.config.phases:
            return self.config.voltage_v, self.config.phases
        try:
            vd = self.vehicle_module.get_vehicle_data(
                self.vehicle_tag, bearer_token=self.bearer_token
            )
            cs = _extract_charge_state(vd)
            voltage = int(cs.get("charger_voltage") or 0)
            phases = int(cs.get("charger_phases") or 0)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("voltage/phases probe failed: %s", exc)
            voltage = 0
            phases = 0
        if voltage <= 0:
            voltage = self.config.voltage_v or 230
        if phases <= 0:
            phases = self.config.phases or 1
        return voltage, phases

    async def _do_tick(self, voltage: int, phases: int) -> TickResult:
        live = self.energy_module.live_status(
            self.config.energy_site_id, bearer_token=self.bearer_token
        )
        live_payload = _unwrap_response(live)
        grid_power = float(live_payload.get("grid_power", 0) or 0)
        pw_soc = live_payload.get("percentage_charged")

        surplus = compute_surplus_w(grid_power)
        if pw_soc is not None and pw_soc < self.config.min_pw_soc_percent:
            target = 0
        else:
            target = compute_target_amps(
                surplus_w=surplus,
                voltage_v=voltage,
                phases=phases,
                min_amps=self.config.min_amps,
                max_amps=self.config.max_amps,
            )

        vd = self.vehicle_module.get_vehicle_data(
            self.vehicle_tag, bearer_token=self.bearer_token
        )
        cs = _extract_charge_state(vd)
        charging_state = cs.get("charging_state")
        vehicle_soc = cs.get("battery_level")
        current_amps = int(
            cs.get("charge_amps")
            or cs.get("charger_actual_current")
            or 0
        )
        target_soc = self.config.target_soc_percent
        if target_soc is None:
            target_soc = cs.get("charge_limit_soc")

        now = time.time()
        if target >= self.config.min_amps:
            if self._above_since is None:
                self._above_since = now
            self._below_since = None
        else:
            if self._below_since is None:
                self._below_since = now
            self._above_since = None

        action, terminate_reason = decide_action(
            target_amps=target,
            current_amps=current_amps,
            charging_state=charging_state,
            vehicle_soc=vehicle_soc,
            target_soc=target_soc,
            above_since=self._above_since,
            below_since=self._below_since,
            now=now,
            start_hysteresis_s=self.config.start_hysteresis_s,
            stop_hysteresis_s=self.config.stop_hysteresis_s,
            min_amps=self.config.min_amps,
        )

        if action == "start":
            self.commands_module.charge_start(
                self.vehicle_tag, bearer_token=self.bearer_token
            )
            self.commands_module.set_charging_amps(
                self.vehicle_tag,
                charging_amps=target,
                bearer_token=self.bearer_token,
            )
        elif action == "stop":
            self.commands_module.charge_stop(
                self.vehicle_tag, bearer_token=self.bearer_token
            )
        elif action == "adjust":
            self.commands_module.set_charging_amps(
                self.vehicle_tag,
                charging_amps=target,
                bearer_token=self.bearer_token,
            )

        return TickResult(
            surplus_w=surplus,
            target_amps=target,
            pw_soc_percent=pw_soc,
            vehicle_soc_percent=vehicle_soc,
            charging_state=charging_state,
            action=action,
            terminate=action == "terminate",
            terminate_reason=terminate_reason,
        )

    async def run(self, progress: Any = None) -> Dict[str, Any]:
        """Main control loop. Returns final state dict on exit."""
        voltage, phases = self._detect_voltage_phases()
        self.state.voltage_v = voltage
        self.state.phases = phases
        self.logger.info(
            "PV-follow started vehicle=%s site=%s voltage=%dV phases=%d",
            self.vehicle_tag,
            self.config.energy_site_id,
            voltage,
            phases,
        )

        while not self._stop_event.is_set():
            try:
                tick = await self._do_tick(voltage, phases)
                self.state.consecutive_errors = 0
                self.state.last_tick_at = time.time()
                self.state.surplus_w = tick.surplus_w
                self.state.target_amps = tick.target_amps
                self.state.pw_soc_percent = tick.pw_soc_percent
                self.state.vehicle_soc_percent = tick.vehicle_soc_percent
                self.state.charging_state = tick.charging_state
                self.state.last_action = tick.action
                self.state.last_error = None

                if progress is not None:
                    try:
                        await progress.set_message(self._format_progress())
                    except Exception:  # noqa: BLE001
                        pass

                if tick.terminate:
                    self.state.terminated = True
                    self.state.terminate_reason = tick.terminate_reason
                    break
            except Exception as exc:  # noqa: BLE001
                self.state.consecutive_errors += 1
                self.state.last_error = str(exc)
                self.logger.exception(
                    "PV-follow tick failed (#%d)", self.state.consecutive_errors
                )
                if self.state.consecutive_errors >= self.config.max_consecutive_errors:
                    self.state.terminated = True
                    self.state.terminate_reason = f"too_many_errors ({exc})"
                    break

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.config.interval_s
                )
                break
            except asyncio.TimeoutError:
                continue

        if self._stop_event.is_set() and not self.state.terminated:
            self.state.terminated = True
            self.state.terminate_reason = "stopped_by_user"

        self.logger.info(
            "PV-follow ended vehicle=%s reason=%s",
            self.vehicle_tag,
            self.state.terminate_reason,
        )
        return asdict(self.state)

    def _format_progress(self) -> str:
        s = self.state
        return (
            f"surplus={s.surplus_w}W amps={s.target_amps}A "
            f"pw_soc={s.pw_soc_percent} v_soc={s.vehicle_soc_percent} "
            f"state={s.charging_state} action={s.last_action}"
        )


# === Registry + persistence module =========================================


class PVFollowRegistry:
    """In-memory registry of active sessions, keyed by vehicle_tag."""

    def __init__(self) -> None:
        self._sessions: Dict[str, PVFollowSession] = {}
        self._lock = asyncio.Lock()

    def get(self, vehicle_tag: str) -> Optional[PVFollowSession]:
        return self._sessions.get(vehicle_tag)

    async def register(self, session: PVFollowSession) -> None:
        async with self._lock:
            existing = self._sessions.get(session.vehicle_tag)
            if existing and not existing.stop_requested:
                raise RuntimeError(
                    f"PV-follow session already running for {session.vehicle_tag}"
                )
            self._sessions[session.vehicle_tag] = session

    async def unregister(self, vehicle_tag: str) -> None:
        async with self._lock:
            self._sessions.pop(vehicle_tag, None)


class PVFollowConfigStore(TeslaModule):
    """JSON-backed config persistence for PV-follow per vehicle."""

    def __init__(self, client: TeslaClient, *, data_dir: Optional[str] = None):
        super().__init__(client)
        self.data_dir = Path(
            data_dir or os.environ.get("TESLA_PV_FOLLOW_DATA_DIR", DEFAULT_DATA_DIR)
        )
        self.config_path = self.data_dir / CONFIG_FILENAME

    def _load_all(self) -> Dict[str, Dict[str, Any]]:
        if not self.config_path.exists():
            return {}
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.warning("failed to read pv_follow config: %s", exc)
            return {}

    def _save_all(self, data: Dict[str, Dict[str, Any]]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.config_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.config_path)

    def get_config(self, vehicle_tag: str) -> PVFollowConfig:
        all_cfg = self._load_all()
        raw = all_cfg.get(vehicle_tag, {})
        return PVFollowConfig.from_dict(raw)

    def set_config(self, vehicle_tag: str, config: PVFollowConfig) -> PVFollowConfig:
        all_cfg = self._load_all()
        all_cfg[vehicle_tag] = asdict(config)
        self._save_all(all_cfg)
        return config


# === Internal helpers =======================================================


def _unwrap_response(payload: Any) -> Dict[str, Any]:
    """Tesla Fleet wraps responses in ``{"response": {...}}``; normalize."""
    if isinstance(payload, dict) and "response" in payload and isinstance(payload["response"], dict):
        return payload["response"]
    if isinstance(payload, dict):
        return payload
    return {}


def _extract_charge_state(vehicle_data: Any) -> Dict[str, Any]:
    response = _unwrap_response(vehicle_data)
    cs = response.get("charge_state")
    if isinstance(cs, dict):
        return cs
    return {}
