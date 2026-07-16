"""Pure, DB-free statistical generators for Ask Sous's seed data.

Every function here takes an explicit `rng: random.Random` (and, where text
is needed, an explicit `faker: Faker`) rather than relying on global seeding
— this is what makes each function independently unit-testable without a
database or hidden global state. See docs/decisions/004-seed-data-determinism-and-patterns.md.

This module contains all statistical/pattern logic. `seed.py` contains none
— it only orchestrates (truncate, call these functions, bulk-insert).
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from faker import Faker

FIXED_SEED = 42

# Fixed, not datetime.now() — re-running the seed script on a different day
# must not change the seeded transaction-time range (see ADR-004).
SEED_END_DATE = date(2026, 7, 14)
SEED_WINDOW_DAYS = 90

RESTAURANT_PROFILES = [
    {
        "name": "Golden Skillet",
        "cuisine": "American comfort food",
        "city": "Austin",
        "region": "South",
        "size_category": "medium",
        "brand_voice_guide": (
            "Warm, down-to-earth, and generous — like a family kitchen that never "
            "stopped cooking. Short sentences, comfort-food language, no pretension."
        ),
        "pattern": "tuesday_slowdown",
    },
    {
        "name": "Bella Notte",
        "cuisine": "Italian",
        "city": "Chicago",
        "region": "Midwest",
        "size_category": "medium",
        "brand_voice_guide": (
            "Romantic, unhurried, and proud of tradition — candlelight and slow-cooked "
            "sauces. Warm but a little formal, with the occasional Italian phrase."
        ),
        "pattern": "trending_item",
    },
    {
        "name": "Sakura Table",
        "cuisine": "Japanese",
        "city": "Seattle",
        "region": "West",
        "size_category": "large",
        "brand_voice_guide": (
            "Refined, minimalist, and precise — every dish is a small act of craft. "
            "Calm, confident language; never oversells, lets quality speak."
        ),
        "pattern": "premium_ticket",
    },
    {
        "name": "Casa Verde",
        "cuisine": "Mexican",
        "city": "Austin",
        "region": "South",
        "size_category": "small",
        "brand_voice_guide": (
            "Playful, vibrant, and family-friendly — bright colours in every sentence. "
            "Loves exclamation points and a good pun."
        ),
        "pattern": None,
    },
    {
        "name": "Harbor & Vine",
        "cuisine": "Seafood & wine bar",
        "city": "Portland",
        "region": "West",
        "size_category": "medium",
        "brand_voice_guide": (
            "Coastal, easygoing, and a little upscale — think golden-hour patio and a "
            "good glass of white. Relaxed confidence, never stuffy."
        ),
        "pattern": None,
    },
]

MENU_ITEM_POOLS: dict[str, list[tuple[str, str]]] = {
    "Golden Skillet": [
        ("Buttermilk Fried Chicken", "entree"),
        ("Meatloaf Platter", "entree"),
        ("Mac and Cheese Bowl", "entree"),
        ("Chicken Fried Steak", "entree"),
        ("Cornbread Muffins", "appetizer"),
        ("Fried Green Tomatoes", "appetizer"),
        ("Deviled Eggs", "appetizer"),
        ("Peach Cobbler", "dessert"),
        ("Banana Pudding", "dessert"),
        ("Sweet Tea", "beverage"),
        ("Lemonade", "beverage"),
        ("Root Beer Float", "beverage"),
    ],
    "Bella Notte": [
        ("Truffle Fries", "appetizer"),
        ("Bruschetta al Pomodoro", "appetizer"),
        ("Calamari Fritti", "appetizer"),
        ("Spaghetti Carbonara", "entree"),
        ("Margherita Pizza", "entree"),
        ("Chicken Parmigiana", "entree"),
        ("Fettuccine Alfredo", "entree"),
        ("Osso Buco", "entree"),
        ("Tiramisu", "dessert"),
        ("Panna Cotta", "dessert"),
        ("Chianti (glass)", "beverage"),
        ("San Pellegrino", "beverage"),
    ],
    "Sakura Table": [
        ("Omakase Nigiri Set", "entree"),
        ("Wagyu Donburi", "entree"),
        ("Chirashi Bowl", "entree"),
        ("Miso Black Cod", "entree"),
        ("Uni Toast", "appetizer"),
        ("Agedashi Tofu", "appetizer"),
        ("Edamame", "appetizer"),
        ("Gyoza", "appetizer"),
        ("Mochi Ice Cream", "dessert"),
        ("Matcha Tiramisu", "dessert"),
        ("Junmai Sake (glass)", "beverage"),
        ("Sencha Tea", "beverage"),
    ],
    "Casa Verde": [
        ("Al Pastor Tacos", "entree"),
        ("Carne Asada Plate", "entree"),
        ("Chile Relleno", "entree"),
        ("Enchiladas Verdes", "entree"),
        ("Guacamole & Chips", "appetizer"),
        ("Queso Fundido", "appetizer"),
        ("Elote", "appetizer"),
        ("Churros", "dessert"),
        ("Tres Leches Cake", "dessert"),
        ("Horchata", "beverage"),
        ("Jamaica Agua Fresca", "beverage"),
        ("Michelada", "beverage"),
    ],
    "Harbor & Vine": [
        ("Grilled Salmon", "entree"),
        ("Seared Scallops", "entree"),
        ("Lobster Roll", "entree"),
        ("Cioppino", "entree"),
        ("Oysters on the Half Shell", "appetizer"),
        ("Crab Cakes", "appetizer"),
        ("Clam Chowder", "appetizer"),
        ("Key Lime Pie", "dessert"),
        ("Chocolate Lava Cake", "dessert"),
        ("Sauvignon Blanc (glass)", "beverage"),
        ("Sparkling Water", "beverage"),
    ],
}

# Standard price ranges (low, high), applied to every restaurant except
# Sakura Table (see SAKURA_PRICE_RANGES — deliberate pattern 3).
STANDARD_PRICE_RANGES: dict[str, tuple[float, float]] = {
    "entree": (11, 22),
    "appetizer": (6, 12),
    "dessert": (5, 9),
    "beverage": (3, 9),
}
SAKURA_PRICE_RANGES: dict[str, tuple[float, float]] = {
    "entree": (24, 46),
    "appetizer": (12, 22),
    "dessert": (9, 14),
    "beverage": (6, 16),
}

BASE_DAILY_COUNT = {"small": 45, "medium": 75, "large": 115}
# Python's date.weekday(): Monday=0 ... Sunday=6.
DOW_MULTIPLIER = {0: 0.90, 1: 1.00, 2: 0.95, 3: 1.00, 4: 1.25, 5: 1.35, 6: 1.10}
TUESDAY = 1

# Hour -> relative weight for allocating a day's transactions across the
# clock. Hours absent from this dict are closed (weight 0).
HOURLY_WEIGHTS: dict[int, float] = {
    11: 3.0,
    12: 3.0,
    13: 3.0,
    14: 0.6,
    15: 0.6,
    16: 0.6,
    17: 4.0,
    18: 4.0,
    19: 4.0,
    20: 4.0,
    21: 1.0,
    22: 1.0,
}
_HOURS = list(HOURLY_WEIGHTS.keys())
_HOUR_WEIGHTS = list(HOURLY_WEIGHTS.values())

QUANTITY_CHOICES = [1, 2, 3]
QUANTITY_WEIGHTS = [60, 30, 10]
CHANNEL_CHOICES = ["dine-in", "takeout", "delivery"]
CHANNEL_WEIGHTS = [55, 30, 15]
PAYMENT_CHOICES = ["credit_card", "debit_card", "mobile_pay", "cash"]
PAYMENT_WEIGHTS = [55, 20, 20, 5]
RATING_CHOICES = [1, 2, 3, 4, 5]
RATING_WEIGHTS = [2, 3, 10, 35, 50]
REVIEW_SOURCE_CHOICES = ["google", "yelp", "walk_in", "in_app"]
REVIEW_SOURCE_WEIGHTS = [40, 25, 20, 15]
CAMPAIGN_CHANNEL_CHOICES = ["sms", "email", "social"]
CAMPAIGN_CHANNEL_WEIGHTS = [40, 35, 25]

# Golden Skillet's additional Tuesday-only multiplier, layered on top of the
# shared DOW_MULTIPLIER[TUESDAY]=1.00 baseline. See seed-patterns.md for the
# worked-out expected gap (~59% below Golden Skillet's own weekly average).
GOLDEN_SKILLET_TUESDAY_MULTIPLIER = 0.45

# Bella Notte's Truffle Fries inclusion-probability ramp: p(day_index) =
# TRUFFLE_FRIES_P_START + TRUFFLE_FRIES_P_SLOPE * (day_index / (SEED_WINDOW_DAYS - 1)).
TRUFFLE_FRIES_P_START = 0.05
TRUFFLE_FRIES_P_SLOPE = 0.30
TRUFFLE_FRIES_ITEM_NAME = "Truffle Fries"

# Designated add-on/upsell items (Phase 8) — kept in a companion structure,
# not mixed into MENU_ITEM_POOLS, so the existing item-velocity/trend
# patterns above (keyed off the base pool) are untouched. Two per
# restaurant: enough to be interesting without diluting the base menu.
UPSELL_ITEM_POOLS: dict[str, list[str]] = {
    "Golden Skillet": ["Extra Gravy", "Add Bacon"],
    "Bella Notte": ["Extra Parmesan", "Add Prosciutto"],
    "Sakura Table": ["Add Extra Toro", "Extra Wasabi Flight"],
    "Casa Verde": ["Add Guac", "Extra Salsa Roja"],
    "Harbor & Vine": ["Add Butter-Poached Lobster", "Extra Remoulade"],
}
ADDON_PRICE_RANGE: tuple[float, float] = (2.0, 6.0)
UPSELL_CATEGORY = "addon"

# Probability that a transaction's base order also includes one upsell
# item, independent of restaurant identity or the Truffle Fries pattern
# above (which is about a real, primarily-ordered appetizer's trend over
# time, not an add-on). See docs/decisions on upsell measurement.
UPSELL_ATTACH_PROBABILITY = 0.25

# Synthetic campaign-to-transaction attribution (Phase 8) — not a real
# promo-code mechanism, since none exists in this schema. See
# docs/decisions on campaign attribution.
CAMPAIGN_ATTRIBUTION_WINDOW_DAYS = 5
CAMPAIGN_ATTRIBUTION_RATE_RANGE: tuple[float, float] = (0.15, 0.30)

CAMPAIGN_COPY_TEMPLATES = [
    "Craving {cuisine}? {name} has something special waiting this week — come try {item}.",
    "{name} misses you! Stop by for {item} and a seat at our table.",
    "This week only at {name}: bring a friend and split {item} on us.",
    "{name} presents {item} — the dish everyone's been asking about.",
]

# Real restaurant-domain content, not generic Faker sentence()/paragraph()
# text — the latter is grammatically plausible but never actually about
# anything, so real semantic search over it can never find a genuinely
# relevant match (see docs/decisions/013-live-credentials-verification.md's
# "content-quality limitation" finding, discovered via a live search that
# technically worked but never returned anything relevant). Bucketed by
# sentiment so a review's tone correlates with its numeric rating, matching
# how real reviews actually read. {cuisine}/{item} placeholders are
# optional per-template — str.format() ignores unused kwargs.
POSITIVE_REVIEW_TEMPLATES = [
    "The service here was fantastic — our server was attentive and friendly the whole time.",
    "Best {cuisine} I've had in ages. The {item} was cooked perfectly.",
    "We didn't wait long at all, and the staff greeted us warmly right away.",
    "Great value for the portion size — the {item} alone was worth the trip.",
    "Cozy atmosphere and the food came out quick. We'll definitely be back.",
    "The staff went out of their way to accommodate our allergies. Really impressed.",
    "Fresh ingredients and bold flavors — the {item} stood out from anything else on the menu.",
    "Quick, friendly service even during the dinner rush. Highly recommend.",
]

NEGATIVE_REVIEW_TEMPLATES = [
    "Service was painfully slow — we waited over 40 minutes just to have our order taken.",
    "The {item} arrived cold and the staff seemed uninterested in helping.",
    "Way overpriced for what you get. Wouldn't come back.",
    "Our server disappeared for most of the meal and never checked back in.",
    "The dining room was noisy and cramped, and the wait was way too long.",
    "Disappointing {cuisine} — the {item} was bland and overcooked.",
    "Rude staff and a messy dining room. Not what I expected.",
    "Took forever to get seated even though half the tables were empty.",
]

MIXED_REVIEW_TEMPLATES = [
    "The {item} was good but service was a bit slow during the rush.",
    "Decent {cuisine}, though the prices felt a little high for the portion sizes.",
    "Friendly staff, but we had to wait a while for our food to come out.",
    "The food was fine, nothing special, but the atmosphere was nice.",
    "Good flavors overall, though the {item} could have come out warmer.",
]


def rng_uuid(rng) -> uuid.UUID:
    """Deterministic UUID drawn from the seeded RNG.

    Scoped to seed.py/generators.py only — Phase 7's live-trickle generator
    must NOT reuse this, since it's meant to simulate genuinely
    non-deterministic ongoing activity (see ADR-004).
    """
    return uuid.UUID(int=rng.getrandbits(128), version=4)


def make_rng_and_faker(seed: int = FIXED_SEED) -> tuple:
    """Construct one rng/faker pair from the given seed.

    Callers pass these explicitly into every generator function below —
    no global `random.seed()`/`Faker.seed()` is ever called.
    """
    import random

    rng = random.Random(seed)
    faker = Faker()
    faker.seed_instance(seed)
    return rng, faker


def seed_window_dates() -> list[date]:
    start = SEED_END_DATE - timedelta(days=SEED_WINDOW_DAYS - 1)
    return [start + timedelta(days=i) for i in range(SEED_WINDOW_DAYS)]


def generate_menu_items(rng, restaurant_id: uuid.UUID, restaurant_name: str) -> list[dict]:
    pool = MENU_ITEM_POOLS[restaurant_name]
    price_ranges = (
        SAKURA_PRICE_RANGES if restaurant_name == "Sakura Table" else STANDARD_PRICE_RANGES
    )
    items = []
    for name, category in pool:
        low, high = price_ranges[category]
        price = Decimal(str(round(rng.uniform(low, high), 2)))
        items.append(
            {
                "id": rng_uuid(rng),
                "restaurant_id": restaurant_id,
                "name": name,
                "category": category,
                "price": price,
                "is_upsell": False,
            }
        )

    addon_low, addon_high = ADDON_PRICE_RANGE
    for name in UPSELL_ITEM_POOLS[restaurant_name]:
        price = Decimal(str(round(rng.uniform(addon_low, addon_high), 2)))
        items.append(
            {
                "id": rng_uuid(rng),
                "restaurant_id": restaurant_id,
                "name": name,
                "category": UPSELL_CATEGORY,
                "price": price,
                "is_upsell": True,
            }
        )
    return items


def _deliberate_multiplier(restaurant_name: str, day: date) -> float:
    if restaurant_name == "Golden Skillet" and day.weekday() == TUESDAY:
        return GOLDEN_SKILLET_TUESDAY_MULTIPLIER
    return 1.0


def _truffle_fries_probability(day_index: int) -> float:
    return TRUFFLE_FRIES_P_START + TRUFFLE_FRIES_P_SLOPE * (day_index / (SEED_WINDOW_DAYS - 1))


def generate_transactions_and_items(
    rng, restaurant_id: uuid.UUID, restaurant_name: str, size_category: str, menu_items: list[dict]
) -> tuple[list[dict], list[dict]]:
    transactions: list[dict] = []
    transaction_items: list[dict] = []

    non_truffle_items = [
        m for m in menu_items if m["name"] != TRUFFLE_FRIES_ITEM_NAME and not m["is_upsell"]
    ]
    truffle_item = next((m for m in menu_items if m["name"] == TRUFFLE_FRIES_ITEM_NAME), None)
    upsell_items = [m for m in menu_items if m["is_upsell"]]

    for day_index, day in enumerate(seed_window_dates()):
        weekday = day.weekday()
        expected = (
            BASE_DAILY_COUNT[size_category]
            * DOW_MULTIPLIER[weekday]
            * _deliberate_multiplier(restaurant_name, day)
        )
        count = max(1, round(rng.gauss(expected, expected * 0.12)))

        for _ in range(count):
            hour = rng.choices(_HOURS, weights=_HOUR_WEIGHTS)[0]
            minute = rng.randint(0, 59)
            second = rng.randint(0, 59)
            tx_time = datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=UTC)

            num_items = rng.randint(1, min(4, len(non_truffle_items)))
            selected = rng.sample(non_truffle_items, k=num_items)
            line_items = [
                {
                    "menu_item": m,
                    "quantity": rng.choices(QUANTITY_CHOICES, weights=QUANTITY_WEIGHTS)[0],
                }
                for m in selected
            ]

            if restaurant_name == "Bella Notte" and truffle_item is not None:
                if rng.random() < _truffle_fries_probability(day_index):
                    qty = rng.choices(QUANTITY_CHOICES, weights=QUANTITY_WEIGHTS)[0]
                    line_items.append({"menu_item": truffle_item, "quantity": qty})

            if upsell_items and rng.random() < UPSELL_ATTACH_PROBABILITY:
                line_items.append({"menu_item": rng.choice(upsell_items), "quantity": 1})

            total_amount = sum(
                (Decimal(li["quantity"]) * li["menu_item"]["price"] for li in line_items),
                Decimal("0"),
            )

            tx_id = rng_uuid(rng)
            transactions.append(
                {
                    "id": tx_id,
                    "restaurant_id": restaurant_id,
                    "transaction_time": tx_time,
                    "total_amount": total_amount,
                    "payment_type": rng.choices(PAYMENT_CHOICES, weights=PAYMENT_WEIGHTS)[0],
                    "channel": rng.choices(CHANNEL_CHOICES, weights=CHANNEL_WEIGHTS)[0],
                }
            )
            for li in line_items:
                transaction_items.append(
                    {
                        "id": rng_uuid(rng),
                        "transaction_id": tx_id,
                        "menu_item_id": li["menu_item"]["id"],
                        "quantity": li["quantity"],
                        "unit_price": li["menu_item"]["price"],
                    }
                )

    return transactions, transaction_items


def _review_text_for_rating(rng, rating: int, cuisine: str, menu_items: list[dict]) -> str:
    if rating <= 2:
        templates = NEGATIVE_REVIEW_TEMPLATES
    elif rating == 3:
        templates = MIXED_REVIEW_TEMPLATES
    else:
        templates = POSITIVE_REVIEW_TEMPLATES
    item = rng.choice(menu_items)["name"] if menu_items else ""
    return rng.choice(templates).format(cuisine=cuisine, item=item)


def generate_reviews(
    rng, faker: Faker, restaurant_id: uuid.UUID, cuisine: str, menu_items: list[dict]
) -> list[dict]:
    count = rng.randint(20, 40)
    window = seed_window_dates()
    reviews = []
    for _ in range(count):
        day = rng.choice(window)
        created_at = datetime(
            day.year, day.month, day.day, rng.randint(8, 22), rng.randint(0, 59), tzinfo=UTC
        )
        rating = rng.choices(RATING_CHOICES, weights=RATING_WEIGHTS)[0]
        reviews.append(
            {
                "id": rng_uuid(rng),
                "restaurant_id": restaurant_id,
                "rating": rating,
                "review_text": _review_text_for_rating(rng, rating, cuisine, menu_items),
                "source": rng.choices(REVIEW_SOURCE_CHOICES, weights=REVIEW_SOURCE_WEIGHTS)[0],
                "created_at": created_at,
            }
        )
    return reviews


def generate_campaigns(
    rng,
    faker: Faker,
    restaurant_id: uuid.UUID,
    restaurant_name: str,
    cuisine: str,
    menu_items: list[dict],
) -> list[dict]:
    count = rng.randint(3, 5)
    window = seed_window_dates()
    # A campaign shouldn't feature an add-on ("Extra Gravy") as its star
    # dish — only real, primarily-ordered items are eligible.
    featurable_items = [m for m in menu_items if not m["is_upsell"]]
    campaigns = []
    for _ in range(count):
        day = rng.choice(window)
        sent_at = datetime(
            day.year, day.month, day.day, rng.randint(9, 20), rng.randint(0, 59), tzinfo=UTC
        )
        item = rng.choice(featurable_items)["name"]
        template = rng.choice(CAMPAIGN_COPY_TEMPLATES)
        copy_text = template.format(name=restaurant_name, cuisine=cuisine, item=item)
        campaigns.append(
            {
                "id": rng_uuid(rng),
                "restaurant_id": restaurant_id,
                "name": f"{faker.word().title()} {rng.choice(['Special', 'Promo', 'Push'])}",
                "channel": rng.choices(CAMPAIGN_CHANNEL_CHOICES, weights=CAMPAIGN_CHANNEL_WEIGHTS)[
                    0
                ],
                "sent_at": sent_at,
                "copy_text": copy_text,
                "conversion_rate": Decimal(str(round(rng.uniform(0.01, 0.15), 4))),
                "revenue_lift": Decimal(str(round(rng.uniform(50, 3000), 2))),
            }
        )
    return campaigns


def attribute_transactions_to_campaigns(
    rng, transactions: list[dict], campaigns: list[dict]
) -> list[dict]:
    """Synthetic campaign attribution (Phase 8) — not a real promo-code
    mechanism, since none exists in this schema. Returns a new list of
    transaction dicts, each gaining a `campaign_id` key. Processes
    campaigns in `sent_at` order, and for each one, picks a random fraction
    (CAMPAIGN_ATTRIBUTION_RATE_RANGE) of the not-yet-attributed
    transactions falling within CAMPAIGN_ATTRIBUTION_WINDOW_DAYS after its
    `sent_at` — first-touch: a transaction already attributed to an earlier
    campaign is never reassigned, avoiding double-attribution ambiguity.
    """
    result = [dict(t, campaign_id=None) for t in transactions]
    attributed_ids: set[uuid.UUID] = set()

    sent_campaigns = sorted(
        (c for c in campaigns if c["sent_at"] is not None), key=lambda c: c["sent_at"]
    )
    for campaign in sent_campaigns:
        window_end = campaign["sent_at"] + timedelta(days=CAMPAIGN_ATTRIBUTION_WINDOW_DAYS)
        candidates = [
            t
            for t in result
            if t["id"] not in attributed_ids
            and campaign["sent_at"] <= t["transaction_time"] <= window_end
        ]
        if not candidates:
            continue
        rate = rng.uniform(*CAMPAIGN_ATTRIBUTION_RATE_RANGE)
        chosen_count = round(len(candidates) * rate)
        chosen = rng.sample(candidates, k=min(chosen_count, len(candidates)))
        for t in chosen:
            t["campaign_id"] = campaign["id"]
            attributed_ids.add(t["id"])

    return result
