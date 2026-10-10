import pytest

from app.core import clientip
from app.core.config import get_settings


def scope(headers: dict, peer: str = "10.0.0.5") -> dict:
    return {"headers": [(k.encode(), v.encode()) for k, v in headers.items()], "client": (peer, 1234)}


@pytest.fixture
def settings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "client_ip_header", None)
    monkeypatch.setattr(s, "trusted_proxy_hops", 0)
    return s


def test_default_ignores_forwarded_headers(settings):
    assert clientip.client_ip(scope({"x-forwarded-for": "6.6.6.6"})) == "10.0.0.5"  # spoof ignored


def test_trusted_hops_take_what_our_proxy_appended(settings, monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    # Attacker sends "1.1.1.1"; our load balancer appends the real address.
    assert clientip.client_ip(scope({"x-forwarded-for": "1.1.1.1, 203.0.113.9"})) == "203.0.113.9"
    assert clientip.client_ip(scope({"x-forwarded-for": "not-an-ip"})) == "10.0.0.5"


def test_edge_header_preferred_and_validated(settings, monkeypatch):
    monkeypatch.setattr(settings, "client_ip_header", "cf-connecting-ip")
    assert (
        clientip.client_ip(scope({"cf-connecting-ip": "2001:db8::1", "x-forwarded-for": "1.1.1.1"}))
        == "2001:db8::1"
    )
    assert clientip.client_ip(scope({"cf-connecting-ip": "<script>"})) == "10.0.0.5"


def test_bff_forwarded_ip_requires_the_shared_secret(settings, monkeypatch):
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "bff_secret", SecretStr("s3cret-shared-with-nextjs"))
    trusted = {"x-bff-secret": "s3cret-shared-with-nextjs", "x-client-ip": "49.36.1.2"}
    assert clientip.client_ip(scope(trusted)) == "49.36.1.2"
    assert clientip.is_trusted_bff(scope(trusted))
    forged = {"x-bff-secret": "guess", "x-client-ip": "49.36.1.2"}
    assert clientip.client_ip(scope(forged)) == "10.0.0.5" and not clientip.is_trusted_bff(scope(forged))
    assert clientip.client_ip(scope({"x-client-ip": "49.36.1.2"})) == "10.0.0.5"  # no secret, no trust
    monkeypatch.setattr(settings, "bff_secret", None)
    assert not clientip.is_trusted_bff(scope(trusted))  # feature off: header ignored
