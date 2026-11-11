import asyncio

from app.core.database import AsyncSessionLocal
from app.domain.session_bookings.services.acknowledgement_workflow_service import (
    AcknowledgementWorkflowService,
)


async def main():
    async with AsyncSessionLocal() as db:
        result = await AcknowledgementWorkflowService(db).process_deadlines()

        print(result)


if __name__ == "__main__":
    asyncio.run(main())
