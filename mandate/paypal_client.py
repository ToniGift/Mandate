"""Small PayPal sandbox client: gets an OAuth token, caches it, refreshes it before it expires."""
from __future__ import annotations

import os
import time

import requests
from dotenv import load_dotenv

REFRESH_MARGIN_SECONDS = 60  # fetch a new token this long before the old one expires


class PayPalClient:
    def __init__(self) -> None:
        load_dotenv()
        self.client_id = os.environ.get("PAYPAL_CLIENT_ID", "")
        self.client_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "")
        self.base_url = os.environ.get("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com").rstrip("/")
        if not self.client_id or not self.client_secret:
            raise RuntimeError("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set in .env")
        self._token: str | None = None
        self._expires_at = 0.0  # time.time() value after which the token is no longer safe

    def get_token(self) -> str:
        """Return a valid token, fetching a new one only when needed."""
        if self._token is None or time.time() >= self._expires_at - REFRESH_MARGIN_SECONDS:
            self._fetch_token()
        return self._token

    def token_seconds_left(self) -> int:
        return max(0, int(self._expires_at - time.time()))

    def _fetch_token(self) -> None:
        resp = requests.post(
            f"{self.base_url}/v1/oauth2/token",
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        self._token = body["access_token"]
        self._expires_at = time.time() + int(body["expires_in"])

    def request(self, method: str, path: str, json: dict | None = None) -> requests.Response:
        """Call a PayPal API. Returns the response as is (the caller checks the status)."""
        return requests.request(
            method,
            f"{self.base_url}{path}",
            json=json,
            headers={"Authorization": f"Bearer {self.get_token()}"},
            timeout=30,
        )
