"""Tests for payouts.py with a fake client: no network."""
from decimal import Decimal as D
from unittest.mock import MagicMock, patch

import pytest

from mandate.payouts import PayoutError, fake_payouts_enabled, get_payout_status, send_payout


def fake_client(status_code, body):
    client = MagicMock()
    client.request.return_value = MagicMock(status_code=status_code, **{"json.return_value": body})
    return client


def test_send_payout_builds_request_and_returns_batch():
    client = fake_client(201, {"batch_header": {"payout_batch_id": "B1", "batch_status": "PENDING"}})
    result = send_payout("a@example.test", D("25"), "USD", "INV-9", "paper", client=client)
    assert result == {"batch_id": "B1", "status": "PENDING"}
    method, path, payload = client.request.call_args.args
    assert (method, path) == ("POST", "/v1/payments/payouts")
    assert payload["sender_batch_header"]["sender_batch_id"] == "mandate-INV-9"  # same invoice, same id
    assert payload["items"][0]["amount"] == {"value": "25.00", "currency": "USD"}
    assert payload["items"][0]["receiver"] == "a@example.test"


def test_send_payout_error_raises_with_paypal_message():
    client = fake_client(400, {"name": "USER_BUSINESS_ERROR", "message": "Batch already exists",
                               "details": [{"issue": "DUPLICATE_BATCH"}]})
    with pytest.raises(PayoutError, match="DUPLICATE_BATCH"):
        send_payout("a@example.test", D("25"), "USD", "INV-9", "", client=client)


def test_get_payout_status():
    client = fake_client(200, {"batch_header": {"batch_status": "SUCCESS"}})
    assert get_payout_status("B1", client=client) == "SUCCESS"
    assert client.request.call_args.args[:2] == ("GET", "/v1/payments/payouts/B1")


# ---- offline demo mode (MANDATE_FAKE_PAYOUTS) ---------------------------------------------------

@pytest.mark.parametrize("value", ["", "0", "no", "off", "false"])
def test_offline_mode_is_off_by_default_and_for_other_values(monkeypatch, value):
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", value)
    assert fake_payouts_enabled() is False
    # real mode behaves exactly as before: the PayPal client is used
    client = fake_client(201, {"batch_header": {"payout_batch_id": "B1", "batch_status": "PENDING"}})
    assert send_payout("a@example.test", D("25"), "USD", "INV-9", "", client=client) == {
        "batch_id": "B1", "status": "PENDING"}
    client.request.assert_called_once()


def test_offline_mode_is_off_when_the_variable_is_missing(monkeypatch):
    monkeypatch.delenv("MANDATE_FAKE_PAYOUTS", raising=False)
    assert fake_payouts_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "YES", " on "])
def test_offline_mode_on_returns_a_simulated_result_without_any_paypal_call(monkeypatch, value):
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", value)
    for name in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_BASE_URL"):
        monkeypatch.delenv(name, raising=False)  # no credentials at all
    assert fake_payouts_enabled() is True

    def no_network(*args, **kwargs):
        raise AssertionError("offline mode must not contact PayPal")

    client = MagicMock()
    client.request.side_effect = no_network
    with patch("mandate.payouts.PayPalClient", no_network), \
            patch("requests.post", no_network), patch("requests.request", no_network):
        result = send_payout("a@example.test", D("25"), "USD", "INV-9", "paper")          # no client given
        also = send_payout("a@example.test", D("25"), "USD", "INV-9", "paper", client=client)  # client ignored
    assert result == also == {"batch_id": "FAKE-INV-9", "status": "SUCCESS"}
    client.request.assert_not_called()


def test_offline_mode_status_lookup(monkeypatch):
    monkeypatch.setenv("MANDATE_FAKE_PAYOUTS", "1")
    client = MagicMock()
    assert get_payout_status("FAKE-INV-9", client=client) == "SUCCESS"
    with pytest.raises(PayoutError, match="offline demo mode"):
        get_payout_status("REAL-BATCH-ID", client=client)   # a real batch is never looked up offline
    client.request.assert_not_called()
