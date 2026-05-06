import os
import time

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.analyzer import analyze_reviews_with_openai
from src.scraper import scrape_amazon_reviews

load_dotenv()

st.set_page_config(
    page_title="Review Analytics Pro",
    page_icon="📊",
    layout="wide",
)

st.title("Review Analytics Pro")
st.caption("Amazon Review Intelligence for Product Teams")

with st.sidebar:
    st.header("Setup")
    api_key_input = st.text_input(
        "OpenAI API Key",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
        help="Optional: App still works with built-in demo analysis fallback.",
    )
    review_target = st.slider("Target review count", min_value=30, max_value=100, value=60, step=10)
    st.markdown("---")
    st.write("Built for startup founder demo velocity.")

product_url = st.text_input(
    "Amazon Product URL",
    placeholder="https://www.amazon.com/dp/B0XXXXXXXX",
)

run = st.button("Analyze Reviews", type="primary", use_container_width=True)

if run:
    if not product_url.strip():
        st.error("Please paste an Amazon product URL.")
        st.stop()

    with st.spinner("Scraping reviews and generating insights..."):
        t0 = time.time()
        reviews, used_mock, source_message = scrape_amazon_reviews(product_url.strip(), review_target)
        analysis = analyze_reviews_with_openai(reviews, api_key_input.strip())
        elapsed = time.time() - t0

    c1, c2, c3 = st.columns(3)
    c1.metric("Reviews Processed", len(reviews))
    c2.metric("Source", "Demo Dataset" if used_mock else "Live Scrape")
    c3.metric("Runtime", f"{elapsed:.1f}s")

    st.info(source_message)

    st.markdown("## Sentiment")
    s_col1, s_col2 = st.columns([1, 1.5])
    with s_col1:
        st.metric("Positive", f"{analysis.sentiment.get('positive', 0):.1f}%")
        st.metric("Negative", f"{analysis.sentiment.get('negative', 0):.1f}%")
        st.metric("Neutral", f"{analysis.sentiment.get('neutral', 0):.1f}%")
    with s_col2:
        sentiment_df = pd.DataFrame(
            {
                "Sentiment": ["Positive", "Negative", "Neutral"],
                "Percent": [
                    analysis.sentiment.get("positive", 0),
                    analysis.sentiment.get("negative", 0),
                    analysis.sentiment.get("neutral", 0),
                ],
            }
        )
        st.bar_chart(sentiment_df.set_index("Sentiment"))

    st.markdown("## Top 5 Customer Pain Points")
    for idx, item in enumerate(analysis.pain_points[:5], start=1):
        st.write(f"{idx}. {item}")

    st.markdown("## Key Buying Factors")
    factors_df = pd.DataFrame({"Buying Factor": analysis.buying_factors[:5]})
    st.dataframe(factors_df, hide_index=True, use_container_width=True)

    st.markdown("## Actionable Improvement Suggestions")
    for idx, item in enumerate(analysis.suggestions[:5], start=1):
        st.success(f"{idx}. {item}")

    st.markdown("## Strategic Insights")
    st.write(analysis.summary)
    if analysis.competitor_comparison:
        st.markdown("### Competitor Comparison (Quick View)")
        for idx, line in enumerate(analysis.competitor_comparison[:3], start=1):
            st.write(f"- {line}")

    with st.expander("Sample of Parsed Reviews"):
        preview = pd.DataFrame(
            [{"title": r.title, "body": r.body, "rating": r.rating, "reviewer": r.reviewer} for r in reviews[:12]]
        )
        st.dataframe(preview, hide_index=True, use_container_width=True)

else:
    st.markdown(
        """
### How it works
1. Paste an Amazon product URL.
2. App scrapes review pages (with smart fallback to realistic demo data).
3. OpenAI generates founder-ready review intelligence.
4. You get sentiment, pain points, buying factors, and action plan instantly.
"""
    )
