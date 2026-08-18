#!/usr/bin/env python3
"""Generate deterministic sample parquet files for the s3-parquet-dbt-demo.

Output layout (under --out-dir):
  customers/customers_000.parquet  500 rows
  products/products_000.parquet     50 rows
  orders/orders_000..002.parquet    --rows-orders rows total, split across 3 files

Pure stdlib + pyarrow (pandas is not used; it is broken in this environment).
"""

import argparse
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone

# pandas in this environment is binary-incompatible with numpy and crashes on
# import. pyarrow's pandas shim imports it lazily; making the import raise
# ImportError makes pyarrow treat pandas as absent, which is what we want.
class _BlockPandas:
    def find_spec(self, name, path=None, target=None):
        if name == "pandas" or name.startswith("pandas."):
            raise ImportError("pandas import blocked (broken in this environment)")
        return None


sys.meta_path.insert(0, _BlockPandas())

import pyarrow as pa
import pyarrow.parquet as pq

SEED = 20260818

REGIONS = ["Northeast", "Southeast", "Midwest", "West"]
CATEGORIES = ["Trading Cards", "Accessories", "Apparel", "Collectibles"]
STATUSES = ["placed", "shipped", "delivered", "cancelled"]
# Weights skew toward completed orders but guarantee cancelled orders appear.
STATUS_WEIGHTS = [0.15, 0.30, 0.45, 0.10]

FIRST_NAMES = [
    "Jason", "Jack", "Andy", "Sarah", "Peter", "Maria", "Devon", "Priya",
    "Carlos", "Emma", "Liam", "Nina", "Owen", "Tessa", "Marcus", "Holly",
    "Derek", "Alana", "Felix", "Grace", "Hector", "Ivy", "Jonah", "Kara",
    "Leo", "Mona", "Nate", "Opal", "Paulo", "Quinn", "Rosa", "Sam",
    "Tara", "Umar", "Vera", "Wes", "Ximena", "Yusuf", "Zoe", "Brent",
]
LAST_NAMES = [
    "Chen", "Rivera", "Okafor", "Nguyen", "Silva", "Kowalski", "Brooks",
    "Delgado", "Fitzgerald", "Grant", "Hayes", "Ibrahim", "Jansen", "Kim",
    "Lopez", "Morrow", "Novak", "Ortega", "Patel", "Quigley", "Ramsey",
    "Sato", "Turner", "Ueda", "Vance", "Whitfield", "Xu", "Young", "Zeller",
    "Abbott", "Barnes", "Cortez", "Dunlap", "Ellis", "Foster", "Griggs",
]

# Product name parts by category, storefront-flavored (JC2 Cards).
PRODUCT_PARTS = {
    "Trading Cards": [
        "Rookie Refractor Single", "Base Set Booster Pack", "Chrome Prism Single",
        "Draft Picks Hobby Box", "Holo Insert Single", "Vintage Wax Pack",
        "Full-Art Promo Single", "Prizm Blaster Box", "Optic Mega Box",
        "Select Hanger Pack", "Mosaic Cello Pack", "Heritage Team Set",
        "Update Series Blaster", "Allen & Ginter Box", "Stadium Club Pack",
        "Numbered Parallel Single", "Case Hit Insert Single", "Retro Reprint Set",
        "Graded Rookie Slab", "Team Lot Assorted 20ct", "Short Print Variation Single",
    ],
    "Accessories": [
        "Penny Sleeves 100ct", "Toploaders 25ct", "Magnetic One-Touch 35pt",
        "Card Saver Semi-Rigid 50ct", "9-Pocket Binder Pages", "Team Bag Resealable 100ct",
        "Graded Slab Stand", "UV-Protect Display Case", "Sorting Tray",
        "Storage Box 800ct", "Card Grading Sleeve Kit", "Dividers 25ct",
        "Shipping Kit Bubble Mailers 10ct",
    ],
    "Apparel": [
        "JC2 Cards Logo Tee", "Collector Hoodie", "Trade Night Cap",
        "Rip & Ship Crewneck", "Card Shop Beanie", "Breaker Zip Jacket",
        "Vintage Wax Tee", "Grading Day Long Sleeve", "Mail Day Tee",
        "Set Builder Polo",
    ],
    "Collectibles": [
        "Sealed Mini Figure", "Enamel Pin Set", "Championship Pennant",
        "Autograph Display Plaque", "Limited Print Poster", "Die-Cast Replica",
        "Commemorative Coin", "Bobblehead Figure", "Stadium Seat Replica",
        "Signed Photo Reprint",
    ],
}


