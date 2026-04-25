# Build multi-rule orphan gap pricing engine

Agent: Pricing Agent
Assignee: Rohith Panchagam, Harshit Choudhary
Labels: Backend
Priority: P1-High
Source Doc: Pricing Engine Analysis
Sprint: Sprint 3
Status: Backlog
Story Points: 8

Source: [PriceOS Pricing Engine Customizations](https://www.notion.so/PriceOS-Pricing-Engine-Customizations-c71ffe80b8424829960ebc09927e8fb0?pvs=21)

Reference: Product > Specs & PRDs > Pricing Engine Customizations Analysis

Support up to 5 gap range rules (e.g. 1-night gaps, 2-night gaps, 3-4 night gaps).

Each rule configurable with:

- fixed price or percentage discount/premium
- separate weekday and weekend settings
- "apply only within X days" window

Stacking rules:

- When orphan day is also a last-minute day: apply the larger discount only (prevent stacking).
- When both are premiums: stack them.

Assignee: [Name 1] (not set in database yet).