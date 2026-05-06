import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from src.mock_data import get_mock_reviews
from src.models import Review

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


def extract_asin(url: str) -> str | None:
    patterns = [
        r"/dp/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})",
        r"/product-reviews/([A-Z0-9]{10})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None


def normalize_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if not domain:
        return "www.amazon.com"
    if "amazon." in domain:
        return domain
    return "www.amazon.com"


def _build_review_url(domain: str, asin: str, page_number: int) -> str:
    return (
        f"https://{domain}/product-reviews/{asin}/"
        f"ref=cm_cr_arp_d_paging_btm_next_{page_number}"
        f"?pageNumber={page_number}&sortBy=recent"
    )


def scrape_amazon_reviews(product_url: str, target_reviews: int = 60) -> tuple[list[Review], bool, str]:
    asin = extract_asin(product_url)
    if not asin:
        return get_mock_reviews()[:target_reviews], True, "Could not extract ASIN from URL. Using demo review set."

    domain = normalize_domain(product_url)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )

    reviews: list[Review] = []
    max_pages = 10
    try:
        for page in range(1, max_pages + 1):
            url = _build_review_url(domain, asin, page)
            response = session.get(url, timeout=15)
            if response.status_code != 200:
                break

            soup = BeautifulSoup(response.text, "html.parser")
            review_blocks = soup.select("div[data-hook='review']")
            if not review_blocks:
                break

            for block in review_blocks:
                title_el = block.select_one("a[data-hook='review-title'] span")
                body_el = block.select_one("span[data-hook='review-body'] span")
                rating_el = block.select_one("i[data-hook='review-star-rating'] span")
                date_el = block.select_one("span[data-hook='review-date']")
                reviewer_el = block.select_one("span.a-profile-name")

                if not body_el:
                    continue

                rating = 0.0
                if rating_el and rating_el.text:
                    try:
                        rating = float(rating_el.text.strip().split(" ")[0])
                    except (ValueError, IndexError):
                        rating = 0.0

                reviews.append(
                    Review(
                        title=(title_el.text.strip() if title_el else ""),
                        body=body_el.text.strip(),
                        rating=rating,
                        date=(date_el.text.strip() if date_el else ""),
                        reviewer=(reviewer_el.text.strip() if reviewer_el else "Anonymous"),
                    )
                )

                if len(reviews) >= target_reviews:
                    return reviews, False, f"Scraped {len(reviews)} live Amazon reviews."
            time.sleep(0.4)
    except requests.RequestException:
        pass

    if len(reviews) < 30:
        fallback = get_mock_reviews()[:target_reviews]
        return fallback, True, "Amazon blocked scraping or low result count. Showing realistic demo review dataset."

    return reviews, False, f"Scraped {len(reviews)} live Amazon reviews."
