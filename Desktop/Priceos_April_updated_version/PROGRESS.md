# PriceOS — Project Progress & Task Tracker

**Last Updated:** 2026-04-09
**Current Phase:** MongoDB Migration + Global Expansion + Agent Architecture

---

## 1. What Has Been Done

### ✅ Phase 1: MongoDB / Mongoose Migration (Complete)

**Objective:** Migrate PriceOS V1 from NeonDB (Postgres) + Drizzle ORM to MongoDB + Mongoose.

| Task | Status | Notes |
|------|--------|-------|
| Replace Drizzle schema with Mongoose models | ✅ Done | 16 models in `src/lib/db/models/` |
| Replace NeonAuth with JWT auth system | ✅ Done | `/api/auth/login`, `/api/auth/logout`, `/api/auth/me` |
| Fix all TypeScript build errors | ✅ Done | 71 static pages generate cleanly |
| Fix `$round` aggregation (not supported by DocumentDB) | ✅ Done | Computed in JS post-aggregation in 3 pages |
| Fix `propertyId` type: `number` → `string` (MongoDB ObjectId) | ✅ Done | Changed across 10+ components |
| Fix `authClient` stubs (no `useSession`, no `signOut`) | ✅ Done | Replaced with direct fetch to `/api/user/settings` |
| Fix `authClient.signOut()` → `fetch("/api/auth/logout")` | ✅ Done | header.tsx, header-nav.tsx |
| Fix `ListingRow` → `PropertyListing` shared interface | ✅ Done | `src/types/index.ts` |
| Fix agent-drawer.tsx wrong Badge import | ✅ Done | Changed to Button import |
| Rewrite hostaway/reply to use MongoDB | ✅ Done | Removed Neon SQL |
| Redirect auth/[path] → /login, account/[path] → /profile | ✅ Done | |
| Fix `getMode()` return type: add `"db"` | ✅ Done | `src/lib/pms/types.ts` |

**MongoDB Models (16 total):**
- `Organization` — org + user account
- `Listing` — properties with guardrails, autopilot config
- `InventoryMaster` — daily calendar (price, status, proposals)
- `Reservation` — bookings with channel, guest, dates
- `PricingRule` — seasonal rules, LOS discounts, gap fill rules
- `MarketEvent` — events with impact and premium %
- `MarketTemplate` — pre-built market configs (Dubai, London, NYC, etc.)
- `BenchmarkData` — comp set rates from OTA scan
- `Source` — PMS connection config
- `SourceRun` — PMS sync history
- `EngineRun` — pricing engine execution log
- `Insight` — AI-generated insights (pending/approved/rejected)
- `HostawayConversation` — guest inbox threads
- `ChatMessage` — CRO chat history
- `GuestSummary` — AI-generated conversation summaries
- `Detector` — anomaly detection config

---

### ✅ Phase 2: Seed Data Script

**File:** `seed_data.py` (project root)

Seeds all critical MongoDB collections with demo data:
- 1 Organization (`admin@priceos.ae` / `Admin@123456`)
- 5 Dubai listings with hostawayId, pricing guardrails, autopilot settings
- 450 InventoryMaster rows (90 days × 5 properties)
- 25 Reservations (past + future per property)
- 6 MarketEvents (GITEX, Eid, DSF, F1, Art Dubai, Airshow)
- 15 PricingRules (seasonal, LOS discount, gap fill)

**Commands to run seed:**
```bash
cd /Users/rohithp/Desktop/Priceos_April_updated_version/Original_priceos/priceos
pip install pymongo bcrypt python-dotenv
python ../../seed_data.py
```

**Not yet seeded:** `MarketTemplate`, `Source`, `Detector`, `BenchmarkData`, `HostawayConversation` (demo), `Insight`

---

### ✅ Phase 3: Agent Prompts — Updated for Global Expansion

**Prompt files location:** `updated_prompts_2/`

