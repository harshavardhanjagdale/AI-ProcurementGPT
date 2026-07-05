"""
Negotiation Service - Manages multi-round price negotiations with suppliers.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.negotiation import Negotiation
from app.repositories.negotiation_repository import NegotiationRepository
from app.repositories.quotation_repository import QuotationRepository
from app.repositories.rfq_repository import RFQRepository
from app.repositories.supplier_repository import SupplierRepository
from app.services.email_service import EmailService
from app.ai.llm_client import llm_client

logger = logging.getLogger(__name__)

MAX_ROUNDS = 3


class NegotiationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.neg_repo = NegotiationRepository(db)
        self.quotation_repo = QuotationRepository(db)
        self.rfq_repo = RFQRepository(db)
        self.supplier_repo = SupplierRepository(db)

    async def initiate_negotiation(
        self,
        rfq_id: str,
        supplier_id: str,
        quotation_id: str,
        target_price: float,
        notes: str | None = None,
    ) -> Negotiation:
        """Start a new negotiation round with a supplier."""
        quotation = await self.quotation_repo.get_by_id(quotation_id)
        if not quotation:
            raise NotFoundError("Quotation", quotation_id)

        current_round = await self.neg_repo.get_latest_round(rfq_id, supplier_id)
        if current_round >= MAX_ROUNDS:
            raise ValidationError(f"Maximum {MAX_ROUNDS} negotiation rounds reached")

        new_round = current_round + 1

        # Generate AI negotiation strategy
        strategy = await self._generate_strategy(
            quotation=quotation,
            target_price=target_price,
            round_number=new_round,
        )

        negotiation = Negotiation(
            rfq_id=rfq_id,
            supplier_id=supplier_id,
            quotation_id=quotation_id,
            round_number=new_round,
            original_price=float(quotation.total_amount),
            target_price=target_price,
            status="pending",
            ai_strategy_notes=strategy,
            notes=notes,
        )
        negotiation = await self.neg_repo.create(negotiation)

        # Generate and send negotiation email
        supplier = await self.supplier_repo.get_by_id(supplier_id)
        rfq = await self.rfq_repo.get_by_id(rfq_id)

        negotiation_message = await self._generate_negotiation_message(
            supplier_name=supplier.name if supplier else "Supplier",
            original_price=float(quotation.total_amount),
            target_price=target_price,
            currency=quotation.currency,
            round_number=new_round,
            product=rfq.title if rfq else "procurement items",
        )

        email_service = EmailService(self.db)
        email_result = await email_service.send_negotiation_email(
            rfq_id=rfq_id,
            supplier_id=supplier_id,
            round_number=new_round,
            original_price=float(quotation.total_amount),
            target_price=target_price,
            negotiation_message=negotiation_message,
            sender_name="Procurement Team",
        )

        if email_result["success"]:
            await self.neg_repo.update_by_id(negotiation.id, {
                "status": "sent",
                "email_id": email_result.get("email_id"),
            })

        # Update RFQ status
        await self.rfq_repo.update_by_id(rfq_id, {"status": "negotiation"})

        await self.db.flush()
        return negotiation

    async def accept_counter_offer(
        self,
        negotiation_id: str,
        negotiated_price: float,
    ) -> Negotiation:
        """Accept a supplier's counter-offer."""
        negotiation = await self.neg_repo.get_by_id(negotiation_id)
        if not negotiation:
            raise NotFoundError("Negotiation", negotiation_id)

        await self.neg_repo.update_by_id(negotiation_id, {
            "status": "accepted",
            "negotiated_price": negotiated_price,
        })

        # Update quotation with new price
        await self.quotation_repo.update_by_id(
            negotiation.quotation_id,
            {"total_amount": negotiated_price, "status": "shortlisted"},
        )

        return await self.neg_repo.get_by_id(negotiation_id)

    async def reject_counter_offer(self, negotiation_id: str) -> Negotiation:
        """Reject a counter-offer (may trigger another round or end)."""
        negotiation = await self.neg_repo.get_by_id(negotiation_id)
        if not negotiation:
            raise NotFoundError("Negotiation", negotiation_id)

        await self.neg_repo.update_by_id(negotiation_id, {"status": "rejected"})
        return await self.neg_repo.get_by_id(negotiation_id)

    async def get_rfq_negotiations(self, rfq_id: str) -> list[Negotiation]:
        return await self.neg_repo.get_by_rfq(rfq_id)

    async def get_negotiation(self, negotiation_id: str) -> Negotiation:
        negotiation = await self.neg_repo.get_by_id(negotiation_id)
        if not negotiation:
            raise NotFoundError("Negotiation", negotiation_id)
        return negotiation

    async def _generate_strategy(
        self, quotation, target_price: float, round_number: int
    ) -> str:
        """Generate AI negotiation strategy notes."""
        discount_pct = ((float(quotation.total_amount) - target_price) / float(quotation.total_amount)) * 100

        prompt = (
            f"Suggest a negotiation strategy for round {round_number}.\n"
            f"Current quote: {quotation.currency} {float(quotation.total_amount):,.2f}\n"
            f"Target: {quotation.currency} {target_price:,.2f} ({discount_pct:.1f}% reduction)\n"
            f"Provide 2-3 bullet points of strategy."
        )

        try:
            return await llm_client.generate(
                system_prompt="You are a procurement negotiation strategist. Be concise.",
                user_prompt=prompt,
                max_tokens=300,
            )
        except Exception:
            return f"Target {discount_pct:.1f}% reduction. Round {round_number} of {MAX_ROUNDS}."

    async def _generate_negotiation_message(
        self,
        supplier_name: str,
        original_price: float,
        target_price: float,
        currency: str,
        round_number: int,
        product: str,
    ) -> str:
        """Generate the negotiation email message using AI."""
        prompt = (
            f"Write a negotiation message to {supplier_name} for {product}.\n"
            f"Their price: {currency} {original_price:,.2f}\n"
            f"Our target: {currency} {target_price:,.2f}\n"
            f"Round: {round_number}\n"
            f"Be professional, firm but respectful. 2-3 paragraphs."
        )

        try:
            return await llm_client.generate(
                system_prompt="You are a skilled procurement negotiator writing an email.",
                user_prompt=prompt,
                max_tokens=500,
            )
        except Exception:
            return (
                f"We appreciate your quotation of {currency} {original_price:,.2f}. "
                f"However, based on our budget and market research, we'd like to request "
                f"a revised price of {currency} {target_price:,.2f}. "
                f"We value our partnership and hope to reach a mutually beneficial agreement."
            )
