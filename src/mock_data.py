from src.models import Review


def get_mock_reviews() -> list[Review]:
    samples = [
        ("Great value for money", "Solid quality for the price and works as expected.", 5.0, "2026-01-18", "Alex"),
        ("Stopped working quickly", "It died after three weeks of normal use.", 2.0, "2026-01-21", "Riya"),
        ("Good but packaging was bad", "Product is fine, but arrived with damaged box.", 3.0, "2026-02-02", "Sam"),
        ("Excellent quality", "Feels premium and very durable.", 5.0, "2026-02-11", "Nina"),
        ("Not as described", "Material looks cheaper than listing photos.", 2.0, "2026-02-20", "Mark"),
        ("Fast delivery", "Arrived a day early, nice shopping experience.", 4.0, "2026-03-04", "Ava"),
        ("Battery life is poor", "Needs charging too often for daily usage.", 2.0, "2026-03-08", "Priya"),
        ("Perfect for daily use", "Simple and reliable for everyday tasks.", 5.0, "2026-03-15", "John"),
        ("Customer support was slow", "Took a week to get a replacement response.", 2.0, "2026-03-22", "Mia"),
        ("Very happy overall", "Great purchase and would recommend.", 5.0, "2026-03-24", "Ethan"),
    ]
    reviews: list[Review] = []
    for i in range(8):
        for title, body, rating, date, reviewer in samples:
            reviews.append(
                Review(
                    title=title,
                    body=body,
                    rating=rating,
                    date=date,
                    reviewer=f"{reviewer}_{i + 1}",
                )
            )
    return reviews
