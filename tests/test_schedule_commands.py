"""Payloads of add_precondition_schedule / add_charge_schedule.

Keys and types mirror what Tesla's vehicle-command proxy parses
(pkg/proxy/command.go): lat/lon numbers, precondition_time / start_time /
end_time numbers in minutes after midnight, days_of_week a day-name string,
enabled / start_enabled / end_enabled / one_time booleans. A missing key or a
wrong type makes the proxy answer 400 (e.g. "missing lat param").
"""

from __future__ import annotations

import pytest

from tesla_mcp.modules.commands import VehicleCommandsModule

VIN = "5YJ3E1EA0KF000000"


class RecordingClient:
    def __init__(self):
        self.calls = []

    def post(self, endpoint, *, context, json=None):
        self.calls.append((endpoint, json))
        return {"response": {"result": True, "reason": ""}}


@pytest.fixture
def module():
    return VehicleCommandsModule(RecordingClient())


def _sent(module):
    assert len(module.client.calls) == 1
    return module.client.calls[0]


def _assert_proxy_types(payload, numbers, bools):
    for key in numbers:
        assert isinstance(payload[key], (int, float)) and not isinstance(payload[key], bool), key
    for key in bools:
        assert isinstance(payload[key], bool), key
    assert isinstance(payload["days_of_week"], str)


def test_precondition_schedule_payload(module):
    result = module.add_precondition_schedule(
        VIN, precondition_time=450, lat=48.85, lon=2.35, bearer_token="t"
    )
    endpoint, payload = _sent(module)
    assert endpoint == f"/api/1/vehicles/{VIN}/command/add_precondition_schedule"
    assert payload == {
        "precondition_time": 450,
        "lat": 48.85,
        "lon": 2.35,
        "days_of_week": "All",
        "enabled": True,
        "one_time": False,
    }
    _assert_proxy_types(payload, ["precondition_time", "lat", "lon"], ["enabled", "one_time"])
    assert not {"time", "latitude", "longitude", "name"} & payload.keys()
    assert result == {"result": True, "reason": ""}


def test_precondition_schedule_options(module):
    module.add_precondition_schedule(
        VIN,
        precondition_time=180,
        lat=48.85,
        lon=2.35,
        days_of_week="Mon,Tues,Wed,Thurs,Fri",
        enabled=False,
        one_time=True,
        schedule_id=1794867432,
        bearer_token="t",
    )
    _, payload = _sent(module)
    assert payload["days_of_week"] == "Mon,Tues,Wed,Thurs,Fri"
    assert payload["enabled"] is False
    assert payload["one_time"] is True
    assert payload["id"] == 1794867432


def test_charge_schedule_payload(module):
    module.add_charge_schedule(
        VIN, lat=48.85, lon=2.35, start_time=1380, end_time=360, bearer_token="t"
    )
    endpoint, payload = _sent(module)
    assert endpoint == f"/api/1/vehicles/{VIN}/command/add_charge_schedule"
    assert payload == {
        "lat": 48.85,
        "lon": 2.35,
        "start_time": 1380,
        "start_enabled": True,
        "end_time": 360,
        "end_enabled": True,
        "days_of_week": "All",
        "enabled": True,
        "one_time": False,
    }
    _assert_proxy_types(
        payload,
        ["lat", "lon", "start_time", "end_time"],
        ["enabled", "one_time", "start_enabled", "end_enabled"],
    )
    assert not {"time", "latitude", "longitude", "name"} & payload.keys()


def test_charge_schedule_start_only(module):
    module.add_charge_schedule(VIN, lat=48.85, lon=2.35, start_time=1380, bearer_token="t")
    _, payload = _sent(module)
    assert payload["start_enabled"] is True
    assert payload["end_enabled"] is False
    assert "end_time" not in payload


def test_charge_schedule_needs_a_time(module):
    with pytest.raises(ValueError):
        module.add_charge_schedule(VIN, lat=48.85, lon=2.35, bearer_token="t")
    assert module.client.calls == []


def test_mcp_tools_expose_proxy_parameter_names():
    import inspect

    from tesla_mcp import app

    def params(tool):
        fn = getattr(tool, "fn", tool)
        return set(inspect.signature(fn).parameters)

    pre = params(app.add_precondition_schedule)
    assert {"precondition_time", "lat", "lon", "days_of_week", "enabled", "one_time"} <= pre
    assert not {"time", "latitude", "longitude"} & pre

    charge = params(app.add_charge_schedule)
    assert {"lat", "lon", "start_time", "end_time", "days_of_week", "enabled", "one_time"} <= charge
    assert not {"time", "latitude", "longitude"} & charge
