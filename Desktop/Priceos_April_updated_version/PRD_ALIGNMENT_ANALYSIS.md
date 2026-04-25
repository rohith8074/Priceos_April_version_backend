# PRD Alignment Analysis: Dubai → Global Change Spec vs V1 & V2 Codebase

> **Document:** Dubai → Global Change Spec (PriceOS | AI Revenue Manager for Short-Term Rentals)
> **Purpose:** Gap analysis between what the PRD demands and what currently exists in V1 and V2.

---

## What the PRD Says (Executive Summary)

The PRD is a **strategic repositioning document** — it moves PriceOS from a Dubai-first, Dubai-hardcoded product to a **global STR platform** where Dubai remains the best-proven market template, not the only market.

### What Must Stay the Same (per PRD)
- 9-agent Manager–Worker architecture (CRO + Workers)
- Execution loop: observe → propose → approve → execute → verify → monitor → rollback
- State machine: Connected → Observing → Simulating → Active → Paused
- Pricing model: $30/property/month
- Dubai as first market (but now as a "template", not a hardcoded scope)

### What Must Change (per PRD)
| Area | Current (Dubai-hardcoded) | Required (Global) |
|:-----|:--------------------------|:------------------|
| Event Intelligence | GITEX, UAE National Day, Ramadan hardcoded | Configurable market layer via API (Ticketmaster, Eventbrite) |
| Pricing Optimizer | Islamic Thu/Fri weekend premium hardcoded | Weekend definition = configurable parameter |
| Seasonal patterns | Jul–Aug Dubai trough hardcoded | Market-templated, loaded from operator's market |
| Currency | AED hardcoded throughout | Auto-detect from PMS account (operator base currency) |
| Competitor Scanner | Dubai zones, Dubai Airbnb/Booking.com | Market-agnostic, operator-provided comp set URLs |
| CRO Agent prompts | Dubai-specific language, AED, DTCM refs | Market-neutral + localisation layer from system_state |
| Guardrail defaults | ±15% fixed (Dubai calibrated) | Market-calibrated: UAE ±15%, Europe ±10%, US Leisure ±20% |
| Onboarding | Dubai zone names pre-filled | Market selection step → template loading |
| Copy/Positioning | "Built for Dubai" everywhere | "Autonomous Pricing for Short-Term Rentals" globally |
| PMS list | 5 UAE-focused PMS | Global: + Ownerrez, Track, VRBO/Escapia, Smoobu, BookingSync |
| Compliance flags | DTCM only | 6 market flags: Barcelona, Amsterdam, Paris, NYC, London, Dubai |

---

## Are V1 and V2 Aligned to This PRD?

### 🔴 V1 (Original PriceOS) — SEVERELY MISALIGNED

**V1 is ~90% misaligned with the PRD.** Here's why:

| PRD Requirement | V1 Status | Gap |
|:----------------|:---------:|:----|
| Market-configurable event layer | ❌ | V1 uses hardcoded Dubai event logic in agents |
| Configurable weekend definition | ❌ | Islamic Thu/Fri hardcoded in pricing engine |
| Dynamic currency from PMS | ❌ | AED hardcoded throughout schemas and prompts |
| Market-neutral CRO prompts | ❌ | All system prompts reference Dubai, DTCM, AED |
| Market template loading at onboarding | ❌ | No concept of market templates exists |
| Guardrail calibration by market | ❌ | Fixed ±15% Dubai-calibrated defaults |
| Comp set by operator URL | ❌ | Dubai zone-based competitor logic |
| Regulatory compliance flags | ❌ | DTCM only, no global regulatory awareness |
| Multi-PMS global priority list | ❌ | Hostaway-first, UAE-focused order |
| Timezone-relative scheduling | ❌ | Dubai timezone hardcoded in scheduling |
| Multi-currency normalization | ❌ | No currency normalization layer |
| Groups from PMS data (not Dubai zones) | ❌ | Dubai zone names as group defaults |

