import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.seed.generators import (
    FIXED_SEED,
    MENU_ITEM_POOLS,
    RESTAURANT_PROFILES,
    SEED_END_DATE,
    SEED_WINDOW_DAYS,
    attribute_transactions_to_campaigns,
    generate_campaigns,
    generate_menu_items,
    generate_reviews,
    generate_transactions_and_items,
    make_rng_and_faker,
    seed_window_dates,
)


def _profile(name: str) -> dict:
    return next(p for p in RESTAURANT_PROFILES if p["name"] == name)


def _restaurant_id_for(name: str, seed: int = FIXED_SEED) -> uuid.UUID:
    """A fixed, stable restaurant_id per name, independent of rng draw order,
    used purely so test setup can address a specific restaurant's generated data."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"ask-sous-test-{name}-{seed}")


def test_seed_window_is_exactly_90_days_ending_at_seed_end_date():
    window = seed_window_dates()
    assert len(window) == SEED_WINDOW_DAYS
    assert window[0] == SEED_END_DATE - timedelta(days=89)
    assert window[-1] == SEED_END_DATE


def test_determinism_menu_items():
    rng1, _ = make_rng_and_faker(FIXED_SEED)
    rng2, _ = make_rng_and_faker(FIXED_SEED)
    rid = _restaurant_id_for("Golden Skillet")

    items1 = generate_menu_items(rng1, rid, "Golden Skillet")
    items2 = generate_menu_items(rng2, rid, "Golden Skillet")

    assert items1 == items2


def test_determinism_transactions_and_items():
    rng1, _ = make_rng_and_faker(FIXED_SEED)
    rng2, _ = make_rng_and_faker(FIXED_SEED)
    rid = _restaurant_id_for("Golden Skillet")

    menu_items1 = generate_menu_items(rng1, rid, "Golden Skillet")
    menu_items2 = generate_menu_items(rng2, rid, "Golden Skillet")
    tx1, items1 = generate_transactions_and_items(
        rng1, rid, "Golden Skillet", "medium", menu_items1
    )
    tx2, items2 = generate_transactions_and_items(
        rng2, rid, "Golden Skillet", "medium", menu_items2
    )

    assert tx1 == tx2
    assert items1 == items2


def test_every_restaurant_has_a_transaction_on_every_seeded_day():
    rng, _ = make_rng_and_faker(FIXED_SEED)
    rid = _restaurant_id_for("Casa Verde")
    menu_items = generate_menu_items(rng, rid, "Casa Verde")
    tx, _ = generate_transactions_and_items(rng, rid, "Casa Verde", "small", menu_items)

    seeded_dates = {t["transaction_time"].date() for t in tx}
    assert seeded_dates == set(seed_window_dates())


def test_golden_skillet_tuesday_revenue_is_well_below_its_weekly_average():
    rng, _ = make_rng_and_faker(FIXED_SEED)
    rid = _restaurant_id_for("Golden Skillet")
    menu_items = generate_menu_items(rng, rid, "Golden Skillet")
    tx, _ = generate_transactions_and_items(rng, rid, "Golden Skillet", "medium", menu_items)

    by_day: dict = {}
    for t in tx:
        by_day.setdefault(t["transaction_time"].date(), Decimal("0"))
        by_day[t["transaction_time"].date()] += t["total_amount"]

    tuesday_revenues = [rev for day, rev in by_day.items() if day.weekday() == 1]
    all_avg = sum(by_day.values()) / len(by_day)
    tuesday_avg = sum(tuesday_revenues) / len(tuesday_revenues)

    # Designed gap is ~59% below average; assert at least 30% to tolerate noise.
    assert tuesday_avg <= all_avg * Decimal("0.70")


def test_casa_verde_control_tuesday_is_not_suppressed():
    rng, _ = make_rng_and_faker(FIXED_SEED)
    rid = _restaurant_id_for("Casa Verde")
    menu_items = generate_menu_items(rng, rid, "Casa Verde")
    tx, _ = generate_transactions_and_items(rng, rid, "Casa Verde", "small", menu_items)

    by_day: dict = {}
    for t in tx:
        by_day.setdefault(t["transaction_time"].date(), Decimal("0"))
        by_day[t["transaction_time"].date()] += t["total_amount"]

    tuesday_revenues = [rev for day, rev in by_day.items() if day.weekday() == 1]
    all_avg = sum(by_day.values()) / len(by_day)
    tuesday_avg = sum(tuesday_revenues) / len(tuesday_revenues)

    assert tuesday_avg >= all_avg * Decimal("0.80")


def test_bella_notte_truffle_fries_trending_up():
    rng, _ = make_rng_and_faker(FIXED_SEED)
    rid = _restaurant_id_for("Bella Notte")
    menu_items = generate_menu_items(rng, rid, "Bella Notte")
    tx, items = generate_transactions_and_items(rng, rid, "Bella Notte", "medium", menu_items)

    truffle_id = next(m["id"] for m in menu_items if m["name"] == "Truffle Fries")
    window = seed_window_dates()
    first_30 = set(window[:30])
    last_30 = set(window[-30:])
    tx_date_by_id = {t["id"]: t["transaction_time"].date() for t in tx}

    first_qty = sum(
        i["quantity"]
        for i in items
        if i["menu_item_id"] == truffle_id and tx_date_by_id[i["transaction_id"]] in first_30
    )
    last_qty = sum(
        i["quantity"]
        for i in items
        if i["menu_item_id"] == truffle_id and tx_date_by_id[i["transaction_id"]] in last_30
    )

    assert last_qty >= first_qty * 2


def test_sakura_table_premium_ticket_size():
    rng, _ = make_rng_and_faker(FIXED_SEED)

    sakura_id = _restaurant_id_for("Sakura Table")
    sakura_menu = generate_menu_items(rng, sakura_id, "Sakura Table")
    sakura_tx, _ = generate_transactions_and_items(
        rng, sakura_id, "Sakura Table", "large", sakura_menu
    )
    sakura_avg = sum(t["total_amount"] for t in sakura_tx) / len(sakura_tx)

    other_totals = []
    for name, size in [
        ("Golden Skillet", "medium"),
        ("Bella Notte", "medium"),
        ("Casa Verde", "small"),
        ("Harbor & Vine", "medium"),
    ]:
        rid = _restaurant_id_for(name)
        menu = generate_menu_items(rng, rid, name)
        tx, _ = generate_transactions_and_items(rng, rid, name, size, menu)
        other_totals.extend(t["total_amount"] for t in tx)

    others_avg = sum(other_totals) / len(other_totals)

    assert sakura_avg >= others_avg * Decimal("1.3")


def test_total_amount_equals_sum_of_line_items():
    rng, _ = make_rng_and_faker(FIXED_SEED)
    rid = _restaurant_id_for("Harbor & Vine")
    menu_items = generate_menu_items(rng, rid, "Harbor & Vine")
    tx, items = generate_transactions_and_items(rng, rid, "Harbor & Vine", "medium", menu_items)

    items_by_tx: dict = {}
    for i in items:
        items_by_tx.setdefault(i["transaction_id"], Decimal("0"))
        items_by_tx[i["transaction_id"]] += i["quantity"] * i["unit_price"]

    for t in tx:
        assert t["total_amount"] == items_by_tx[t["id"]]


def test_generate_menu_items_includes_flagged_upsell_items():
    rng, _ = make_rng_and_faker(FIXED_SEED)
    rid = _restaurant_id_for("Golden Skillet")
    items = generate_menu_items(rng, rid, "Golden Skillet")

    upsell_items = [i for i in items if i["is_upsell"]]
    base_items = [i for i in items if not i["is_upsell"]]

    assert len(upsell_items) == 2
    assert len(base_items) == len(MENU_ITEM_POOLS["Golden Skillet"])
    for item in upsell_items:
        assert Decimal("2.00") <= item["price"] <= Decimal("6.00")
    for item in base_items:
        assert item["is_upsell"] is False


def test_upsell_attach_rate_is_measurable_and_near_target():
    rng, _ = make_rng_and_faker(FIXED_SEED)
    rid = _restaurant_id_for("Golden Skillet")
    menu_items = generate_menu_items(rng, rid, "Golden Skillet")
    tx, items = generate_transactions_and_items(rng, rid, "Golden Skillet", "large", menu_items)

    upsell_item_ids = {i["id"] for i in menu_items if i["is_upsell"]}
    items_by_tx: dict = {}
    for i in items:
        items_by_tx.setdefault(i["transaction_id"], []).append(i)

    with_upsell = sum(
        1
        for t in tx
        if any(i["menu_item_id"] in upsell_item_ids for i in items_by_tx.get(t["id"], []))
    )
    attach_rate = with_upsell / len(tx)

    # Target is ~0.25 (UPSELL_ATTACH_PROBABILITY) — allow real sampling
    # variance rather than asserting an exact value.
    assert 0.15 <= attach_rate <= 0.35


def test_generate_reviews_shape():
    rng, faker = make_rng_and_faker(FIXED_SEED)
    rid = _restaurant_id_for("Golden Skillet")
    profile = _profile("Golden Skillet")
    menu_items = generate_menu_items(rng, rid, "Golden Skillet")
    reviews = generate_reviews(rng, faker, rid, profile["cuisine"], menu_items)

    assert 20 <= len(reviews) <= 40
    for r in reviews:
        assert 1 <= r["rating"] <= 5
        assert r["review_text"]
        assert r["source"] in {"google", "yelp", "walk_in", "in_app"}


def test_generate_reviews_text_is_restaurant_domain_content_not_generic_faker_text():
    # Real semantic search over reviews is only meaningful if the review
    # text is actually about restaurant topics (service, food, wait times,
    # price, ambiance) — generic Faker sentence()/paragraph() text is
    # grammatically plausible but never about anything, so a query like
    # "what are customers saying about the service?" can never find a
    # genuinely relevant match. Spot-check for restaurant-domain vocabulary
    # rather than asserting exact template text, so this stays robust to
    # template wording changes.
    rng, faker = make_rng_and_faker(FIXED_SEED)
    rid = _restaurant_id_for("Golden Skillet")
    profile = _profile("Golden Skillet")
    menu_items = generate_menu_items(rng, rid, "Golden Skillet")
    reviews = generate_reviews(rng, faker, rid, profile["cuisine"], menu_items)

    domain_words = {
        "service",
        "server",
        "staff",
        "food",
        "wait",
        "waited",
        "price",
        "priced",
        "portion",
        "atmosphere",
        "flavor",
        "flavors",
        "seated",
        "menu",
        "dish",
        "meal",
    }
    matching = [
        r for r in reviews if domain_words & set(r["review_text"].lower().replace(".", "").split())
    ]
    # Not every review needs every word, but the large majority should read
    # as genuinely restaurant-related, not generic filler text.
    assert len(matching) >= len(reviews) * 0.8


def test_generate_reviews_sentiment_correlates_with_rating():
    # A 1-2 star review reading as glowingly positive (or vice versa) would
    # be a giveaway that ratings and text are generated independently,
    # undermining any demo that shows both together. Spot-check the
    # extremes: low ratings should skew toward templates with negative
    # framing (slow, cold, rude, overpriced, disappointing), high ratings
    # toward positive framing (fantastic, great, friendly, fresh, quick).
    rng, faker = make_rng_and_faker(FIXED_SEED)
    rid = _restaurant_id_for("Golden Skillet")
    profile = _profile("Golden Skillet")
    menu_items = generate_menu_items(rng, rid, "Golden Skillet")
    reviews = generate_reviews(rng, faker, rid, profile["cuisine"], menu_items)

    negative_words = {"slow", "cold", "rude", "overpriced", "disappointing", "bland", "messy"}
    positive_words = {"fantastic", "great", "friendly", "fresh", "quick", "perfectly", "impressed"}

    low_rated = [r for r in reviews if r["rating"] <= 2]
    high_rated = [r for r in reviews if r["rating"] >= 4]

    if low_rated:
        assert any(
            negative_words & set(r["review_text"].lower().replace(".", "").replace(",", "").split())
            for r in low_rated
        )
    if high_rated:
        assert any(
            positive_words & set(r["review_text"].lower().replace(".", "").replace(",", "").split())
            for r in high_rated
        )


def test_generate_campaigns_shape():
    rng, faker = make_rng_and_faker(FIXED_SEED)
    rid = _restaurant_id_for("Golden Skillet")
    profile = _profile("Golden Skillet")
    menu_items = generate_menu_items(rng, rid, "Golden Skillet")
    campaigns = generate_campaigns(
        rng, faker, rid, "Golden Skillet", profile["cuisine"], menu_items
    )

    assert 3 <= len(campaigns) <= 5
    for c in campaigns:
        assert c["channel"] in {"sms", "email", "social"}
        assert c["copy_text"]
        assert Decimal("0.01") <= c["conversion_rate"] <= Decimal("0.15")


def _tx(tx_id: uuid.UUID, when: datetime) -> dict:
    return {
        "id": tx_id,
        "restaurant_id": uuid.uuid4(),
        "transaction_time": when,
        "total_amount": Decimal("20.00"),
        "payment_type": "cash",
        "channel": "dine-in",
    }


def _campaign(campaign_id: uuid.UUID, sent_at: datetime) -> dict:
    return {
        "id": campaign_id,
        "restaurant_id": uuid.uuid4(),
        "name": "Test Campaign",
        "channel": "email",
        "sent_at": sent_at,
        "copy_text": "x",
        "conversion_rate": Decimal("0.05"),
        "revenue_lift": Decimal("100.00"),
    }


def test_attribute_transactions_to_campaigns_only_attributes_within_window():
    rng, _ = make_rng_and_faker(FIXED_SEED)
    sent_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    campaign = _campaign(uuid.uuid4(), sent_at)

    in_window = _tx(uuid.uuid4(), sent_at + timedelta(days=1))
    outside_window = _tx(uuid.uuid4(), sent_at + timedelta(days=30))
    before_campaign = _tx(uuid.uuid4(), sent_at - timedelta(days=1))

    result = attribute_transactions_to_campaigns(
        rng, [in_window, outside_window, before_campaign], [campaign]
    )
    by_id = {t["id"]: t for t in result}

    assert by_id[outside_window["id"]]["campaign_id"] is None
    assert by_id[before_campaign["id"]]["campaign_id"] is None
    # in_window may or may not be attributed (probabilistic) but must never
    # be attributed to anything other than this one campaign if it is.
    assert by_id[in_window["id"]]["campaign_id"] in (None, campaign["id"])


def test_attribute_transactions_to_campaigns_no_double_attribution():
    rng, _ = make_rng_and_faker(FIXED_SEED)
    sent_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    # Two campaigns whose attribution windows overlap for the same transaction.
    campaign_a = _campaign(uuid.uuid4(), sent_at)
    campaign_b = _campaign(uuid.uuid4(), sent_at + timedelta(days=1))

    overlapping_tx = [_tx(uuid.uuid4(), sent_at + timedelta(days=2)) for _ in range(50)]

    result = attribute_transactions_to_campaigns(rng, overlapping_tx, [campaign_a, campaign_b])

    # Every transaction is attributed to at most one campaign — never both.
    for t in result:
        assert t["campaign_id"] in (None, campaign_a["id"], campaign_b["id"])


def test_attribute_transactions_to_campaigns_is_deterministic():
    sent_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    campaign = _campaign(uuid.uuid4(), sent_at)
    transactions = [_tx(uuid.uuid4(), sent_at + timedelta(hours=i)) for i in range(40)]

    rng1, _ = make_rng_and_faker(FIXED_SEED)
    result1 = attribute_transactions_to_campaigns(rng1, transactions, [campaign])

    rng2, _ = make_rng_and_faker(FIXED_SEED)
    result2 = attribute_transactions_to_campaigns(rng2, transactions, [campaign])

    assert [t["campaign_id"] for t in result1] == [t["campaign_id"] for t in result2]


def test_attribute_transactions_to_campaigns_produces_a_measurable_rate():
    rng, _ = make_rng_and_faker(FIXED_SEED)
    sent_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    campaign = _campaign(uuid.uuid4(), sent_at)
    transactions = [_tx(uuid.uuid4(), sent_at + timedelta(hours=i)) for i in range(200)]

    result = attribute_transactions_to_campaigns(rng, transactions, [campaign])
    attributed = sum(1 for t in result if t["campaign_id"] == campaign["id"])

    assert attributed > 0
    assert attributed / len(transactions) <= 0.35
