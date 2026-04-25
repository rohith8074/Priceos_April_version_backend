from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from bson import ObjectId
from datetime import datetime

from app.models.pricing_rule import PricingRule

rules_router = APIRouter(prefix="/rules", tags=["rules"])

class RuleCreate(BaseModel):
    orgId: str
    listingId: Optional[str] = None
    groupId: Optional[str] = None
    scope: str = "listing"
    ruleType: str
    name: str
    enabled: bool = True
    priority: int = 100
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    daysOfWeek: Optional[List[int]] = None
    minNights: Optional[int] = None
    priceOverride: Optional[float] = None
    priceAdjPct: Optional[float] = None
    minPriceOverride: Optional[float] = None
    maxPriceOverride: Optional[float] = None
    minStayOverride: Optional[int] = None
    isBlocked: bool = False
    closedToArrival: bool = False
    closedToDeparture: bool = False
    suspendLastMinute: bool = False
    suspendGapFill: bool = False

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    daysOfWeek: Optional[List[int]] = None
    minNights: Optional[int] = None
    priceOverride: Optional[float] = None
    priceAdjPct: Optional[float] = None
    minPriceOverride: Optional[float] = None
    maxPriceOverride: Optional[float] = None
    minStayOverride: Optional[int] = None
    isBlocked: Optional[bool] = None
    closedToArrival: Optional[bool] = None
    closedToDeparture: Optional[bool] = None
    suspendLastMinute: Optional[bool] = None
    suspendGapFill: Optional[bool] = None

@rules_router.get("/")
async def get_rules(orgId: str, listingId: Optional[str] = None, groupId: Optional[str] = None):
    query = {"orgId": orgId}
    if listingId:
        query["listingId"] = ObjectId(listingId)
    if groupId:
        query["groupId"] = ObjectId(groupId)
        
    rules = await PricingRule.find(query).to_list()
    return {"rules": [{"id": str(r.id), "listingId": str(r.listingId) if r.listingId else None, "groupId": str(r.groupId) if r.groupId else None, **r.model_dump(exclude={'id', 'listingId', 'groupId'})} for r in rules]}

@rules_router.post("/")
async def create_rule(req: RuleCreate):
    data = req.model_dump()
    if data.get('listingId'):
        data['listingId'] = ObjectId(data['listingId'])
    if data.get('groupId'):
        data['groupId'] = ObjectId(data['groupId'])
        
    new_rule = PricingRule(**data)
    new_rule.createdAt = datetime.utcnow()
    new_rule.updatedAt = datetime.utcnow()
    await new_rule.insert()
    return {"id": str(new_rule.id), "success": True}

@rules_router.put("/{rule_id}")
async def update_rule(rule_id: str, req: RuleUpdate, orgId: str):
    rule = await PricingRule.find_one(PricingRule.id == ObjectId(rule_id), PricingRule.orgId == orgId)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    update_data = req.model_dump(exclude_unset=True)
    update_data['updatedAt'] = datetime.utcnow()
    
    await rule.set(update_data)
    return {"success": True, "message": "Rule updated"}

@rules_router.delete("/{rule_id}")
async def delete_rule(rule_id: str, orgId: str):
    rule = await PricingRule.find_one(PricingRule.id == ObjectId(rule_id), PricingRule.orgId == orgId)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    await rule.delete()
    return {"success": True}
