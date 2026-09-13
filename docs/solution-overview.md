# Solution Overview

## What We Built

MedRescue AI is a web platform where pharmacies and hospitals register their medicine stock along with expiry dates. The system uses AI to spot medicines that are about to expire, automatically finds another nearby facility that actually needs that medicine, and sends both sides a clear recommendation to transfer it - before it goes to waste or a patient goes without it.

## How It Works

1. A pharmacy or hospital registers their medicine stock (name, quantity, manufacture date, expiry date) into the system.
2. The AI continuously scans this stock and flags medicines approaching expiry (30/15/7-day alerts), ranked by urgency and quantity.
3. For each flagged medicine, the AI searches other registered facilities and ranks them by real need - based on medicine type match, quantity required, recent usage patterns, and proximity.
4. The AI generates a clear, reasoned notification explaining the recommended transfer (e.g., "Hospital B has consistent demand for Insulin and is 4km away") and sends it to both facilities.
5. Staff at each facility review the recommendation and approve or decline the transfer.
6. The system logs the outcome (redistributed, expired unused, or consumed) to improve future predictions.

## Architecture Diagram

> See [`architecture.md`](architecture.md) for the detailed diagram..

[Optionally include a simple ASCII or Mermaid diagram here for quick reference.]

```
[User] → [Frontend:HTML/CSS/JS ] → [API:Flask API] → [Matching Engine (Python)] → [Dashboard]
                                    ↓
                             [SQLite Database]
```
coul 

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Human approval required before any transfer executes | Medicine transfers have real consequences; keeping a human in the loop avoids relying on a fully automated decision in a healthcare context |
| Used simulated inventory data | Real pharmacy/hospital data could not be sourced within the hackathon timeframe; a realistic synthetic dataset demonstrates the same end-to-end logic |
| Scoped to a single cooperative network (e.g., a district hospital system) | Independent, competing pharmacies are unlikely to share stock data; a cooperative network removes this barrier for the initial version |
| Used Flask + SQLite instead of a heavier stack | Kept the build simple and fast to demo within hackathon time constraints, while remaining easy to extend later |

## IBM Technologies Used

- **IBM Bob:** Used throughout development to scaffold the Flask backend routes, generate the matching logic, and assist with debugging and code review during the build.