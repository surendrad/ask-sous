import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError

EXPECTED_TABLES = [
    "restaurants",
    "menu_items",
    "transactions",
    "transaction_items",
    "reviews",
    "campaigns",
]


async def test_all_tables_exist(admin_engine):
    async with admin_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = ANY(:names)"
            ),
            {"names": EXPECTED_TABLES},
        )
        found = {row[0] for row in result}
    assert found == set(EXPECTED_TABLES)


async def test_key_column_types(admin_engine):
    async with admin_engine.connect() as conn:

        async def column_type(table: str, column: str) -> tuple[str, str]:
            result = await conn.execute(
                text(
                    "SELECT data_type, is_nullable FROM information_schema.columns "
                    "WHERE table_name = :table AND column_name = :column"
                ),
                {"table": table, "column": column},
            )
            row = result.one()
            return row[0], row[1]

        assert (await column_type("restaurants", "id"))[0] == "uuid"
        assert (await column_type("menu_items", "restaurant_id"))[0] == "uuid"
        assert (await column_type("menu_items", "price"))[0] == "numeric"
        assert (await column_type("transactions", "total_amount"))[0] == "numeric"
        assert (await column_type("transaction_items", "unit_price"))[0] == "numeric"
        assert (await column_type("campaigns", "conversion_rate"))[0] == "numeric"
        assert (await column_type("campaigns", "revenue_lift"))[0] == "numeric"

        embedding_type, embedding_nullable = await column_type("reviews", "embedding")
        assert embedding_type == "USER-DEFINED"
        assert embedding_nullable == "YES"

        campaign_embedding_type, campaign_embedding_nullable = await column_type(
            "campaigns", "embedding"
        )
        assert campaign_embedding_type == "USER-DEFINED"
        assert campaign_embedding_nullable == "YES"


async def test_smoke_insert_one_row_per_table_in_dependency_order(admin_engine):
    restaurant_id = uuid.uuid4()
    menu_item_id = uuid.uuid4()
    transaction_id = uuid.uuid4()

    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO restaurants "
                "(id, name, cuisine, city, region, size_category, brand_voice_guide) "
                "VALUES (:id, 'Test Kitchen', 'Test', 'Testville', 'Test', 'small', 'Warm.')"
            ),
            {"id": restaurant_id},
        )
        await conn.execute(
            text(
                "INSERT INTO menu_items (id, restaurant_id, name, category, price) "
                "VALUES (:id, :restaurant_id, 'Test Dish', 'entree', 12.50)"
            ),
            {"id": menu_item_id, "restaurant_id": restaurant_id},
        )
        await conn.execute(
            text(
                "INSERT INTO transactions "
                "(id, restaurant_id, transaction_time, total_amount, payment_type, channel) "
                "VALUES (:id, :restaurant_id, now(), 12.50, 'cash', 'dine-in')"
            ),
            {"id": transaction_id, "restaurant_id": restaurant_id},
        )
        await conn.execute(
            text(
                "INSERT INTO transaction_items "
                "(id, transaction_id, menu_item_id, quantity, unit_price) "
                "VALUES (:id, :transaction_id, :menu_item_id, 1, 12.50)"
            ),
            {
                "id": uuid.uuid4(),
                "transaction_id": transaction_id,
                "menu_item_id": menu_item_id,
            },
        )
        await conn.execute(
            text(
                "INSERT INTO reviews (id, restaurant_id, rating, review_text, source) "
                "VALUES (:id, :restaurant_id, 5, 'Great!', 'google')"
            ),
            {"id": uuid.uuid4(), "restaurant_id": restaurant_id},
        )
        await conn.execute(
            text(
                "INSERT INTO campaigns (id, restaurant_id, name, channel, copy_text) "
                "VALUES (:id, :restaurant_id, 'Test Campaign', 'sms', 'Come eat!')"
            ),
            {"id": uuid.uuid4(), "restaurant_id": restaurant_id},
        )

    try:
        async with admin_engine.connect() as conn:
            for table in EXPECTED_TABLES:
                result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                assert result.scalar() >= 1

        with pytest.raises((IntegrityError, ProgrammingError)):
            async with admin_engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO menu_items (id, restaurant_id, name, category, price) "
                        "VALUES (:id, :bad_restaurant_id, 'Orphan Dish', 'entree', 5.00)"
                    ),
                    {"id": uuid.uuid4(), "bad_restaurant_id": uuid.uuid4()},
                )
    finally:
        async with admin_engine.begin() as conn:
            await conn.execute(text("DELETE FROM transaction_items"))
            await conn.execute(text("DELETE FROM transactions"))
            await conn.execute(text("DELETE FROM reviews"))
            await conn.execute(text("DELETE FROM campaigns"))
            await conn.execute(text("DELETE FROM menu_items"))
            await conn.execute(text("DELETE FROM restaurants"))


@pytest.mark.parametrize("table", EXPECTED_TABLES)
async def test_readonly_role_can_select_from_every_table(readonly_engine, table):
    async with readonly_engine.connect() as conn:
        result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
        assert result.scalar() is not None


async def test_readonly_role_cannot_insert_into_restaurants(readonly_engine):
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError, match="permission denied|InsufficientPrivilege"):
        async with readonly_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO restaurants "
                    "(id, name, cuisine, city, region, size_category, brand_voice_guide) "
                    "VALUES (gen_random_uuid(), 'x', 'x', 'x', 'x', 'small', 'x')"
                )
            )


async def test_menu_items_is_upsell_column(admin_engine):
    async with admin_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT data_type, is_nullable, column_default FROM information_schema.columns "
                "WHERE table_name = 'menu_items' AND column_name = 'is_upsell'"
            )
        )
        data_type, is_nullable, column_default = result.one()
    assert data_type == "boolean"
    assert is_nullable == "NO"
    assert column_default is not None


async def test_transactions_campaign_id_column(admin_engine):
    async with admin_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT data_type, is_nullable FROM information_schema.columns "
                "WHERE table_name = 'transactions' AND column_name = 'campaign_id'"
            )
        )
        data_type, is_nullable = result.one()
    assert data_type == "uuid"
    assert is_nullable == "YES"


async def test_transactions_campaign_id_foreign_key_set_null_on_delete(admin_engine):
    async with admin_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT confdeltype FROM pg_constraint "
                "WHERE conname = 'fk_transactions_campaign_id_campaigns'"
            )
        )
        (confdeltype,) = result.one()
    assert confdeltype == b"n"  # 'n' = SET NULL
