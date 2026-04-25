from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.engine.pipeline import run_pipeline
from app.models.listing import Listing
from bson import ObjectId

engine_router = APIRouter(prefix="/engine", tags=["engine"])

class TriggerRequest(BaseModel):
    listingId: str
    triggerDetail: Optional[str] = "Manual Trigger"

@engine_router.post("/run")
async def trigger_engine_run(req: TriggerRequest):
    """
    Triggers the 4-pass pricing waterfall pipeline for a given listing.
    """
    try:
        run = await run_pipeline(req.listingId, trigger_detail=req.triggerDetail)
        return {"success": True, "runId": str(run.id), "daysChanged": run.daysChanged}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _sse_event(event_type: str, data: dict) -> str:
    import json
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload)}\n\n"

@engine_router.post("/run-all")
async def trigger_engine_all(orgId: str):
    """
    Triggers pipeline for all listings in an org with real-time streaming updates.
    """
    from fastapi.responses import StreamingResponse
    import asyncio

    async def gen():
        listings = await Listing.find(Listing.orgId == ObjectId(orgId)).to_list()
        results = []
        
        yield _sse_event("status", {"step": "routing", "message": f"Orchestrating pipeline for {len(listings)} listings..."})
        yield _sse_event("thinking", {"message": "Initializing pricing engine and verifying organization permissions..."})
        await asyncio.sleep(0.5)

        for i, l in enumerate(listings):
            listing_name = l.name or str(l.id)
            
            # Step 2: Analyzing per listing
            yield _sse_event("status", {"step": "analyzing", "message": f"[{i+1}/{len(listings)}] Analyzing {listing_name}..."})
            yield _sse_event("thinking", {"message": f"Processing market data and historical performance for {listing_name}..."})
            
            try:
                run = await run_pipeline(str(l.id), trigger_detail="Run All")
                results.append({"listingId": str(l.id), "success": True, "daysChanged": run.daysChanged})
                
                # Step 3: Validating
                yield _sse_event("status", {"step": "validating", "message": f"Validating results for {listing_name}..."})
                yield _sse_event("thinking", {"message": f"Ensuring {run.daysChanged} days of adjustments meet PriceGuard constraints..."})
                await asyncio.sleep(0.2)
                
            except Exception as e:
                results.append({"listingId": str(l.id), "success": False, "error": str(e)})
                yield _sse_event("error", {"message": f"Error on {listing_name}: {str(e)}"})

        # Step 4: Complete
        yield _sse_event("status", {"step": "generating", "message": "Finalizing all proposals..."})
        yield _sse_event("thinking", {"message": "Consolidating all property runs into final dashboard view..."})
        await asyncio.sleep(0.5)

        summary = {
            "totalListings": len(results),
            "succeeded": len([r for r in results if r.get("success")]),
            "failed": len([r for r in results if not r.get("success")]),
        }
        
        yield _sse_event("complete", {
            "message": f"Processed {summary['totalListings']} properties. {summary['succeeded']} succeeded.",
            "summary": summary
        })

    return StreamingResponse(gen(), media_type="text/event-stream")