| File | Agent | Status | Key Changes |
|------|-------|--------|-------------|
| `01-cro-router.md` | CRO / Aria | ✅ Updated | Market-neutral language; `market_context` injection; regulatory awareness (London 90-night, Paris 120-night, Amsterdam, NYC, Barcelona, Dubai DTCM); regulatory escalation triggers |
| `02-property-analyst.md` | Property Analyst | No changes needed | Gap fill rules already market-agnostic |
| `03-booking-intelligence.md` | Booking Intelligence | No changes needed | Velocity + LOS analysis is market-agnostic |
| `04-market-research.md` | Market Research | No changes needed | Reads pre-cached data; no Dubai hardcoding |
| `05-price-guard.md` | PriceGuard (Adjustment Reviewer) | ✅ Updated | Market-calibrated guardrail table (UAE/GCC, Europe, US Leisure, US Urban, Global); market-specific weekend definition (`fri_sat`, `sat_sun`, `thu_fri`); market-specific hard-reject thresholds |
| `06-marketing-agent.md` | Event Intelligence Agent | ✅ Updated | Market-configurable queries (uses `market_context.city/country`); Dubai pre-built events preserved as template; Islamic calendar logic preserved for UAE; added European + US market seasonality; removed all Dubai hardcoding from global path |
| `07-benchmark-agent.md` | Benchmark Agent (Competitor Scanner) | ✅ Updated | Market-agnostic OTA selection (Airbnb-heavy US/AU; Booking.com-heavy Europe; mixed UAE); OTA weighting from `market_context`; scale reality checks adjusted per market currency |
| `08-channel-sync-agent.md` | Channel Sync Agent | ✅ NEW | Full new prompt: execution protocol, verification read-back, rollback rules, stale data protection, EngineRun logging |
| `09-anomaly-detector.md` | Anomaly Detector | ✅ NEW | Full new prompt: 6 anomaly detection rules, scoring model (0–1), severity thresholds, rollback triggers, CRO escalation |
| `10-guardrails-agent.md` | Guardrails Agent | ✅ Updated | Market-calibrated floor/ceiling defaults per profile (UAE/GCC, Europe, US Leisure, US Urban, Global); profile-aware safety checks; multi-currency reasoning |
| `conversation-summary-agent.md` | Conversation Summary Agent | No changes needed | Market-agnostic |
| `guest-reply-agent.md` | Reservation Agent (Guest Reply) | ✅ Updated | Removed Dubai-specific hardcoding; uses `market_context.city/currency`; added regulatory escalation triggers (permit/licence keywords → `escalate_to_host: true`); configurable check-in/check-out times |

---

### ✅ Phase 4: Backend API Routes — New & Updated

**New routes added:**

| Route | Method | Purpose | File |
|-------|--------|---------|------|
| `POST /api/proposals/[id]/reject` | POST | Reject individual pricing proposal | `src/app/api/proposals/[id]/reject/route.ts` |
| `GET /api/agents/status` | GET | Get health + last-run status of all 9 agents | `src/app/api/agents/status/route.ts` |
| `POST /api/engine/run-all` | POST | Trigger pricing engine for all org listings | `src/app/api/engine/run-all/route.ts` |

**Existing routes (already present):**
- `POST /api/proposals/[id]/approve` — Approve + execute via Channel Sync
- `POST /api/proposals/bulk-approve` — Batch approve
- `POST /api/proposals/bulk-reject` — Batch reject
- `GET /api/sync/status` — Data sync status
- `POST /api/sync/run` — Trigger PMS sync
- `GET /api/market-templates` — Get market templates
- `POST /api/market-setup` — Save market setup
- `GET /api/benchmark` — Get comp set data
- `GET /api/events` — Get market events
- `GET /api/insights` + `PATCH /api/insights/[id]` — Insights CRUD

---

## 2. What Needs To Be Done Next

### 🔲 Phase 5: Onboarding Flow (HIGH PRIORITY)

**Goal:** Replace the missing/incomplete onboarding with a 4-step wizard per the PRD.

| Step | What to build | Route |
|------|---------------|-------|
| Stage 0 | Market selection (country + city) → load market template | `/onboarding/market` |
| Stage 1 | PMS connection (Hostaway API key + OTA weighting question) | `/onboarding/connect` |
| Stage 2 | Portfolio import + zone/neighbourhood grouping | `/onboarding/portfolio` |
| Stage 3 | Guardrails setup with market-calibrated defaults pre-filled | `/onboarding/guardrails` |
| Stage 4 | Regulatory check — show compliance warnings per market | `/onboarding/compliance` |

**Backend needed:**
- `POST /api/onboarding/market-select` — Save market selection, load template
- `POST /api/onboarding/connect-pms` — Test PMS connection
- `POST /api/onboarding/import-portfolio` — Trigger initial PMS sync
- `POST /api/onboarding/set-guardrails` — Save market-calibrated guardrails

---

### 🔲 Phase 6: Pricing Rules Studio (HIGH REVENUE IMPACT)

**Goal:** Build the full pricing rules UI for operators to configure all Tier 1-2 pricing features.

**Pages/Tabs to build in `/pricing`:**

