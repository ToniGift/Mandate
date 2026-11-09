"""Tests for the PayPal client. HTTP is mocked, so no network and no real credentials are needed."""
from unittest.mock import MagicMock, patch

import pytest

from mandate import paypal_client
from mandate.paypal_client import PayPalClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "test-id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("PAYPAL_BASE_URL", "https://example.test")
    with patch.object(paypal_client, "load_dotenv"):  # do not read a real .env in tests
        return PayPalClient()


def token_response(token="tok-1", expires_in=3600):
    resp = MagicMock()
    resp.json.return_value = {"access_token": token, "expires_in": expires_in}
    return resp


def test_missing_credentials_raise(monkeypatch):
    monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
    monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)
    with patch.object(paypal_client, "load_dotenv"):
        with pytest.raises(RuntimeError):
            PayPalClient()


def test_token_is_fetched_with_client_credentials(client):
    with patch.object(paypal_client.requests, "post", return_value=token_response()) as post:
        assert client.get_token() == "tok-1"
    args, kwargs = post.call_args
    assert args[0] == "https://example.test/v1/oauth2/token"
    assert kwargs["auth"] == ("test-id", "test-secret")
    assert kwargs["data"] == {"grant_type": "client_credentials"}


def test_token_is_cached(client):
    with patch.object(paypal_client.requests, "post", return_value=token_response()) as post:
        client.get_token()
        client.get_token()
    assert post.call_count == 1


def test_token_is_refreshed_before_it_expires(client):
    with patch.object(paypal_client.requests, "post",
                      side_effect=[token_response("tok-1", 3600), token_response("tok-2", 3600)]) as post:
        with patch.object(paypal_client.time, "time", return_value=1000.0):
            assert client.get_token() == "tok-1"
        # 3600 s lifetime, so at t=1000+3600-30 we are inside the 60 s refresh margin
        with patch.object(paypal_client.time, "time", return_value=1000.0 + 3600 - 30):
            assert client.get_token() == "tok-2"
    assert post.call_count == 2


def test_token_not_refreshed_while_still_fresh(client):
    with patch.object(paypal_client.requests, "post", return_value=token_response()) as post:
        with patch.object(paypal_client.time, "time", return_value=1000.0):
            client.get_token()
        with patch.object(paypal_client.time, "time", return_value=1000.0 + 3000):
            client.get_token()
    assert post.call_count == 1


def test_request_sends_bearer_token_and_returns_response(client):
    api_response = MagicMock(status_code=201)
    with patch.object(paypal_client.requests, "post", return_value=token_response()):
        with patch.object(paypal_client.requests, "request", return_value=api_response) as req:
            result = client.request("POST", "/v2/checkout/orders", {"a": 1})
    assert result is api_response
    args, kwargs = req.call_args
    assert args == ("POST", "https://example.test/v2/checkout/orders")
    assert kwargs["json"] == {"a": 1}
    assert kwargs["headers"] == {"Authorization": "Bearer tok-1"}
