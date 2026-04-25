#!/usr/bin/env python3
"""
scripts/ingest_airbtics.py
──────────────────────────
Reads Airbtics CSV exports from data/airbtics/ and upserts them into the
AirbticsCache MongoDB collection so the pricing engine uses them
identically to the live API path.

USAGE:
    python scripts/ingest_airbtics.py                    # all files
    python scripts/ingest_airbtics.py --file demand      # only demand calendar

SUPPORTED FILES (place in data/airbtics/):
    market_overview*.csv      → cacheKey: "market_overview:<market_id>:<date>"
    demand_calendar*.csv      → cacheKey: "demand_calendar:<market_id>:<date>"
    comp_listings*.csv        → cacheKey: "comp_listings:<market_id>:<bedrooms>"
"""

import asyncio
import csv
import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── Bootstrap Django-style path so we can import app modules ──────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.airbtics_cache import AirbticsCache

DATA_DIR = Path(__file__).parent.parent / "data" / "airbtics"
MARKET_ID = os.environ.get("AIRBTICS_DUBAI_MARKET_ID", "2286")
TTL_DAYS = 30  # How long to treat uploaded data as fresh


def parse_float(v: str) -> float | None:
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except Exception:
        return None


async def upsert(key: str, data: dict) -> None:
    expires = datetime.now(timezone.utc) + timedelta(days=TTL_DAYS)
    existing = await AirbticsCache.find_one(AirbticsCache.cacheKey == key)
    if existing:
        existing.data = data
        existing.expiresAt = expires
        existing.updatedAt = datetime.now(timezone.utc)
        await existing.save()
        print(f"  Updated: {key}")
    else:
        doc = AirbticsCache(cacheKey=key, data=data, expiresAt=expires)
        await doc.insert()
        print(f"  Inserted: {key}")


# ── Ingestors ──────────────────────────────────────────────────────────────────

