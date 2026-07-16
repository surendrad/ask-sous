"""Seed orchestration: truncate, generate, bulk-insert, summarize.

Contains no statistical/pattern logic — that all lives in generators.py, so
this file stays a thin, obviously-correct orchestrator. Run via:

    python -m app.seed.seed
"""

import asyncio

from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Campaign, MenuItem, Restaurant, Review, Transaction, TransactionItem
from app.db.session import async_session_maker
from app.seed.generators import (
    FIXED_SEED,
    RESTAURANT_PROFILES,
    attribute_transactions_to_campaigns,
    generate_campaigns,
    generate_menu_items,
    generate_reviews,
    generate_transactions_and_items,
    make_rng_and_faker,
    rng_uuid,
)

TABLES_IN_TRUNCATE_ORDER = [
    "transaction_items",
    "transactions",
    "reviews",
    "campaigns",
    "menu_items",
    "restaurants",
]


async def _truncate_all(session: AsyncSession) -> None:
    tables = ", ".join(TABLES_IN_TRUNCATE_ORDER)
    await session.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


async def seed_database(session: AsyncSession) -> dict[str, int]:
    await _truncate_all(session)

    rng, faker = make_rng_and_faker(FIXED_SEED)

    all_restaurants: list[dict] = []
    all_menu_items: list[dict] = []
    all_transactions: list[dict] = []
    all_transaction_items: list[dict] = []
    all_reviews: list[dict] = []
    all_campaigns: list[dict] = []

    for profile in RESTAURANT_PROFILES:
        restaurant_id = rng_uuid(rng)
        all_restaurants.append(
            {
                "id": restaurant_id,
                "name": profile["name"],
                "cuisine": profile["cuisine"],
                "city": profile["city"],
                "region": profile["region"],
                "size_category": profile["size_category"],
                "brand_voice_guide": profile["brand_voice_guide"],
            }
        )

        menu_items = generate_menu_items(rng, restaurant_id, profile["name"])
        all_menu_items.extend(menu_items)

        transactions, transaction_items = generate_transactions_and_items(
            rng, restaurant_id, profile["name"], profile["size_category"], menu_items
        )
        campaigns = generate_campaigns(
            rng, faker, restaurant_id, profile["name"], profile["cuisine"], menu_items
        )
        # Attribution needs both this restaurant's transactions and
        # campaigns to already exist, so it runs after both are generated.
        transactions = attribute_transactions_to_campaigns(rng, transactions, campaigns)

        all_transactions.extend(transactions)
        all_transaction_items.extend(transaction_items)
        all_campaigns.extend(campaigns)
        all_reviews.extend(
            generate_reviews(rng, faker, restaurant_id, profile["cuisine"], menu_items)
        )

    # Bulk Core-level inserts — at ~30-40k transaction rows, per-row ORM
    # flushes would be far too slow. Campaigns must be inserted before
    # transactions now that transactions.campaign_id FKs into campaigns.
    await session.execute(insert(Restaurant.__table__), all_restaurants)
    await session.execute(insert(MenuItem.__table__), all_menu_items)
    await session.execute(insert(Campaign.__table__), all_campaigns)
    await session.execute(insert(Transaction.__table__), all_transactions)
    await session.execute(insert(TransactionItem.__table__), all_transaction_items)
    await session.execute(insert(Review.__table__), all_reviews)
    await session.commit()

    return {
        "restaurants": len(all_restaurants),
        "menu_items": len(all_menu_items),
        "transactions": len(all_transactions),
        "transaction_items": len(all_transaction_items),
        "reviews": len(all_reviews),
        "campaigns": len(all_campaigns),
    }


async def main() -> None:
    async with async_session_maker() as session:
        summary = await seed_database(session)
    print("Seed complete:")
    for table, count in summary.items():
        print(f"  {table}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
