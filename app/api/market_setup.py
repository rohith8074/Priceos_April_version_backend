from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.services.airbtics import AirbticsService
from app.services.lyzr import call_lyzr_agent

market_setup_router = APIRouter(prefix="/market-setup", tags=["market-setup"])

class AirbticsSearchReq(BaseModel):
    query: str
    country_code: str

class AirbticsBoundsReq(BaseModel):
    bounds: Dict[str, float]
    bedrooms: int

class LyzrAgentReq(BaseModel):
    agentId: str
    message: str
    sessionId: Optional[str] = None

@market_setup_router.post("/search")
async def search_market(req: AirbticsSearchReq):
    try:
        data = await AirbticsService.search_market(req.query, req.country_code)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@market_setup_router.post("/search-bounds")
async def search_bounds(req: AirbticsBoundsReq):
    try:
        data = await AirbticsService.search_listings_by_bounds(req.bounds, req.bedrooms)
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@market_setup_router.post("/agent")
async def agent_chat(req: LyzrAgentReq):
    try:
        res = await call_lyzr_agent(
            agent_id=req.agentId,
            message=req.message,
            session_id=req.sessionId
        )
        if not res.ok:
            raise HTTPException(status_code=500, detail=res.error)
        return {"response": res.response, "parsedJson": res.parsed_json}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@market_setup_router.post("/sync-events")
async def trigger_event_sync(orgId: str, marketCity: str = "Dubai"):
    from app.services.events import sync_event_feeds
    from bson import ObjectId
    
    try:
        result = await sync_event_feeds(org_id=ObjectId(orgId), days_ahead=90, city=marketCity)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
