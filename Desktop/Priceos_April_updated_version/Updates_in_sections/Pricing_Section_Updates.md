# Pricing Section — Updates & PRD Alignment

**Date:** 2026-04-10  
**Status:** Complete — 100% aligned with PRD and Knowledge Base

---

## Summary of Changes

The entire Pricing section was rebuilt from scratch in this session. Five files were modified or created:

| File | Change Type |
|------|------------|
| `src/app/api/listings/[id]/rules/[ruleId]/route.ts` | Restored (was returning 410 Gone) |
| `src/app/(dashboard)/pricing/page.tsx` | Enhanced — fetches all statuses + listings |
| `src/app/(dashboard)/pricing/pricing-page-tabs.tsx` | Updated — passes `listings` prop |
| `src/app/(dashboard)/pricing/pricing-client.tsx` | Full rewrite |
| `src/components/pricing/pricing-rules-studio.tsx` | Full rewrite |

All saves go to **MongoDB only** (no Hostaway/PMS writes). This is intentional for the current V1 scope.

---

## 1. Pricing Proposals (pricing-client.tsx)

### What Was There Before
- A flat list of pending proposals only
- No status history
- No risk classification
- No filtering or sorting
- Basic approve/reject buttons with no bulk actions

### What Was Built

#### Status Tabs
Four status tabs with live counts:
- **Pending** — today and future proposals awaiting review
- **Approved** — manager-approved proposals (past 14 days)
- **Rejected** — dismissed proposals (past 14 days)  
- **Pushed** — proposals pushed to PMS (past 14 days)

#### Risk Classification
Client-side risk scoring derived from `changePct`:
```
|changePct| ≥ 20% → HIGH (red)
|changePct| ≥ 8%  → MEDIUM (amber)
otherwise          → LOW (green)
```
Displayed as colored `RiskBadge` on every proposal row.

#### Stale / Expiring Flag
Proposals within 1 day of their date show an amber "Expiring" label + amber left border on the row. This prevents stale proposals from being silently missed.

#### Filter Bar (Pending tab only)
- **Property filter** — dropdown to filter by listing name
- **Direction filter** — All / Increases only / Decreases only

#### Sort Controls
Three sort keys with ascending/descending toggle:
- Date (default)
- Change %
- Property name

#### Individual Actions
Each pending proposal row has Approve / Reject buttons that POST to:
- `POST /api/proposals/bulk-approve` — `{ ids: [singleId] }`
- `POST /api/proposals/bulk-reject` — `{ ids: [singleId] }`

#### Bulk Actions Toolbar
Appears when ≥1 row is selected (checkbox on each row):
- Select All / Deselect All
- Bulk Approve — sends all selected IDs to `bulk-approve`
- Bulk Reject — sends all selected IDs to `bulk-reject`

#### High-Risk Warning Banner
If any currently-displayed proposals are classified HIGH risk, a red warning banner appears at the bottom of the list prompting extra review before approval.

---

## 2. Pricing Rules Studio (pricing-rules-studio.tsx)

### What Was There Before
- Fully local state — no connection to MongoDB
- No listing selector
- Save buttons that did nothing (or called endpoints that returned 410)
- Tabs were cosmetic only

### What Was Built

#### Listing Selector
Dropdown to select any active listing. On change:
- Parallel fetch: `GET /api/listings/[id]/engine-config` + `GET /api/listings/[id]/rules`
- Hydrates all 6 tabs with real MongoDB data

#### Tab 1: Guardrails
Edits engine config fields on the Listing document:
- Price Floor (`priceFloor`) — minimum price hard cap
- Price Ceiling (`priceCeiling`) — maximum price hard cap
- Lowest Min Stay (`lowestMinStayAllowed`) — never below this
- Default Max Stay (`defaultMaxStay`)
- Allowed Check-in Days — day-of-week checkboxes
- Allowed Check-out Days — day-of-week checkboxes

Save → `PATCH /api/listings/[id]/engine-config`

#### Tab 2: Seasons
CRUD for `PricingRule` documents of type `SEASON`:
- Create: name, date range (start/end), price override or % adjustment, min stay, priority
- Toggle enabled/disabled — `PUT /api/listings/[id]/rules/[ruleId]`
- Delete rule — `DELETE /api/listings/[id]/rules/[ruleId]`
- List shows all SEASON rules with enable toggle and delete button

Create → `POST /api/listings/[id]/rules` with `{ type: "SEASON", ... }`

#### Tab 3: Lead Time
Three sub-sections, all saving to engine config:

**Day-of-Week Pricing:**
- Enabled toggle
- Per-day % adjustment (Mon–Sun sliders)
- Per-day min stay override

**Last-Minute Discounts:**
- Enabled toggle
- Days-out threshold (`lastMinuteDaysOut`)
- Discount % (`lastMinuteDiscountPct`)

**Far-Out Markup:**
- Enabled toggle
- Days-out threshold (`farOutDaysOut`)
- Markup % (`farOutMarkupPct`)

