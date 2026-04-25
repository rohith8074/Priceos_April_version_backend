#!/usr/bin/env python3
"""
scripts/seed_market_data.py
────────────────────────────
Seeds Airbtics market data into MongoDB (database: priceos).
Uses bulk upserts — one round-trip per file, completes in < 10 seconds.

USAGE:
    cd priceos-backend
    python scripts/seed_market_data.py             # all 3 files
    python scripts/seed_market_data.py --file 1    # File 1: historical CSV  → demand_calendar + market_overview
    python scripts/seed_market_data.py --file 2    # File 2: forecast CSV    → demand_calendar + market_overview
    python scripts/seed_market_data.py --file 3    # File 3: comp listings   → comp_listings

COLLECTION:  airbtics_caches  (database: priceos)
CACHE KEYS:
    demand_calendar:2286:YYYY-MM-DD   ← ~730 docs (daily pacing)
    market_overview:2286:YYYY-MM-01   ← ~24 docs  (monthly ADR/occupancy)
    comp_listings:2286:Nbr            ← ~5 docs   (per-bedroom comp summary)
"""

import csv, os, sys, argparse, statistics, calendar, time
from collections import defaultdict
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
TTL_DAYS  = 365

FILE1 = DATA_DIR / "historical_market_performance.csv"   # historical
FILE2 = DATA_DIR / "future_performance_projections.csv"   # forecast
FILE3 = sorted(DATA_DIR.glob("listing_metadata_ttm.csv"))                        # comp listings

WEEKEND_DAYS = {5, 6}
DOW_NAMES    = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_float(v) -> float:
    try:
        return float(str(v).replace(",","").replace("%","").strip())
    except Exception:
        return 0.0

def month_to_days(year: int, month: int) -> list[str]:
    _, days = calendar.monthrange(year, month)
    return [f"{year}-{month:02d}-{d:02d}" for d in range(1, days + 1)]

def percentile(lst: list[float], p: int) -> float:
    if not lst:
        return 0.0
    s = sorted(lst)
    return s[max(0, min(int(len(s) * p / 100), len(s) - 1))]

def infer_area(row: dict) -> str:
    lat = safe_float(row.get("latitude", 0))
    lng = safe_float(row.get("longitude", 0))
    BOXES = [
        ("Dubai Marina",   (25.065, 25.095), (55.125, 55.155)),
        ("JBR",            (25.070, 25.085), (55.125, 55.145)),
        ("Downtown Dubai", (25.185, 25.210), (55.265, 55.295)),
        ("Business Bay",   (25.175, 25.200), (55.245, 55.275)),
        ("Palm Jumeirah",  (25.095, 25.135), (55.115, 55.175)),
        ("DIFC",           (25.205, 25.220), (55.270, 55.290)),
        ("Jumeirah",       (25.175, 25.230), (55.200, 55.260)),
        ("JLT",            (25.058, 25.080), (55.140, 55.165)),
        ("JVC",            (25.035, 25.065), (55.185, 55.215)),
    ]
    for area, (lmin, lmax), (lgmin, lgmax) in BOXES:
        if lmin <= lat <= lmax and lgmin <= lng <= lgmax:
            return area
    return "Dubai"

def expires() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=TTL_DAYS)

def make_op(key: str, data: dict) -> UpdateOne:
    """Build a single bulk upsert operation."""
    now = datetime.now(timezone.utc)
    return UpdateOne(
        {"cacheKey": key},
        {"$set": {"cacheKey": key, "data": data, "expiresAt": expires(), "updatedAt": now},
         "$setOnInsert": {"createdAt": now}},
        upsert=True
    )


# ── File 1 & 2: historical + forecast CSVs ───────────────────────────────────

