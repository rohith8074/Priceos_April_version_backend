from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from bson import ObjectId
from datetime import datetime

from app.models.listing import Listing
from app.models.pricing_rule import PricingRule
from app.models.inventory_master import InventoryMaster

listings_router = APIRouter(prefix="/listings", tags=["listings"])

class ListingCreate(BaseModel):
    orgId: str
    name: str
    externalId: Optional[str] = None
    price: Optional[float] = 0
    bedrooms: Optional[int] = 1
    marketId: Optional[str] = None
    # Add other needed config attributes here

class ListingUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    priceFloor: Optional[float] = None
    priceCeiling: Optional[float] = None
    occupancyTargetPct: Optional[float] = None
    lastMinuteEnabled: Optional[bool] = None
    # Add other attributes

@listings_router.get("/")
async def get_listings(orgId: str):
    listings = await Listing.find(Listing.orgId == ObjectId(orgId)).to_list()
    return {"listings": [{"id": str(ls.id), **ls.model_dump(exclude={'id'})} for ls in listings]}

@listings_router.get("/{listing_id}")
async def get_listing(listing_id: str, orgId: str):
    listing = await Listing.find_one(Listing.id == ObjectId(listing_id), Listing.orgId == ObjectId(orgId))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return {"id": str(listing.id), **listing.model_dump(exclude={'id'})}

@listings_router.post("/")
async def create_listing(req: ListingCreate):
    new_listing = Listing(**req.model_dump())
    new_listing.createdAt = datetime.utcnow()
    new_listing.updatedAt = datetime.utcnow()
    await new_listing.insert()
    return {"id": str(new_listing.id), **new_listing.model_dump(exclude={'id'})}

@listings_router.put("/{listing_id}")
async def update_listing(listing_id: str, req: ListingUpdate, orgId: str):
    listing = await Listing.find_one(Listing.id == ObjectId(listing_id), Listing.orgId == ObjectId(orgId))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
        
    update_data = req.model_dump(exclude_unset=True)
    update_data['updatedAt'] = datetime.utcnow()
    
    await listing.set(update_data)
    return {"success": True, "message": "Listing updated"}

@listings_router.delete("/{listing_id}")
async def delete_listing(listing_id: str, orgId: str):
    listing = await Listing.find_one(Listing.id == ObjectId(listing_id), Listing.orgId == ObjectId(orgId))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
        
    await listing.delete()
    return {"success": True}
