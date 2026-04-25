# PriceOS Implementation Checklist
> PRD & Knowledge Base vs Current Implementation (April 2026)
> Sources: architecture.md, product-walkthrough.md, product-guide/README.md, pricing_rules_features.md, strategy_parameters.md

---

## 1. Navigation & Layout

| Feature | PRD Requirement | Status | Notes |
|---------|----------------|--------|-------|
| 3-column layout: Sidebar + Main + Agent Panel | Agent Panel collapsible on right, always accessible | ⚠️ Partial | Dashboard has embedded panel. Other pages don't have it. Agent Chat is a separate full page instead. |
| Sidebar — Dashboard | `/dashboard` | ✅ Done | |
| Sidebar — Pricing | `/pricing` | ✅ Done | |
| Sidebar — Market | `/market` | ✅ Done | |
| Sidebar — Insights | `/insights` | ✅ Done | Moved to Business group |
| Sidebar — Agent Chat | `/agent-chat` | ✅ Done | |
| Sidebar — Guest Inbox | `/guest-chat` | ✅ Done | With unread badge |
| Sidebar — Agents | `/agents` | ✅ Done | With warning badge |
| Sidebar — Sync | `/sync` | ✅ Done | Consolidated from Sources/Detectors/Signals |
| Sidebar — User Management | `/users` | ✅ Done | |
| Sidebar — Settings | `/settings` | ✅ Done | |
| Sidebar badge: pending proposals count | Shows on Insights nav item | ✅ Done | |
| Sidebar badge: critical insights | Shows on Insights nav item | ✅ Done | |
| Sidebar badge: agent warnings | Shows on Agents nav item | ✅ Done | |
| Sidebar badge: guest unread | Shows on Guest Inbox item | ✅ Done | |
| Dark/Light mode toggle | Sidebar bottom | ✅ Done | |
| Context-aware Agent Panel (knows current page + selected entity) | PRD §08 | ❌ Missing | Agent Chat is a standalone page, not injected into every page's right column |

---

## 2. Dashboard

| Feature | PRD Requirement | Status | Notes |
|---------|----------------|--------|-------|
| Portfolio KPI strip (properties, occupancy, ADR, revenue) | Dashboard §02 | ✅ Done | |
| Top Drivers by Revenue chart (bar) | Dashboard §02 | ✅ Done | |
| Occupancy Rate by Property chart (bar) | Dashboard §02 | ✅ Done | |
| Global Calendar (30-day, all properties) | Dashboard §02 | ✅ Done | |
| Property detail table (sortable) | Dashboard §02 | ✅ Done | |
| Sync Hostaway button | Dashboard §02 | ✅ Done | |
| Agent status strip (active agents, warnings, pending proposals) | Added in sprint | ✅ Done | |
| Floating "Ask AI" FAB button | Dashboard §02 | ✅ Done | Links to /agent-chat |
| Focus mode (single property calendar with insight banners) | Dashboard V2 §02 | ❌ Missing | V2 has per-property focus mode. Current dashboard is portfolio-only. |
| Property carousel (cycle through properties) | Dashboard V2 §02 | ❌ Missing | |
| Month navigation arrows | Dashboard V2 §02 | ⚠️ Partial | Month picker input exists, no prev/next arrows |
| Insight banners on calendar days | Dashboard V2 §02 | ❌ Missing | |
| Strategy effect indicators on calendar (e.g. -20%, +12%) | Dashboard V2 §02 | ❌ Missing | |

---

## 3. Pricing

| Feature | PRD Requirement | Status | Notes |
|---------|----------------|--------|-------|
| Pending proposals list | Pricing §03 | ✅ Done | |
| Proposal reasoning (expandable) | Pricing §03 | ✅ Done | |
| Constraint badges (minStay, maxStay, CTA, CTD) | Pricing §03 | ✅ Done | |
| KPI summary strip (pending, increases, decreases, avg change) | Pricing §03 | ✅ Done | |
| Bulk approve / bulk reject | Pricing §03 | ✅ Done | |
| Select all / select individual | Pricing §03 | ✅ Done | |
| Pricing Rules Studio (base price, floor, ceiling, DOW, seasonal) | Pricing §03 | ✅ Done | UI built |
| Save PricingRulesStudio to real API | Pricing §03 | ❌ Missing | Buttons exist but state is local only — not wired to `PUT /api/listings/[id]/engine-config` |
| Guardrails: BASE, FLOOR, CEILING per property | V2 Pricing §03 | ❌ Missing | Not per-property, portfolio-level only |
| Strategy creation form (name, priority, scope, date range, DOW, effects) | V2 Pricing §03 | ❌ Missing | No strategy CRUD in UI |
| Strategy list with priority ordering | V2 Pricing §03 | ❌ Missing | |
| Strategy effect waterfall visualization | V2 architecture | ❌ Missing | |
| Push approved price changes to Hostaway | Channel Sync agent | ⚠️ Partial | Approve removes from list but no Hostaway push confirmation |

