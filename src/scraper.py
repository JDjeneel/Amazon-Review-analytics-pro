import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

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


def _scrape_via_jina_markdown(domain: str, asin: str, target_reviews: int, max_pages: int = 8) -> list[Review]:
    # Fallback path when Amazon blocks HTML review pages:
    # use a text mirror (r.jina.ai) and extract review snippets from "Reviewed in ..." blocks.
    #
    # Note: Amazon frequently limits how many reviews are visible without login, so this may
    # still return fewer than target. We try multiple pages first to improve the odds.
    reviewed_blocks_pattern = re.compile(
        r"Reviewed in (?P<country>.*?) on (?P<date>.*?)(?P<body>.*?)(?=Reviewed in |\Z)",
        re.DOTALL,
    )

    def _extract_from_text(text: str, limit: int) -> list[Review]:
        matches = reviewed_blocks_pattern.findall(text)
        out: list[Review] = []
        for country, date, body in matches:
            # The mirror typically represents the star rating like: "_4.5 out of 5 stars_"
            rating_match = re.search(
                r'_([0-9]+(?:\.[0-9]+)?) out of 5 stars_',
                body,
                re.IGNORECASE,
            )
            rating = 0.0
            if rating_match:
                try:
                    rating = float(rating_match.group(1))
                except ValueError:
                    rating = 0.0

            clean_body = re.sub(r"\s+", " ", body).strip()
            clean_body = clean_body.replace(
                "Brief content visible, double tap to read full content.", ""
            )
            clean_body = clean_body.replace(
                "Full content visible, double tap to read brief content.", ""
            )
            clean_body = clean_body.strip()
            if len(clean_body) < 30:
                continue
            title = clean_body[:72] + ("..." if len(clean_body) > 72 else "")
            out.append(
                Review(
                    title=title,
                    body=clean_body,
                    rating=rating,
                    date=date.strip(),
                    reviewer=f"Amazon {country.strip()} Reviewer",
                )
            )
            if len(out) >= limit:
                break
        return out

    reviews: list[Review] = []

    # 1) Product page mirror (often contains multiple "Reviewed in ..." entries)
    product_url = f"https://r.jina.ai/http://{domain}/dp/{asin}"
    response = requests.get(product_url, timeout=25)
    if response.status_code == 200:
        reviews.extend(_extract_from_text(response.text, target_reviews))
        if len(reviews) >= target_reviews:
            return reviews[:target_reviews]

    # 2) Try review listing pages (if accessible via mirror)
    for page in range(1, max_pages + 1):
        if len(reviews) >= target_reviews:
            break
        review_page_url = (
            f"https://r.jina.ai/http://{domain}/product-reviews/{asin}/"
            f"?pageNumber={page}&sortBy=recent"
        )
        r = requests.get(review_page_url, timeout=25)
        if r.status_code != 200:
            continue
        chunk = _extract_from_text(r.text, target_reviews - len(reviews))
        if chunk:
            reviews.extend(chunk)
            # be gentle to avoid rate-limits
            time.sleep(0.3)

    return reviews[:target_reviews]


def scrape_amazon_reviews(product_url: str, target_reviews: int = 60) -> tuple[list[Review], bool, str]:
    asin = extract_asin(product_url)
    if not asin:
        return [], False, "Could not extract ASIN from URL. Please enter a valid Amazon product link."

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

    if len(reviews) == 0:
        try:
            mirrored_reviews = _scrape_via_jina_markdown(domain, asin, target_reviews)
            if mirrored_reviews:
                return (
                    mirrored_reviews,
                    False,
                    f"Scraped {len(mirrored_reviews)} live Amazon review snippets via resilient fallback.",
                )
        except requests.RequestException:
            pass
        return [], False, "Amazon blocked review extraction for this product right now. Try another URL/domain."
    if len(reviews) < target_reviews:
        return reviews, False, f"Scraped {len(reviews)} live Amazon reviews (lower than target due to page limits/blocking)."
    return reviews, False, f"Scraped {len(reviews)} live Amazon reviews."
