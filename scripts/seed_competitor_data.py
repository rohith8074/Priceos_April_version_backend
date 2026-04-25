#!/usr/bin/env python3
"""
scripts/seed_competitor_data.py
────────────────────────────────
Seeds Airbtics competitor data into 3 separate MongoDB collections:

  1. competitor_listings      — static listing details (lat, lon, bedrooms, name)
  2. competitor_performances  — per-listing per-month performance (raw, no aggregation)
  3. competitor_reviews       — per-listing per-month review counts

Data window: 7 months past + 7 months future from today (14 months total).
Rows outside this window are skipped.
No aggregation — every CSV row is stored as-is.

USAGE:
    cd priceos-backend
    python scripts/seed_competitor_data.py                 # all files
    python scripts/seed_competitor_data.py --file details  # only listing details
    python scripts/seed_competitor_data.py --file perf     # only performance CSVs
    python scripts/seed_competitor_data.py --file reviews  # only reviews CSV
    python scripts/seed_competitor_data.py --clear          # drop collections first
"""

import csv, os, sys, argparse, time, math
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Path bootstrap ────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
import asyncio

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR  = ROOT / "data"
MARKET_ID = os.environ.get("AIRBTICS_DUBAI_MARKET_ID", "2286")
MONTHS_WINDOW = 7  # 7 past + 7 future

# CSV file paths
FILE_HIST    = DATA_DIR / "part-00294-56eb3db9-d23c-4bfa-94f6-f328fafbfe54.c000.csv"
FILE_FORE    = DATA_DIR / "part-00294-cac8f0ac-16be-4a89-b16f-326fdca455ea.c000.csv"
FILE_DETAILS = sorted(DATA_DIR.glob("part-00294-e685bf03*.csv"))
FILE_REVIEWS = DATA_DIR / "part-00294-bc49a9e7-6fb2-4c78-8b36-2219e49e97d4.c000.csv"

# Date window: 7 months past → 7 months future
TODAY = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

def add_months(d: datetime, months: int) -> datetime:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    return d.replace(year=year, month=month, day=1)

WINDOW_START = add_months(TODAY, -MONTHS_WINDOW).strftime("%Y-%m-01")
WINDOW_END   = add_months(TODAY, MONTHS_WINDOW).strftime("%Y-%m-01")


# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_float(v) -> float:
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except Exception:
        return 0.0

def safe_int(v) -> int:
    try:
        return int(float(str(v).strip()))
    except Exception:
        return 0

def parse_amenities(raw: str) -> list[str]:
    """Parse comma-separated amenities string (may be quoted)."""
    if not raw or raw.strip() in ('""', "''", ""):
        return []
    return [a.strip() for a in raw.split(",") if a.strip()]

def in_window(date_str: str) -> bool:
    """Check if a YYYY-MM-01 date falls within our 7-past/7-future window."""
    return WINDOW_START <= date_str <= WINDOW_END


# ── Collection 1: Listing Details ─────────────────────────────────────────────

def build_details_ops(path: Path) -> tuple[list[UpdateOne], int]:
    """Parse listing details CSV → one UpdateOne per competitor listing."""
    ops = []
    raw = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            lid = row.get("listing_id", "").strip()
            if not lid:
                continue
            raw += 1
            ops.append(UpdateOne(
                {"marketId": MARKET_ID, "airbticsListingId": lid},
                {"$set": {
                    "marketId":         MARKET_ID,
                    "airbticsListingId": lid,
                    "listingName":      (row.get("listing_name") or "").strip()[:120],
                    "latitude":         safe_float(row.get("latitude", 0)),
                    "longitude":        safe_float(row.get("longitude", 0)),
                    "bedrooms":         safe_int(row.get("bedrooms", 1)),
                    "beds":             safe_int(row.get("beds", 0)) or None,
                    "baths":            safe_float(row.get("baths", 0)) or None,
                    "guests":           safe_int(row.get("guests", 0)) or None,
                    "hostName":         (row.get("host_name") or "").strip(),
                    "roomType":         (row.get("room_type") or "").strip(),
                    "amenities":        parse_amenities(row.get("amenities", "")),
                    "ratingOverall":    safe_float(row.get("rating_overall", 0)) or None,
                    "numReviews":       safe_int(row.get("num_reviews", 0)),
                    "currency":         (row.get("currency") or "AED").strip(),
                    "ttmOccupancy":     safe_float(row.get("ttm_occupancy", 0)) or None,
                    "ttmAvgRateNative": safe_float(row.get("ttm_avg_rate_native", 0)) or None,
                    "ttmRevenueNative": safe_float(row.get("ttm_revenue_native", 0)) or None,
                    "l90dOccupancy":    safe_float(row.get("l90d_occupancy", 0)) or None,
                    "l90dAvgRateNative": safe_float(row.get("l90d_avg_rate_native", 0)) or None,
                },
                "$setOnInsert": {"createdAt": datetime.now(timezone.utc)}},
                upsert=True,
            ))
    return ops, raw