**What V1 does have that aligns:**
- ✅ 9-agent Manager–Worker architecture (CRO + 8 workers) — PRD says keep this
- ✅ Execution loop (propose → approve → execute) — PRD says keep this
- ✅ State machine (Connected → Active) — PRD says keep this
- ✅ Hostaway as primary PMS — PRD keeps Hostaway as global primary

---

### 🟡 V2 (PriceOS 2.0) — PARTIALLY ALIGNED

**V2 is ~50% aligned.** It has the right infrastructure but is still Dubai-specific in many places:

| PRD Requirement | V2 Status | Gap |
|:----------------|:---------:|:----|
| Market-configurable event layer | 🟡 Partial | V2 has `events` source in pipeline, but it still fetches Dubai events. Not yet fully parameterized by market |
| Configurable weekend definition | ❌ | Strategy runner doesn't have configurable weekend definitions |
| Dynamic currency from PMS | 🟡 Partial | `organizations.settings` JSONB has currency field, but not wired end-to-end |
| Market-neutral CRO prompts | 🟡 Partial | V2 AI gateway has `OrgAISettings` — context is org-scoped, but prompts still contain market assumptions |
| Market template loading at onboarding | ❌ | Settings > Connections only links Hostaway — no market selection step |
| Guardrail calibration by market | ❌ | Strategy defaults not market-calibrated in V2 either |
| Comp set by operator URL | 🟡 Partial | V2 competitor scanner exists but not fully operator-configured |
| Regulatory compliance flags | ❌ | Not implemented in V2 |
| Multi-PMS global priority list | ❌ | V2 only has Hostaway integration |
| Timezone-relative scheduling | 🟡 Partial | `organizations.settings` has timezone, but pipeline cron not using it |
| Multi-currency normalization | ❌ | Not implemented |
| Groups from PMS data | ✅ | V2 `auto-groups.ts` pulls from listing metadata — good! |
| `org_id` multi-tenant scoping | ✅ | V2 is fully multi-tenant — aligns with global operator model |
| Configurable sources/detectors | ✅ | V2 pipeline sources/detectors are DB-driven configs — aligns with "market-configurable layer" |
| Insights with HITL | ✅ | V2 HITL lifecycle aligns with "propose → approve → execute" loop |

---

## The Core Mismatches (What Needs to Be Built)

### Mismatch 1: No Market Template System ❌ CRITICAL
**PRD says:** At Stage 0 onboarding, user selects their market. System loads a full template (event calendar, OTA weighting, weekend definition, seasonal patterns, regulatory flags).

**Reality:** Neither V1 nor V2 has any concept of a market template. There is no `market_templates` table, no onboarding market selector, no template loading mechanism.

**What to build:**
```
DB table: market_templates
  - id, market_code (dubai, london, nyc, barcelona...)
  - weekend_definition (thu_fri / fri_sat / sat_sun)
  - currency_default
  - event_api_config (JSON)
  - seasonal_patterns (JSON)
  - ota_weighting (JSON)
  - guardrail_defaults (JSON)
  - regulatory_flags (JSON)
  - timezone

DB table: market_regulatory_flags
  - market_code, regulation_name, description, night_cap, warning_threshold

Settings > Connections: Add market selection step
organizations table: Add market_code foreign key
```

---

### Mismatch 2: Hardcoded Dubai Event Logic ❌ HIGH
**PRD says:** Event Intelligence Agent must pull from Ticketmaster/Eventbrite APIs based on operator's selected market. Dubai stays as a pre-built template.

**Reality:**
- V1: Hardcoded Dubai events in agent prompts
- V2: `src/lib/pipeline/sources/events.ts` — still Dubai-focused event scraping

**What to build:**
- `events.ts` source must accept `market_code` from `organizations.settings`
- Integrate Ticketmaster/Eventbrite APIs with market-specific queries
- Store Dubai data as market template (not hardcoded)
- Allow operators to add custom events (UI in Market > Events page)

