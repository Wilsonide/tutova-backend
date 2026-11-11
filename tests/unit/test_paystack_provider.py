import hashlib
import hmac
import json

import httpx
import pytest

from app.domain.payments.paystack import PaystackProvider


@pytest.mark.asyncio
async def test_initialize_payment_uses_kobo_and_returns_checkout_url():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": True, "message": "Success", "data": {
            "authorization_url": "https://checkout.paystack.com/example",
            "reference": "tutova_attempt-1",
        }})

    provider = PaystackProvider("sk_test_secret", transport=httpx.MockTransport(handler))
    checkout_url = await provider.initialize_payment(
        reference="tutova_attempt-1", amount_minor=600000, currency="NGN", email="parent@example.com"
    )

    assert checkout_url == "https://checkout.paystack.com/example"
    assert captured["url"].endswith("/transaction/initialize")
    assert captured["body"]["amount"] == 600000
    assert captured["body"]["currency"] == "NGN"
    assert captured["body"]["reference"] == "tutova_attempt-1"


@pytest.mark.asyncio
async def test_verify_payment_normalizes_success_and_checks_reference():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/transaction/verify/ref-123")
        return httpx.Response(200, json={"status": True, "data": {
            "reference": "ref-123", "amount": 600000, "currency": "NGN", "status": "success"
        }})

    provider = PaystackProvider("sk_test_secret", transport=httpx.MockTransport(handler))
    payment = await provider.verify_payment(provider_reference="ref-123")
    assert payment.provider == "PAYSTACK"
    assert payment.provider_reference == "ref-123"
    assert payment.amount_minor == 600000
    assert payment.currency == "NGN"
    assert payment.status == "SUCCESS"


def test_paystack_signature_validation_and_webhook_parsing():
    secret = "sk_test_webhook_secret"
    provider = PaystackProvider(secret)
    body = json.dumps({"event": "charge.success", "data": {"reference": "ref-123"}}).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()

    assert provider.verify_webhook_signature(raw_body=body, signature=signature)
    assert not provider.verify_webhook_signature(raw_body=body, signature="bad-signature")
    event = provider.parse_webhook(raw_body=body)
    assert event.event_type == "charge.success"
    assert event.provider_reference == "ref-123"


def test_paystack_webhook_rejects_invalid_payload():
    provider = PaystackProvider("sk_test_secret")
    with pytest.raises(ValueError):
        provider.parse_webhook(raw_body=b'{"event":"charge.success","data":{}}')


@pytest.mark.asyncio
async def test_paystack_rejects_amount_zero_and_mismatched_reference():
    provider = PaystackProvider("sk_test_secret")
    with pytest.raises(ValueError, match="positive"):
        await provider.initialize_payment(reference="r", amount_minor=0, currency="NGN", email="p@example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": True, "data": {
            "reference": "other-ref", "amount": 600000, "currency": "NGN", "status": "success"
        }})
    provider = PaystackProvider("sk_test_secret", transport=httpx.MockTransport(handler))
    from app.domain.payments.paystack import PaystackError
    with pytest.raises(PaystackError, match="reference"):
        await provider.verify_payment(provider_reference="expected-ref")


@pytest.mark.asyncio
async def test_create_transfer_recipient_returns_maskable_recipient_details():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/transferrecipient")
        body = json.loads(request.content)
        assert body["type"] == "nuban"
        assert body["account_number"] == "0123456789"
        assert body["bank_code"] == "058"
        return httpx.Response(200, json={"status": True, "data": {
            "recipient_code": "RCP_test123",
            "name": "Test Tutor",
            "details": {"account_name": "Test Tutor", "account_number": "0123456789", "bank_name": "GTBank"}
        }})
    provider = PaystackProvider("sk_test_secret", transport=httpx.MockTransport(handler))
    result = await provider.create_transfer_recipient(
        name="Test Tutor", account_number="0123456789", bank_code="058"
    )
    assert result["recipient_code"] == "RCP_test123"
    assert result["bank_name"] == "GTBank"
    assert result["account_number"].endswith("6789")


@pytest.mark.asyncio
async def test_initiate_refund_uses_kobo_and_reference():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/refund")
        body = json.loads(request.content)
        assert body["transaction"] == "payment-ref"
        assert body["amount"] == 250000
        assert body["reference"] == "tutova-refund-12345678"
        return httpx.Response(200, json={"status": True, "data": {
            "reference": "tutova-refund-12345678", "status": "pending"
        }})
    provider = PaystackProvider("sk_test_secret", transport=httpx.MockTransport(handler))
    result = await provider.initiate_refund(
        transaction_reference="payment-ref", reference="tutova-refund-12345678",
        amount_minor=250000, currency="NGN", reason="Lesson cancelled"
    )
    assert result["status"] == "PENDING"


@pytest.mark.asyncio
async def test_finalize_transfer_uses_transfer_code_and_otp():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/transfer/finalize_transfer")
        body = json.loads(request.content)
        assert body == {"transfer_code": "TRF_test123", "otp": "123456"}
        return httpx.Response(200, json={"status": True, "data": {
            "reference": "tutova-payout-1234567890", "amount": 150000,
            "currency": "NGN", "status": "pending", "transfer_code": "TRF_test123"
        }})
    provider = PaystackProvider("sk_test_secret", transport=httpx.MockTransport(handler))
    result = await provider.finalize_payout(transfer_code="TRF_test123", otp="123456")
    assert result.provider_reference == "tutova-payout-1234567890"
    assert result.transfer_code == "TRF_test123"
    assert result.status == "PENDING"