# ── Collection 2: Performance ─────────────────────────────────────────────────

def build_perf_ops(path: Path, data_type: str) -> tuple[list[UpdateOne], int, int]:
    """Parse performance CSV → one UpdateOne per listing per month.
    Skips rows outside the 14-month window.
    Returns (ops, total_rows, skipped_rows).
    """
    ops = []
    total = 0
    skipped = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            date = row.get("date", "").strip()
            lid  = row.get("listing_id", "").strip()
            if not date or not lid:
                continue
            total += 1
            if not in_window(date):
                skipped += 1
                continue
            ops.append(UpdateOne(
                {"marketId": MARKET_ID, "airbticsListingId": lid, "date": date},
                {"$set": {
                    "marketId":           MARKET_ID,
                    "airbticsListingId":  lid,
                    "date":              date,
                    "dataType":          data_type,
                    "vacantDays":        safe_int(row.get("vacant_days", 0)),
                    "reservedDays":      safe_int(row.get("reserved_days", 0)),
                    "occupancy":         safe_float(row.get("occupancy", 0)),
                    "revenue":           safe_float(row.get("revenue", 0)),
                    "rateAvg":           safe_float(row.get("rate_avg", 0)),
                    "bookedRateAvg":     safe_float(row.get("booked_rate_avg", 0)),
                    "bookingLeadTimeAvg": safe_float(row.get("booking_lead_time_avg", 0)) or None,
                    "lengthOfStayAvg":   safe_float(row.get("length_of_stay_avg", 0)) or None,
                    "minNightsAvg":      safe_float(row.get("min_nights_avg", 0)) or None,
                    "nativeBookedRateAvg": safe_float(row.get("native_booked_rate_avg", 0)),
                    "nativeRateAvg":     safe_float(row.get("native_rate_avg", 0)),
                    "nativeRevenue":     safe_float(row.get("native_revenue", 0)),
                },
                "$setOnInsert": {"createdAt": datetime.now(timezone.utc)}},
                upsert=True,
            ))
    return ops, total, skipped


# ── Collection 3: Reviews ─────────────────────────────────────────────────────

def build_review_ops(path: Path) -> tuple[list[UpdateOne], int, int]:
    """Parse reviews CSV → one UpdateOne per listing per month.
    Skips rows outside the 14-month window.
    """
    ops = []
    total = 0
    skipped = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            date = row.get("date", "").strip()
            lid  = row.get("listing_id", "").strip()
            if not date or not lid:
                continue
            total += 1
            if not in_window(date):
                skipped += 1
                continue
            reviewers_raw = row.get("reviewers", "").strip().strip('"')
            reviewer_ids = [r.strip() for r in reviewers_raw.split(",") if r.strip()]
            ops.append(UpdateOne(
                {"marketId": MARKET_ID, "airbticsListingId": lid, "date": date},
                {"$set": {
                    "marketId":          MARKET_ID,
                    "airbticsListingId": lid,
                    "date":              date,
                    "numReviews":        safe_int(row.get("num_reviews", 0)),
                    "reviewerIds":       reviewer_ids,
                },
                "$setOnInsert": {"createdAt": datetime.now(timezone.utc)}},
                upsert=True,
            ))
    return ops, total, skipped


# ── Bulk write helper ─────────────────────────────────────────────────────────

