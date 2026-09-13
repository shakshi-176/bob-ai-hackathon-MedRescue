# MedRescue AI

> A hackathon prototype connecting hospitals and pharmacies to redistribute medicine stock before it expires.

---

## Team

| Field | Value |
|---|---|
| **Team Name** | MedRescue |
| **Track** | AI |
| **Team Lead** | Sakshi Parmar - lead-shakshiparmar108@gmail.com |
| **Members** | Rajvi Khunt, Ayushi Raval, Hir Ramani |

---

## Problem Statement

Hospitals and pharmacies regularly stock medicines that go unused and expire, while nearby facilities may urgently need the same medicine and run short. There is currently no easy way for facilities to see each other's surplus or shortage in real time, leading to wasted stock on one side and unmet urgent need on the other - especially critical for time-sensitive medicines like injectables.

---

## Solution

MedRescue AI lets hospitals and pharmacies list their medicine stock (with type, expiry date, and price) and automatically flags items nearing expiry using type-specific urgency thresholds. A rule-based matching engine then ranks other facilities that need that medicine, shows a transparent price breakdown (base price + markup + transportation), and lets facilities request and simulate payment for a transfer - with notifications keeping both sides updated throughout.

---

## Key Features

- **Role-based login** - separate Hospital and Pharmacy accounts with dedicated dashboards
- **Type-aware expiry urgency** - injectables are flagged sooner than tablets/capsules, using tiered red/orange/yellow/green thresholds
- **Rule-based matching engine** - ranks candidate facilities by need, quantity fit, and urgency
- **Transparent pricing** - automatic 5% markup and tiered transportation charge shown as a full price breakdown on every match
- **Order and simulated payment flow** - request a medicine, see the total, and simulate payment confirmation
- **Real-time notifications** - simulated SMS/email alerts on urgency and payment events, surfaced via a navbar notification bell with unread count

---

## Tech Stack

| Category | Technologies |
|---|---|
| **Languages** | Python, HTML, CSS, JavaScript |
| **Frameworks** | Flask |
| **IBM Technologies** | IBM Bob (used to scaffold, extend, and debug the backend and matching logic) |
| **Databases** | SQLite |
| **Other** | Flask sessions (auth), Git/GitHub |

---

## Repository Structure
src/ All source code
docs/ Written documentation
problem-statement.md
solution-overview.md
architecture.md
setup-guide.md
demo/ Demo artifacts
screenshots/ App screenshots
demo-video-link.txt Link to demo video
presentation/ Slide deck
submission.yaml Structured submission metadata

---

## How to Run

---

See docs/setup-guide.md for exact steps.

git clone https://github.com/shakshi-176/bob-ai-hackathon-MedRescue.git
cd bob-ai-hackathon-MedRescue/src
pip install -r requirements.txt
python app.py


---

## Demo

| Artifact | Link |
|---|---|
| Demo Video | See demo/demo-video-link.txt |
| Live Demo | https://shakshi17.pythonanywhere.com/ |
| Screenshots | See demo/screenshots/ |
| Presentation | See presentation/slides.pdf |

---

## Known Limitations

- Login uses plaintext password storage - not production-ready, for hackathon demo purposes only
- Uses simulated inventory data, not real pharmacy/hospital records
- SMS/email notifications are simulated (logged in-app), not sent via a real messaging API
- Cold-chain and controlled substances are excluded from this version

---

## What We're Most Proud Of

The AI-driven matching engine and type-aware urgency system, which reasons across medicine type, expiry timeline, quantity, and facility need to produce a ranked, explainable transfer recommendation - not just a simple expiry-date sort.