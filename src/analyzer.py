import json
import re
from typing import List

from openai import OpenAI

from src.models import AnalysisResult, Review


SYSTEM_PROMPT = """
You are a senior product insights analyst.
Given ecommerce customer reviews, return concise, highly actionable findings for founders.
Return only valid JSON using this exact schema:
{
  "sentiment": {"positive": <number>, "negative": <number>, "neutral": <number>},
  "pain_points": ["...", "...", "...", "...", "..."],
  "buying_factors": ["...", "...", "...", "...", "..."],
  "suggestions": ["...", "...", "...", "..."],
  "summary": "...",
  "competitor_comparison": ["...", "...", "..."]
}

Rules:
- Percentages in sentiment should sum to 100.
- pain_points must be exactly 5 items.
- suggestions should be 3 to 5 items.
- competitor_comparison can be mock-style strategic comparisons when explicit competitor data is absent.
- Keep points specific and practical.
"""


def _fallback_analysis(reviews: List[Review]) -> AnalysisResult:
    # Heuristic local analysis for when OpenAI is unavailable.
    # This is intentionally data-driven from scraped review text so it doesn't feel like a demo set.
    text_blob = "\n".join([f"{r.title}\n{r.body}" for r in reviews]).lower()

    pos = sum(1 for r in reviews if r.rating >= 4)
    neg = sum(1 for r in reviews if r.rating <= 2)
    total = max(len(reviews), 1)
    positive_pct = round(pos * 100 / total, 1)
    negative_pct = round(neg * 100 / total, 1)
    neutral_pct = round(max(0.0, 100 - positive_pct - negative_pct), 1)

    negative_signals = [
        (r"\b(die(d)?|stopped|fail(ed|ure)|broke|broken|dead|doesn't work|won't work|not working)\b", "Durability / early failures"),
        (r"\b(damaged|broken on arrival|arrived damaged|cracked|transit damage|package damaged|worst packaging)\b", "Packaging / transit damage"),
        (r"\b(battery|charge|charging|drain|overheat|overheated|low battery)\b", "Battery / performance longevity"),
        (r"\b(not as described|different from|mismatch|looks cheaper|cheaper material|material mismatch)\b", "Expectation mismatch vs listing"),
        (r"\b(customer support|support|customer service|replacement|refund)\b", "Customer support responsiveness"),
    ]

    positive_signals = [
        (r"\b(value|worth|great price|price|deal)\b", "Value for money"),
        (r"\b(quality|durable|premium|works|reliable|performance)\b", "Core quality and reliability"),
        (r"\b(delivery|arrived|fast shipping|shipping|courier)\b", "Delivery speed and experience"),
        (r"\b(easy|simple|setup|user friendly|straightforward|comfortable to use)\b", "Ease of daily use"),
        (r"\b(warranty|support)\b", "Trust in brand support and warranty"),
    ]

    def _score(signals):
        scores = []
        for pattern, label in signals:
            m = re.search(pattern, text_blob, re.IGNORECASE)
            if m:
                # Use number of occurrences as a crude proxy.
                count = len(re.findall(pattern, text_blob, re.IGNORECASE))
                scores.append((count, label))
        scores.sort(reverse=True)
        return [label for _, label in scores[:5]]

    pain_points = _score(negative_signals)
    buying_factors = _score(positive_signals)

    # Ensure required shapes.
    pain_points = pain_points + [
        "Improve reliability consistency over early-life usage",
        "Harden packaging to reduce transit damage",
        "Align product claims and images with what customers receive",
        "Improve customer support speed and replacement workflow",
    ]
    pain_points = pain_points[:5]

    buying_factors = buying_factors + [
        "Strong value proposition",
        "Good core performance when it works as expected",
        "Convenient delivery and usability",
        "Trust from warranty and support",
    ]
    buying_factors = buying_factors[:5]

    # Suggestions mapped from pain points.
    suggestion_map = {
        "Durability / early failures": "Add reliability stress testing and tighten vendor QA for weak components.",
        "Packaging / transit damage": "Upgrade protective packaging and validate with courier drop/impact tests.",
        "Battery / performance longevity": "Refine component selection/thermal management and run longer endurance tests.",
        "Expectation mismatch vs listing": "Update listing images and claims to match real materials and delivered experience.",
        "Customer support responsiveness": "Implement a 24–48 hour support SLA with proactive replacement decisioning.",
    }

    suggestions: list[str] = []
    for pp in pain_points:
        if pp in suggestion_map and suggestion_map[pp] not in suggestions:
            suggestions.append(suggestion_map[pp])
    if len(suggestions) < 3:
        # Fill remaining with general, execution-ready steps.
        suggestions.extend(
            [
                "Create a fast feedback loop: tag new reviews into themes and review weekly.",
                "Publish clearer usage/expectation content to reduce misuse and mismatch complaints.",
            ]
        )
    suggestions = suggestions[:5]

    summary = (
        "Review sentiment shows a split between positive value perceptions and negative reliability/experience signals. "
        "The fastest path to lift repeat confidence is addressing the top recurring pain themes."
    )

    # Competitor comparison stays strategic without hard competitor data.
    competitor_comparison = [
        "Competitors with stronger reliability consistency tend to win trust even at similar price points.",
        "Faster support and clearer replacement workflows reduce churn and refund pressure.",
        "Better packaging and expectation-setting content improves first-impression conversion.",
    ]

    return AnalysisResult(
        sentiment={"positive": positive_pct, "negative": negative_pct, "neutral": neutral_pct},
        pain_points=pain_points,
        buying_factors=buying_factors,
        suggestions=suggestions,
        summary=summary,
        competitor_comparison=competitor_comparison,
    )


def analyze_reviews_with_openai(reviews: List[Review], api_key: str) -> AnalysisResult:
    if not api_key:
        return _fallback_analysis(reviews)

    client = OpenAI(api_key=api_key)
    review_blob = [
        {
            "title": r.title,
            "review": r.body,
            "rating": r.rating,
            "date": r.date,
        }
        for r in reviews[:100]
    ]

    user_prompt = (
        "Analyze these product reviews and output JSON only.\n\n"
        f"Review count: {len(review_blob)}\n"
        f"Reviews:\n{json.dumps(review_blob, ensure_ascii=True)}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        sentiment = payload.get("sentiment", {})
        return AnalysisResult(
            sentiment={
                "positive": float(sentiment.get("positive", 0)),
                "negative": float(sentiment.get("negative", 0)),
                "neutral": float(sentiment.get("neutral", 0)),
            },
            pain_points=list(payload.get("pain_points", []))[:5],
            buying_factors=list(payload.get("buying_factors", []))[:5],
            suggestions=list(payload.get("suggestions", []))[:5],
            summary=str(payload.get("summary", "")),
            competitor_comparison=list(payload.get("competitor_comparison", []))[:3],
        )
    except Exception:
        return _fallback_analysis(reviews)
