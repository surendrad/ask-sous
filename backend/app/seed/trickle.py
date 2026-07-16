"""Live-trickle background generator (Phase 7, post-MVP polish) — inserts a
trickle of new transactions on a timer so a demo doesn't look frozen in
time. Deliberately does **not** reuse generators.py's deterministic seeded
RNG: this module uses genuine `uuid.uuid4()`/`random` module randomness,
since it exists specifically to simulate non-deterministic ongoing
activity, unlike the reproducible seed data (see
docs/decisions/004-seed-data-determinism-and-patterns.md).

Writes go through the same privileged session path seed.py uses, not
`readonly_connection()` — the read-only boundary is specific to agent tool
code (app/agent/), not the whole app, and this is a normal app-level write.
"""

import asyncio
import random
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import MenuItem, Restaurant, Transaction, TransactionItem
from app.db.session import async_session_maker as default_session_maker
from app.seed.generators import CHANNEL_CHOICES, PAYMENT_CHOICES, QUANTITY_CHOICES

logger = structlog.get_logger()

DEFAULT_INTERVAL_SECONDS = 30.0


async def insert_trickle_transaction(
    session: AsyncSession, restaurant: Restaurant, menu_items: list[MenuItem]
) -> None:
    if not menu_items:
        return

    num_items = random.randint(1, min(3, len(menu_items)))
    selected = random.sample(menu_items, k=num_items)
    line_items = [(item, random.choice(QUANTITY_CHOICES)) for item in selected]
    total_amount = sum((Decimal(qty) * item.price for item, qty in line_items), Decimal("0"))

    transaction = Transaction(
        id=uuid.uuid4(),
        restaurant_id=restaurant.id,
        transaction_time=datetime.now(UTC),
        total_amount=total_amount,
        payment_type=random.choice(PAYMENT_CHOICES),
        channel=random.choice(CHANNEL_CHOICES),
    )
    session.add(transaction)
    for item, qty in line_items:
        session.add(
            TransactionItem(
                id=uuid.uuid4(),
                transaction_id=transaction.id,
                menu_item_id=item.id,
                quantity=qty,
                unit_price=item.price,
            )
        )


async def _tick(session_maker: async_sessionmaker[AsyncSession]) -> None:
    async with session_maker() as session:
        restaurants = (await session.execute(select(Restaurant))).scalars().all()
        if not restaurants:
            return
        restaurant = random.choice(restaurants)
        menu_items = (
            (await session.execute(select(MenuItem).where(MenuItem.restaurant_id == restaurant.id)))
            .scalars()
            .all()
        )
        await insert_trickle_transaction(session, restaurant, list(menu_items))
        await session.commit()


async def run_trickle_loop(
    *,
    session_maker: async_sessionmaker[AsyncSession] | None = None,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
) -> None:
    """Runs until cancelled — no manual on-demand trigger, per
    implementation-plan.md 7.1's agreed testability approach. Callers
    (tests, main.py's lifespan) drive lifetime via task cancellation."""
    maker = session_maker or default_session_maker
    while True:
        try:
            await _tick(maker)
        except Exception as exc:  # noqa: BLE001 - one bad tick must not permanently kill
            # the background loop for the rest of the process's life (the
            # default asyncio behavior for an unhandled task exception is a
            # silent "Task exception was never retrieved" on stderr) —
            # logged and retried on the next tick instead.
            logger.warning("trickle_tick_failed", exc_info=exc)
        await asyncio.sleep(interval_seconds)
