"""
Provider-neutral contracts for payment collection and tutor payouts.

Concrete Paystack/Flutterwave adapters must implement these contracts and be
registered explicitly. The core application deliberately has no fake live
provider and fails closed when no adapter is configured.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderPayment:
    provider: str
    provider_reference: str
    amount_minor: int
    currency: str
    status: str


@dataclass(frozen=True)
class ProviderPayout:
    provider: str
    provider_reference: str
    amount_minor: int
    currency: str
    status: str
    transfer_code: str | None = None


@dataclass(frozen=True)
class ProviderWebhookEvent:
    provider_reference: str
    event_type: str


class PaymentProvider(Protocol):
    name: str

    async def initialize_payment(
        self, *, reference: str, amount_minor: int, currency: str, email: str
    ) -> str: ...
    async def verify_payment(self, *, provider_reference: str) -> ProviderPayment: ...
    def verify_webhook_signature(self, *, raw_body: bytes, signature: str) -> bool: ...
    def parse_webhook(self, *, raw_body: bytes) -> ProviderWebhookEvent: ...
    async def initiate_payout(
        self,
        *,
        reference: str,
        amount_minor: int,
        currency: str,
        destination_token: str,
    ) -> ProviderPayout: ...
    async def verify_payout(self, *, provider_reference: str) -> ProviderPayout: ...


class _PaymentProviderRegistry:
    def __init__(self) -> None:
        self._provider: PaymentProvider | None = None

    def register(self, provider: PaymentProvider | None) -> None:
        self._provider = provider

    def get(self) -> PaymentProvider:
        provider = self._provider
        if provider is None:
            raise RuntimeError(
                "No payment provider adapter is configured. Select and configure a provider before enabling checkout or payouts."
            )
        return provider


_provider_registry = _PaymentProviderRegistry()


def register_payment_provider(provider: PaymentProvider | None) -> None:
    """Register the selected concrete adapter during application startup/tests."""
    _provider_registry.register(provider)


def get_payment_provider() -> PaymentProvider:
    return _provider_registry.get()
