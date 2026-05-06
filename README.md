# Review Analytics Pro

AI-powered review intelligence platform for Amazon sellers. Analyze product and competitor reviews to uncover sentiment, customer pain points, buying factors, and actionable improvement insights using OpenAI and Streamlit.

## Project Structure

```
review-analytics-pro/
├── app.py
├── requirements.txt
├── .env.example
├── .streamlit/
│   └── config.toml
└── src/
    ├── __init__.py
    ├── models.py
    ├── scraper.py
    ├── analyzer.py
    └── mock_data.py
```

## Run Instructions

1. Create and activate virtual environment:
   - Windows PowerShell:
     - `python -m venv .venv`
     - `.venv\Scripts\Activate.ps1`

2. Install dependencies:
   - `pip install -r requirements.txt`

3. Configure environment:
   - Copy `.env.example` to `.env`
   - Set `OPENAI_API_KEY` in `.env` (optional but recommended)

4. Start app:
   - `streamlit run app.py`

5. Open browser:
   - Streamlit will auto-open a local URL like `http://localhost:8501`

## Notes

- If Amazon blocks scraping, app automatically switches to realistic demo review dataset.
- Target review count is configurable between 30 and 100 in the sidebar.
