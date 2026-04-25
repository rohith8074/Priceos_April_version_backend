# Build adjacent booking factor

Agent: Pricing Agent
Assignee: Rohith Panchagam, Harshit Choudhary
Labels: Backend
Priority: P2-Medium
Source Doc: Pricing Engine Analysis
Sprint: Sprint 5
Status: Backlog
Story Points: 5

Source: [PriceOS Pricing Engine Customizations](https://www.notion.so/PriceOS-Pricing-Engine-Customizations-c71ffe80b8424829960ebc09927e8fb0?pvs=21)

Reference: Product > Specs & PRDs > Pricing Engine Customizations Analysis

Adjust price for nights immediately before/after an existing booking.

Configurable as discount (encourage fill) or premium (discourage same-day turnovers).

Range: 1-30 days.

Option to exclude weekends.

Add turnaround cost parameter per property so system auto-prices adjacent days to cover cleaning/ops costs.

Stacking rules:

- Largest discount wins
- Premiums stack
- Mixed = largest discount + premium

Assignee: [Name 1] (not set in database yet).