---

### Mismatch 3: Weekend Definition Hardcoded ❌ HIGH
**PRD says:** Weekend definition must be a configurable parameter (Thu/Fri for UAE, Fri/Sat globally, Sat/Sun for some markets).

**Reality:**
- V1: Islamic weekend premium hardcoded in waterfall engine
- V2: Strategy waterfall in `waterfall.ts` and `strategy-runner.ts` — `daysOfWeek` is in `strategies` table but not fed by market template

**What to build:**
- Add `weekend_definition` to `organizations.settings`
- Strategy runner must apply weekend premium logic based on org's weekend setting
- Market template auto-populates this on onboarding

---

### Mismatch 4: AED Hardcoded Everywhere ❌ HIGH
**PRD says:** Currency must auto-detect from PMS account. All internal calculations in operator base currency.

**Reality:**
- V1: AED hardcoded in schema (`numeric` columns without currency awareness), system prompts, UI
- V2: `organizations` table has `settings` JSONB (could hold currency), but not wired through

**What to build:**
- `organizations.currency` column (varchar, e.g. "AED", "GBP", "USD")
- Currency normalization layer in Data Aggregator / pipeline sources
- All price display in UI must use `org.currency` not hardcoded AED
- CRO prompt must pull currency from `system_state.currency`

---

### Mismatch 5: Guardrails Not Market-Calibrated ❌ MEDIUM
**PRD says:** Guardrail defaults must vary by market:

| Market | Max single-day change | Auto-approve threshold |
|:-------|:---------------------:|:---------------------:|
| UAE/GCC | ±15% | 5% |
| Europe | ±10% | 3% |
| US Leisure | ±20% | 7% |
| US Urban | ±12% | 4% |

**Reality:**
- V1: Fixed ±15% in waterfall logic
- V2: `strategies` table has `priceAdjPct`, `minPriceOverride`, `maxPriceOverride` — fixed values, not market-calibrated

**What to build:**
- Market template includes guardrail defaults JSON
- Onboarding Stage 2 pre-fills guardrails from market template
- `organizations.settings` stores active guardrail profile
- Settings > Automation page exposes these values for operator override

---

### Mismatch 6: CRO Agent Prompts Dubai-Specific ❌ HIGH
**PRD says:** CRO (Manager Agent) must use market-neutral language. All Dubai/AED/DTCM references go into the Dubai market template only. CRO must pull market context from `system_state`.

**Reality:**
- V1: All agent prompts hardcoded with Dubai zones, AED, DTCM
- V2: `src/lib/ai/context.ts` and `src/lib/ai/prompts/` — need review but likely still Dubai-aware

**What to build:**
- Build `system_state` market context object from `organizations.settings` + `market_templates`
- Prepend market context block to every CRO/insight prompt
- Remove all hardcoded Dubai/AED/DTCM references from V1 agent prompts
- Add regulatory awareness: if `org.market_code` matches restricted market, surface compliance warning

---

### Mismatch 7: Competitor Scanner Dubai Zone-Bound ❌ MEDIUM
**PRD says:** Comp set is built from URLs/property names provided by operator during Stage 1 onboarding. Compression threshold configurable. OTA weighting by market.

**Reality:**
- V1: Dubai Airbnb/Booking.com zone-based logic
- V2: `src/lib/pipeline/sources/competitors.ts` exists — not yet fully operator-configured

**What to build:**
- Stage 1 onboarding: add comp set URL input field
- `listings` table or `organizations.settings`: store comp set URLs per property
- Competitor source uses these URLs, not hardcoded Dubai zones
- OTA weighting stored in market template

---

### Mismatch 8: No Regulatory Compliance System ❌ MEDIUM
**PRD says:** Onboarding Stage 2 must surface regulatory flags. CRO must track night counts for Paris (120 cap), London (90 cap), Amsterdam (30 cap), NYC (hard ban warning).

**Reality:** This system does not exist in V1 or V2.

