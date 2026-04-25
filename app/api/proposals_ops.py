from datetime import datetime, timezone
from typing import Optional, Literal

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from beanie.operators import In

from app.models.inventory_master import InventoryMaster
from app.models.listing import Listing

def now_utc():
    return datetime.now(timezone.utc)


proposals_ops_router = APIRouter(prefix="/proposals", tags=["proposals-ops"])
revenue_v1_router = APIRouter(prefix="/v1/revenue", tags=["revenue-v1"])


class BulkModifyRequest(BaseModel):
    orgId: str
    proposalIds: list[str]
    newPrice: float


class BulkStatusRequest(BaseModel):
    orgId: str
    proposalIds: list[str]


class BulkRevenueActionRequest(BaseModel):
    orgId: str
    _ids: list[str]
    action: Literal["push", "approve", "reject", "save", "apply"]


@proposals_ops_router.post("/bulk-modify")
async def bulk_modify(req: BulkModifyRequest):
    if req.newPrice <= 0:
        raise HTTPException(status_code=400, detail="newPrice must be positive")
    org_oid = ObjectId(req.orgId)

    docs = await InventoryMaster.find(
        InventoryMaster.id.in_([ObjectId(x) for x in req.proposalIds if ObjectId.is_valid(x)]),
        InventoryMaster.orgId == org_oid,
        InventoryMaster.proposalStatus == "pending",
    ).to_list()

    modified = 0
    for doc in docs:
        current = float(doc.currentPrice or 0)
        change_pct = round(((req.newPrice - current) / current) * 100) if current > 0 else None
        doc.proposedPrice = req.newPrice
        doc.changePct = change_pct
        doc.reasoning = f"Manually modified to {req.newPrice}"
        await doc.save()
        modified += 1

    return {"success": True, "count": modified}


@proposals_ops_router.post("/bulk-approve")
async def bulk_approve(req: BulkStatusRequest):
    org_oid = ObjectId(req.orgId)
    valid_ids = [ObjectId(x) for x in req.proposalIds if ObjectId.is_valid(x)]
    result = await InventoryMaster.find(
        InventoryMaster.id.in_(valid_ids),
        InventoryMaster.orgId == org_oid,
    ).update({"$set": {"proposalStatus": "approved"}})
    return {"success": True, "count": int(result.modified_count if hasattr(result, "modified_count") else 0)}


@proposals_ops_router.post("/bulk-reject")
async def bulk_reject(req: BulkStatusRequest):
    org_oid = ObjectId(req.orgId)
    valid_ids = [ObjectId(x) for x in req.proposalIds if ObjectId.is_valid(x)]
    result = await InventoryMaster.find(
        InventoryMaster.id.in_(valid_ids),
        InventoryMaster.orgId == org_oid,
    ).update({"$set": {"proposalStatus": "rejected"}})
    return {"success": True, "count": int(result.modified_count if hasattr(result, "modified_count") else 0)}


