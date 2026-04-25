import os
import asyncio
import httpx
from datetime import datetime, timedelta
import re
from typing import List, Dict, Any, Tuple
from app.models.market_event import MarketEvent
from bson import ObjectId

def classify_impact(category: str, attendance: int = 0) -> Tuple[str, float]:
    high_keywords = ["formula", "f1", "expo", "gitex", "world cup", "cup final", "grand prix", "fashion week", "art dubai", "dubai airshow", "ufc", "boxing", "concert", "festival", "new year"]
    low_keywords = ["webinar", "workshop", "networking", "seminar"]
    cat_lower = category.lower()
    
    if any(k in cat_lower for k in high_keywords):
        return ("high", 30.0)
    if any(k in cat_lower for k in low_keywords):
        return ("low", 5.0)
    if attendance > 10000:
        return ("high", 25.0)
    if attendance > 2000:
        return ("medium", 15.0)
    return ("medium", 12.0)

async def fetch_eventbrite(days_ahead=90, city="Dubai") -> List[Dict[str, Any]]:
    api_key = os.environ.get("EVENTBRITE_API_KEY")
    if not api_key: return []
    
    events = []
    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=days_ahead)
    
    url = "https://www.eventbriteapi.com/v3/events/search/"
    params = {
        "location.address": city,
        "location.within": "50km",
        "start_date.range_start": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "start_date.range_end": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expand": "venue,category",
        "page_size": "100"
    }
    
    async with httpx.AsyncClient() as client:
        page = 1
        has_more = True
        while has_more and page <= 5:
            params["page"] = str(page)
            try:
                res = await client.get(url, params=params, headers={"Authorization": f"Bearer {api_key}"}, timeout=10.0)
                if res.status_code != 200: break
                
                data = res.json()
                for ev in data.get("events", []):
                    cat = ev.get("category", {}).get("name", "General")
                    capacity = ev.get("capacity", 0)
                    impact, uplift = classify_impact(cat, capacity)
                    
                    venue = ev.get("venue", {}).get("address", {})
                    area = venue.get("localized_area_display") or venue.get("city") or "Dubai"
                    
                    events.append({
                        "name": ev.get("name", {}).get("text", ""),
                        "startDate": ev.get("start", {}).get("local", "")[:10],
                        "endDate": ev.get("end", {}).get("local", "")[:10],
                        "location": f"Dubai — {area}",
                        "area": area,
                        "impactLevel": impact,
                        "upliftPct": uplift,
                        "description": (ev.get("description", {}).get("text") or cat)[:500],
                        "source": "eventbrite",
                        "externalId": f"eventbrite:{ev.get('id')}"
                    })
                
                has_more = data.get("pagination", {}).get("has_more_items", False)
                page += 1
            except Exception as e:
                break
    return events

# Simplified for example... (TicketMaster and DTCM would follow similar patterns)

async def sync_event_feeds(org_id: ObjectId, days_ahead=90, city="Dubai") -> Dict[str, Any]:
    events = await fetch_eventbrite(days_ahead, city)
    
    result = {"inserted": 0, "updated": 0, "skipped": 0, "errors": []}
    
    for ev in events:
        try:
            if not ev["name"] or not ev["startDate"]: continue
            
            existing = await MarketEvent.find_one({"orgId": org_id, "externalId": ev["externalId"]})
            if existing:
                existing.endDate = ev["endDate"]
                existing.area = ev["area"]
                existing.impactLevel = ev["impactLevel"]
                existing.upliftPct = max(0, ev["upliftPct"])
                existing.description = ev["description"]
                await existing.save()
                result["updated"] += 1
            else:
                new_event = MarketEvent(
                    orgId=org_id,
                    name=ev["name"],
                    startDate=ev["startDate"],
                    endDate=ev["endDate"],
                    area=ev["area"],
                    areas=[ev["area"]],
                    impactLevel=ev["impactLevel"],
                    upliftPct=max(0, ev["upliftPct"]),
                    description=ev["description"],
                    source=ev["source"],
                    isActive=True
                )
                # Store the external ID as an extra field if not in schema, or adjust schema
                # (For simplicity here we just insert)
                await new_event.insert()
                result["inserted"] += 1
        except Exception as e:
            result["errors"].append(str(e))
            
    return result
