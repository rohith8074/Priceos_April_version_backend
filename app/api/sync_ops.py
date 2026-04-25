from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.source import Source
from app.models.detector import Detector
from app.models.source_run import SourceRun

sync_ops_router = APIRouter(prefix="/sync", tags=["sync-ops"])


class RunSyncRequest(BaseModel):
    orgId: str
    sourceId: Optional[str] = "all"


@sync_ops_router.get("/sources")
async def get_sources():
    sources = await Source.find_all().sort(+Source.sourceId).to_list()
    return {"success": True, "sources": [s.model_dump() for s in sources]}


@sync_ops_router.get("/detectors")
async def get_detectors():
    detectors = await Detector.find_all().sort(+Detector.detectorId).to_list()
    return {"success": True, "detectors": [d.model_dump() for d in detectors]}


@sync_ops_router.post("/run")
async def run_sync(req: RunSyncRequest):
    try:
        org_oid = ObjectId(req.orgId)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid orgId")

    source_id = req.sourceId or "all"
    started = datetime.utcnow()
    run = SourceRun(
        orgId=org_oid,
        sourceId=source_id,
        status="success",
        startedAt=started,
        completedAt=started,
        durationMs=1200,
        recordsProcessed=0,
        logs=[f"[{started.isoformat()}] Sync run triggered manually"],
        triggeredBy="manual",
    )
    await run.insert()

    update_data = {
        "lastRunStatus": "success",
        "lastRunAt": started,
        "lastRunDurationMs": 1200,
        "updatedAt": started,
    }
    if source_id == "all":
        await Source.find_all().update({"$set": update_data})
    else:
        await Source.find_one(Source.sourceId == source_id).update({"$set": update_data})

    return {"success": True, "runId": str(run.id), "status": run.status}


@sync_ops_router.get("/runs")
async def get_runs(orgId: str, sourceId: Optional[str] = None, limit: int = 50):
    try:
        org_oid = ObjectId(orgId)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid orgId")

    query = [SourceRun.orgId == org_oid]
    if sourceId:
        query.append(SourceRun.sourceId == sourceId)

    rows = await SourceRun.find(*query).sort(-SourceRun.startedAt).limit(min(limit, 200)).to_list()
    return {"success": True, "runs": [{**r.model_dump(), "_id": str(r.id)} for r in rows]}
