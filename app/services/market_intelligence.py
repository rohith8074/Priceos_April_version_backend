import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.services.lyzr import call_lyzr_agent
from app.models.market_event import MarketEvent
from beanie import PydanticObjectId
from bson import ObjectId

def normalize_impact(impact: Any) -> str:
    imp = str(impact or "medium").lower()
    if "high" in imp: return "high"
    if "low" in imp: return "low"
    return "medium"

def safe_float(val: Any) -> float:
    try:
        if isinstance(val, str):
            val = val.replace("%", "").strip()
        return float(val)
    except:
        return 0.0

async def sync_external_market_intelligence(
    org_id: ObjectId, 
    city: str, 
    area: str, 
    date_from: str, 
    date_to: str,
    force: bool = False
) -> Dict[str, Any]:
    """
    Calls Agent 6 (Marketing Intelligence) to perform an internet search for news and events.
    Upserts findings into the MarketEvent collection.
    """
    # 1. Check for recent sync to avoid redundant Perplexity calls (cost/latency)
    if not force:
        cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        existing_count = await MarketEvent.find(
            MarketEvent.orgId == PydanticObjectId(str(org_id)),
            MarketEvent.source == "perplexity",
            MarketEvent.updatedAt >= cutoff
        ).count()
        
        if existing_count > 0:
            print(f"    [INTEL] Recent perplexity data found for {city}. Skipping live sync.")
            return {"success": True, "source": "db", "count": existing_count}

    agent_id = os.environ.get("Marketing_Agent_ID")
    if not agent_id:
        print("    [INTEL ERROR] Marketing_Agent_ID not found in environment.")
        return {"success": False, "error": "Marketing_Agent_ID not configured"}

    print(f"    [INTEL] Triggering Agent 6 (Marketing Intelligence) for {city}/{area}...")

    # 2. Construct the research prompt following Agent 6's required context
    prompt = f"""
    SYSTEM_INVOCATION: Perform a full 7-step Intelligence Sweep (Geopolitical -> Holidays -> Events -> Local -> Economic -> Weather -> Viral).
    
    MARKET_CONTEXT:
    - City: {city}
    - Area: {area}
    - Date Window: {date_from} to {date_to}
    
    INSTRUCTIONS:
    - Search the internet using your Perplexity capabilities.
    - Return a single STABLE JSON block matching the 'market_research_response' schema.
    - Focus on finding real signals that justify pricing adjustments.
    - Every event/news must include a source URL.
    """

    res = await call_lyzr_agent(agent_id=agent_id, message=prompt)
    if not res.ok:
        return {"success": False, "error": res.error}

    data = res.parsed_json or {}
    
    # 3. Process and Upsert findings
    results = {"inserted": 0, "updated": 0, "signals": []}
    
    # We combine events, news, and daily_events into the MarketEvent collection
    # Distinguishing them by 'category' metadata if possible
    
    all_signals = []
    
    # Process 'events'
    for ev in data.get("events", []):
        all_signals.append({
            "name": ev.get("title", "Event"),
            "startDate": ev.get("date_start"),
            "endDate": ev.get("date_end"),
            "impact": ev.get("impact", "medium"),
            "uplift": ev.get("suggested_premium_pct", 0),
            "desc": ev.get("description", ""),
            "src": ev.get("source", "perplexity"),
            "cat": "event"
        })
        
    # Process 'news'
    for n in data.get("news", []):
        all_signals.append({
            "name": n.get("headline", "News"),
            "startDate": n.get("date"),
            "endDate": n.get("date"),
            "impact": n.get("demand_impact", "neutral").split("_")[-1] if "_" in n.get("demand_impact", "") else "medium",
            "uplift": n.get("suggested_premium_pct", 0),
            "desc": n.get("description", ""),
            "src": n.get("source", "perplexity"),
            "cat": "news"
        })

    # Process 'holidays'
    for h in data.get("holidays", []):
        all_signals.append({
            "name": h.get("name", "Holiday"),
            "startDate": h.get("date_start"),
            "endDate": h.get("date_end"),
            "impact": h.get("impact", "medium"),
            "uplift": h.get("premium_pct", 0),
            "desc": f"National/Public Holiday in {city}",
            "src": h.get("source", "perplexity"),
            "cat": "holiday"
        })

    # 4. Save to MongoDB
    for s in all_signals:
        if not s["name"] or not s["startDate"]: continue
        
        # Check for existing by name + start date to avoid duplicates
        existing = await MarketEvent.find_one(
            MarketEvent.orgId == PydanticObjectId(str(org_id)),
            MarketEvent.name == s["name"],
            MarketEvent.startDate == s["startDate"]
        )
        
        if existing:
            existing.endDate = s["endDate"]
            existing.impactLevel = normalize_impact(s["impact"])
            existing.upliftPct = safe_float(s["uplift"])
            existing.description = s["desc"]
            existing.source = s["src"]
            existing.updatedAt = datetime.now(timezone.utc)
            await existing.save()
            results["updated"] += 1
        else:
            new_ev = MarketEvent(
                orgId=PydanticObjectId(str(org_id)),
                name=s["name"],
                startDate=s["startDate"],
                endDate=s["endDate"],
                area=area or city,
                impactLevel=normalize_impact(s["impact"]),
                upliftPct=safe_float(s["uplift"]),
                description=s["desc"],
                source=s["src"],
                isActive=True
            )
            await new_ev.insert()
            results["inserted"] += 1
            
    print(f"    [INTEL] Sync complete. Added {results['inserted']} signals, updated {results['updated']}.")
    return {"success": True, "results": results}

async def sync_internet_benchmark(
    org_id: ObjectId,
    listing_id: ObjectId,
    city: str,
    area: str,
    bedrooms: int,
    date_from: str,
    date_to: str
) -> Dict[str, Any]:
    """
    Calls Agent 7 (Benchmark Agent) as a fallback for internet search of competitor rates.
    """
    agent_id = os.environ.get("LYZR_Competitor_Benchmark_Agent_ID")
    if not agent_id:
        return {"success": False, "error": "Benchmark agent ID not configured"}

    print(f"    [BENCHMARK] Triggering Agent 7 (Internet Fallback) for {area}...")

    prompt = f"""
    FALLBACK_RESEARCH: No cached Airbtics neighborhood data found for this property.
    
    PROPERTY_CONTEXT:
    - City: {city}
    - Area: {area}
    - Bedrooms: {bedrooms}
    - Analysis Window: {date_from} to {date_to}
    
    INSTRUCTIONS:
    - Perform an internet search for similar {bedrooms}-bedroom listings in {area}, {city}.
    - Calculate P25, P50, P75, P90 percentiles based on your findings.
    - Return a structured JSON response matching the 'benchmark_response' schema.
    """

    res = await call_lyzr_agent(agent_id=agent_id, message=prompt)
    if not res.ok:
        return {"success": False, "error": res.error}

    # Agent 7 output will be used by the CRO Router/PriceGuard
    # We can also cache it in the BenchmarkData collection if needed
    return {"success": True, "data": res.parsed_json}
