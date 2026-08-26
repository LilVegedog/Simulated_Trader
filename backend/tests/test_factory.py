from market_data.factory import get_market_data_provider
from market_data.massive_client import MassiveProvider
from market_data.simulator import SimulatorProvider


def test_returns_simulator_when_no_api_key_set(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    provider = get_market_data_provider()
    assert isinstance(provider, SimulatorProvider)


def test_returns_simulator_when_api_key_is_blank(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "   ")
    provider = get_market_data_provider()
    assert isinstance(provider, SimulatorProvider)


async def test_returns_massive_provider_when_api_key_is_set(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "abc123")
    provider = get_market_data_provider()
    try:
        assert isinstance(provider, MassiveProvider)
        assert provider._api_key == "abc123"
    finally:
        await provider._client.aclose()


async def test_massive_poll_interval_defaults_to_fifteen_seconds(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "abc123")
    monkeypatch.delenv("MASSIVE_POLL_INTERVAL", raising=False)
    provider = get_market_data_provider()
    try:
        assert provider._poll_interval == 15.0
    finally:
        await provider._client.aclose()


async def test_massive_poll_interval_is_overridable_via_env(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "abc123")
    monkeypatch.setenv("MASSIVE_POLL_INTERVAL", "5")
    provider = get_market_data_provider()
    try:
        assert provider._poll_interval == 5.0
    finally:
        await provider._client.aclose()
