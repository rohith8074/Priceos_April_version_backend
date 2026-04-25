# PriceOS V1 → V2 Migration: Complete Analysis & Implementation Plan

## Executive Summary

This document is the result of a deep file-by-file analysis of both codebases. The goal is to migrate V2's new features into the V1 codebase. Below is a section-wise breakdown of **every major difference**, what each section does, and **how to achieve the migration**.

> [!IMPORTANT]
> The two codebases share a common ancestor (Next.js 16 + Drizzle + Zustand + Tailwind v4) but diverge fundamentally in **database provider**, **auth system**, **multi-tenancy model**, **AI pipeline**, and **UI architecture**. This is NOT a simple feature port — it requires foundational infrastructure changes.

---

## Section 1: Database & ORM Layer

### What Changed

| Aspect | V1 (Original) | V2 (New) |
| :--- | :--- | :--- |
| **Provider** | Neon Postgres (`@neondatabase/serverless`) | Supabase Postgres (`postgres` package) |
| **Driver** | `drizzle-orm/neon-http` (HTTP-only, stateless) | `drizzle-orm/postgres-js` (TCP, connection pooling) |
| **Schema Size** | ~465 lines, 12 tables, `serial` PKs | ~805 lines, **21+ tables**, `uuid` PKs for org/user |
| **Multi-Tenancy** | Per-user (`userId` column) | Per-org (`orgId` UUID FK on **every** table) |
| **RLS** | None | Designed for Supabase RLS via `org_id` |
| **Enums** | 1 enum (`rule_type`) | **21 enums** (signal categories, status lifecycles, etc.) |

### V2-Only Tables (Not in V1)

| Table | Purpose | Priority |
| :--- | :--- | :--- |
| `organizations` | B2B tenant root (uuid PK, settings JSONB, Hostaway creds) | 🔴 Critical |
| `users` | Team members with roles (owner/admin/manager/viewer) | 🔴 Critical |
| `groups` | Market segmentation (area, BHK, type) | 🟡 High |
| `listing_groups` | Join table: listing ↔ group membership | 🟡 High |
| `strategies` | Pricing rule definitions (replaces embedded `rul_*` booleans) | 🔴 Critical |
| `strategy_changelog` | Audit trail for strategy mutations | 🟢 Medium |
| `sources` | L1 pipeline config (data collection agents) | 🟡 High |
| `detectors` | L2 pipeline config (signal analysis agents) | 🟡 High |
| `source_runs` | L1 execution history | 🟡 High |
| `detector_runs` | L2 execution history | 🟡 High |
| `insights` | Merged signals + suggestions (HITL lifecycle) | 🔴 Critical |
| `signal_snapshots` | Raw numeric outputs from detectors | 🟡 High |
| `competitor_snapshots` | Market rate/occupancy data per group | 🟢 Medium |
| `market_events` (redesigned) | Event data scoped to org, areas | 🟡 High |
| `seasonal_patterns` | Monthly demand benchmarks per area | 🟢 Medium |
| `staged_price_changes` | Engine-computed price diffs awaiting push | 🔴 Critical |
| `staged_strategy_toggles` | Pending activation/deactivation intents | 🟢 Medium |
| `team_invites` | Pending team invitations | 🟢 Medium |

### How to Achieve This

1. **Create a migration script** that adds the `organizations` table first, then updates every existing table to include an `org_id` column.
2. **Port the V2 schema** (`src/lib/db/schema.ts` — 805 lines) into V1, creating all 21+ enums and new tables.
3. **Swap the DB client** from `@neondatabase/serverless` (Neon HTTP) to `postgres` (TCP pooling). This means replacing:
   - `src/lib/db/index.ts`: Change from `neon()` + `drizzle(neon-http)` → `postgres()` + `drizzle(postgres-js)`.
4. **Add seed scripts** from V2's `scripts/` directory (5 scripts including `seed-production.ts`).
5. **Data migration**: Write a one-time script to create a default `organization`, assign all existing users to it, and backfill `org_id` on every table.

