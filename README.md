## Macro + Market + Events Dashboard

Minimal Streamlit dashboard that surfaces daily market moves, key macro releases, and breaking events using locally stored JSON data.

### Setup
- Create a virtual environment (e.g., `python -m venv .venv` and `source .venv/bin/activate`).
- Install dependencies: `pip install -r requirements.txt`.

### Update data
- Generate the latest market snapshot JSON: `python update_market.py`.

### Run the app
- Start Streamlit: `streamlit run app.py`.

### Notes
- See `AI_RULES.md` for collaboration guidelines.