| Tab | Feature | Revenue Impact |
|-----|---------|---------------|
| Season Profiles | Named seasons with % or fixed price override per date range | 9/10 |
| Day-of-Week | 7-day grid with % adjustment sliders; weekend definition selector | 7/10 |
| Last-Minute Curve | Visual curve editor: x=days out, y=discount %; configurable ramp | 9/10 |
| Gap Fill Rules | Up to 5 gap rules (1-night, 2-night, 3-4 night) + weekday/weekend split | 8/10 |
| LOS Discounts | 7-night / 14-night / 28-night tiers | 7/10 |
| Date Overrides | Calendar picker for manual date-specific price overrides | 8/10 |
| Far-Out Floor | Booking window floor: minimum price rises as dates get closer | 8/10 |

**Backend needed:**
- `GET/POST /api/listings/[id]/pricing-rules` — CRUD for all rule types
- `POST /api/listings/[id]/preview-price` — Preview calculated price for a date given current rules

**Data model:** `PricingRule` model already exists. Extend with:
- `ruleType`: `"season"` | `"day_of_week"` | `"last_minute_curve"` | `"gap_fill"` | `"los_discount"` | `"date_override"` | `"far_out_floor"`
- `parameters`: `Record<string, unknown>` (flexible per rule type)

---

### 🔲 Phase 7: Market Intelligence Dashboard

**Goal:** Replace the empty `/market` page with a real dashboard.

**Components to build:**

| Component | Data Source | API |
|-----------|-------------|-----|
| Market Header (name, timezone, last refresh) | `market_context` from org settings | Existing `/api/user/settings` |
| Avg Market ADR card | `BenchmarkData` | `/api/benchmark` |
| Market Occupancy % card | `BenchmarkData` | `/api/benchmark` |
| Event Timeline (next 90 days) | `MarketEvent` | `/api/events` |
| Comp Set Rate Trend Chart | `BenchmarkData` (30-day history) | `/api/benchmark?history=true` |
| "Run Market Analysis" button | Triggers Agent 6 + 7 | `/api/sync/run` |

---

### 🔲 Phase 8: Agent Status Panel

**Goal:** Replace the current `agent-drawer.tsx` with a professional Agent Status Panel.

**Component:** `src/components/agents/agent-status-panel.tsx` (new)

**Features:**
- 9 agent cards with: name, role, status badge (Active / Warning / Error / Idle), last run time
- System state machine indicator: `Connected → Observing → Simulating → Active → Paused`
- `pendingProposals` count badge
- `criticalInsights` alert count
- "Run All" button → `POST /api/engine/run-all`
- Per-agent "Force Run" / "Pause" buttons (where applicable)

**Data source:** `GET /api/agents/status` (already built in Phase 4)

---

### 🔲 Phase 9: Regulatory Compliance Widget

**Goal:** Surface licence/permit tracking in Settings and Property detail pages.

**What to build:**
- `Listing` model: Add `licenceNumber: String`, `nightsUsedThisYear: Number`
- `GET /api/listings/[id]/compliance` — Return licence status + night count
- `PATCH /api/listings/[id]/compliance` — Update licence number
- UI component: `src/components/properties/compliance-widget.tsx`
  - Show: licence number input, nights used this year, warning at threshold, cap info
  - Market-aware caps (London 90, Paris 120, Amsterdam 30, Dubai: no cap but DTCM required)

---

### 🔲 Phase 10: Seed Script — Remaining Collections

**Collections not yet seeded:**

| Collection | What to add |
|------------|-------------|
| `MarketTemplate` | 10 market templates (Dubai, London, Barcelona, NYC, Miami, Amsterdam, Paris, Lisbon, Nashville, Sydney) |
| `Source` | 1 Hostaway source record per org |
| `Detector` | 6 detector configs (booking_pace, competitor_rate, gap_fill, anomaly, cancellation_risk, occupancy) |
| `BenchmarkData` | 5 comp sets (one per listing), each with 8-12 comp properties |
| `HostawayConversation` | 10 sample guest conversations (mix of resolved + needs-reply) |
| `Insight` | 15 sample insights (mix of pending/approved/rejected across all categories) |

---

## 3. APIs to Integrate (Deferred — Next Discussion)

### External APIs to use for agent intelligence:

| API | Agent | Purpose | Cost |
|-----|-------|---------|------|
| **Ticketmaster Discovery API** | Event Intelligence | Pull upcoming events near property (free tier: 5000 req/day) | Free |
| **Eventbrite API** | Event Intelligence | Local/niche events Ticketmaster misses | Free |
| **AirDNA API** | Competitor Scanner | Comp set ADR, occupancy, RevPAR by market | ~$200-500/month |
| **Hostaway REST API** | Data Aggregator + Channel Sync | Listings, reservations, calendar, inbox | Per plan |
| **Guesty API** | Data Aggregator + Channel Sync | Same (OAuth2) | Per plan |
| **VRBO/Rentals United** | Data Aggregator (US) | US market PMS integration | Per plan |
| **DTCM Open Data** | Event Intelligence (Dubai only) | Official Dubai tourism + events data | Free |