@proposals_ops_router.post("/bulk-save")
async def bulk_save(req: dict):
    """
    Saves or updates proposals in InventoryMaster.
    Expected payload: { "orgId": str, "proposals": [ { "listingId": str, "date": str, "proposedPrice": float, "changePct": float, "reasoning": str, "status": Optional[str] } ] }
    """
    org_id = req.get("orgId")
    proposals = req.get("proposals", [])
    if not org_id or not proposals:
        return {"success": False, "message": "Missing orgId or proposals"}

    org_oid = ObjectId(org_id)
    modified = 0
    
    for p in proposals:
        listing_id = p.get("listingId")
        date_str = p.get("date")
        if not listing_id or not date_str:
            continue
            
        # Resolve listingId (could be ObjectId string or Hostaway ID)
        listing_oid = None
        try:
            if len(str(listing_id)) == 24:
                listing_oid = ObjectId(listing_id)
        except:
            pass
            
        if not listing_oid:
            # Try finding listing by hostawayId
            listing = await Listing.find_one(Listing.hostawayId == str(listing_id), Listing.orgId == org_oid)
            if listing:
                listing_oid = listing.id
                
        if not listing_oid:
            print(f"!!! [bulk_save] Could not resolve listingId: {listing_id}")
            continue
        
        # Find existing record for this property and date
        doc = await InventoryMaster.find_one(
            InventoryMaster.orgId == org_oid,
            InventoryMaster.listingId == listing_oid,
            InventoryMaster.date == date_str
        )
        
        if doc:
            doc.proposedPrice = p.get("proposedPrice")
            doc.changePct = p.get("changePct")
            doc.reasoning = p.get("reasoning")
            doc.proposalStatus = p.get("status", "pending")
            doc.updatedAt = now_utc()
            await doc.save()
            modified += 1
        else:
            # Upsert: Create new record if it doesn't exist
            current_price = p.get("currentPrice")
            if current_price is not None:
                new_doc = InventoryMaster(
                    orgId=org_oid,
                    listingId=listing_oid,
                    date=date_str,
                    currentPrice=float(current_price),
                    proposedPrice=p.get("proposedPrice"),
                    changePct=p.get("changePct"),
                    reasoning=p.get("reasoning"),
                    proposalStatus=p.get("status", "pending"),
                    status="available" 
                )
                await new_doc.insert()
                modified += 1
            
    return {"success": True, "modified": modified}


@revenue_v1_router.get("/proposals")
async def get_revenue_proposals(orgId: str, listingId: Optional[str] = None, status: str = "all"):
    org_oid = ObjectId(orgId)
    query = [InventoryMaster.orgId == org_oid, InventoryMaster.proposedPrice != None]
    if listingId:
        query.append(InventoryMaster.listingId == ObjectId(listingId))
    if status != "all":
        query.append(InventoryMaster.proposalStatus == status)
    else:
        query.append(In(InventoryMaster.proposalStatus, ["pending", "approved", "rejected", "pushed"]))

    docs = await InventoryMaster.find(*query).sort(+InventoryMaster.date).limit(500).to_list()
    listing_ids = list({str(d.listingId) for d in docs})
    valid_listing_oids = [ObjectId(x) for x in listing_ids if ObjectId.is_valid(x)]
    listings = (
        await Listing.find(In(Listing.id, valid_listing_oids)).to_list()
        if valid_listing_oids
        else []
    )
    listing_map = {str(l.id): l for l in listings}

    proposals = []
    for d in docs:
        listing = listing_map.get(str(d.listingId))
        proposals.append({
            "id": str(d.id),
            "_id": str(d.id),
            "listingId": str(d.listingId),
            "listingName": listing.name if listing else "Unknown Property",
            "date": d.date,
            "currentPrice": d.currentPrice,
            "proposedPrice": d.proposedPrice,
            "changePct": d.changePct,
            "proposalStatus": d.proposalStatus or "pending",
            "status": d.proposalStatus or "pending",
            "reasoning": d.reasoning or "",
        })
    return {"proposals": proposals, "count": len(proposals)}


@revenue_v1_router.post("/proposals")
async def revenue_proposals_action(req: BulkRevenueActionRequest):
    org_oid = ObjectId(req.orgId)
    valid_ids = [ObjectId(x) for x in req._ids if ObjectId.is_valid(x)]
    if not valid_ids:
        return {"processed": 0, "action": req.action, "newStatus": "none"}

    if req.action in ("approve", "save"):
        status = "approved"
    elif req.action == "reject":
        status = "rejected"
    else:
        status = "pushed"

    docs = await InventoryMaster.find(InventoryMaster.id.in_(valid_ids), InventoryMaster.orgId == org_oid).to_list()
    processed = 0
    for d in docs:
        d.proposalStatus = status
        if status == "pushed" and d.proposedPrice is not None:
            d.previousPrice = d.currentPrice
            d.currentPrice = d.proposedPrice
        await d.save()
        processed += 1

    return {"processed": processed, "action": req.action, "newStatus": status}