async def ingest_market_overview(file: Path) -> int:
    """
    Expected columns (Airbtics Market Overview export):
    date, adr, revpar, occupancy_rate, active_listings, demand_score
    """
    count = 0
    with open(file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        # Normalise header names to lowercase with underscores
        rows = [{k.lower().strip().replace(" ", "_"): v for k, v in row.items()} for row in reader]

    for row in rows:
        date = row.get("date") or row.get("month") or ""
        if not date:
            continue
        key = f"market_overview:{MARKET_ID}:{date}"
        data = {
            "marketId": MARKET_ID,
            "date": date,
            "adr": parse_float(row.get("adr", row.get("average_daily_rate", "0"))),
            "revpar": parse_float(row.get("revpar", row.get("revenue_per_available_room", "0"))),
            "occupancyRate": parse_float(row.get("occupancy_rate", row.get("occupancy", "0"))),
            "activeListings": parse_float(row.get("active_listings", row.get("listings", "0"))),
            "demandScore": parse_float(row.get("demand_score", row.get("demand", "0"))),
            "source": "csv_upload",
            "uploadedAt": datetime.now(timezone.utc).isoformat()
        }
        await upsert(key, data)
        count += 1
    return count


async def ingest_demand_calendar(file: Path) -> int:
    """
    Expected columns:
    date, demand_score, avg_price, pacing, day_of_week, is_weekend
    """
    count = 0
    with open(file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [{k.lower().strip().replace(" ", "_"): v for k, v in row.items()} for row in reader]

    for row in rows:
        date = row.get("date", "")
        if not date:
            continue
        key = f"demand_calendar:{MARKET_ID}:{date}"
        demand = parse_float(row.get("demand_score", row.get("demand", "0"))) or 0
        avg_price = parse_float(row.get("avg_price", row.get("average_price", row.get("adr", "0")))) or 0
        pacing = parse_float(row.get("pacing", row.get("booking_pace", "0"))) or 0

        # Classify demand tier automatically if not provided
        if demand >= 80:
            tier = "high"
        elif demand >= 50:
            tier = "medium"
        else:
            tier = "low"

        data = {
            "marketId": MARKET_ID,
            "date": date,
            "demandScore": demand,
            "avgPrice": avg_price,
            "pacing": pacing,
            "demandTier": row.get("demand_tier", tier),
            "dayOfWeek": row.get("day_of_week", ""),
            "isWeekend": str(row.get("is_weekend", "")).lower() in ("true", "1", "yes"),
            "source": "csv_upload",
            "uploadedAt": datetime.now(timezone.utc).isoformat()
        }
        await upsert(key, data)
        count += 1
    return count


async def ingest_comp_listings(file: Path) -> int:
    """
    Expected columns:
    name, area, bedrooms, last_30d_occupancy, adr, avg_price, rating, reviews
    """
    # Group by bedrooms for a percentile summary
    from collections import defaultdict

    count = 0
    bedroom_groups: dict[int, list[dict]] = defaultdict(list)

    with open(file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [{k.lower().strip().replace(" ", "_"): v for k, v in row.items()} for row in reader]

    for row in rows:
        beds_str = row.get("bedrooms", row.get("bedroom_count", "1"))
        try:
            beds = int(float(beds_str))
        except Exception:
            beds = 1
        bedroom_groups[beds].append(row)
        count += 1

    # Build per-bedroom-count comp summaries
    import statistics

    for beds, comps in bedroom_groups.items():
        adrs = [parse_float(r.get("adr", r.get("avg_price", r.get("average_price", "0")))) or 0 for r in comps]
        occs = [parse_float(r.get("last_30d_occupancy", r.get("occupancy", "0"))) or 0 for r in comps]

        adrs_sorted = sorted(adrs)
        n = len(adrs_sorted)

        def percentile(lst, p):
            if not lst:
                return 0
            i = int(len(lst) * p / 100)
            return lst[min(i, len(lst) - 1)]

        key = f"comp_listings:{MARKET_ID}:{beds}br"
        data = {
            "marketId": MARKET_ID,
            "bedrooms": beds,
            "compCount": n,
            "p25Adr": round(percentile(adrs_sorted, 25), 2),
            "p50Adr": round(percentile(adrs_sorted, 50), 2),
            "p75Adr": round(percentile(adrs_sorted, 75), 2),
            "avgAdr": round(statistics.mean(adrs), 2) if adrs else 0,
            "avgOccupancy": round(statistics.mean(occs), 2) if occs else 0,
            "comps": [
                {
                    "name": r.get("name", r.get("listing_name", "")),
                    "area": r.get("area", r.get("neighbourhood", "")),
                    "adr": parse_float(r.get("adr", r.get("avg_price", "0"))),
                    "occupancy": parse_float(r.get("last_30d_occupancy", r.get("occupancy", "0"))),
                }
                for r in comps[:50]  # cap at 50 to keep doc size reasonable
            ],
            "source": "csv_upload",
            "uploadedAt": datetime.now(timezone.utc).isoformat()
        }
        await upsert(key, data)

    return count


# ── Main ───────────────────────────────────────────────────────────────────────

async def main(target: str | None) -> None:
    # Connect to MongoDB
    mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("MONGODB_DB", "priceos_db")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.get_database(db_name)
    await init_beanie(database=db, document_models=[AirbticsCache])

    print(f"\n{'='*60}")
    print(f"Airbtics CSV Ingestion — Market ID: {MARKET_ID}")
    print(f"Data directory: {DATA_DIR}")
    print(f"{'='*60}\n")

    files = sorted(DATA_DIR.glob("*.csv"))
    if not files:
        print(f"⚠  No CSV files found in {DATA_DIR}")
        print("   Download data from https://airbtics.com and place CSVs here.")
        return

    for file in files:
        name = file.name.lower()
        if target and target not in name:
            continue

        print(f"\n📂 Processing: {file.name}")

        if "market_overview" in name or "market-overview" in name:
            n = await ingest_market_overview(file)
            print(f"   ✅ {n} market overview records ingested")

        elif "demand" in name:
            n = await ingest_demand_calendar(file)
            print(f"   ✅ {n} demand calendar records ingested")

        elif "comp" in name or "listing" in name or "competitor" in name:
            n = await ingest_comp_listings(file)
            print(f"   ✅ {n} competitor listings ingested")

        else:
            print(f"   ⚠  Unrecognised file pattern — skipping")
            print(f"      Rename to: market_overview_*.csv, demand_calendar_*.csv, or comp_listings_*.csv")

    print(f"\n{'='*60}")
    print("Ingestion complete. Data is now available in AirbticsCache.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Airbtics CSV exports into MongoDB")
    parser.add_argument("--file", help="Filter by filename pattern (e.g. demand, market, comp)", default=None)
    args = parser.parse_args()
    asyncio.run(main(args.file))