---

## Section 2: Authentication System

### What Changed

| Aspect | V1 | V2 |
| :--- | :--- | :--- |
| **Auth Provider** | Neon Auth (cookie-based) | Supabase Auth (`@supabase/ssr`) |
| **Session Cookies** | `__Secure-neon-auth.session_token` + variants | Supabase cookies (managed by `@supabase/ssr`) |
| **Middleware** | Checks Neon auth cookies | Calls `supabase.auth.getUser()` (JWT validation) |
| **Preview Mode** | Not present | `PREVIEW_MODE=1` bypasses auth for dev |
| **Password Auth** | bcrypt + `userSettings` table | bcrypt + `users` table |
| **RBAC** | Single `role` field | `userRoleEnum`: owner, admin, manager, viewer |

### V2 Auth Files (New)

- `src/lib/supabase/client.ts` — Browser client
- `src/lib/supabase/server.ts` — Server-side client
- `src/lib/supabase/env.ts` — Environment variable resolution
- `src/middleware.ts` — Supabase session refresh + auth guard

### How to Achieve This

1. **Install** `@supabase/ssr` and `@supabase/supabase-js`.
2. **Create** a Supabase project and configure env vars: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.
3. **Replace** V1's middleware with V2's Supabase middleware (port `src/middleware.ts`).
4. **Port** V2's `src/lib/supabase/` directory (3 files).
5. **Update** login/signup pages to use Supabase Auth instead of Neon Auth.
6. **Remove** Neon Auth dependencies: `@neondatabase/auth`.

---

## Section 3: State Management & Data Fetching

### What Changed

| Aspect | V1 | V2 |
| :--- | :--- | :--- |
| **Stores** | 5 Zustand stores (agent, chat, context, property, settings) | 3 Zustand stores (app, strategy, ui) |
| **Data Fetching** | Direct fetch / no caching layer | **TanStack React Query** (16 hooks) |
| **Caching** | Manual `AgentCacheProvider` | React Query auto-caching + optimistic updates |
| **Mock Data** | `src/data/` directory | `src/mock-data/` with 12 JSON fixtures |

### V2 Query Hooks (All New — `src/hooks/queries/`)

| Hook | Purpose |
| :--- | :--- |
| `use-bookings.ts` | Reservation data |
| `use-calendar.ts` | Calendar day pricing |
| `use-conversations.ts` | Guest messaging threads |
| `use-detector-runs.ts` | L2 execution history |
| `use-detectors.ts` | Detector configuration |
| `use-groups.ts` | Market segment groups |
| `use-insights.ts` | AI insights (HITL lifecycle) |
| `use-market.ts` | Market events & seasonality |
| `use-properties.ts` | Listing data |
| `use-settings.ts` | Org settings |
| `use-source-runs.ts` | L1 execution history |
| `use-sources.ts` | Source configuration |
| `use-staged-prices.ts` | Pending price changes |
| `use-strategies.ts` | Pricing strategies |
| `use-strategy-impact.ts` | Impact preview calculations |
| `use-team.ts` | Team members |

### How to Achieve This

1. **Install** `@tanstack/react-query`.
2. **Create** `src/lib/query-client.ts` (from V2).
3. **Create** `src/components/providers.tsx` wrapping `QueryClientProvider`.
4. **Port** all 16 hooks from V2's `src/hooks/queries/`.
5. **Consolidate** V1's 5 stores into V2's 3-store pattern (app, strategy, ui).
6. **Port** V2's mock-data system (`src/mock-data/` — 12 JSON files + index.ts).

---

## Section 4: AI & Intelligence Pipeline (ENTIRELY NEW)

### What V2 Adds

This is the largest new feature set. V1 has **no equivalent** — it has a basic AI chat and a simple pricing engine. V2 introduces a complete **3-layer intelligence pipeline**:

```
L1: Sources (Data Gathering) → L2: Detectors (Signal Analysis) → L3: Insights (AI Suggestions)
```

