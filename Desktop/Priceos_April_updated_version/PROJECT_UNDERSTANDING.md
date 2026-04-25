# PriceOS 2.0: Project Understanding & Analysis

This document outlines the architectural structure, product requirements, and engineering logic for **PriceOS 2.0**, based on an in-depth analysis of the project workspace.

---

## 🏗️ High-Level Architecture

PriceOS 2.0 is an AI-powered revenue management platform designed for short-term rental property managers in Dubai. It uses a **3-layer data pipeline** to transform market signals into automated pricing actions.

### 1. Data Pipeline Layers
- **Layer 1: Sources (Gathering)**: Pulls data from Hostaway PMS, competitor rates, Dubai events, and seasonality patterns.
- **Layer 2: Detectors (Analysis)**: Identifies signals like booking pace, occupancy gaps, lead time shifts, and event-driven demand spikes.
- **Layer 3: Insights (AI Suggestions)**: An LLM-powered agent (using OpenRouter) processes detector signals to generate structured pricing and operational recommendations.

### 2. The Pricing Engine (Waterfall Logic)
The core value of PriceOS is its deterministic pricing engine which computes a "Price Waterfall":
- **Base Price** (e.g., $450)
- **(+) Weekend Premium** (+15%)
- **(+) High Season/Event** (+10%)
- **(-) Gap Fill/Last Minute** (-5%)
- **(=) Staged Price** ($541)
- **Guardrails**: All prices are clamped by predefined floor and ceiling limits.

---

## 📂 Understanding the Folder Structure

The workspace is organized into three distinct layers of project maturity:

### 1. `Private & Shared` (Product Requirements)
This is a **Notion Export** that acts as the "Source of Truth" for the product vision.
- **Sprint Board**: Contains ~33 detailed specifications for features like tiered length-of-stay discounts, competitive rate panels, and automated base price calculations.
- **Engineering Logic**: Defines the specific rules for detectors (e.g., how to calculate "Orphan Gap" pricing).

### 2. `priceos-v2` (Engineering Implementation)
The active development folder using a modern enterprise tech stack:
- **Frontend**: Next.js 16, Tailwind CSS v4, Zustand, TanStack React Query.
- **Backend & DB**: Supabase (Postgres/Auth), Drizzle ORM.
- **Integration**: Bi-directional sync with **Hostaway PMS**.

### 3. `Original_priceos` (Legacy)
The predecessor version, likely retained for reference or migration purposes.

---

## 🛠️ Tech Stack Breakdown

| Category | Technology |
| :--- | :--- |
| **Framework** | Next.js 16 (App Router) |
| **Styling** | Tailwind CSS v4 (Dark-only theme) |
| **State Management** | Zustand (Global) + React Query (Server) |
| **Database** | Supabase Postgres with RLS |
| **ORM** | Drizzle ORM |
| **AI Layer** | OpenRouter (LLM Gateway) |
| **PMS Integration** | Hostaway API |

---

## 🚀 Complexity & Key Challenges

As we move forward with this project, these are the critical focus areas:
1. **Multi-Tenancy Security**: Ensuring strict `org_id` scoping at the database level (Supabase RLS).
2. **Signal-to-Action Reliability**: Ensuring the AI Insight agent accurately interprets detector signals without hallucinations.
3. **Pipeline Performance**: Orchestrating Source -> Detector -> Insight runs efficiently across large property portfolios.
4. **Approval Workflow**: Maintaining the "Staged Changes" state to ensure no prices are pushed to the PMS without human approval.

---
*Created by Antigravity AI - Project Analysis Phase*
