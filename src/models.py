from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Review:
    title: str
    body: str
    rating: float
    date: str
    reviewer: str


@dataclass
class AnalysisResult:
    sentiment: Dict[str, float]
    pain_points: List[str]
    buying_factors: List[str]
    suggestions: List[str]
    summary: str
    competitor_comparison: List[str]