---

## 4. Market Intelligence

| Feature | PRD Requirement | Status | Notes |
|---------|----------------|--------|-------|
| Event Calendar (next 90 days) | Market §04 | ✅ Done | |
| High-impact event badge count | Market §04 | ✅ Done | |
| Demand signal summary alert | Market §04 | ✅ Done | |
| Portfolio occupancy & ADR KPI cards | Market §04 | ✅ Done | |
| Run Market Analysis button | Market §04 | ✅ Done | |
| Competitor Benchmark panel | Market §04 | ✅ Done | Verdict, P25/P50/P75/P90, recommended rates, comp table |
| Listing selector for benchmark | Market §04 | ✅ Done | |
| Rate trend indicator (rising/stable/falling) | Market §04 | ✅ Done | |
| Seasonal demand benchmarks per area | V2 reference | ❌ Missing | `seasonal_patterns` table not implemented |

---

## 5. Insights

| Feature | PRD Requirement | Status | Notes |
|---------|----------------|--------|-------|
| Insights list with severity (critical/warning/info) | Insights §06 | ✅ Done | |
| Status filter tabs (pending/approved/snoozed/dismissed) | Insights §06 | ✅ Done | |
| Approve / Snooze / Dismiss actions | Insights §06 | ✅ Done | |
| Confidence score display | Insights §06 | ✅ Done | |
| Action type badge (price-change, min-stay, etc.) | Insights §06 | ✅ Done | |
| Staged tab → "Push to Hostaway" button | V2 Insights §06 | ❌ Missing | No staged state or push flow |
| Insight → auto-create strategy from insight | V2 Insights §06 | ❌ Missing | |
| Sidebar badge decrements after approval | V2 §06 | ⚠️ Partial | Badge fetches on page load, doesn't live-update after action |

---

## 6. Sync / Pipeline

| Feature | PRD Requirement | Status | Notes |
|---------|----------------|--------|-------|
| Sources tab (list, last run, status) | Sync §05 | ✅ Done | |
| Detectors tab (list, signals found) | Sync §05 | ✅ Done | |
| Engine Runs tab (run history, days changed, duration) | Sync §05 | ✅ Done | |
| Run Engine Now button | Sync §05 | ✅ Done | |
| Per-source manual trigger | Sync §05 | ❌ Missing | No per-source run button |
| Scan history per source (sourceRuns) | V2 Sync §05 | ❌ Missing | Only engine-level runs shown |
| Signal snapshot viewer | V2 Sync §05 | ❌ Missing | Raw signal values not exposed in UI |

---

## 7. Agents

