# Setup Guide

> **This file is read by the automated evaluation pipeline. Be precise and complete.**

## Prerequisites

Before you begin, ensure you have the following installed:

- [ ] Python 3.9+
- [ ] pip (comes with Python)
- [ ] No external accounts, API keys, or database server required — this project uses SQLite, which is created automatically on first run.

## Environment Variables

No `.env` file is required for this project. The Flask secret key is set directly in `app.py` for the purposes of this hackathon demo (not suitable for production use — see Known Limitations in the README).

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/shakshi-176/bob-ai-hackathon-MedRescue.git
cd bob-ai-hackathon-MedRescue/src

# 2. (Recommended) Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt
```

## Running the Application

```bash
python app.py
```

The application will be available at: `http://localhost:5000`

The SQLite database (`medrescue.db`) is created and seeded with sample data automatically on first run — no manual setup step is needed.

## Quick Demo

1. Open `http://localhost:5000` in your browser.
2. Click **Sign Up** and create a Hospital account (or Pharmacy — try both to see each dashboard).
3. Log in, then go to **Add Medicine** and add a medicine with a type, expiry date, and price per unit.
4. Go to **Matches** to see ranked results with the price breakdown (base price + 5% markup + transportation charge).
5. Click **Request this medicine**, then **Pay Now** to simulate a payment.
6. Check the notification bell in the navbar — it should show a new unread notification confirming the simulated payment.

## Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError: No module named 'flask'` | Run `pip install -r requirements.txt` again, and make sure your virtual environment is activated |
| `Address already in use` / port 5000 busy | Stop any other process using port 5000, or edit the port in `app.py` |
| Changes not showing in browser | Restart the server (`Ctrl+C`, then `python app.py`) and hard-refresh the browser (`Ctrl+Shift+R`) |
| `sqlite3.OperationalError: no such table` | Delete `medrescue.db` and restart the server so it can be recreated and reseeded |