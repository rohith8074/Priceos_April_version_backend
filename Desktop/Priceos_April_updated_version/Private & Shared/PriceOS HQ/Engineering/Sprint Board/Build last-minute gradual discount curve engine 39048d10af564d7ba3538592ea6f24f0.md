# Build last-minute gradual discount curve engine

Agent: Pricing Agent
Assignee: Rohith Panchagam, Harshit Choudhary
Labels: Backend, ML/AI
Priority: P1-High
Source Doc: Pricing Engine Analysis
Sprint: Sprint 3
Status: Backlog
Story Points: 8

Source: [PriceOS Pricing Engine Customizations](https://www.notion.so/PriceOS-Pricing-Engine-Customizations-c71ffe80b8424829960ebc09927e8fb0?pvs=21)

Reference: Product > Specs & PRDs > Pricing Engine Customizations Analysis

Configurable parameters: discount depth (default 30%), ramp period (default 15 days), curve type (gradual or flat), floor protection (never below minimum price).

Gradual mode applies decreasing discount from day 1 to day N.

Add velocity awareness:

- If booking velocity is high for upcoming dates, reduce or skip the discount.
- If velocity is stalled, increase the discount.

Assignee: [Name 1] (not set in database yet).