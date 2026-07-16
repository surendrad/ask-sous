from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.seed.seed import seed_database

# Expected transaction-count range, computed from generators.py's baseline math:
# sum over restaurants of 90 days * base_count[size] * avg(dow_multiplier) * noise.
# base_count: medium=75 (x3 restaurants incl. Golden Skillet's Tuesday dip),
# small=45 (x1), large=115 (x1). avg(dow_multiplier) ~= 1.065.
# Lower bound accounts for Golden Skillet's Tuesday suppression; upper bound
# gives headroom for the +12% Gaussian noise ceiling.
EXPECTED_TRANSACTION_COUNT_RANGE = (26000, 38000)


@pytest.fixture
async def seeded_session(admin_engine: AsyncEngine) -> AsyncSession:
    session_maker = async_sessionmaker(admin_engine, expire_on_commit=False)
    async with session_maker() as session:
        await seed_database(session)
        yield session


async def test_seed_produces_five_restaurants(seeded_session):
    result = await seeded_session.execute(text("SELECT COUNT(*) FROM restaurants"))
    assert result.scalar() == 5


async def test_every_restaurant_has_at_least_eight_menu_items(seeded_session):
    result = await seeded_session.execute(
        text(
            "SELECT r.name, COUNT(m.id) FROM restaurants r "
            "JOIN menu_items m ON m.restaurant_id = r.id "
            "GROUP BY r.name"
        )
    )
    counts = dict(result.all())
    assert len(counts) == 5
    for name, count in counts.items():
        assert count >= 8, f"{name} has only {count} menu items"


async def test_total_transaction_count_within_expected_range(seeded_session):
    result = await seeded_session.execute(text("SELECT COUNT(*) FROM transactions"))
    total = result.scalar()
    low, high = EXPECTED_TRANSACTION_COUNT_RANGE
    assert low <= total <= high, f"total transactions {total} outside expected range"


async def test_every_restaurant_has_a_transaction_every_seeded_day(seeded_session):
    result = await seeded_session.execute(
        text(
            "SELECT r.name, COUNT(DISTINCT transaction_time::date) "
            "FROM restaurants r JOIN transactions t ON t.restaurant_id = r.id "
            "GROUP BY r.name"
        )
    )
    for name, distinct_days in result.all():
        assert distinct_days == 90, f"{name} has only {distinct_days} distinct seeded days"


async def test_every_restaurant_has_reviews_and_campaigns(seeded_session):
    result = await seeded_session.execute(
        text(
            "SELECT "
            "(SELECT COUNT(*) FROM reviews rv WHERE rv.restaurant_id = r.id), "
            "(SELECT COUNT(*) FROM campaigns c WHERE c.restaurant_id = r.id) "
            "FROM restaurants r"
        )
    )
    for review_count, campaign_count in result.all():
        assert review_count >= 1
        assert campaign_count >= 1


async def test_seed_is_idempotent(admin_engine: AsyncEngine):
    session_maker = async_sessionmaker(admin_engine, expire_on_commit=False)

    async with session_maker() as session:
        summary1 = await seed_database(session)
        result1 = await session.execute(
            text(
                "SELECT SUM(t.total_amount) FROM transactions t "
                "JOIN restaurants r ON r.id = t.restaurant_id "
                "WHERE r.name = 'Golden Skillet'"
            )
        )
        revenue1 = result1.scalar()

    async with session_maker() as session:
        summary2 = await seed_database(session)
        result2 = await session.execute(
            text(
                "SELECT SUM(t.total_amount) FROM transactions t "
                "JOIN restaurants r ON r.id = t.restaurant_id "
                "WHERE r.name = 'Golden Skillet'"
            )
        )
        revenue2 = result2.scalar()

    assert summary1 == summary2
    assert revenue1 == revenue2


async def test_golden_skillet_tuesday_pattern_via_sql(seeded_session):
    result = await seeded_session.execute(
        text(
            "SELECT EXTRACT(DOW FROM transaction_time)::int AS dow, AVG(daily_total) "
            "FROM ("
            "  SELECT transaction_time::date AS d, SUM(total_amount) AS daily_total "
            "  FROM transactions t JOIN restaurants r ON r.id = t.restaurant_id "
            "  WHERE r.name = 'Golden Skillet' "
            "  GROUP BY transaction_time::date"
            ") daily "
            "JOIN transactions t2 ON t2.transaction_time::date = daily.d "
            "GROUP BY dow"
        )
    )
    # Postgres EXTRACT(DOW): Sunday=0 ... Saturday=6, so Tuesday=2.
    by_dow = dict(result.all())
    tuesday_avg = by_dow[2]
    all_avg = sum(by_dow.values()) / len(by_dow)
    assert tuesday_avg <= all_avg * Decimal("0.80")


async def test_bella_notte_truffle_fries_trend_via_sql(seeded_session):
    # Symmetric first-30 / last-30 buckets, with the middle 30 days excluded
    # entirely — NOT a first-30-vs-everything-else split.
    result = await seeded_session.execute(
        text(
            "SELECT bucket, SUM(qty) FROM ("
            "  SELECT ti.quantity AS qty, "
            "    CASE "
            "      WHEN t.transaction_time::date <= ("
            "        SELECT MIN(transaction_time::date) + 29 FROM transactions tt "
            "        JOIN restaurants rr ON rr.id = tt.restaurant_id WHERE rr.name = 'Bella Notte'"
            "      ) THEN 'first_30' "
            "      WHEN t.transaction_time::date >= ("
            "        SELECT MAX(transaction_time::date) - 29 FROM transactions tt "
            "        JOIN restaurants rr ON rr.id = tt.restaurant_id WHERE rr.name = 'Bella Notte'"
            "      ) THEN 'last_30' "
            "      ELSE NULL "
            "    END AS bucket "
            "  FROM transaction_items ti "
            "  JOIN transactions t ON t.id = ti.transaction_id "
            "  JOIN restaurants r ON r.id = t.restaurant_id "
            "  JOIN menu_items m ON m.id = ti.menu_item_id "
            "  WHERE r.name = 'Bella Notte' AND m.name = 'Truffle Fries'"
            ") bucketed "
            "WHERE bucket IS NOT NULL "
            "GROUP BY bucket"
        )
    )
    by_bucket = dict(result.all())
    assert by_bucket["last_30"] >= by_bucket.get("first_30", 0) * 2


async def test_sakura_table_premium_ticket_via_sql(seeded_session):
    result = await seeded_session.execute(
        text(
            "SELECT r.name = 'Sakura Table' AS is_sakura, AVG(t.total_amount) "
            "FROM transactions t JOIN restaurants r ON r.id = t.restaurant_id "
            "GROUP BY is_sakura"
        )
    )
    by_group = dict(result.all())
    assert by_group[True] >= by_group[False] * Decimal("1.3")
