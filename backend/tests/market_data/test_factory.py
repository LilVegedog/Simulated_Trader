from app.market_data.factory import create_provider
from app.market_data.massive import MassiveProvider
from app.market_data.simulator import SimulatorProvider


def test_uses_simulator_when_no_api_key_is_given(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    assert isinstance(create_provider(massive_api_key=None), SimulatorProvider)


def test_uses_simulator_when_api_key_is_empty_string():
    assert isinstance(create_provider(massive_api_key=""), SimulatorProvider)


def test_uses_massive_when_api_key_is_explicitly_provided():
    provider = create_provider(massive_api_key="secret")
    assert isinstance(provider, MassiveProvider)


def test_reads_api_key_from_environment_when_not_passed_explicitly(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "from-env")
    assert isinstance(create_provider(), MassiveProvider)


def test_falls_back_to_simulator_when_environment_variable_is_unset(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    assert isinstance(create_provider(), SimulatorProvider)


def test_massive_provider_uses_default_poll_interval_when_unconfigured(monkeypatch):
    monkeypatch.delenv("MASSIVE_POLL_INTERVAL", raising=False)
    provider = create_provider(massive_api_key="secret")
    assert provider._poll_interval == 15.0  # noqa: SLF001


def test_massive_poll_interval_reads_from_environment(monkeypatch):
    monkeypatch.setenv("MASSIVE_POLL_INTERVAL", "5")
    provider = create_provider(massive_api_key="secret")
    assert provider._poll_interval == 5.0  # noqa: SLF001


def test_massive_poll_interval_explicit_argument_overrides_environment(monkeypatch):
    monkeypatch.setenv("MASSIVE_POLL_INTERVAL", "5")
    provider = create_provider(massive_api_key="secret", massive_poll_interval=2.0)
    assert provider._poll_interval == 2.0  # noqa: SLF001