def build_ops_from_performance_csv(path: Path) -> tuple[list[UpdateOne], list[UpdateOne], int]:
    """
    Returns (demand_ops, market_ops, raw_row_count).
    demand_ops  → demand_calendar:2286:YYYY-MM-DD  (one per calendar day)
    market_ops  → market_overview:2286:YYYY-MM-01  (one per month)
    Deduplicates by key — if the same month appears for many listings,
    they are averaged; only one document per date/month is written.
    """
    monthly_demand: dict[str, list[tuple[float, float]]] = defaultdict(list)
    monthly_market: dict[str, dict]                       = defaultdict(lambda: {
        "ids": set(), "occs": [], "rates": [], "revs": []
    })
    raw_rows = 0

    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            date = row.get("date","").strip()
            lid  = row.get("listing_id","").strip()
            if not date:
                continue
            occ  = safe_float(row.get("occupancy", 0))
            rate = safe_float(row.get("native_rate_avg") or row.get("rate_avg") or 0)
            rev  = safe_float(row.get("native_revenue") or row.get("revenue") or 0)
            if occ > 0 or rate > 0:
                monthly_demand[date].append((occ, rate))
            monthly_market[date]["ids"].add(lid)
            monthly_market[date]["occs"].append(occ)
            if rate > 0:
                monthly_market[date]["rates"].append(rate)
            if rev > 0:
                monthly_market[date]["revs"].append(rev)
            raw_rows += 1

    # ── demand_calendar ops ──
    demand_ops: list[UpdateOne] = []
    seen_days: set[str] = set()
    for month_date in sorted(monthly_demand.keys()):
        pairs    = monthly_demand[month_date]
        avg_occ  = statistics.mean(o for o, _ in pairs) if pairs else 0
        avg_rate = statistics.mean(r for _, r in pairs if r > 0) if any(r > 0 for _, r in pairs) else 0
        try:
            year, month, _ = map(int, month_date.split("-"))
        except Exception:
            continue
        for day_str in month_to_days(year, month):
            if day_str in seen_days:
                continue
            seen_days.add(day_str)
            dt = datetime.strptime(day_str, "%Y-%m-%d")
            dow = dt.weekday()
            is_wknd = dow in WEEKEND_DAYS
            score   = round(min(avg_occ * 100 * (1.08 if is_wknd else 1.0), 99.0), 1)
            tier    = "high" if score >= 70 else ("medium" if score >= 40 else "low")
            demand_ops.append(make_op(f"demand_calendar:{MARKET_ID}:{day_str}", {
                "marketId": MARKET_ID, "date": day_str,
                "demandScore": score, "avgPrice": round(avg_rate, 2),
                "pacing": round(score * 0.95, 1), "demandTier": tier,
                "dayOfWeek": DOW_NAMES[dow], "isWeekend": is_wknd,
                "source": "seed_script", "uploadedAt": datetime.now(timezone.utc).isoformat(),
            }))

    # ── market_overview ops ──
    market_ops: list[UpdateOne] = []
    seen_months: set[str] = set()
    for month_date in sorted(monthly_market.keys()):
        if month_date in seen_months:
            continue
        seen_months.add(month_date)
        d       = monthly_market[month_date]
        avg_occ = statistics.mean(d["occs"]) if d["occs"] else 0
        avg_adr = statistics.mean(d["rates"]) if d["rates"] else 0
        market_ops.append(make_op(f"market_overview:{MARKET_ID}:{month_date}", {
            "marketId": MARKET_ID, "date": month_date,
            "adr": round(avg_adr, 2), "revpar": round(avg_adr * avg_occ, 2),
            "occupancyRate": round(avg_occ * 100, 1),
            "activeListings": len(d["ids"]),
            "demandScore": round(avg_occ * 100, 1),
            "source": "seed_script", "uploadedAt": datetime.now(timezone.utc).isoformat(),
        }))

    return demand_ops, market_ops, raw_rows


# ── File 3: competitor listings CSV ──────────────────────────────────────────

def build_ops_from_comp_csv(path: Path) -> tuple[list[UpdateOne], int]:
    """
    Returns (comp_ops, raw_row_count).
    Writes one doc per unique bedroom count: comp_listings:2286:Nbr
    """
    bedroom_groups: dict[int, list[dict]] = defaultdict(list)
    raw_rows = 0

    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("listing_name") or "").strip()
            try:
                beds = int(float(row.get("bedrooms", row.get("bedroom_count","1"))))
            except Exception:
                beds = 1
            occ  = safe_float(row.get("l90d_occupancy") or row.get("ttm_adjusted_occupancy") or row.get("ttm_occupancy") or 0)
            adr  = safe_float(row.get("l90d_avg_rate_native") or row.get("ttm_avg_rate_native") or row.get("ttm_avg_rate") or 0)
            if not name or adr == 0:
                continue
            bedroom_groups[beds].append({
                "name": name[:80], "area": infer_area(row),
                "adr": adr, "occupancy": round(occ * 100, 1),
                "rating": round(safe_float(row.get("rating_overall") or 0), 2),
                "reviews": int(safe_float(row.get("num_reviews") or 0)),
            })
            raw_rows += 1

    ops: list[UpdateOne] = []
    for beds, comps in sorted(bedroom_groups.items()):
        adrs = sorted(c["adr"] for c in comps)
        occs = [c["occupancy"] for c in comps]
        ops.append(make_op(f"comp_listings:{MARKET_ID}:{beds}br", {
            "marketId": MARKET_ID, "bedrooms": beds, "compCount": len(comps),
            "p25Adr": round(percentile(adrs, 25), 2),
            "p50Adr": round(percentile(adrs, 50), 2),
            "p75Adr": round(percentile(adrs, 75), 2),
            "p90Adr": round(percentile(adrs, 90), 2),
            "avgAdr": round(statistics.mean(adrs), 2) if adrs else 0,
            "avgOccupancy": round(statistics.mean(occs), 1) if occs else 0,
            "comps": comps[:50],
            "source": "seed_script", "uploadedAt": datetime.now(timezone.utc).isoformat(),
        }))

    return ops, raw_rows


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

