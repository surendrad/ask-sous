import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.db.models import MenuItem, Restaurant, Transaction
from app.seed.trickle import insert_trickle_transaction, run_trickle_loop


async def _menu_items_for(session, restaurant_id: uuid.UUID) -> list[MenuItem]:
    result = await session.execute(select(MenuItem).where(MenuItem.restaurant_id == restaurant_id))
    return list(result.scalars().all())


async def _transaction_count(session, restaurant_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.restaurant_id == restaurant_id)
    )
    return result.scalar_one()


async def test_insert_trickle_transaction_inserts_one_transaction_near_now(
    admin_engine, seeded_restaurants
):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_maker = async_sessionmaker(admin_engine, expire_on_commit=False)
    restaurant_id = seeded_restaurants["Golden Skillet"]

    async with session_maker() as session:
        restaurant = await session.get(Restaurant, restaurant_id)
        menu_items = await _menu_items_for(session, restaurant_id)
        before = await _transaction_count(session, restaurant_id)

        await insert_trickle_transaction(session, restaurant, menu_items)
        await session.commit()

        after = await _transaction_count(session, restaurant_id)
        assert after == before + 1

        result = await session.execute(
            select(Transaction)
            .where(Transaction.restaurant_id == restaurant_id)
            .order_by(Transaction.transaction_time.desc())
            .limit(1)
        )
        newest = result.scalar_one()
        assert datetime.now(UTC) - newest.transaction_time < timedelta(seconds=10)
        assert isinstance(newest.id, uuid.UUID)


async def test_run_trickle_loop_inserts_rows_over_a_short_run(admin_engine, seeded_restaurants):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_maker = async_sessionmaker(admin_engine, expire_on_commit=False)

    async def total_transactions() -> int:
        async with session_maker() as session:
            result = await session.execute(select(func.count()).select_from(Transaction))
            return result.scalar_one()

    before = await total_transactions()

    task = asyncio.create_task(run_trickle_loop(session_maker=session_maker, interval_seconds=0.05))
    await asyncio.sleep(0.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    after = await total_transactions()
    assert after > before
