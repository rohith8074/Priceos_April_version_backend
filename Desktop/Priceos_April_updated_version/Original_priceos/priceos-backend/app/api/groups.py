from datetime import datetime, timezone
from typing import Optional, List

from beanie import PydanticObjectId
from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.property_group import PropertyGroup
from app.models.pricing_rule import PricingRule

groups_router = APIRouter(prefix="/groups", tags=["groups"])


def now_utc():
    return datetime.now(timezone.utc)


class GroupUpsertRequest(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = "#6366f1"
    listingIds: List[str] = []


class RuleCreateRequest(BaseModel):
    ruleType: str
    ruleCategory: Optional[str] = None
    name: str
    enabled: bool = True
    priority: int = 0
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


@groups_router.get("/")
async def list_groups(orgId: str):
    org_oid = ObjectId(orgId)
    groups = await PropertyGroup.find(PropertyGroup.orgId == org_oid).sort(-PropertyGroup.createdAt).to_list()
    return [
        {
            "_id": str(g.id),
            "name": g.name,
            "description": g.description,
            "color": g.color,
            "listingIds": [str(x) for x in g.listingIds],
        }
        for g in groups
    ]


@groups_router.post("/")
async def create_group(orgId: str, req: GroupUpsertRequest):
    org_oid = ObjectId(orgId)
    listing_ids = [PydanticObjectId(x) for x in req.listingIds]
    group = PropertyGroup(
        orgId=org_oid,
        name=req.name,
        description=req.description,
        color=req.color or "#6366f1",
        listingIds=listing_ids,
        createdAt=now_utc(),
        updatedAt=now_utc(),
    )
    await group.insert()
    return {
        "_id": str(group.id),
        "name": group.name,
        "description": group.description,
        "color": group.color,
        "listingIds": [str(x) for x in group.listingIds],
    }


@groups_router.put("/{group_id}")
async def update_group(group_id: str, req: GroupUpsertRequest):
    group = await PropertyGroup.get(PydanticObjectId(group_id))
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    group.name = req.name
    group.description = req.description
    group.color = req.color or group.color
    group.listingIds = [PydanticObjectId(x) for x in req.listingIds]
    group.updatedAt = now_utc()
    await group.save()
    return {
        "_id": str(group.id),
        "name": group.name,
        "description": group.description,
        "color": group.color,
        "listingIds": [str(x) for x in group.listingIds],
    }


@groups_router.delete("/{group_id}")
async def delete_group(group_id: str):
    group_oid = PydanticObjectId(group_id)
    await PropertyGroup.find_one(PropertyGroup.id == group_oid).delete()
    await PricingRule.find(PricingRule.groupId == group_oid).delete()
    return {"success": True}


@groups_router.get("/{group_id}/rules")
async def list_group_rules(group_id: str):
    group_oid = PydanticObjectId(group_id)
    rules = await PricingRule.find(PricingRule.groupId == group_oid).sort(-PricingRule.createdAt).to_list()
    return [{**r.model_dump(), "_id": str(r.id), "groupId": str(r.groupId) if r.groupId else None} for r in rules]


@groups_router.post("/{group_id}/rules")
async def create_group_rule(group_id: str, req: RuleCreateRequest):
    group = await PropertyGroup.get(PydanticObjectId(group_id))
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    rule = PricingRule(
        orgId=group.orgId,
        groupId=group.id,
        scope="group",
        **req.model_dump(),
        createdAt=now_utc(),
        updatedAt=now_utc(),
    )
    await rule.insert()
    return {**rule.model_dump(), "_id": str(rule.id), "groupId": str(rule.groupId)}


@groups_router.put("/{group_id}/rules/{rule_id}")
async def update_group_rule(group_id: str, rule_id: str, body: dict):
    group_oid = PydanticObjectId(group_id)
    rule = await PricingRule.find_one(PricingRule.id == PydanticObjectId(rule_id), PricingRule.groupId == group_oid)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for key, value in body.items():
        if hasattr(rule, key):
            setattr(rule, key, value)
    rule.updatedAt = now_utc()
    await rule.save()
    return {**rule.model_dump(), "_id": str(rule.id), "groupId": str(rule.groupId) if rule.groupId else None}


@groups_router.delete("/{group_id}/rules/{rule_id}")
async def delete_group_rule(group_id: str, rule_id: str):
    group_oid = PydanticObjectId(group_id)
    rule = await PricingRule.find_one(PricingRule.id == PydanticObjectId(rule_id), PricingRule.groupId == group_oid)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await rule.delete()
    return {"success": True}