### V2 Pipeline Files

#### Layer 1 — Sources (`src/lib/pipeline/sources/`)
| File | What It Does |
| :--- | :--- |
| `hostaway.ts` | Pulls listings, calendar, reservations from Hostaway PMS |
| `competitors.ts` | Fetches competitor market rates via AI |
| `events.ts` | Scrapes Dubai events calendar |
| `seasonality.ts` | Generates seasonal demand patterns |
| `index.ts` | Source runner factory |

#### Layer 2 — Detectors (`src/lib/pipeline/detectors/`)
| File | What It Detects |
| :--- | :--- |
| `booking-pace.ts` | Booking velocity vs baseline |
| `lead-time.ts` | Booking lead time shifts |
| `cancellation-rate.ts` | Cancellation spikes |
| `occupancy.ts` | Occupancy gaps and trends |
| `gap-analysis.ts` | Unbooked gaps between reservations |
| `length-of-stay.ts` | LOS pattern changes |
| `competitor-rate.ts` | Rate positioning vs market |
| `day-of-week.ts` | Day-of-week pricing patterns |
| `review-score.ts` | Review score impact |
| `event-impact.ts` | Event-driven demand changes |
| `seasonality-detector.ts` | Seasonal demand patterns |
| `channel-mix.ts` | Channel distribution shifts |
| `index.ts` | Detector runner factory |
| `types.ts` | Shared types |

#### Layer 3 — AI Agent
| File | What It Does |
| :--- | :--- |
| `insight-agent.ts` | LLM-powered: takes signals → generates actionable insights |
| `orchestrator.ts` | Runs full L1→L2→L3 cascade |
| `pricing-automation.ts` | Auto-stage policy evaluation |
| `strategy-runner.ts` | **576 lines** — strategy engine with waterfall computation |
| `auto-groups.ts` | Auto-generates groups from listing properties |

#### AI Gateway (`src/lib/ai/`)
| File | What It Does |
| :--- | :--- |
| `gateway.ts` | Abstraction over OpenRouter + Lyzr APIs (factory pattern) |
| `context.ts` | Builds rich context for AI calls |
| `prompts/` | Prompt templates for insight generation |
| `tools/` | Tool definitions for function-calling |

### How to Achieve This

1. **Port the entire `src/lib/pipeline/` directory** (9 files + 2 subdirectories with 19 files).
2. **Port `src/lib/ai/` directory** (2 files + 2 subdirectories).
3. **Port the API routes**: `api/pipeline/`, `api/insights/`, `api/detectors/`, `api/sources/`, `api/staged-prices/`, `api/strategies/`, `api/signals/`, `api/push/`.
4. **Install** `ai` and `@ai-sdk/openai` packages.
5. **Database prerequisite**: All pipeline tables must exist first (sources, detectors, insights, signal_snapshots, etc.).

---

## Section 5: Pricing Engine

### What Changed

| Aspect | V1 | V2 |
| :--- | :--- | :--- |
| **Rules System** | Embedded `rul_*` booleans on `listings` table | Separate `strategies` table with priority ordering |
| **Engine Files** | `pipeline.ts` + `waterfall.ts` (22KB) | `pipeline.ts` + `waterfall.ts` + `server-pipeline.ts` (32KB) |
| **Staging** | `proposedPrice` on `inventory_master` | Separate `staged_price_changes` table with waterfall JSONB |
| **Scope** | Per-listing only | `global` / `group` / `property` |
| **Audit** | None | `strategy_changelog` table |
| **Strategy Runner** | Not present | **576-line** server-side engine (`strategy-runner.ts`) |

### How to Achieve This

1. **Port** V2's `src/lib/engine/` (3 files replacing V1's 2 files).
2. **Port** `src/lib/pipeline/strategy-runner.ts` (the 576-line server engine).
3. **Migrate** V1's `pricingRules` table → V2's `strategies` table.
4. **Create** `staged_price_changes` and `staged_strategy_toggles` tables.
5. **Port** API routes: `api/strategies/`, `api/staged-prices/`, `api/push/`.