async def main(target: str | None) -> None:
    mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    db_name   = (os.environ.get("DATABASE_NAME")
                 or os.environ.get("MONGODB_DB")
                 or "priceos")

    client     = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=5000)
    collection = client[db_name]["airbtics_caches"]

    # Ensure index on cacheKey for fast upserts.
    # Use create_index without unique=True so it works even if the index already
    # exists as non-unique (MongoDB raises OperationFailure on option mismatch).
    try:
        await collection.create_index("cacheKey", background=True)
        await collection.create_index("expiresAt", background=True)
    except Exception:
        pass  # indexes already exist — safe to continue

    print(f"\n{'='*60}")
    print(f"  PriceOS Market Data Seeder")
    print(f"  Database   : {db_name}")
    print(f"  Collection : airbtics_caches")
    print(f"  Market ID  : {MARKET_ID}")
    print(f"{'='*60}\n")

    run_all = target is None
    t_total = time.perf_counter()

    # ── File 1: Historical CSV ────────────────────────────────────────────────
    if run_all or target == "1":
        print(f"📂 File 1 — Historical performance")
        print(f"   {FILE1.name}")
        if not FILE1.exists():
            print("   ❌ File not found — skipping")
        else:
            d_ops, m_ops, rows = build_ops_from_performance_csv(FILE1)
            print(f"   📊 {rows:,} raw rows → {len(d_ops)} demand_calendar + {len(m_ops)} market_overview keys")
            await bulk_write(collection, d_ops, "demand_calendar (historical)")
            await bulk_write(collection, m_ops, "market_overview  (historical)")

    # ── File 2: Forecast CSV ──────────────────────────────────────────────────
    if run_all or target == "2":
        print(f"\n📂 File 2 — Forecast performance")
        print(f"   {FILE2.name}")
        if not FILE2.exists():
            print("   ❌ File not found — skipping")
        else:
            d_ops, m_ops, rows = build_ops_from_performance_csv(FILE2)
            print(f"   📊 {rows:,} raw rows → {len(d_ops)} demand_calendar + {len(m_ops)} market_overview keys")
            await bulk_write(collection, d_ops, "demand_calendar (forecast)  ")
            await bulk_write(collection, m_ops, "market_overview  (forecast)  ")

    # ── File 3: Competitor listings CSV ──────────────────────────────────────
    if run_all or target == "3":
        print(f"\n📂 File 3 — Competitor listings")
        if not FILE3:
            print("   ❌ part-00294-e685bf03*.csv not found — skipping")
        else:
            path = FILE3[0]
            print(f"   {path.name}")
            c_ops, rows = build_ops_from_comp_csv(path)
            print(f"   📊 {rows:,} raw rows → {len(c_ops)} comp_listings keys "
                  f"(grouped by bedroom count)")
            for op in c_ops:
                key = op._filter["cacheKey"]
                beds_doc = op._doc["$set"]["data"]
                print(f"      {key}: {beds_doc['compCount']} comps  "
                      f"P25={beds_doc['p25Adr']} P50={beds_doc['p50Adr']} "
                      f"P75={beds_doc['p75Adr']} P90={beds_doc['p90Adr']} AED")
            await bulk_write(collection, c_ops, "comp_listings               ")

    total_ms = round((time.perf_counter() - t_total) * 1000)
    print(f"\n{'='*60}")
    print(f"  ✅ Done in {total_ms} ms")
    print(f"\n  Cache keys in '{db_name}'.airbtics_caches:")
    print(f"    demand_calendar:{MARKET_ID}:YYYY-MM-DD")
    print(f"    market_overview:{MARKET_ID}:YYYY-MM-01")
    print(f"    comp_listings:{MARKET_ID}:Nbr")
    print(f"{'='*60}\n")

    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Airbtics market data — file by file")
    parser.add_argument(
        "--file",
        choices=["1", "2", "3"],
        default=None,
        help="1=historical, 2=forecast, 3=comp listings  (omit to run all)"
    )
    args = parser.parse_args()
    asyncio.run(main(args.file))
