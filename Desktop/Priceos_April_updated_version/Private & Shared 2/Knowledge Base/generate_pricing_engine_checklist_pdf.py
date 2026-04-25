#!/usr/bin/env python3
"""
Generates PriceOS_Pricing_Engine_Checklist_Status.pdf
Run: python3 generate_pricing_engine_checklist_pdf.py

Status source: audit of Original_priceos/priceos (waterfall.ts, pipeline.ts,
Listing/PricingRule models, pricing UI, proposals APIs). Edit CHECKLIST to refine.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

OUT_NAME = "PriceOS_Pricing_Engine_Checklist_Status.pdf"

# [x] = complete, [ ] = pending (ASCII for core PDF fonts)
CHECKLIST: list[tuple[bool, str]] = [
    # --- Strategy & planning (complete) ---
    (
        True,
        "Competitive analysis: PriceLabs pricing stack documented (base -> seasonal -> DOW -> lead time -> demand -> occupancy -> gap -> adjacent -> LOS -> guardrails)",
    ),
    (
        True,
        "Customization map: all PriceLabs-style levers categorized into Tier 1 / 2 / 3 with revenue-impact framing",
    ),
    (True, "Prioritization: Dubai STR-focused scoring (80/20: top 6 Tier 1 items ~80% impact)"),
    (True, "Roadmap: Phases 1-4 with sprint mapping (Foundation -> Intelligence -> Advanced -> V2)"),
    (True, "Differentiation narrative captured (agents, simulation-first, Dubai context, NL control, auto ADR)"),
    (
        True,
        "Engineering backlog: sprint-board tickets exported for pricing engine workstreams (see Sprint Board folder)",
    ),
    (True, "Source document: PriceOS Pricing Engine Customizations (strategy PDF, Apr 2026)"),
    (
        True,
        "Code audit: Original_priceos pricing engine (waterfall.ts, pipeline.ts, models, UI) - Apr 2026",
    ),
    # --- Tier 1 — Must build (implementation) ---
    # T1.1: computeDay uses listing.price + absoluteMin/Max clamp; comp ADR not auto-fed as base in engine
    (
        True,
        "T1.1 Base price + min/max guardrails (engine: listing base + floor/ceiling clamp in waterfall)",
    ),
    (
        False,
        "T1.1b Auto base from comp ADR into engine default (benchmark exists; not wired into computeDay base)",
    ),
    (
        True,
        "T1.2 Seasonal profiles (SEASON rules: date range, DOW mask, price/% adj, min/max overrides)",
    ),
    (
        True,
        "T1.3a Last-minute discount (flat % within days-out window; floor enforced via final clamp)",
    ),
    (
        False,
        "T1.3b Last-minute gradual ramp (min/max discount over ramp days; Listing fields not used in waterfall)",
    ),
    (
        False,
        "T1.4 Occupancy-based adjustments in rules engine (schema + Rules Studio UI; not applied in computeDay)",
    ),
    (
        True,
        "T1.5 Orphan / gap pricing (gap prevention + gap-fill discount by length band; not weekday split rules)",
    ),
    (
        True,
        "T1.6 Day-of-week pricing (configurable dowDays e.g. Thu/Fri; no auto-pattern from booking history)",
    ),
    # --- Tier 2 — Should build ---
    (True, "T2.7 Far-out premium (markup when lead time >= farOutDaysOut)"),
    (
        False,
        "T2.8 Minimum weekend pricing (weekendMinPrice on model/UI; not enforced in waterfall clamp)",
    ),
    (
        True,
        "T2.9 Date-specific overrides (listing-level rules: SEASON/EVENT/ADMIN_BLOCK, min stay, block, CTA/CTD)",
    ),
    (False, "T2.9b Overrides at group / account scope (listing-level only today)"),
    (False, "T2.10 Adjacent booking factor (turnaround premium/discount)"),
    (
        False,
        "T2.11 Length-of-stay discounts applied to nightly rate (LOS_DISCOUNT rules only noted in engine note)",
    ),
    # --- Tier 3 — Later ---
    (False, "T3.12 Demand factor sensitivity / hotel weight"),
    (False, "T3.13 Customization hierarchy (account > group > sub-group > listing)"),
    (
        True,
        "T3.14 Check-in / check-out day restrictions (allowedCheckinDays / allowedCheckoutDays in waterfall)",
    ),
    (False, "T3.15 Channel-specific pricing offsets"),
    (False, "T3.16 Intra-day portfolio occupancy adjustments"),
    # --- Phase 1 — Foundation (Sprint 1–2) ---
    (False, "P1.1 Base + guardrails + auto-ADR as engine default (ADR via market flow; not pipeline base)"),
    (True, "P1.2 Seasonal profiles engine (PricingRule SEASON + runPipeline)"),
    (True, "P1.3 Day-of-week adjustments (UAE-style weekend days configurable)"),
    (True, "P1.4 Date-specific override system + UI (rules API + Pricing Rules Studio)"),
    (False, "P1.5 Bar-level rate grid (not found as product surface)"),
    # --- Phase 2 — Intelligence (Sprint 3–4) ---
    (False, "P2.1 Last-minute curve + velocity awareness (flat discount only; no velocity in waterfall)"),
    (False, "P2.2 Occupancy in waterfall + portfolio-level pricing rules"),
    (
        True,
        "P2.3 Orphan/gap pricing (implemented; not full multi-rule matrix / weekday split)",
    ),
    (True, "P2.4 Far-out minimum protection (implemented as far-out markup pass)"),
    (False, "P2.5 Minimum weekend pricing (field exists; not in computeDay)"),
    # --- Phase 3 — Advanced (Sprint 5–6) ---
    (False, "P3.1 Adjacent booking factor"),
    (False, "P3.2 Tiered LOS discounts in nightly calculation"),
    (
        True,
        "P3.3 Competitor rate comparison UI (benchmark panel; no auto-positioning in engine)",
    ),
    (False, "P3.3b Auto-positioning from comps in engine"),
    (False, "P3.4 Portfolio occupancy + booking-window segmentation in engine"),
    (False, "P3.5 Customization hierarchy"),
    # --- Phase 4 — V2 / post-launch ---
    (False, "P4.1 Intra-day pricing adjustments"),
    (False, "P4.2 Channel-specific offsets"),
    (False, "P4.3 Hotel weighting / demand sensitivity"),
    (False, "P4.4 CI/CO restrictions (already in V1 engine; phased doc item)"),
    (False, "P4.5 Automatic monthly base recalibration + nudges"),
    # --- Supporting product / UX ---
    (True, "Pricing calculation pipeline with layer stacking (4-pass waterfall in waterfall.ts)"),
    (
        False,
        "365-day calendar grid with prices per cell (engine runs 365d; UI uses proposal table + 30d heatmap)",
    ),
    (
        True,
        "User overrides on automated prices (approve/reject; bulk-modify / bulk-save proposals APIs)",
    ),
    (True, "Competitor rate comparison panel (benchmark-panel + benchmark data)"),
    (
        True,
        "Portfolio-level views (dashboard occupancy, market page; chat portfolio summary)",
    ),
    (
        True,
        "Market / comp workflow (market-setup + benchmark agents; recommended rates in DB/chat context)",
    ),
    (True, "Occupancy-based sorting (e.g. overview-client property list by occupancy)"),
]


class ChecklistPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(80, 80, 80)
        self.cell(0, 6, f"Page {self.page_no()}/{{nb}}", align="C")
        self.set_text_color(0, 0, 0)


def main() -> None:
    base = Path(__file__).resolve().parent
    out_path = base / OUT_NAME

    pdf = ChecklistPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 9, "PriceOS Pricing Engine - Completion Checklist")
    pdf.ln(1)
    done_n = sum(1 for d, _ in CHECKLIST if d)
    pend_n = len(CHECKLIST) - done_n
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, f"Summary: {done_n} complete, {pend_n} pending (see legend below).")
    pdf.ln(2)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(
        0,
        5,
        "Legend:  [x] = complete   [ ] = pending\n"
        "Implementation rows reflect a full-repo audit of Original_priceos/priceos. "
        "Re-run this script after shipping features; edit CHECKLIST tuples to adjust.",
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    current_section = ""
    for done, text in CHECKLIST:
        sec = (
            "Strategy & planning"
            if text.startswith("Competitive")
            or text.startswith("Code audit:")
            or "Prioritization" in text
            or "Roadmap:" in text
            or "Differentiation narrative" in text
            or "Engineering backlog:" in text
            or "Source document:" in text
            or "Customization map:" in text
            else ""
        )
        if sec:
            if current_section != "plan":
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, "Strategy & planning (documentation)")
                pdf.set_font("Helvetica", "", 10)
                current_section = "plan"
        elif text.startswith("T1."):
            if current_section != "t1":
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, "Tier 1 - Must build (product/engine)")
                pdf.set_font("Helvetica", "", 10)
                current_section = "t1"
        elif text.startswith("T2."):
            if current_section != "t2":
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, "Tier 2 - Should build")
                pdf.set_font("Helvetica", "", 10)
                current_section = "t2"
        elif text.startswith("T3."):
            if current_section != "t3":
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, "Tier 3 - Build later")
                pdf.set_font("Helvetica", "", 10)
                current_section = "t3"
        elif text.startswith("P1."):
            if current_section != "p1":
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, "Phase 1 - Foundation (Sprint 1-2)")
                pdf.set_font("Helvetica", "", 10)
                current_section = "p1"
        elif text.startswith("P2."):
            if current_section != "p2":
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, "Phase 2 - Intelligence layer (Sprint 3-4)")
                pdf.set_font("Helvetica", "", 10)
                current_section = "p2"
        elif text.startswith("P3."):
            if current_section != "p3":
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, "Phase 3 - Advanced (Sprint 5-6)")
                pdf.set_font("Helvetica", "", 10)
                current_section = "p3"
        elif text.startswith("P4."):
            if current_section != "p4":
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, "Phase 4 - V2 / post-launch")
                pdf.set_font("Helvetica", "", 10)
                current_section = "p4"
        elif text.startswith("Pricing calculation") or text.startswith("365-day"):
            if current_section != "ux":
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, "Supporting UX / platform (sprint backlog)")
                pdf.set_font("Helvetica", "", 10)
                current_section = "ux"

        mark = "[x]" if done else "[ ]"
        pdf.set_x(pdf.l_margin)
        col_marks = 16
        pdf.set_font("Courier", "", 10)
        pdf.cell(col_marks, 6, mark)
        pdf.set_font("Helvetica", "", 10)
        text_w = pdf.epw - col_marks
        pdf.multi_cell(text_w, 6, text)

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(70, 70, 70)
    pdf.multi_cell(
        0,
        5,
        "Ticks from Original_priceos codebase audit + strategy PDF. "
        "Script: generate_pricing_engine_checklist_pdf.py",
    )

    pdf.output(str(out_path))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
