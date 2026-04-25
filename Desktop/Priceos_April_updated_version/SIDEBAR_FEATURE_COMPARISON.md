# PriceOS — Sidebar & Feature Comparison: V1 vs V2

> Comprehensive comparison of every navigation item, page, and feature between Original PriceOS (V1) and PriceOS 2.0 (V2).

---

## V1 Sidebar (5 Items — Minimal Flat List)

V1 uses a collapsible icon-only sidebar (16px → 256px on hover) with just 5 navigation items hardcoded in an array.

| # | Label | Route | Description |
|:--|:------|:------|:------------|
| 1 | **Portfolio** | `/dashboard` | Main dashboard with property overview, calendar, and booking data |
| 2 | **Agent Chat** | `/agent-chat` | AI CRO (Chief Revenue Officer) chat interface |
| 3 | **Guest Inbox** | `/guest-chat` | Guest messaging threads from Hostaway |
| 4 | **Pricing** | `/pricing` | Pricing rules and proposal management |
| 5 | **Team** | `/users` | User/team member management |

### V1 Hidden Pages (Not in Sidebar, Accessible via Header or Direct URL)

| Page | Route | Description |
|:-----|:------|:------------|
| Bookings | `/bookings` | Reservation list view |
| Calendar | `/calendar` | Calendar grid with daily pricing |
| Reservations | `/reservations` | Detailed reservation management |
| Properties | `/properties` | Property list and configuration |
| Proposals | `/proposals` | AI-generated pricing proposals (current → proposed) |
| Insights | `/insights` | Analytics and intelligence overview |
| Finance | `/finance` | Revenue tracking and owner statements |
| Tasks | `/tasks` | Task board (cleaning, maintenance, inspections) |
| Operations | `/operations` | Operations dashboard |
| Profile | `/profile` | User profile settings |
| DB Viewer | `/db-viewer` | Debug tool for database inspection |

---

## V2 Sidebar (10 Items in 2 Groups + 4 Bottom Actions)

V2 uses a fixed-width sidebar (232px desktop, 272px mobile drawer) with structured 2-group navigation, live insight count badges, and bottom utility actions.

### Group 1: Business Pages

| # | Label | Route | Description |
|:--|:------|:------|:------------|
| 1 | **Dashboard** | `/dashboard` | Calendar + portfolio view with Focus/Portfolio modes, booking pace tracking |
| 2 | **Pricing** | `/pricing` | Strategy cards with waterfall breakdown, guardrails bar, engine runner |
| 3 | **Market** | `/market` | Market intelligence hub — 3 sub-tabs: Competitors, Events, Seasonality |
| 4 | **Inbox** | `/inbox` | Guest conversations with AI draft → approve → send workflow |
| 5 | **Content** | `/content` | AI-powered listing description editor with per-channel tabs |

### Group 2: Pipeline Pages

| # | Label | Route | Badge | Description |
|:--|:------|:------|:------|:------------|
| 6 | **Sources** | `/sources` | — | L1 data collection agents (Hostaway, Competitors, Events, Seasonality) |
| 7 | **Detectors** | `/detectors` | — | L2 signal detection algorithms (12 detectors) |
| 8 | **Signals** | `/signals` | — | Raw numeric signal snapshots from detectors |
| 9 | **Insights** | `/insights` | Live pending count | AI suggestions with HITL lifecycle (approve/reject/snooze/supersede) |

### Bottom Section (4 Actions)

| Action | Type | Description |
|:-------|:-----|:------------|
| **Settings** | Link → `/settings` | Org configuration with 4 sub-pages |
| **Log out** | Button | Supabase sign-out |
| **Restart Tour** | Button | Restarts the interactive product walkthrough |
| **How it works** | Button → Modal | Educational modal explaining Price/Inbox/Content workflows step-by-step |

### V2 Settings Sub-Pages

| Sub-Page | Route | Description |
|:---------|:------|:------------|
| Properties | `/settings/properties` | Property configuration, sync settings |
| Connections | `/settings/connections` | Hostaway API key, connection status |
| Organization | `/settings/organization` | Org name, timezone, currency, team members |
| Automation | `/settings/automation` | Pricing automation policies (auto-stage thresholds) |

### V2 Market Sub-Pages

| Sub-Page | Route | Description |
|:---------|:------|:------------|
| Competitors | `/market/competitors` | Competitor rate snapshots per group |
| Events | `/market/events` | Dubai events calendar with demand impact |
| Seasonality | `/market/seasonality` | Monthly demand/rate benchmarks per area |

---

## Side-by-Side Feature Comparison