---

## Section 6: UI Components & Design System

### What Changed

| Aspect | V1 | V2 |
| :--- | :--- | :--- |
| **UI Library** | shadcn/ui + **Radix UI** | shadcn/ui + **Base UI** (`@base-ui/react`) |
| **Component Count** | 18 component groups | 14 component groups (more focused) |
| **Layout** | Header + Sidebar (2-column) | Sidebar + TopBar + Agent Drawer (3-column) |
| **Design Tokens** | Basic CSS vars | 60+ CSS custom properties (surfaces, text, borders, status, charts, glow) |
| **Icons** | Lucide only | Lucide + Solar Bold (custom icon set) |
| **Fonts** | System fonts | Geist Sans + Geist Mono |
| **Product Tour** | Not present | Dynamic `ProductTour` component |

### V2-Only Components

| Component Directory | Purpose |
| :--- | :--- |
| `agent-bar/` | Collapsible AI agent side panel |
| `intelligence/` | InsightCard, InsightsBanner, InsightActions |
| `pricing/` | StrategyCard, GuardrailsBar, WaterfallBreakdown |
| `content/` | ContentEditor, ChannelTabs |
| `shared/` | PropertyFilterList, EntityPanel, StatusBadge |
| `icons/` | Custom Solar icon set wrapper |
| `tour/` | Interactive product tour |
| `settings/` | ManageView, GroupsSection, TeamSection |

### V1-Only Components (May Need Updating)

| Component Directory | Notes |
| :--- | :--- |
| `bookings/` | Merged into dashboard in V2 |
| `finance/` | Not present in V2 (deferred) |
| `proposals/` | Replaced by insights + staged-prices in V2 |
| `tasks/` | Not present in V2 (deferred) |
| `reservations/` | Merged into calendar in V2 |
| `signals/` | Replaced by detectors in V2 |
| `events/` | Replaced by market page in V2 |

### How to Achieve This

1. **Port** V2's `globals.css` (229 lines of design tokens replacing V1's 86 lines).
2. **Install** `geist` font package.
3. **Port** V2's component directories one at a time (start with `layout/`, then `shared/`, then feature-specific).
4. **Update** `components.json` to use `@base-ui/react` instead of Radix.
5. **Port** the `src/components/icons/` custom icon set.

---

## Section 7: API Routes

### V1 API Routes (26 endpoints)

```
api/agent/, api/auth/, api/benchmark/, api/calendar/, api/calendar-metrics/,
api/chat/, api/conversations/, api/db-viewer/, api/events/, api/expenses/,
api/hostaway/, api/listings/, api/lyzr-cleanup/, api/market-setup/,
api/proposals/, api/rag/, api/research/, api/reservations/, api/sync/,
api/tasks/, api/test-agent/, api/test-agent-alt/, api/upload/,
api/user/, api/users/, api/v1/
```

### V2 API Routes (26 endpoints — completely different)

```
api/agent/, api/auth/, api/bookings/, api/calendar/, api/conversations/,
api/detector-runs/, api/detectors/, api/groups/, api/health/, api/insights/,
api/listings/, api/market/, api/pipeline/, api/properties/, api/push/,
api/seed/, api/seed-strategies/, api/settings/, api/signals/,
api/source-runs/, api/sources/, api/staged-prices/, api/strategies/,
api/sync/, api/team/, api/webhooks/
```

### How to Achieve This

1. **Keep** V1's unique APIs that V2 doesn't have: `api/expenses/`, `api/tasks/`, `api/proposals/` (if still needed).
2. **Port** V2's new API routes for: `insights`, `strategies`, `staged-prices`, `push`, `pipeline`, `detectors`, `sources`, `signals`, `groups`, `settings`, `team`, `webhooks`.
3. **Replace** V1's `api/events/` with V2's `api/market/`.
4. **Replace** V1's `api/auth/` with Supabase-based auth.