Save → `PATCH /api/listings/[id]/engine-config`

#### Tab 4: Gap Logic
Two sub-sections:

**Gap Prevention:**
- Enabled toggle
- Minimum fragment threshold (days) — gaps shorter than this get blocked

**Gap Fill:**
- Enabled toggle
- Min/Max gap length to attempt fill
- Discount % for gap-fill nights
- Override CICO restrictions toggle

Save → `PATCH /api/listings/[id]/engine-config`

#### Tab 5: LOS Discounts
CRUD for `PricingRule` documents of type `LOS_DISCOUNT`:
- Minimum nights trigger (`minNights`)
- % adjustment (`priceAdjPct` — negative = discount)
- Priority

Create → `POST /api/listings/[id]/rules` with `{ type: "LOS_DISCOUNT", ... }`  
Toggle/Delete → same PUT/DELETE endpoints as Seasons

#### Tab 6: Date Overrides
CRUD for `PricingRule` documents of type `ADMIN_BLOCK`:
- Date range
- Block availability (`isBlocked`)
- Closed to Arrival / Closed to Departure flags
- Suspend last-minute auto-set to `true` (overrides auto-pricing for the period)

Create → `POST /api/listings/[id]/rules` with `{ type: "ADMIN_BLOCK", suspendLastMinute: true, ... }`  
Toggle/Delete → same PUT/DELETE endpoints as Seasons

---

## 3. API Routes Fixed

### PUT /api/listings/[id]/rules/[ruleId]
Was previously returning `410 Gone` with message "Seasonal rules removed in Price Intelligence Layer redesign."

Fixed: Updates any of the `ALLOWED_FIELDS` on the PricingRule document. Scoped by both `_id` and `listingId` for safety.

### DELETE /api/listings/[id]/rules/[ruleId]
Was also returning `410 Gone`.

Fixed: Deletes the PricingRule document scoped by `_id` + `listingId`.

---

## 4. PRD Alignment Checklist

| PRD Requirement | Status | Notes |
|----------------|--------|-------|
| Daily price proposals from AI engine | ✅ | InventoryMaster → proposals rendered |
| Approve/reject individual proposals | ✅ | Calls bulk-approve/reject API |
| Bulk approve/reject | ✅ | Multi-select with toolbar |
| Risk classification (High/Medium/Low) | ✅ | Client-side from changePct |
| Reasoning display | ✅ | Available on each proposal row |
| Status history (approved/rejected/pushed) | ✅ | Past 14 days shown in tabs |
| Stale/expiring proposal warnings | ✅ | Amber flag for proposals within 1 day |
| Season pricing rules CRUD | ✅ | Full CRUD → MongoDB |
| Day-of-week pricing | ✅ | Per-day sliders → engine-config |
| Last-minute discounts | ✅ | Toggle + threshold + % → engine-config |
| Far-out markup | ✅ | Toggle + threshold + % → engine-config |
| Gap prevention | ✅ | Threshold → engine-config |
| Gap fill discounts | ✅ | LengthMin/Max/Pct → engine-config |
| LOS discounts | ✅ | Full CRUD → MongoDB |
| Date overrides / admin blocks | ✅ | Full CRUD → MongoDB |
| Price floor/ceiling guardrails | ✅ | PATCH → engine-config |
| Min/max stay guardrails | ✅ | PATCH → engine-config |
| Allowed check-in/out days | ✅ | Day-checkbox → engine-config |
| All saves → MongoDB only | ✅ | No Hostaway writes |
| Per-property rule management | ✅ | Listing selector in Rules Studio |

---

## 5. Data Flow

```
PricingAnalystAgent (waterfall.ts)
  → Generates InventoryMaster docs with proposedPrice, changePct, reasoning
  → Sets proposalStatus = "pending"

Pricing Page (server component)
  → Queries InventoryMaster: pending (today+) + history (past 14d)
  → Queries Listing: all active → for Rules Studio selector
  → Passes to PricingPageTabs → PricingClient + PricingRulesStudio

User Action (approve/reject)
  → POST /api/proposals/bulk-approve or bulk-reject
  → Updates proposalStatus in InventoryMaster

User Action (save rule/config)
  → PATCH /api/listings/[id]/engine-config → updates Listing doc fields
  → POST/PUT/DELETE /api/listings/[id]/rules → creates/updates/deletes PricingRule docs

Next Waterfall Run
  → Reads PricingRule + engine-config from Listing
  → Applies in 4-pass sequence
  → Generates new InventoryMaster proposals
```

---

## 6. What Is NOT Included (By Design)

- **Push to Hostaway** — intentionally deferred. All writes are MongoDB-only.
- **Proposal editing** — proposals are approve/reject only; price edits go through the Rules Studio.
- **Real-time websocket updates** — proposals refresh on page load; no live push.
- **Automated auto-approval** — all proposals require human review in V1.
