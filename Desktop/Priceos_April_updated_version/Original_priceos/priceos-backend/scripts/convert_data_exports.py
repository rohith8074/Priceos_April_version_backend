#!/usr/bin/env python3
"""
scripts/convert_data_exports.py
───────────────────────────────
Converts the raw Airbtics Spark export files in data/ into the 3 CSV
formats that ingest_airbtics.py expects, then places them in da/airbtics/.

RUN:
    cd priceos-backend
    python scripts/convert_data_exports.py

OUTPUT files (written to da/airbtics/):
    demand_calendar_dubai.csv     ← daily demand/pacing from monthly actuals + forecast
    market_overview_dubai.csv     ← market-level ADR, occupancy, RevPAR by month
    comp_listings_dubai.csv       ← competitor properties with bedrooms, ADR, occupancy, ratings
"""

import csv
import json
import os
import statistics
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "da" / "airbtics"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── Utility ───────────────────────────────────────────────────────────────────

def safe_float(v) -> float:
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return 0.0

def month_to_days(year: int, month: int) -> list[str]:
    """Expand a YYYY-MM-01 month into individual YYYY-MM-DD dates."""
    import calendar
    _, days_in_month = calendar.monthrange(year, month)
    return [f"{year}-{month:02d}-{d:02d}" for d in range(1, days_in_month + 1)]

WEEKEND = {5, 6}  # Saturday=5, Sunday=6 (Python weekday)
DOW_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# ─── 1. demand_calendar_dubai.csv ──────────────────────────────────────────────
# Source: historical actuals (part-00294-56eb3db9...csv)
#       + forecast       (part-00294-cac8f0ac...csv)
# Aggregates: for each calendar date, average occupancy & ADR across all listings
# Output cols: date, demand_score, avg_price, pacing, day_of_week, is_weekend

def build_demand_calendar():
    source_files = [
        DATA_DIR / "part-00294-56eb3db9-d23c-4bfa-94f6-f328fafbfe54.c000.csv",  # historical
        DATA_DIR / "part-00294-cac8f0ac-16be-4a89-b16f-326fdca455ea.c000.csv",  # forecast
    ]

    # month_date → list of (occupancy, native_rate_avg) across listings
    monthly: dict[str, list[tuple[float, float]]] = defaultdict(list)

    for src in source_files:
        if not src.exists():
            print(f"  ⚠  Missing: {src.name}")
            continue
        with open(src, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                date = row.get("date", "").strip()
                if not date:
                    continue
                occ = safe_float(row.get("occupancy", 0))
                # Use AED (native) rate — more accurate for Dubai market
                rate = safe_float(row.get("native_rate_avg") or row.get("rate_avg") or 0)
                if occ > 0 or rate > 0:
                    monthly[date].append((occ, rate))

    if not monthly:
        print("  ❌ No data found for demand calendar")
        return 0

    out_path = OUT_DIR / "demand_calendar_dubai.csv"
    written = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "demand_score", "avg_price", "pacing", "day_of_week", "is_weekend"
        ])
        writer.writeheader()

        for month_date in sorted(monthly.keys()):
            pairs = monthly[month_date]
            avg_occ = statistics.mean(o for o, _ in pairs) if pairs else 0
            avg_rate = statistics.mean(r for _, r in pairs if r > 0) if any(r > 0 for _, r in pairs) else 0

            # Expand month into daily rows
            try:
                year, month, _ = map(int, month_date.split("-"))
            except Exception:
                continue

            for day_str in month_to_days(year, month):
                dt = datetime.strptime(day_str, "%Y-%m-%d")
                dow = dt.weekday()
                is_weekend = dow in WEEKEND

                # Demand score: occupancy as 0-100 scale, boosted slightly for weekends
                demand_score = round(avg_occ * 100 * (1.08 if is_weekend else 1.0), 1)
                demand_score = min(demand_score, 99.0)

                # Pacing: estimate = demand_score with small weekend premium
                pacing = round(demand_score * 0.95, 1)

                writer.writerow({
                    "date": day_str,
                    "demand_score": demand_score,
                    "avg_price": round(avg_rate, 2),
                    "pacing": pacing,
                    "day_of_week": DOW_NAMES[dow],
                    "is_weekend": str(is_weekend).lower(),
                })
                written += 1

    print(f"  ✅ demand_calendar_dubai.csv — {written} daily rows")
    return written


# ─── 2. market_overview_dubai.csv ──────────────────────────────────────────────
# Source: same historical + forecast files, aggregated at month level
# Output cols: date, adr, revpar, occupancy_rate, active_listings, demand_score