**What to build:**
- `market_regulatory_flags` table
- Night count tracking on `reservations` + calendar
- CRO warning trigger when approaching cap
- Stage 2 onboarding: show regulatory step if market has known restrictions
- `listings` table: add `short_stay_licence_number` field (for Barcelona, Dubai)

---

### Mismatch 9: Multi-PMS Support Not Global ❌ MEDIUM
**PRD says:** Global PMS priority — Hostaway/Guesty global, + Smoobu/BookingSync/Rentals United for Europe, + Ownerrez/Track/Vacasa for US, + VRBO/Escapia on V2 roadmap.

**Reality:**
- V1: PMSClient factory exists but only Hostaway is truly implemented
- V2: Only Hostaway (`src/lib/hostaway/`) — no Guesty, no Ownerrez, no Smoobu

**What to build (V2 roadmap):**
- Abstract `src/lib/pms/` interface (like V1's approach but actually complete)
- Implement Guesty connector first (biggest second PMS globally)
- Add PMS selection in Settings > Connections
- Timezone-aware API call scheduling per operator

---

### Mismatch 10: Onboarding Has No Market Selection Step ❌ CRITICAL
**PRD says:** Stage 0 must have a market selection step — country + city → template loads automatically.

**Reality:** Neither V1 nor V2 has multi-step onboarding. V2's Settings > Connections just accepts an API key.

**What to build:**
- Multi-step onboarding flow (Stage 0 → Stage 1 → Stage 2 wizard)
- Stage 0: Market selector (country + city dropdown)
- System auto-loads matching market template
- Timezone confirmed and stored
- Stage 1: Portfolio import → auto-grouping (from PMS data, not Dubai defaults)
- Stage 2: Guardrails pre-filled from market template + regulatory awareness

---

## Summary: Alignment Score

| Area | V1 Alignment | V2 Alignment |
|:-----|:------------:|:------------:|
| Core architecture (9 agents, state machine) | ✅ 100% | N/A (different architecture) |
| Market template system | ❌ 0% | ❌ 0% |
| Event intelligence (configurable) | ❌ 0% | 🟡 30% |
| Currency (auto-detect) | ❌ 0% | 🟡 20% |
| Weekend definition (configurable) | ❌ 0% | 🟡 20% |
| Guardrails (market-calibrated) | ❌ 0% | 🟡 25% |
| CRO prompts (market-neutral) | ❌ 0% | 🟡 30% |
| Competitor scanner (operator-configured) | ❌ 0% | 🟡 40% |
| Regulatory compliance | ❌ 0% | ❌ 0% |
| Multi-PMS support | 🟡 30% | 🟡 20% |
| Onboarding (market selection) | ❌ 0% | ❌ 0% |
| Multi-tenancy (multi-operator) | ❌ 0% | ✅ 90% |
| AI pipeline (Sources→Detectors→Insights) | ❌ 0% | ✅ 80% |
| **Overall** | **~12%** | **~42%** |

---

## How to Achieve Full PRD Compliance: Roadmap

### Phase 1: Foundation — Market Template System (Week 1-2)

This unblocks everything else.

1. Create `market_templates` DB table
2. Seed templates: Dubai, London, NYC, Barcelona, Amsterdam, Paris, Miami, Lisbon, Nashville, Sydney
3. Add `market_code` + `currency` + `timezone` + `weekend_definition` to `organizations` table
4. Build market selection onboarding step in Settings > Connections
5. Load template into `organizations.settings` on selection

### Phase 2: Pricing Engine Globalisation (Week 2-3)

6. Make weekend definition configurable in waterfall engine (read from org settings)
7. Market-calibrate guardrail defaults from market template
8. Remove AED hardcoding — wire currency through all price displays
9. Add currency normalization in pipeline data aggregator
10. Make guardrail defaults editable in Settings > Automation

### Phase 3: Event Intelligence Globalisation (Week 3-4)

11. Refactor `events.ts` source to accept `market_code` + call Ticketmaster/Eventbrite APIs
12. Preserve Dubai event data as pre-loaded template
13. Add custom event creation UI in Market > Events
14. Store market-specific event configs in `market_templates`

### Phase 4: AI / Agent Globalisation (Week 4-5)

15. Build `system_state` market context object (currency, market, weekend def, regulatory flags)
16. Inject this context block into ALL CRO/insight agent prompts
17. Strip Dubai/AED/DTCM from V1 agent prompts
18. Update V2 `src/lib/ai/context.ts` to pull from org's market template
19. Add regulatory night-count warnings to CRO logic

### Phase 5: Regulatory & Compliance System (Week 5-6)

20. Create `market_regulatory_flags` table + seed with 6 markets
21. Add `short_stay_licence_number` to `listings` table
22. Add regulatory awareness step to onboarding Stage 2
23. Implement night-count tracking (Paris 120, London 90, Amsterdam 30)
24. Add CRO warning trigger when approaching cap

### Phase 6: Competitor Scanner & Multi-PMS (Week 6-7)

25. Add comp set URL fields to Stage 1 onboarding
26. Refactor competitor source to use operator-provided URLs / market template
27. Add OTA weighting config to market templates
28. Design abstract PMS interface to support Guesty as second integration
29. Add PMS selector to Settings > Connections

### Phase 7: Copy & Onboarding UX (Week 7-8)

30. Build multi-step onboarding wizard (Stage 0 → 1 → 2)
31. Replace all Dubai/AED-specific UI copy with market-neutral equivalents
32. Add "Proven in Dubai. Built for everywhere." messaging
33. Property Selector: show market alongside property name
34. Demo Banner: show market template status

---

## What to Build Into V1 Specifically

Since the goal is to bring V2 features into V1, here is the **complete list scoped to V1**:

| Priority | Item | V2 Has It? | Build in V1? |
|:---------|:-----|:----------:|:------------:|
| 🔴 Critical | Market template DB table + seeding | ❌ | Yes |
| 🔴 Critical | Multi-step onboarding with market selection | ❌ | Yes |
| 🔴 Critical | `org_id` / `currency` / `market_code` on organizations | ✅ partial | Port from V2 |
| 🔴 Critical | AI pipeline (Sources → Detectors → Insights) | ✅ | Port from V2 |
| 🔴 Critical | Strategies table replacing pricingRules | ✅ | Port from V2 |
| 🟡 High | Event source globalisation (Ticketmaster/Eventbrite) | 🟡 partial | Build new |
| 🟡 High | Configurable weekend definition in waterfall | ❌ | Build new |
| 🟡 High | Currency auto-detect + normalization layer | ❌ | Build new |
| 🟡 High | Market-calibrated guardrail defaults | ❌ | Build new |
| 🟡 High | CRO prompts market-neutral + system_state context | ❌ | Build new |
| 🟡 High | Supabase Auth (replace Neon Auth) | ✅ | Port from V2 |
| 🟡 High | TanStack React Query hooks (16 hooks) | ✅ | Port from V2 |
| 🟢 Medium | Regulatory compliance system | ❌ | Build new |
| 🟢 Medium | Competitor scanner with operator URLs | 🟡 partial | Build new |
| 🟢 Medium | Multi-PMS abstract interface + Guesty | ❌ | Build new |
| 🟢 Medium | Settings page (Properties, Connections, Org, Automation) | ✅ | Port from V2 |
| 🟢 Medium | Market Intelligence pages (Market > Competitors/Events/Seasonality) | ✅ | Port from V2 |
| 🟢 Medium | Content editor page | ✅ | Port from V2 |
| 🟢 Medium | Product tour + How it Works modal | ✅ | Port from V2 |
| 🔵 V2 Roadmap | VRBO/Escapia integration | ❌ | Future |
| 🔵 V2 Roadmap | Guest language detection (auto-reply) | ❌ | Future |