| Feature / Section | V1 | V2 | Notes |
|:------------------|:--:|:--:|:------|
| **Dashboard** | ✅ | ✅ | V2 is significantly more advanced |
| **Pricing** | ✅ | ✅ | V1 = `pricingRules` on listings. V2 = `strategies` table + waterfall engine |
| **Market Intelligence** | ❌ | ✅ | **V2-only** — 3 tabs: Competitors, Events, Seasonality |
| **Inbox / Guest Chat** | ✅ | ✅ | V2 adds AI draft → approve → send workflow |
| **Content Editor** | ❌ | ✅ | **V2-only** — AI-powered listing description editor |
| **Sources (Pipeline L1)** | ❌ | ✅ | **V2-only** — Data collection config and run history |
| **Detectors (Pipeline L2)** | ❌ | ✅ | **V2-only** — 12 signal detection algorithms |
| **Signals** | ❌ | ✅ | **V2-only** — Raw detector output snapshots |
| **Insights** | ✅ (basic) | ✅ (advanced) | V1 = simple analytics. V2 = full HITL lifecycle |
| **Settings** | ❌ | ✅ | **V2-only** — 4 sub-pages: Properties, Connections, Org, Automation |
| **Agent Chat** | ✅ (sidebar page) | ✅ (Aria drawer) | V1 = dedicated sidebar page. V2 = collapsible drawer available on every page |
| **Team / Users** | ✅ (sidebar item) | ✅ (in Settings) | V1 = standalone sidebar item at `/users`. V2 = Settings > Organization |
| **Bookings** | ✅ (page) | ✅ (embedded) | V1 = separate page. V2 = merged into Dashboard calendar |
| **Calendar** | ✅ (page) | ✅ (embedded) | V1 = separate page. V2 = merged into Dashboard |
| **Reservations** | ✅ (page) | ✅ (embedded) | V1 = separate page. V2 = shown inside Dashboard |
| **Proposals** | ✅ (page) | ❌ (replaced) | **Replaced in V2** by Insights + Staged Prices system |
| **Finance** | ✅ (page) | ❌ | **V1-only** — Revenue tracking, owner statements |
| **Tasks** | ✅ (page) | ❌ | **V1-only** — Task board (cleaning, maintenance) |
| **Properties** | ✅ (page) | ✅ (Settings tab) | V1 = standalone page. V2 = Settings > Properties |
| **Operations** | ✅ (page) | ❌ | **V1-only** — Operations dashboard |
| **DB Viewer** | ✅ (debug) | ❌ | **V1-only** — Database inspection debug tool |
| **Product Tour** | ❌ | ✅ | **V2-only** — Interactive onboarding walkthrough |
| **"How It Works" Modal** | ❌ | ✅ | **V2-only** — Tabbed modal explaining Price/Inbox/Content workflows |
| **Demo Banner** | ❌ | ✅ | **V2-only** — Shows when Hostaway is not connected |
| **Property Selector (TopBar)** | ❌ | ✅ | **V2-only** — Global property/group filter in the TopBar |

---

## Summary Statistics

| Metric | V1 | V2 |
|:-------|:--:|:--:|
| Sidebar Items | 5 | 10 (in 2 groups) |
| Bottom Actions | 0 | 4 |
| Total Navigable Pages | 16 | 17 |
| V2-only new pages | — | 6 |
| V1-only pages | 4 | — |
| Extra UX features | — | 3 (Tour, Modal, Demo Banner) |
| Sidebar code size | 71 lines / 3.6KB | 389 lines / 19.7KB |

---

## Migration Priorities

### 🔴 Critical — New Sidebar Sections (must port)
1. **Market** (`/market`) — Competitors, Events, Seasonality tabs
2. **Content** (`/content`) — AI listing description editor
3. **Sources** (`/sources`) — Pipeline L1 data collection
4. **Detectors** (`/detectors`) — Pipeline L2 signal analysis
5. **Signals** (`/signals`) — Signal snapshots viewer
6. **Settings** (`/settings`) — Properties, Connections, Org, Automation

### 🟡 High — Upgraded Existing Sections
7. **Pricing** — Migrate from `pricingRules` to `strategies` + waterfall engine
8. **Insights** — Upgrade from basic analytics to full HITL lifecycle
9. **Inbox** — Add AI draft → approve → send workflow
10. **Dashboard** — Merge bookings/calendar into single unified view

### 🟢 Medium — UX Enhancements
11. **Agent Chat → Aria Drawer** — Move from sidebar page to omnipresent collapsible panel
12. **Product Tour** — Add interactive onboarding
13. **How It Works Modal** — Add educational workflow modal
14. **Property Selector** — Add global filter in TopBar
15. **Demo Banner** — Add demo mode indicator

### ⚪ Decision Required — V1-Only Features
16. **Finance** — Keep or drop?
17. **Tasks** — Keep or drop?
18. **Operations** — Keep or drop?
19. **DB Viewer** — Keep or drop?