**Next session discussion:** How to wire these APIs into the existing agent architecture — which endpoints to call, where to store responses (which MongoDB collection), and how agents consume the cached data.

---

## 4. Architecture Summary

### 9-Agent Architecture (Manager-Worker Pattern)

```
User
  ↓
CRO / Aria (Manager — orchestrates, never executes)
  ├── Event Intelligence Agent (Worker — market events, news, threats)
  ├── Pricing Optimizer (Worker — 10-layer pricing formula)
  ├── Competitor Scanner / Benchmark Agent (Worker — comp set rates)
  ├── Data Aggregator (Worker — PMS sync)
  ├── Adjustment Reviewer / PriceGuard (Worker — guardrails)
  ├── Channel Sync Agent (Worker — PMS write + verify)
  ├── Anomaly Detector (Worker — post-execution monitoring)
  └── Reservation Agent (Worker — guest inbox)
```

### Pricing Formula (10 layers, applied in order)
```
Final Price =
  Base Price
  × Season Factor          (named season: Peak/Shoulder/Trough)
  × Day-of-Week Factor     (market-specific weekend definition)
  × Lead-Time Factor       (far-out premium OR last-minute curve)
  × Occupancy Factor       (listing + portfolio level)
  × Demand/Event Factor    (from Event Intelligence Agent)
  × Gap/Orphan Factor      (1-5 night gap rules)
  × LOS Discount           (7/14/28-night tiers)
  + Adjacent Booking Adj   (premium or discount around existing bookings)
  → Clip to [min_price, max_price]  ← guardrails ALWAYS win
```

### Market Guardrail Profiles

| Profile | Max Daily Change | Max Weekly Drift | Auto-Approve | Gap Discount Max |
|---------|-----------------|-----------------|-------------|-----------------|
| UAE/GCC | ±15% | ±40% | 5% | 20% |
| Europe | ±10% | ±25% | 3% | 15% |
| US Leisure | ±20% | ±50% | 7% | 25% |
| US Urban | ±12% | ±30% | 4% | 15% |
| Global | ±15% | ±40% | 5% | 20% |

### State Machine
```
Connected → Observing → Simulating → Active
                ↓           ↓           ↓
              Paused ← ← ← ← ← ← ← ← ←
```

---

## 5. File Reference

| File | Purpose |
|------|---------|
| `updated_prompts_2/01-cro-router.md` | CRO / Aria system prompt |
| `updated_prompts_2/02-property-analyst.md` | Property Analyst (gap fill, LOS) |
| `updated_prompts_2/03-booking-intelligence.md` | Booking velocity + revenue |
| `updated_prompts_2/04-market-research.md` | Market Research (reads cached data) |
| `updated_prompts_2/05-price-guard.md` | PriceGuard — pricing + guardrails |
| `updated_prompts_2/06-marketing-agent.md` | Event Intelligence (internet search) |
| `updated_prompts_2/07-benchmark-agent.md` | Benchmark / Competitor Scanner |
| `updated_prompts_2/08-channel-sync-agent.md` | Channel Sync (NEW) |
| `updated_prompts_2/09-anomaly-detector.md` | Anomaly Detector (NEW) |
| `updated_prompts_2/10-guardrails-agent.md` | Guardrails Agent (floor/ceiling calc) |
| `updated_prompts_2/guest-reply-agent.md` | Reservation Agent (guest inbox) |
| `updated_prompts_2/conversation-summary-agent.md` | Conversation Summary |
| `src/app/api/proposals/[id]/reject/route.ts` | Reject individual proposal (NEW) |
| `src/app/api/agents/status/route.ts` | All-agent health status (NEW) |
| `src/app/api/engine/run-all/route.ts` | Run pricing engine for all listings (NEW) |
| `seed_data.py` | Python seed script (run from project root) |

---

## 6. Known Issues / Tech Debt

| Issue | Severity | Notes |
|-------|----------|-------|
| `seed_data.py` missing 6 collections | Medium | MarketTemplate, Source, Detector, BenchmarkData, HostawayConversation, Insight |
| No onboarding wizard | High | Users land at dashboard with no market setup |
| `/market` page is empty | High | Market Intelligence dashboard not built |
| `/db-viewer` in production nav | Low | Should be removed from sidebar for production |
| `guardrail_profile` field missing from Listing model | Medium | Need to add to store market profile after onboarding |
| `nightsUsedThisYear` tracking not implemented | Medium | Needed for Paris/London/Amsterdam compliance |
| External API keys not configured | High | Ticketmaster, AirDNA — not in .env yet |
| Agent 6 + 7 run on dummy data | High | Need live Ticketmaster + AirDNA integration |