def build_customers(rng):
    ids, names, regions, signups = [], [], [], []
    seen = set()
    start = date(2022, 1, 1)
    span_days = (date(2026, 6, 30) - start).days
    for cid in range(1, 501):
        # Ensure unique display names by suffixing on collision.
        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        if name in seen:
            name = f"{name} {rng.choice('ABCDEFGH')}."
        seen.add(name)
        ids.append(cid)
        names.append(name)
        regions.append(rng.choice(REGIONS))
        signups.append(start + timedelta(days=rng.randrange(span_days)))
    schema = pa.schema([
        ("customer_id", pa.int64()),
        ("customer_name", pa.string()),
        ("region", pa.string()),
        ("signup_date", pa.date32()),
    ])
    return pa.table(
        {"customer_id": ids, "customer_name": names, "region": regions, "signup_date": signups},
        schema=schema,
    )


def build_products(rng):
    ids, names, cats, prices = [], [], [], []
    # Price ranges chosen per category so revenue numbers look plausible.
    price_range = {
        "Trading Cards": (2.99, 149.99),
        "Accessories": (1.99, 39.99),
        "Apparel": (14.99, 59.99),
        "Collectibles": (9.99, 199.99),
    }
    pid = 0
    pool = []
    for cat, parts in PRODUCT_PARTS.items():
        for part in parts:
            pool.append((cat, part))
    assert len(pool) >= 50, f"product name pool too small: {len(pool)}"
    rng.shuffle(pool)
    for cat, part in pool[:50]:
        pid += 1
        lo, hi = price_range[cat]
        ids.append(pid)
        names.append(part)
        cats.append(cat)
        prices.append(round(rng.uniform(lo, hi), 2))
    schema = pa.schema([
        ("product_id", pa.int64()),
        ("product_name", pa.string()),
        ("category", pa.string()),
        ("unit_price", pa.float64()),
    ])
    return pa.table(
        {"product_id": ids, "product_name": names, "category": cats, "unit_price": prices},
        schema=schema,
    )


def build_orders(rng, n_rows, customer_ids, product_ids):
    ids, cids, pids, qtys, ts_list, statuses = [], [], [], [], [], []
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    span_seconds = int((datetime(2026, 8, 1, tzinfo=timezone.utc) - start).total_seconds())
    for oid in range(1, n_rows + 1):
        ids.append(oid)
        cids.append(rng.choice(customer_ids))
        pids.append(rng.choice(product_ids))
        qtys.append(rng.randint(1, 5))
        ts_list.append(start + timedelta(seconds=rng.randrange(span_seconds)))
        statuses.append(rng.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0])
    schema = pa.schema([
        ("order_id", pa.int64()),
        ("customer_id", pa.int64()),
        ("product_id", pa.int64()),
        ("quantity", pa.int32()),
        ("order_ts", pa.timestamp("us", tz="UTC")),
        ("status", pa.string()),
    ])
    return pa.table(
        {
            "order_id": ids,
            "customer_id": cids,
            "product_id": pids,
            "quantity": qtys,
            "order_ts": ts_list,
            "status": statuses,
        },
        schema=schema,
    )


def main():
    default_out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    parser = argparse.ArgumentParser(description="Generate sample parquet files.")
    parser.add_argument("--rows-orders", type=int, default=5000)
    parser.add_argument("--out-dir", default=os.path.normpath(default_out))
    args = parser.parse_args()

    rng = random.Random(SEED)

    customers = build_customers(rng)
    products = build_products(rng)
    orders = build_orders(
        rng,
        args.rows_orders,
        customers.column("customer_id").to_pylist(),
        products.column("product_id").to_pylist(),
    )

    written = []

    def write(table, subdir, filename):
        d = os.path.join(args.out_dir, subdir)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, filename)
        pq.write_table(table, path)
        written.append((path, table.num_rows))

    write(customers, "customers", "customers_000.parquet")
    write(products, "products", "products_000.parquet")

    # Split orders across 3 files; first files take the remainder.
    n = orders.num_rows
    base, rem = divmod(n, 3)
    offset = 0
    for i in range(3):
        size = base + (1 if i < rem else 0)
        write(orders.slice(offset, size), "orders", f"orders_{i:03d}.parquet")
        offset += size

    for path, rows in written:
        print(f"{path}: {rows} rows")


if __name__ == "__main__":
    main()
