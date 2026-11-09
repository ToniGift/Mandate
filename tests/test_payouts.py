"""Tests for payouts.py with a fake client: no network."""
from decimal import Decimal as D
from unittest.mock import MagicMock

import pytest

from mandate.payouts import PayoutError, get_payout_status, send_payout


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
