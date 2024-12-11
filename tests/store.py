import pytest
from aiojobs import Scheduler
from pytest_assume.plugin import assume

from app.helpers.config import CONFIG
from app.models.call import CallStateModel


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.repeat(10)  # Catch multi-threading and concurrency issues
async def test_acid(call: CallStateModel) -> None:
    """
    Test ACID properties of the database backend.

    Steps:
    1. Create a mock data
    2. Test not exists
    3. Insert test data
    4. Check it exists

    Test is repeated 10 times to catch multi-threading and concurrency issues.
    """
    db = CONFIG.database.instance()

    async with Scheduler() as scheduler:
        # Check not exists
        assume(
            not await db.call_get(
                call_id=call.call_id,
                scheduler=scheduler,
            )
        )
        assume(
            await db.call_search_one(
                phone_number=call.initiate.phone_number,
                scheduler=scheduler,
            )
            != call
        )
        assume(
            call
            not in (
                (
                    await db.call_search_all(
                        phone_number=call.initiate.phone_number, count=1
                    )
                )[0]
                or []
            )
        )

        # Insert test call
        await db.call_create(
            call=call,
            scheduler=scheduler,
        )

        # Check point read
        assume(
            await db.call_get(
                call_id=call.call_id,
                scheduler=scheduler,
            )
            == call
        )
        # Check search one
        assume(
            await db.call_search_one(
                phone_number=call.initiate.phone_number,
                scheduler=scheduler,
            )
            == call
        )
        # Check search all
        assume(
            call
            in (
                (
                    await db.call_search_all(
                        phone_number=call.initiate.phone_number, count=1
                    )
                )[0]
                or []
            )
        )


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.repeat(10)  # Catch multi-threading and concurrency issues
async def test_transaction(
    call: CallStateModel,
    random_text: str,
) -> None:
    """
    Test transactional properties of the database backend.
    """
    db = CONFIG.database.instance()

    async with Scheduler() as scheduler:
        # Check not exists
        assume(
            not await db.call_get(
                call_id=call.call_id,
                scheduler=scheduler,
            )
        )

        # Insert call
        await db.call_create(
            call=call,
            scheduler=scheduler,
        )

        # Check first change
        async with db.call_transac(
            call=call,
            scheduler=scheduler,
        ):
            # Apply change
            call.voice_id = random_text
        # Check change
        assume(call.voice_id == random_text)

        # Check second change
        async with db.call_transac(
            call=call,
            scheduler=scheduler,
        ):
            # Still the same
            assume(call.voice_id == random_text)
            # Apply change
            call.in_progress = True
        # Check change
        assume(call.in_progress)

        # Check first string change
        assume(call.voice_id == random_text)

        # Check point read
        new_call = await db.call_get(
            call_id=call.call_id,
            scheduler=scheduler,
        )
        assume(new_call and new_call.voice_id == random_text and new_call.in_progress)