| Feature | PRD Requirement | Status | Notes |
|---------|----------------|--------|-------|
| Agent status panel (active/warning/error per agent) | Agents | ✅ Done | |
| Engine run history (today's stats + run table) | Agents | ✅ Done | |
| Agent health warning badge in sidebar | Agents | ✅ Done | |
| Per-agent configuration / enable-disable toggle | V2 Agents | ❌ Missing | |
| Agent log viewer (detailed logs per run) | V2 Agents | ❌ Missing | |

---

## 8. Guest Inbox

| Feature | PRD Requirement | Status | Notes |
|---------|----------------|--------|-------|
| Guest conversations list | Inbox §04 | ✅ Done | Fetched from Hostaway cached API |
| Conversation thread view | Inbox §04 | ✅ Done | |
| AI-drafted reply (approve/edit/send) | Inbox §04 | ⚠️ Partial | Draft display exists, send action may be stubbed |
| Unread badge in sidebar | Inbox §04 | ✅ Done | |
| GuestSummary display (AI-generated per-listing summary, sentiment, themes, action items) | GuestSummary model | ❌ Missing | Model exists in DB, not rendered anywhere in UI |
| Channel badges (Airbnb=rose, Booking.com=blue) | V2 Inbox §04 | ❌ Missing | |
| Portfolio mode (all conversations across properties) | V2 Inbox §04 | ⚠️ Unknown | Unclear if current guest-chat shows all properties |

---

## 9. Agent Chat (CRO Interface)

| Feature | PRD Requirement | Status | Notes |
|---------|----------------|--------|-------|
| Chat interface with streaming responses | Agent Chat | ✅ Done | UnifiedChatInterface component |
| Context panel (property list with metrics) | Agent Chat | ✅ Done | |
| Sidebar tabbed view (events + sync status) | Agent Chat | ✅ Done | |
| Portfolio data context injected into agent | Agent Chat | ⚠️ Partial | Data passed as props but unclear if sent to AI system prompt |
| Floating "Ask AI" button on Dashboard | Added in sprint | ✅ Done | Links to /agent-chat |
| Agent accessible from ALL pages (not just dedicated page) | V2 §08 | ❌ Missing | Agent is a full separate page, not an overlay on every page |
| Quick action buttons (Summarize signals, Scan revenue gaps, Compare competitors) | V2 §08 | ✅ Done | |

---

## 10. Settings & User Management

| Feature | PRD Requirement | Status | Notes |
|---------|----------------|--------|-------|
| Users page | Settings §07 | ✅ Done | `/users` route exists |
| Settings page | Settings §07 | ✅ Done | |
| Organization config (name, currency) | V2 Settings §07 | ⚠️ Unknown | Settings page may be a stub |
| Hostaway API key configuration | V2 Settings §07 | ❌ Missing | No Hostaway credentials UI |
| Property setup wizard | V2 Settings §07 | ❌ Missing | |
| Team invites | V2 Settings §07 | ❌ Missing | |
| Groups management (market segmentation) | V2 Settings §07 | ❌ Missing | No group CRUD |
| Property activate / deactivate | V2 §09 | ❌ Missing | |

---

## 11. Content Page

| Feature | PRD Requirement | Status | Notes |
|---------|----------------|--------|-------|
| Property description editor | Content §05 | ⚠️ Page exists | `/content` page exists but may be stubbed |
| House rules editor | Content §05 | ⚠️ Unknown | |
| Content insight banner ("N content insights pending") | Content §05 | ❌ Missing | |
| Auto-save on edit | Content §05 | ❌ Missing | |
| Channel-specific fields (Airbnb, Booking.com) | Content §05 | ❌ Missing | |

---

## 12. Agent Outputs → UI Mapping

| Agent | Data Saved To (MongoDB) | Where Rendered in UI |
|-------|------------------------|---------------------|
| **Data Aggregator** | `InventoryMaster`, `Listing`, `Reservation` | Dashboard KPIs, charts, calendar, Property table |
| **Event Intelligence** | `MarketEvent` | Market → Event Calendar timeline |
| **Competitor Scanner** | `BenchmarkData` | Market → Competitor Benchmark panel |
| **Pricing Optimizer** | `InventoryMaster` (proposedPrice, reasoning, changePct) | Pricing → Proposals tab |
| **Adjustment Reviewer** | `InventoryMaster` (proposalStatus, risk flags) | Pricing → proposal filter (pending only shown) |
| **Channel Sync** | `InventoryMaster` (status: approved/pushed) | Pricing → approve removes from list |
| **Guest AI Responder** | `GuestMessage` (content, isDraft) | Guest Inbox → conversation thread (draft display) |
| **GuestSummary** | `GuestSummary` (summary, sentiment, themes, actionItems) | ❌ **NOT RENDERED** — Model exists, no UI |
| **Engine Runner** | `EngineRun` (status, daysChanged, durationMs) | Agents → Engine Run History panel |
| **Insight Generator** | `Insight` (severity, confidence, action) | Insights → Pending/Approved/Dismissed tabs |

---

## 13. Architecture Requirements (7-Parameter Vector)

| Parameter | Hostaway Field | Status |
|-----------|---------------|--------|
| `price` | `price` | ✅ Stored, proposed, pushed on approve |
| `minimum_stay` | `minimumStay` | ✅ Stored in InventoryMaster, shown in Pricing constraints |
| `maximum_stay` | `maximumStay` | ✅ Stored in InventoryMaster, shown in Pricing constraints |
| `is_available` | `isAvailable` | ⚠️ Stored as status=blocked, not explicitly surfaced |
| `closed_to_arrival` | `closedOnArrival` | ✅ Stored and shown as constraint badge |
| `closed_to_departure` | `closedOnDeparture` | ✅ Stored and shown as constraint badge |
| `note` | `note` | ⚠️ Stored as `reasoning` field, not labeled as audit trail |

---

## 14. Priority Gap Summary

### 🔴 Critical Missing (Blocks Core Value Prop)
- [ ] PricingRulesStudio Save wired to real API (`PUT /api/listings/[id]/engine-config`)
- [ ] Strategy CRUD (create/edit/delete pricing strategies)
- [ ] GuestSummary UI (AI-generated per-listing summaries not shown anywhere)
- [ ] Hostaway push confirmation after approving proposals

### 🟡 High Priority Missing (Reduces PM Workflow Coverage)
- [ ] Per-property focus mode on Dashboard (single property calendar + insight banners)
- [ ] Agent Panel accessible from all pages (not just /agent-chat)
- [ ] Staged insights tab + "Push to Hostaway" flow
- [ ] Content page editor (auto-save, per-channel fields)

### 🟢 Medium Priority (Polish & Completeness)
- [ ] Property setup wizard in Settings
- [ ] Team invites + RBAC roles UI
- [ ] Groups management (market segmentation)
- [ ] Per-source manual trigger in Sync page
- [ ] Seasonal demand benchmarks in Market page
- [ ] Strategy effect waterfall visualization on calendar
