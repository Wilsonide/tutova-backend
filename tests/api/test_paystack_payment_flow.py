"""Paystack adapter tests for the booking-based payment implementation."""

import hashlib
import hmac
import json

import httpx
import pytest

from app.domain.payments.paystack import PaystackProvider


@pytest.mark.asyncio
async def test_paystack_checkout_initialization_and_server_verification():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/transaction/initialize":
            body = json.loads(request.content)
            seen["reference"] = body["reference"]
            assert body["amount"] == 750000
            assert body["currency"] == "NGN"
            return httpx.Response(200, json={"status": True, "data": {
                "authorization_url": "https://checkout.paystack.com/test",
                "reference": body["reference"],
            }})
        if request.url.path.startswith("/transaction/verify/"):
            reference = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"status": True, "data": {
                "reference": reference, "amount": 750000,
                "currency": "NGN", "status": "success",
            }})
        return httpx.Response(404, json={"status": False, "message": "not found"})

    provider = PaystackProvider("sk_test_secret", transport=httpx.MockTransport(handler))
    checkout = await provider.initialize_payment(
        reference="tutova-payment-123", amount_minor=750000,
        currency="NGN", email="learner@example.com",
    )
    assert checkout == "https://checkout.paystack.com/test"

    verified = await provider.verify_payment(provider_reference=seen["reference"])
    assert verified.status == "SUCCESS"
    assert verified.amount_minor == 750000
    assert verified.currency == "NGN"


def test_paystack_webhook_signature_and_event_parsing():
    secret = "sk_test_secret"
    provider = PaystackProvider(secret)
    body = json.dumps(
        {"event": "charge.success", "data": {"reference": "tutova-payment-123"}},
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()

    assert provider.verify_webhook_signature(raw_body=body, signature=signature)
    event = provider.parse_webhook(raw_body=body)
    assert event.event_type == "charge.success"
    assert event.provider_reference == "tutova-payment-123"
    assert not provider.verify_webhook_signature(raw_body=body, signature="invalid")