---

## Section 8: Hostaway PMS Integration

### What Changed

| Aspect | V1 | V2 |
| :--- | :--- | :--- |
| **Abstraction** | `PMSClient` factory (mock/db/live modes) | Direct `HostawayClient` + `HostawaySync` |
| **Files** | `lib/pms/` (5 files: types, mock, db, hostaway, index) | `lib/hostaway/` (2 files: client, sync) |
| **Sync** | Not implemented (stubbed) | **Full sync pipeline** (10.6KB `sync.ts`) |
| **Client** | Basic stub | Full API client (6.7KB) with calendar intervals, reservations, conversations |

### How to Achieve This

1. **Replace** V1's `src/lib/pms/` with V2's `src/lib/hostaway/` (2 files).
2. **Port** V2's `api/sync/` route which triggers the sync pipeline.
3. **Remove** the mock/db/live factory pattern — V2 uses direct Supabase DB + Hostaway API.

---

## Recommended Migration Order

> [!WARNING]
> These phases should be executed sequentially. Each phase depends on the previous one.

### Phase 1: Foundation (Week 1-2)
1. Port V2 database schema (all 21+ tables + enums)
2. Swap DB client (Neon → Supabase/Postgres-js)
3. Swap auth (Neon Auth → Supabase Auth)
4. Install new dependencies (`@tanstack/react-query`, `@supabase/ssr`, `ai`, `geist`)
5. Port middleware

### Phase 2: Data Layer (Week 2-3)
1. Port TanStack React Query hooks (16 hooks)
2. Port Zustand stores (3 stores)
3. Port mock-data system
4. Data migration script (create default org, backfill `org_id`)

### Phase 3: Intelligence Pipeline (Week 3-5)
1. Port AI gateway (`src/lib/ai/`)
2. Port pipeline sources (L1)
3. Port pipeline detectors (L2)
4. Port insight agent (L3)
5. Port orchestrator
6. Port pipeline API routes

### Phase 4: Pricing Engine (Week 5-6)
1. Port strategies system (replacing `pricingRules`)
2. Port strategy runner engine
3. Port staged price changes system
4. Port push-to-PMS flow

### Phase 5: UI & Polish (Week 6-8)
1. Port design system (globals.css)
2. Port layout components (sidebar, topbar, agent drawer)
3. Port feature components (insights, pricing, content)
4. Port settings pages (groups, team, org config)
5. E2E testing

---

## Open Questions

> [!IMPORTANT]
> These decisions will impact the implementation plan significantly.

1. **Database provider**: Do you want to **keep Neon** and just adopt V2's schema? Or **switch to Supabase** entirely? (Switching gives you RLS and Supabase Auth out of the box.)

2. **Auth strategy**: Should we keep Neon Auth, or migrate to Supabase Auth? (V2 is built around Supabase Auth — porting without it requires significant auth rewiring.)

3. **Existing V1 features to keep**: V1 has `finance/`, `tasks/`, `proposals/`, `expenses/` which V2 dropped. Should these be preserved?

4. **Incremental vs. clean rebuild**: Given the ~70% divergence, would you prefer to:
   - **(A)** Incrementally modify V1 (risky, many conflicts), or
   - **(B)** Start from V2 and backport V1's unique features (cleaner)?

5. **Timeline priority**: Which V2 features are most urgent?
   - Intelligence Pipeline (insights, detectors, sources)?
   - Pricing Engine (strategies, waterfall, staged prices)?
   - UI refresh (design system, new components)?

---

## Verification Plan

### Automated Tests
- Run `npm run build` after each phase to ensure no compilation errors
- Run `npm run lint` to catch type errors
- Test DB schema with `npm run db:push -- --dry-run`

### Manual Verification
- Login/signup flow works with new auth
- Dashboard loads with mock data
- Pipeline runs end-to-end (source → detector → insight)
- Strategy engine computes correct waterfall prices
- Push-to-PMS flow sends correct data
