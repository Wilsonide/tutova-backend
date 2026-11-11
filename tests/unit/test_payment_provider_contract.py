import pytest
from app.domain.payments.provider import get_payment_provider, register_payment_provider


def test_provider_registry_fails_closed_without_selected_adapter():
    register_payment_provider(None)
    with pytest.raises(RuntimeError, match="No payment provider adapter is configured"):
        get_payment_provider()


def test_provider_registry_requires_explicit_adapter_registration():
    class TestProvider:
        name = "TEST"
        async def initialize_payment(self, **kwargs): return "https://checkout.invalid"
        async def verify_payment(self, **kwargs): raise NotImplementedError
        def verify_webhook_signature(self, **kwargs): return False
        def parse_webhook(self, **kwargs): raise NotImplementedError
        async def initiate_payout(self, **kwargs): raise NotImplementedError
        async def verify_payout(self, **kwargs): raise NotImplementedError
    provider = TestProvider()
    register_payment_provider(provider)
    try:
        assert get_payment_provider() is provider
    finally:
        register_payment_provider(None)