async def bulk_write(collection, ops: list[UpdateOne], label: str) -> None:
    if not ops:
        print(f"   ⚠  No operations for {label}")
        return
    t0 = time.perf_counter()
    result = await collection.bulk_write(ops, ordered=False)
    elapsed = round((time.perf_counter() - t0) * 1000)
    print(f"   ✅ {label}: {result.upserted_count} inserted, "
          f"{result.modified_count} updated — {elapsed} ms")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(target: str | None, clear: bool) -> None:
    mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    db_name   = (os.environ.get("DATABASE_NAME")
                 or os.environ.get("MONGODB_DB")
                 or "priceos")

    client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db     = client[db_name]

    col_details = db["competitor_listings"]
    col_perf    = db["competitor_performances"]
    col_reviews = db["competitor_reviews"]

    print(f"\n{'='*65}")
    print(f"  PriceOS Competitor Data Seeder (3-Collection Architecture)")
    print(f"  Database     : {db_name}")
    print(f"  Market ID    : {MARKET_ID}")
    print(f"  Date window  : {WINDOW_START} → {WINDOW_END} (±{MONTHS_WINDOW} months)")
    print(f"{'='*65}\n")

    if clear:
        print("🗑  Clearing existing competitor data...")
        r1 = await col_details.delete_many({"marketId": MARKET_ID})
        r2 = await col_perf.delete_many({"marketId": MARKET_ID})
        r3 = await col_reviews.delete_many({"marketId": MARKET_ID})
        print(f"   Deleted: {r1.deleted_count} details, {r2.deleted_count} perf, {r3.deleted_count} reviews\n")

    run_all = target is None
    t_total = time.perf_counter()

    # ── 1. Listing Details ────────────────────────────────────────────────────
    if run_all or target == "details":
        print("📂 Collection 1 — competitor_listings (static details)")
        if not FILE_DETAILS:
            print("   ❌ part-00294-e685bf03*.csv not found — skipping")
        else:
            path = FILE_DETAILS[0]
            print(f"   {path.name}")
            ops, rows = build_details_ops(path)
            print(f"   📊 {rows:,} raw rows → {len(ops)} listing detail documents")
            await bulk_write(col_details, ops, "competitor_listings")

    # ── 2. Historical Performance ─────────────────────────────────────────────
    if run_all or target == "perf":
        print(f"\n📂 Collection 2 — competitor_performances (per-listing per-month)")

        # File 1: historical
        print(f"   📁 Historical: {FILE_HIST.name}")
        if not FILE_HIST.exists():
            print("   ❌ File not found — skipping")
        else:
            ops, total, skipped = build_perf_ops(FILE_HIST, "historical")
            print(f"   📊 {total:,} raw rows → {len(ops)} in window, {skipped} skipped (outside ±{MONTHS_WINDOW}mo)")
            await bulk_write(col_perf, ops, "historical performance")

        # File 2: forecast
        print(f"   📁 Forecast:   {FILE_FORE.name}")
        if not FILE_FORE.exists():
            print("   ❌ File not found — skipping")
        else:
            ops, total, skipped = build_perf_ops(FILE_FORE, "forecast")
            print(f"   📊 {total:,} raw rows → {len(ops)} in window, {skipped} skipped (outside ±{MONTHS_WINDOW}mo)")
            await bulk_write(col_perf, ops, "forecast performance")

    # ── 3. Reviews ────────────────────────────────────────────────────────────
    if run_all or target == "reviews":
        print(f"\n📂 Collection 3 — competitor_reviews (per-listing per-month)")
        print(f"   {FILE_REVIEWS.name}")
        if not FILE_REVIEWS.exists():
            print("   ❌ File not found — skipping")
        else:
            ops, total, skipped = build_review_ops(FILE_REVIEWS)
            print(f"   📊 {total:,} raw rows → {len(ops)} in window, {skipped} skipped")
            await bulk_write(col_reviews, ops, "competitor_reviews")

    total_ms = round((time.perf_counter() - t_total) * 1000)
    print(f"\n{'='*65}")
    print(f"  ✅ Done in {total_ms} ms")
    print(f"\n  Collections in '{db_name}':")
    print(f"    competitor_listings       — static details (lat/lon/bedrooms)")
    print(f"    competitor_performances   — per-listing per-month (raw, no aggregation)")
    print(f"    competitor_reviews        — per-listing per-month review counts")
    print(f"{'='*65}\n")

    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Airbtics competitor data into 3 collections")
    parser.add_argument(
        "--file",
        choices=["details", "perf", "reviews"],
        default=None,
        help="details=listing details, perf=performance CSVs, reviews=review counts (omit for all)"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Drop existing competitor data before seeding"
    )
    args = parser.parse_args()
    asyncio.run(main(args.file, args.clear))