def build_market_overview():
    source_files = [
        DATA_DIR / "part-00294-56eb3db9-d23c-4bfa-94f6-f328fafbfe54.c000.csv",  # historical
        DATA_DIR / "part-00294-cac8f0ac-16be-4a89-b16f-326fdca455ea.c000.csv",  # forecast
    ]

    # month → {listing_ids: set, occs: [], rates: [], revenues: []}
    monthly: dict[str, dict] = defaultdict(lambda: {
        "listing_ids": set(), "occs": [], "rates": [], "revenues": []
    })

    for src in source_files:
        if not src.exists():
            continue
        with open(src, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                date = row.get("date", "").strip()
                lid = row.get("listing_id", "").strip()
                if not date:
                    continue
                occ = safe_float(row.get("occupancy", 0))
                rate = safe_float(row.get("native_rate_avg") or row.get("rate_avg") or 0)
                rev = safe_float(row.get("native_revenue") or row.get("revenue") or 0)
                monthly[date]["listing_ids"].add(lid)
                monthly[date]["occs"].append(occ)
                if rate > 0:
                    monthly[date]["rates"].append(rate)
                if rev > 0:
                    monthly[date]["revenues"].append(rev)

    out_path = OUT_DIR / "market_overview_dubai.csv"
    written = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "adr", "revpar", "occupancy_rate", "active_listings", "demand_score"
        ])
        writer.writeheader()

        for month_date in sorted(monthly.keys()):
            d = monthly[month_date]
            avg_occ = statistics.mean(d["occs"]) if d["occs"] else 0
            avg_rate = statistics.mean(d["rates"]) if d["rates"] else 0
            revpar = avg_rate * avg_occ
            active = len(d["listing_ids"])
            demand_score = round(avg_occ * 100, 1)

            writer.writerow({
                "date": month_date,
                "adr": round(avg_rate, 2),
                "revpar": round(revpar, 2),
                "occupancy_rate": round(avg_occ * 100, 1),
                "active_listings": active,
                "demand_score": demand_score,
            })
            written += 1

    print(f"  ✅ market_overview_dubai.csv — {written} monthly rows")
    return written


# ─── 3. comp_listings_dubai.csv ────────────────────────────────────────────────
# Source: part-00294-e685bf03...csv (full Airbnb listing details)
# Output cols: name, area, bedrooms, last_30d_occupancy, adr, rating, reviews

def infer_area(row: dict) -> str:
    """Try to infer Dubai area from latitude/longitude if not in data."""
    lat = safe_float(row.get("latitude", 0))
    lng = safe_float(row.get("longitude", 0))

    # Rough bounding boxes for major Dubai areas
    AREA_BOXES = [
        ("Dubai Marina",    (25.065, 25.095), (55.125, 55.155)),
        ("JBR",             (25.070, 25.085), (55.125, 55.145)),
        ("Downtown Dubai",  (25.185, 25.210), (55.265, 55.295)),
        ("Business Bay",    (25.175, 25.200), (55.245, 55.275)),
        ("Palm Jumeirah",   (25.095, 25.135), (55.115, 55.175)),
        ("DIFC",            (25.205, 25.220), (55.270, 55.290)),
        ("Jumeirah",        (25.175, 25.230), (55.200, 55.260)),
    ]

    for area, (lat_min, lat_max), (lng_min, lng_max) in AREA_BOXES:
        if lat_min <= lat <= lat_max and lng_min <= lng <= lng_max:
            return area

    return "Dubai"


def build_comp_listings():
    src = DATA_DIR / "part-00294-e685bf03-a693-439c-b3bb-b8b063bf0db5.c000.csv"
    # Try alternate name if above not found
    if not src.exists():
        candidates = list(DATA_DIR.glob("part-00294-e685bf03*.csv"))
        src = candidates[0] if candidates else None

    if not src or not src.exists():
        print("  ⚠  Competitor listings CSV not found — skipping comp_listings")
        return 0

    out_path = OUT_DIR / "comp_listings_dubai.csv"
    written = 0

    with open(src, newline="", encoding="utf-8-sig") as f_in, \
         open(out_path, "w", newline="", encoding="utf-8") as f_out:

        reader = csv.DictReader(f_in)
        writer = csv.DictWriter(f_out, fieldnames=[
            "name", "area", "bedrooms", "last_30d_occupancy", "adr", "rating", "reviews"
        ])
        writer.writeheader()

        for row in reader:
            name = (row.get("listing_name") or "").strip()
            bedrooms = row.get("bedrooms", "1")
            try:
                bedrooms = int(float(bedrooms))
            except Exception:
                bedrooms = 1

            # Use last-90-day occupancy as proxy for last-30-day (more stable)
            occ = safe_float(row.get("l90d_occupancy") or row.get("ttm_adjusted_occupancy") or row.get("ttm_occupancy") or 0)
            # AED native rate preferred
            adr = safe_float(row.get("l90d_avg_rate_native") or row.get("ttm_avg_rate_native") or row.get("ttm_avg_rate") or 0)

            rating = safe_float(row.get("rating_overall") or 0)
            reviews = safe_float(row.get("num_reviews") or 0)

            area = infer_area(row)

            if not name or adr == 0:
                continue

            writer.writerow({
                "name": name[:80],
                "area": area,
                "bedrooms": bedrooms,
                "last_30d_occupancy": round(occ * 100, 1),
                "adr": round(adr, 2),
                "rating": round(rating, 2),
                "reviews": int(reviews),
            })
            written += 1

    print(f"  ✅ comp_listings_dubai.csv — {written} competitor properties")
    return written


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print("Converting Airbtics Spark exports → ingest-ready CSVs")
    print(f"Output: {OUT_DIR}")
    print(f"{'='*60}\n")

    d1 = build_demand_calendar()
    d2 = build_market_overview()
    d3 = build_comp_listings()

    print(f"\n{'='*60}")
    if d1 + d2 + d3 > 0:
        print("✅ Conversion complete!")
        print(f"\nNext step — load into MongoDB:")
        print(f"  cd priceos-backend")
        print(f"  python scripts/ingest_airbtics.py")
        print(f"\nThis will populate AirbticsCache with:")
        print(f"  demand_calendar:2286:<date>  →  {d1} records")
        print(f"  market_overview:2286:<date>  →  {d2} records")
        print(f"  comp_listings:2286:<N>br     →  grouped by bedrooms")
    else:
        print("❌ Nothing was converted — check data/ folder for source files")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
