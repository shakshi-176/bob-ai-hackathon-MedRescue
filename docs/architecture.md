# Architecture

## System Diagram

​```mermaid
graph TD
    A[User - Hospital or Pharmacy Staff] -->|Login / Sign Up| B[Auth System - Flask Sessions]
    B -->|Role-based redirect| C[Hospital or Pharmacy Dashboard]
    C -->|Add medicine + price| D[Frontend - HTML CSS JS]
    D -->|API request| E[Backend - Flask]
    E -->|Store or Retrieve| F[(SQLite Database)]
    E -->|Run check| G[Expiry Risk Engine]
    G -->|Flagged medicines by type/urgency| H[Rule-Based Matching Engine]
    H -->|Ranked match + price breakdown| I[Pricing Calculator]
    I -->|Request this medicine| J[Orders + Payment Simulation]
    J -->|Payment confirmed| K[Notification System]
    K -->|SMS/Email simulated + navbar bell| D
​```

## Component Table

| Component | Technology | Responsibility |
|---|---|---|
| Frontend | HTML, CSS, JavaScript | Displays dashboards, expiry alerts, match results, price breakdowns, orders, and the notification bell |
| Auth System | Flask (built-in sessions) | Handles sign-up/login and enforces role-based access (Hospital vs Pharmacy) via a custom `login_required` decorator and server-side session state |
| Backend / API | Python (Flask) | Routes requests between frontend and database; runs all core logic |
| Database | SQLite | Stores users, facility info, medicine stock (with type and price), orders, and notifications |
| Expiry Risk Engine | Python | Flags medicines nearing expiry using type-specific thresholds (tighter for injectables, looser for tablets/capsules) |
| Matching Engine | Python (rule-based) | Ranks candidate facilities by need, quantity fit, and urgency using fixed deterministic rules — not a trained ML/AI model |
| Pricing Calculator | Python | Computes a 5% markup on base price plus a tiered flat transportation charge to produce the total order amount |
| Orders & Payment | Python + SQLite | Creates order records on request, simulates payment confirmation (no real payment gateway integrated) |
| Notification System | Python + SQLite | Logs simulated SMS/email notifications on urgency and payment events; surfaces unread count via a navbar bell |
| Development Tool | IBM Bob | Used throughout to scaffold, extend, and debug the Flask backend, database schema, and matching/pricing logic |

## Data Flow (End-to-End)

1. A facility signs up as either a Hospital or Pharmacy and logs in; the auth system routes them to the correct dashboard.
2. Staff register medicine stock (name, type, quantity, expiry date, price per unit) via the frontend.
3. The Expiry Risk Engine scans stock and flags items using type-specific urgency thresholds (e.g. injectables flagged sooner than tablets).
4. For each flagged item, the rule-based Matching Engine ranks other facilities by need, quantity fit, and urgency.
5. The Pricing Calculator computes the price breakdown (base price, +5% markup, + transportation charge) for the top match.
6. The requesting facility clicks "Request this medicine," creating a pending order with the full breakdown.
7. Clicking "Pay Now" simulates payment, updating the order to "paid."
8. On payment confirmation, a simulated SMS/email notification is logged and an unread badge appears on the navbar bell, visible only to the relevant facility.

## Security and Scalability Notes

- Authentication is enforced via server-side sessions and a custom `login_required` decorator, restricting access based on facility role (Hospital vs Pharmacy).
- Payment is fully simulated for this hackathon prototype — no real payment gateway (e.g. Razorpay/Stripe) is integrated, since that requires merchant setup and API keys outside the scope of a demo.
- SMS/email notifications are simulated and logged to the database rather than sent through a real messaging API.
- For production use, this would additionally need password hashing (if not already present) and encrypted storage of stock/pricing data, stricter facility-level authorization checks on orders, and a real payment gateway with webhook-based confirmation.
- The matching and pricing logic currently runs against a small demo dataset; a production version would need database indexing to scale matching across hundreds of facilities in real time.