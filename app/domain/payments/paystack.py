"""Paystack collection and transfer adapter.

All amounts passed to Paystack are integer minor units (kobo for NGN).
The adapter deliberately verifies every collection server-to-server; webhooks
are treated as notifications, not as proof of payment on their own.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from urllib.parse import quote

import httpx

from app.domain.payments.provider import (
    ProviderPayment,
    ProviderPayout,
    ProviderWebhookEvent,
)


class PaystackError(RuntimeError):
    """A safe, provider-facing error without credentials or raw payloads."""


class PaystackProvider:
    name = "PAYSTACK"

    def __init__(
        self,
        secret_key: str,
        *,
        base_url: str = "https://api.paystack.co",
        callback_url: str | None = None,
        timeout_seconds: float = 15.0,
        channels: tuple[str, ...] = ("card", "bank_transfer", "ussd"),
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not secret_key or not secret_key.strip():
            raise ValueError("A Paystack secret key is required")
        self._secret_key = secret_key.strip()
        self._base_url = base_url.rstrip("/")
        self._callback_url = callback_url
        self._timeout_seconds = timeout_seconds
        self._channels = tuple(channel for channel in channels if channel)
        self._transport = transport

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._secret_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise PaystackError(
                "Paystack request failed; retry only after checking transaction status"
            ) from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise PaystackError("Paystack returned an invalid response") from exc
        if (
            response.is_error
            or not isinstance(payload, dict)
            or payload.get("status") is not True
        ):
            message = payload.get("message") if isinstance(payload, dict) else None
            # Do not include raw response content or secrets in exceptions/logs.
            safe_message = str(message)[:180] if message else "request was rejected"
            raise PaystackError(
                f"Paystack {method.upper()} {path} failed: {safe_message}"
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise PaystackError("Paystack response did not contain transaction data")
        return data

    async def initialize_payment(
        self, *, reference: str, amount_minor: int, currency: str, email: str
    ) -> str:
        if amount_minor <= 0:
            raise ValueError("Payment amount must be positive")
        body: dict[str, Any] = {
            "email": email,
            "amount": amount_minor,
            "currency": currency.upper(),
            "reference": reference,
            "metadata": {"integration": "tutova", "internal_reference": reference},
        }
        if self._channels:
            body["channels"] = list(self._channels)
        if self._callback_url:
            body["callback_url"] = self._callback_url
        data = await self._request("POST", "/transaction/initialize", json=body)
        authorization_url = data.get("authorization_url")
        returned_reference = data.get("reference")
        if not isinstance(authorization_url, str) or not authorization_url.startswith(
            "https://"
        ):
            raise PaystackError("Paystack did not return a valid checkout URL")
        if returned_reference != reference:
            raise PaystackError("Paystack returned a mismatched payment reference")
        return authorization_url

    async def verify_payment(self, *, provider_reference: str) -> ProviderPayment:
        if not provider_reference:
            raise ValueError("Provider reference is required")
        data = await self._request(
            "GET", f"/transaction/verify/{quote(provider_reference, safe='')}"
        )
        reference = data.get("reference")
        amount = data.get("amount")
        currency = data.get("currency")
        status = data.get("status")
        if reference != provider_reference:
            raise PaystackError("Paystack verification reference did not match")
        if not isinstance(amount, int) or amount < 0:
            raise PaystackError("Paystack verification amount was invalid")
        if not isinstance(currency, str) or not isinstance(status, str):
            raise PaystackError("Paystack verification response was incomplete")
        normalized_status = "SUCCESS" if status.lower() == "success" else status.upper()
        return ProviderPayment(
            provider=self.name,
            provider_reference=reference,
            amount_minor=amount,
            currency=currency.upper(),
            status=normalized_status,
        )

    def verify_webhook_signature(self, *, raw_body: bytes, signature: str) -> bool:
        if not signature:
            return False
        digest = hmac.new(
            self._secret_key.encode("utf-8"), raw_body, hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(digest, signature.strip())

    def parse_webhook(self, *, raw_body: bytes) -> ProviderWebhookEvent:
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON webhook payload") from exc
        if not isinstance(payload, dict):
            raise ValueError("Invalid webhook payload")
        event_type = payload.get("event")
        data = payload.get("data")
        reference = data.get("reference") if isinstance(data, dict) else None
        if (
            not reference
            and isinstance(data, dict)
            and isinstance(data.get("transaction"), dict)
        ):
            reference = data["transaction"].get("reference")
        if (
            not isinstance(event_type, str)
            or not isinstance(reference, str)
            or not reference
        ):
            raise ValueError("Webhook event and transaction reference are required")
        return ProviderWebhookEvent(provider_reference=reference, event_type=event_type)

    async def create_transfer_recipient(
        self, *, name: str, account_number: str, bank_code: str, currency: str = "NGN"
    ) -> dict[str, str]:
        if not account_number.isdigit() or not 8 <= len(account_number) <= 12:
            raise ValueError("A valid bank account number is required")
        if not bank_code.strip() or not name.strip():
            raise ValueError("Account name and bank code are required")
        data = await self._request(
            "POST",
            "/transferrecipient",
            json={
                "type": "nuban",
                "name": name.strip(),
                "account_number": account_number,
                "bank_code": bank_code.strip(),
                "currency": currency.upper(),
            },
        )
        code = data.get("recipient_code")
        details = data.get("details") or {}
        if not isinstance(code, str) or not code.startswith("RCP_"):
            raise PaystackError("Paystack did not return a valid transfer recipient")
        return {
            "recipient_code": code,
            "account_name": str(
                details.get("account_name") or data.get("name") or name
            ).strip(),
            "bank_name": str(details.get("bank_name") or "Bank").strip(),
            "account_number": str(details.get("account_number") or account_number),
        }

    async def initiate_refund(
        self,
        *,
        transaction_reference: str,
        reference: str,
        amount_minor: int,
        currency: str,
        reason: str,
    ) -> dict[str, Any]:
        if amount_minor <= 0:
            raise ValueError("Refund amount must be positive")
        data = await self._request(
            "POST",
            "/refund",
            json={
                "transaction": transaction_reference,
                "reference": reference,
                "amount": amount_minor,
                "currency": currency.upper(),
                "customer_note": reason[:200],
                "merchant_note": f"Tutova refund {reference}",
            },
        )
        returned_reference = data.get("reference")
        if returned_reference and returned_reference != reference:
            raise PaystackError("Paystack returned a mismatched refund reference")
        return {
            "reference": reference,
            "status": str(data.get("status", "pending")).upper(),
        }

    async def initiate_payout(
        self,
        *,
        reference: str,
        amount_minor: int,
        currency: str,
        destination_token: str,
    ) -> ProviderPayout:
        """Initiate a transfer using an already-created Paystack recipient code.

        Recipient creation and bank-account verification should be performed by
        a separately authorised onboarding flow; raw account details must never
        be accepted here or stored as destination_token.
        """
        if amount_minor <= 0:
            raise ValueError("Payout amount must be positive")
        if not destination_token.startswith("RCP_"):
            raise ValueError(
                "destination_token must be a verified Paystack recipient code"
            )
        data = await self._request(
            "POST",
            "/transfer",
            json={
                "source": "balance",
                "amount": amount_minor,
                "recipient": destination_token,
                "reference": reference,
                "reason": "Tutova tutor payout",
                "currency": currency.upper(),
            },
        )
        returned_reference = data.get("reference")
        if returned_reference != reference:
            raise PaystackError("Paystack returned a mismatched transfer reference")
        amount = data.get("amount", amount_minor)
        currency_value = data.get("currency", currency)
        if not isinstance(amount, int) or not isinstance(currency_value, str):
            raise PaystackError("Paystack transfer response was incomplete")
        status = str(data.get("status", "PENDING")).upper()
        return ProviderPayout(
            self.name,
            returned_reference,
            amount,
            currency_value.upper(),
            status,
            str(data.get("transfer_code")) if data.get("transfer_code") else None,
        )

    async def verify_refund(self, *, provider_reference: str) -> dict[str, str | int]:
        data = await self._request(
            "GET", f"/refund/{quote(provider_reference, safe='')}"
        )
        status = data.get("status")
        amount = data.get("amount")
        reference = data.get("reference", provider_reference)
        if not isinstance(status, str) or reference != provider_reference:
            raise PaystackError("Paystack refund verification response was incomplete")
        return {
            "reference": reference,
            "status": status.upper(),
            "amount_minor": int(amount or 0),
        }

    async def finalize_payout(self, *, transfer_code: str, otp: str) -> ProviderPayout:
        if not transfer_code or not otp.strip():
            raise ValueError("Transfer code and OTP are required")
        data = await self._request(
            "POST",
            "/transfer/finalize_transfer",
            json={"transfer_code": transfer_code, "otp": otp.strip()},
        )
        reference = data.get("reference")
        amount = data.get("amount")
        currency = data.get("currency", "NGN")
        status = data.get("status")
        if (
            not isinstance(reference, str)
            or not isinstance(amount, int)
            or not isinstance(currency, str)
            or not isinstance(status, str)
        ):
            raise PaystackError(
                "Paystack transfer finalization response was incomplete"
            )
        return ProviderPayout(
            self.name,
            reference,
            amount,
            currency.upper(),
            status.upper(),
            str(data.get("transfer_code"))
            if data.get("transfer_code")
            else transfer_code,
        )

    async def verify_payout(self, *, provider_reference: str) -> ProviderPayout:
        if not provider_reference:
            raise ValueError("Provider reference is required")
        data = await self._request(
            "GET", f"/transfer/verify/{quote(provider_reference, safe='')}"
        )
        reference = data.get("reference")
        amount = data.get("amount")
        currency = data.get("currency", "NGN")
        status = data.get("status")
        if (
            reference != provider_reference
            or not isinstance(amount, int)
            or not isinstance(currency, str)
            or not isinstance(status, str)
        ):
            raise PaystackError(
                "Paystack transfer verification response was incomplete or mismatched"
            )
        return ProviderPayout(
            self.name, reference, amount, currency.upper(), status.upper()
        )
