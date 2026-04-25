from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from bson import ObjectId
from datetime import datetime

from app.models.inventory_master import InventoryMaster

inventory_router = APIRouter(prefix="/inventory", tags=["inventory"])

class DateRangeQuery(BaseModel):
    startDate: str
    endDate: str

class InventoryOverride(BaseModel):
    date: str
    price: Optional[float] = None
    minStay: Optional[int] = None
    maxStay: Optional[int] = None
    isAvailable: Optional[bool] = None

@inventory_router.get("/portfolio")
async def get_portfolio_inventory(orgId: str, startDate: str, endDate: str):
    inventory = await InventoryMaster.find(
        InventoryMaster.orgId == ObjectId(orgId),
        InventoryMaster.date >= startDate,
        InventoryMaster.date <= endDate
    ).sort(+InventoryMaster.date).to_list()

    return {
        "inventory": [
            {
                "id": str(i.id),
                "listingId": str(i.listingId),
                **i.model_dump(exclude={"id", "orgId", "listingId"})
            }
            for i in inventory
        ]
    }

@inventory_router.get("/{listing_id}")
async def get_inventory(listing_id: str, orgId: str, startDate: str, endDate: str):
    try:
        listing_oid = ObjectId(listing_id)
        org_oid = ObjectId(orgId)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid listing_id or orgId")

    inventory = await InventoryMaster.find(
        InventoryMaster.listingId == listing_oid,
        InventoryMaster.orgId == org_oid,
        InventoryMaster.date >= startDate,
        InventoryMaster.date <= endDate
    ).sort(+InventoryMaster.date).to_list()
    
    return {"inventory": [{"id": str(i.id), **i.model_dump(exclude={'id', 'listingId', 'orgId'})} for i in inventory]}

@inventory_router.put("/{listing_id}/override")
async def override_inventory(listing_id: str, orgId: str, req: InventoryOverride):
    inv = await InventoryMaster.find_one(
        InventoryMaster.listingId == ObjectId(listing_id),
        InventoryMaster.orgId == ObjectId(orgId),
        InventoryMaster.date == req.date
    )
    
    if not inv:
        # If it doesn't exist, we can't reliably override pricing engine data without context
        raise HTTPException(status_code=404, detail="Inventory date not generated yet. Run engine first.")
        
    update_data = {}
    if req.price is not None: update_data['currentPrice'] = req.price
    if req.minStay is not None: update_data['minStay'] = req.minStay
    if req.maxStay is not None: update_data['maxStay'] = req.maxStay
    if req.isAvailable is not None: update_data['status'] = "available" if req.isAvailable else "blocked"
    
    update_data['updatedAt'] = datetime.utcnow()
    
    await inv.set(update_data)
    return {"success": True, "message": "Inventory overridden"}
