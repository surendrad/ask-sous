"""Proves each CHECK constraint actually rejects an out-of-range value —
the defense-in-depth layer docs/plans/phase-1-data-layer.md calls out
against a future direct-SQL bug, not exercised by the FK-focused smoke test
in test_schema_migration.py.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


@pytest_asyncio.fixture
async def restaurant_id(admin_engine):
    rid = uuid.uuid4()
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO restaurants "
                "(id, name, cuisine, city, region, size_category, brand_voice_guide) "
                "VALUES (:id, 'Constraint Test', 'Test', 'Testville', 'Test', 'small', 'Warm.')"
            ),
            {"id": rid},
        )
    yield rid
    async with admin_engine.begin() as conn:
        await conn.execute(text("DELETE FROM restaurants WHERE id = :id"), {"id": rid})


async def test_restaurants_size_category_rejects_invalid_value(admin_engine):
    with pytest.raises(IntegrityError, match="ck_restaurants_size_category"):
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO restaurants "
                    "(id, name, cuisine, city, region, size_category, brand_voice_guide) "
                    "VALUES (gen_random_uuid(), 'x', 'x', 'x', 'x', 'huge', 'x')"
                )
            )


async def test_transactions_payment_type_rejects_invalid_value(admin_engine, restaurant_id):
    with pytest.raises(IntegrityError, match="ck_transactions_payment_type"):
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO transactions "
                    "(id, restaurant_id, transaction_time, total_amount, payment_type, channel) "
                    "VALUES (gen_random_uuid(), :rid, now(), 10.00, 'bitcoin', 'dine-in')"
                ),
                {"rid": restaurant_id},
            )


async def test_transactions_channel_rejects_invalid_value(admin_engine, restaurant_id):
    with pytest.raises(IntegrityError, match="ck_transactions_channel"):
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO transactions "
                    "(id, restaurant_id, transaction_time, total_amount, payment_type, channel) "
                    "VALUES (gen_random_uuid(), :rid, now(), 10.00, 'cash', 'teleport')"
                ),
                {"rid": restaurant_id},
            )


async def test_transaction_items_quantity_rejects_non_positive_value(admin_engine, restaurant_id):
    async with admin_engine.begin() as conn:
        tx_id = uuid.uuid4()
        menu_item_id = uuid.uuid4()
        await conn.execute(
            text(
                "INSERT INTO menu_items (id, restaurant_id, name, category, price) "
                "VALUES (:id, :rid, 'Test Dish', 'entree', 10.00)"
            ),
            {"id": menu_item_id, "rid": restaurant_id},
        )
        await conn.execute(
            text(
                "INSERT INTO transactions "
                "(id, restaurant_id, transaction_time, total_amount, payment_type, channel) "
                "VALUES (:id, :rid, now(), 10.00, 'cash', 'dine-in')"
            ),
            {"id": tx_id, "rid": restaurant_id},
        )

    try:
        with pytest.raises(IntegrityError, match="ck_transaction_items_quantity"):
            async with admin_engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO transaction_items "
                        "(id, transaction_id, menu_item_id, quantity, unit_price) "
                        "VALUES (gen_random_uuid(), :tx_id, :menu_item_id, 0, 10.00)"
                    ),
                    {"tx_id": tx_id, "menu_item_id": menu_item_id},
                )
    finally:
        async with admin_engine.begin() as conn:
            await conn.execute(text("DELETE FROM transactions WHERE id = :id"), {"id": tx_id})
            await conn.execute(text("DELETE FROM menu_items WHERE id = :id"), {"id": menu_item_id})


async def test_reviews_rating_rejects_out_of_range_value(admin_engine, restaurant_id):
    with pytest.raises(IntegrityError, match="ck_reviews_rating"):
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO reviews (id, restaurant_id, rating, review_text, source) "
                    "VALUES (gen_random_uuid(), :rid, 6, 'Too many stars', 'google')"
                ),
                {"rid": restaurant_id},
            )


async def test_reviews_source_rejects_invalid_value(admin_engine, restaurant_id):
    with pytest.raises(IntegrityError, match="ck_reviews_source"):
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO reviews (id, restaurant_id, rating, review_text, source) "
                    "VALUES (gen_random_uuid(), :rid, 5, 'Great!', 'carrier_pigeon')"
                ),
                {"rid": restaurant_id},
            )


async def test_campaigns_channel_rejects_invalid_value(admin_engine, restaurant_id):
    with pytest.raises(IntegrityError, match="ck_campaigns_channel"):
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO campaigns (id, restaurant_id, name, channel, copy_text) "
                    "VALUES "
                    "(gen_random_uuid(), :rid, 'Test Campaign', 'carrier_pigeon', 'Come eat!')"
                ),
                {"rid": restaurant_id},
            )
