"""
audit_engine.py — Hybrid audit engine.
Primary: Python regex/HTML analysis (reliable baseline that always works).
Enhancement: AI overlay via ai_engine.ai_audit_page() when API is available.
If AI is unavailable, regex results still provide accurate audits.
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from dotenv import load_dotenv
import os

load_dotenv()
PSI_API_KEY = os.getenv("PSI_API_KEY", "")


# ─── PAGE FETCH ─────────────────────────────────────────────────────────────
# Primary: a REAL headless browser (Playwright/Chromium). This is essential —
# many local-business sites sit behind Cloudflare/WAFs that serve a JS
# "checking your browser" challenge to datacenter IPs. Plain requests can't run
# that JS and receives a tiny useless shell, which makes every content check
# read as "missing" (the false negatives we kept seeing). A real browser solves
# the challenge AND renders JS-injected content (review widgets, dynamic footers).
# Fallback: plain requests, used only if a browser/Chromium isn't available.

_DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
_SUBPATHS = ["/contact", "/contact-us", "/about", "/about-us", "/enquiry"]


def _fetch_with_browser(url: str) -> dict:
    """Render with headless Chromium. Raises if Playwright/Chromium unavailable."""
    from playwright.sync_api import sync_playwright

    start = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            # Memory-lean flags so a single Chromium fits on small (512MB) hosts.
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled",
                  "--disable-gpu", "--disable-extensions",
                  "--disable-background-networking", "--disable-features=site-per-process",
                  "--js-flags=--max-old-space-size=256"],
        )
        ctx = browser.new_context(user_agent=_DESKTOP_UA,
                                  viewport={"width": 1366, "height": 900},
                                  locale="en-GB")
        page = ctx.new_page()
        resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass  # some sites never go idle; the DOM is already good enough

        html = page.content()

        # Follow a client-side redirect stub (window.location / meta refresh).
        # Some sites serve a tiny "redirect to /lander" page as the homepage.
        if len(html) < _MIN_USABLE_HTML:
            m = (re.search(r"""window\.location(?:\.href)?\s*=\s*['"]([^'"]+)['"]""", html) or
                 re.search(r"""<meta[^>]+http-equiv=['"]?refresh['"]?[^>]*url=([^'">\s]+)""", html, re.I))
            if m:
                try:
                    page.goto(urljoin(page.url, m.group(1).strip()),
                              wait_until="domcontentloaded", timeout=20000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=8000)
                    except Exception:
                        pass
                    html = page.content()
                except Exception:
                    pass

        # Real page load time as measured BY THE BROWSER (Navigation Timing API).
        # This is the network response time of the audited site — it excludes our
        # Chromium start-up and subpage fetches, which the wall-clock would wrongly
        # include (that bug reported e.g. 63s on a slow free host for a fast site).
        elapsed = round(time.time() - start, 2)  # fallback only
        try:
            timing = page.evaluate(
                "() => { const n = performance.getEntriesByType('navigation')[0];"
                " return n ? {resp: n.responseEnd, dcl: n.domContentLoadedEventEnd} : null; }"
            )
            if timing and timing.get("resp", 0) > 0:
                # responseEnd = time to receive the HTML; cap protects against noise.
                elapsed = round(min(timing["resp"] / 1000.0, elapsed), 2)
        except Exception:
            pass

        final_url = page.url
        status = resp.status if resp else 200
        headers = {k.lower(): v for k, v in (resp.headers.items() if resp else [])}
        try:
            body = resp.body() if resp else b""
            size_kb = round(len(body) / 1024, 1) if body else round(len(html.encode()) / 1024, 1)
        except Exception:
            size_kb = round(len(html.encode()) / 1024, 1)

        # Pull a few key subpages so contact/trust info living off the homepage
        # (e.g. /contact, /enquiry) is still seen. Rendered, so JS content counts.
        base = final_url.rstrip("/")
        extra_html = ""
        for path in _SUBPATHS:
            try:
                page.goto(base + path, wait_until="domcontentloaded", timeout=12000)
                sub = page.content()
                if sub and len(sub) > 800:
                    extra_html += " " + sub
            except Exception:
                pass
        browser.close()

    return {
        "html": html,
        "extra_html": extra_html,
        "full_html": html + extra_html,
        "status_code": status,
        "response_time": elapsed,
        "final_url": final_url,
        "is_https": final_url.startswith("https://"),
        "headers": headers,
        "page_size_kb": size_kb,
        "fetch_method": "browser",
        "error": None,
    }


def _fetch_with_requests(url: str) -> dict:
    """Plain HTTP fallback. Fine for simple sites; blocked by JS-challenge WAFs."""
    start = time.time()
    headers = {
        "User-Agent": _DESKTOP_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
    }
    try:
        r = requests.get(url, timeout=15, headers=headers, allow_redirects=True)
        elapsed = round(time.time() - start, 2)
        base = r.url.rstrip("/")
        extra_html = ""
        for path in _SUBPATHS:
            try:
                sub = requests.get(base + path, timeout=8, headers=headers, allow_redirects=True)
                if sub.status_code == 200 and len(sub.text) > 500:
                    extra_html += " " + sub.text
            except Exception:
                pass
        return {
            "html": r.text, "extra_html": extra_html, "full_html": r.text + extra_html,
            "status_code": r.status_code, "response_time": elapsed, "final_url": r.url,
            "is_https": r.url.startswith("https://"), "headers": {k.lower(): v for k, v in r.headers.items()},
            "page_size_kb": round(len(r.content) / 1024, 1), "fetch_method": "requests", "error": None,
        }
    except Exception as e:
        return {"html": "", "extra_html": "", "full_html": "", "error": str(e),
                "is_https": False, "response_time": 0, "final_url": url,
                "headers": {}, "page_size_kb": 0, "status_code": 0, "fetch_method": "requests"}


_MIN_USABLE_HTML = 2000  # bytes; below this the fetch likely failed / was blocked


def fetch_page(url: str) -> dict:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Prefer the real browser; fall back to requests if it can't run OR if it
    # comes back suspiciously small (broken/blocked render). Keep whichever
    # result actually has content so we never trust an empty shell.
    browser_result = None
    try:
        # Run the sync Playwright call in a dedicated worker thread. Streamlit
        # runs the script in a context that may hold an asyncio loop, which the
        # sync API refuses to run inside; a fresh thread has no loop, so it works.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            browser_result = ex.submit(_fetch_with_browser, url).result()
        print(f"[fetch] browser render — {browser_result['page_size_kb']}KB in {browser_result['response_time']}s")
    except Exception as e:
        print(f"[fetch] browser unavailable ({e}); using requests")

    if browser_result and len(browser_result.get("html", "")) >= _MIN_USABLE_HTML:
        return browser_result

    req_result = _fetch_with_requests(url)
    candidates = [r for r in (browser_result, req_result) if r and r.get("html")]
    if not candidates:
        return req_result  # carries the real error message
    # Whichever fetch actually captured more real content wins.
    return max(candidates, key=lambda r: len(r["html"]))


# ─── EVIDENCE HELPERS ───────────────────────────────────────────────────────

def _img_name(src: str) -> str:
    """Filename from an <img> src (strip query/hash and path) for evidence display."""
    src = (src or "").split("?")[0].split("#")[0].rstrip("/")
    name = src.rsplit("/", 1)[-1]
    return name if name and "." in name else src[:60]


_TRACKER_SIGNS = ["facebook.com/tr", "/tr?", "google-analytics", "googletagmanager",
                  "doubleclick", "bat.bing", "/pixel", "pixel.", "analytics.",
                  "quantserve", "hotjar", "clarity.ms", "scorecardresearch"]


def _img_files(img_tags: list) -> list:
    """Real content-image filenames for evidence: skip data-URIs and tracking
    pixels (e.g. facebook.com/tr), and de-duplicate. Display only — never scoring."""
    out, seen = [], set()
    for i in img_tags:
        src = (i.get("src", "") or i.get("data-src", "")).strip()
        low = src.lower()
        if not src or low.startswith("data:") or any(t in low for t in _TRACKER_SIGNS):
            continue
        name = _img_name(src)
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _clean_phone(p: str) -> str:
    """Tidy a detected phone string for display."""
    return re.sub(r'\s+', ' ', str(p)).strip()


def _clean_ctas(ctas: list) -> list:
    """Tidy the CTA list for DISPLAY (scoring uses the raw count, unchanged).
    Product-card anchors concatenate price/description text; keep the short,
    button-like labels so evidence reads cleanly."""
    seen, clean = set(), []
    for c in ctas:
        t = re.sub(r'\s+', ' ', str(c)).strip()
        k = t.lower()
        if not t or k in seen:
            continue
        seen.add(k)
        if len(t) <= 28:                 # a real button label, not a whole card
            clean.append(t)
    if not clean:                        # fallback: shortest few, trimmed
        for c in sorted({re.sub(r'\s+', ' ', str(x)).strip() for x in ctas}, key=len):
            if c:
                clean.append((c[:38] + "…") if len(c) > 38 else c)
    return clean[:6]


def _best_display_phone(candidates: list) -> str:
    """Pick the most phone-like candidate for DISPLAY only (never affects scoring).
    The loose scoring regex can match CSS/SVG coordinates like '225.8 468.2-2.5';
    this ranks candidates so the evidence shows a real number instead of junk."""
    best, best_score = "", -1
    for c in candidates:
        s = _clean_phone(c)
        digits = re.sub(r'\D', '', s)
        if not (9 <= len(digits) <= 14):
            continue
        sc = 0
        if s[:1] in "+(0":
            sc += 2
        if "." not in s:            # dots usually mean coordinates/decimals, not phones
            sc += 3
        if len(digits) in (10, 11):
            sc += 2
        if re.search(r'[A-Za-z]', s):
            sc -= 6
        if re.search(r'\.\d(\D|$)', s):   # ".8 " / ".5-" = SVG/coord noise
            sc -= 5
        if len(set(digits)) <= 2:         # 000-000-0000 / 111-1111 = placeholders
            sc -= 8
        if re.search(r'0123456|1234567|1111111|0000000', digits):
            sc -= 8
        if sc > best_score:
            best, best_score = s, sc
    return best


_SOCIAL_DOMAINS = {"facebook.com": "Facebook", "instagram.com": "Instagram",
                   "linkedin.com": "LinkedIn", "youtube.com": "YouTube",
                   "tiktok.com": "TikTok", "twitter.com": "Twitter/X",
                   "x.com": "Twitter/X", "pinterest.com": "Pinterest"}
# share/SDK/widget/tracking URLs are NOT the business's own profile
_SOCIAL_EXCLUDE = ["/sharer", "sharer.php", "/share?", "/share/", "/intent/", "sharearticle",
                   "/plugins/", "connect.facebook", "platform.", "/tr?", "/embed", "/oauth",
                   "/dialog/", "developers.", "business.facebook", "/ads", "pixel", "gtag", "api."]


def _find_social_links(full_html: str) -> dict:
    """Real social PROFILE links only (actual <a href> to the platform host),
    excluding share buttons, SDKs and tracking scripts. Returns {name: url}."""
    found = {}
    try:
        s = BeautifulSoup(full_html, "lxml")
    except Exception:
        return found
    for a in s.find_all("a", href=True):
        href = a["href"].strip()
        low = href.lower()
        if not low or low.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        if any(x in low for x in _SOCIAL_EXCLUDE):
            continue
        host = urlparse(low if "//" in low else "http://" + low).netloc
        if host.startswith("www."):
            host = host[4:]
        for dom, name in _SOCIAL_DOMAINS.items():
            if host == dom or host.endswith("." + dom):
                found.setdefault(name, href)
    return found


# ─── CONTACT ANALYSIS (regex baseline) ──────────────────────────────────────

def analyze_contact(soup: BeautifulSoup, raw_html: str = "") -> dict:
    """Detect contact info from visible text, href attributes, AND raw HTML."""
    issues, positives = [], []
    score = 0

    clean_soup = BeautifulSoup(str(soup), 'lxml')
    for tag in clean_soup(['script', 'style', 'svg', 'path', 'noscript']):
        tag.decompose()
    html_text = clean_soup.get_text(" ", strip=True)

    raw = raw_html if raw_html else str(soup)

    phone_pattern = re.compile(r'(\+?[\d][\d\s\(\)\-\.]{7,}[\d])')
    email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

    # ── tel: links ──
    tel_links = soup.find_all("a", href=re.compile(r"tel:", re.I))
    tel_in_raw = re.findall(r'href=["\']tel:([+\d\s\-\.\(\)]{6,})["\']', raw, re.I)
    tel_hrefs = list(set(
        [a.get('href', '').replace('tel:', '').strip() for a in tel_links] + tel_in_raw
    ))

    # ── mailto: links ──
    mailto_links = soup.find_all("a", href=re.compile(r"mailto:", re.I))
    mailto_in_raw = re.findall(r'href=["\']mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', raw, re.I)
    mailto_hrefs = list(set(
        [a.get('href', '').replace('mailto:', '').split('?')[0].strip() for a in mailto_links]
        + mailto_in_raw
    ))

    # ── Phone ──
    phones_in_text = [p for p in phone_pattern.findall(html_text) if len(re.sub(r'\D', '', p)) >= 7]
    phones_in_raw = [p for p in phone_pattern.findall(raw) if len(re.sub(r'\D', '', p)) >= 7
                     and len(re.sub(r'\D', '', p)) <= 15]
    phones = list(set(phones_in_text + tel_hrefs + phones_in_raw))
    phones = [p for p in phones if not re.match(r'^20\d\d', p.strip())]

    # Pick the cleanest real-looking number for display (tel: links preferred).
    best_phone = _best_display_phone(tel_hrefs + phones)
    has_tel = bool(tel_links or tel_in_raw)

    if phones:
        score += 30; positives.append("Phone number found")
    else:
        issues.append({"severity": "critical",
                       "issue": "No phone number found on the page",
                       "fix": "Add your phone number to the header AND footer. Make it a clickable tel: link for mobile users.",
                       "impact_key": "no_phone",
                       "evidence": "No phone number or tel: link detected in the page or contact pages."})

    if has_tel:
        score += 10; positives.append("Phone is clickable (tel: link)")
    elif phones:
        issues.append({"severity": "medium",
                       "issue": "Phone number exists but is NOT clickable on mobile",
                       "fix": "Wrap your phone number in <a href='tel:+1...'> so mobile visitors can tap-to-call instantly.",
                       "impact_key": "no_tel_link",
                       "evidence": f"Number on page: {best_phone} — but no <a href=\"tel:\"> link."})

    # ── Email ──
    emails_in_text = [e for e in email_pattern.findall(html_text)
                      if not e.endswith((".png", ".jpg", ".gif", ".svg", ".css", ".js"))]
    emails_in_raw = [e for e in email_pattern.findall(raw)
                     if not e.endswith((".png", ".jpg", ".gif", ".svg", ".css", ".js", ".woff", ".ttf"))]
    emails = list(set(emails_in_text + mailto_hrefs + emails_in_raw))
    emails = [e for e in emails if not any(d in e for d in ['w3.org', 'schema.org', 'example.com', 'sentry.io', 'amazonaws'])]

    if "__cf_email__" in raw or "email-protection" in raw:
        emails.append("cloudflare-protected-email@found.com")

    # A real address for display (hide the internal cloudflare placeholder).
    display_emails = [e for e in emails if "cloudflare-protected-email" not in e]
    best_email = display_emails[0] if display_emails else ("(Cloudflare-protected email)" if emails else "")

    if emails:
        score += 15; positives.append("Email address found")
    else:
        issues.append({"severity": "medium",
                       "issue": "No email address visible on the site",
                       "fix": "Add a contact email address. Use a professional domain email (you@yourbusiness.com) not Gmail or Hotmail.",
                       "impact_key": "no_email",
                       "evidence": "No email address or mailto: link detected."})

    # ── Contact form ──
    forms = soup.find_all("form")
    form_kws = ["contact", "name", "message", "email", "enquir", "inquiry", "quote",
                "book", "appointment", "input", "textarea", "submit"]
    has_form = any(any(kw in str(f).lower() for kw in form_kws) for f in forms)
    form_platforms = ["typeform", "jotform", "wufoo", "formstack", "gravity", "wpforms",
                      "contactform", "ninja-form", "cf7", "hubspot", "mailchimp", "klaviyo"]
    if not has_form:
        has_form = any(kw in raw.lower() for kw in form_platforms)

    if has_form:
        score += 25; positives.append("Contact / enquiry form present")
    else:
        issues.append({"severity": "critical",
                       "issue": "No contact form found — you are only reachable during hours when you can answer the phone",
                       "fix": "Add a simple contact form: Name, Email, Phone, Message. This captures leads 24/7 including nights and weekends.",
                       "impact_key": "no_contact_form"})

    # ── Address ──
    address_kws = ["street", " st,", " ave,", "avenue", " road", " rd,", "blvd", " lane",
                   "suite", "level ", "floor ", "unit ", "shop ",
                   " nsw ", " vic ", " qld ", " wa ", " sa ", " nt ",
                   "new south wales", "victoria", "queensland", "ontario", "alberta",
                   " ny ", " ca ", " tx ", " fl ", "london", "manchester", "sydney",
                   "melbourne", "brisbane", "perth", "toronto", "new york",
                   "doncaster", "sheffield", "leeds", "york", "hull", "nottingham",
                   "birmingham", "liverpool", "bristol", "cardiff", "edinburgh",
                   "house", "walk", "close", "drive", "place", "square", "terrace",
                   "crescent", "court", "gardens", "row", "way", "parade"]
    has_address = any(kw in html_text.lower() for kw in address_kws)
    if not has_address:
        has_address = bool(re.search(r'"streetAddress"', raw, re.I)) or \
                      bool(re.search(r'"addressLocality"', raw, re.I)) or \
                      any(kw in raw.lower() for kw in address_kws)
    # Check for UK postcodes
    if not has_address:
        has_address = bool(re.search(r'[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}', raw, re.I))

    if has_address:
        score += 10; positives.append("Address visible")
    else:
        issues.append({"severity": "medium",
                       "issue": "Physical address not clearly visible — hurts local SEO and trust",
                       "fix": "Show your full street address in the footer. Required for Google Business Profile consistency and local search rankings.",
                       "impact_key": "no_address"})

    # ── Google Maps ──
    has_map = bool(soup.find("iframe", src=re.compile(r"maps\.google|google\.com/maps")))
    if not has_map:
        has_map = bool(re.search(r'maps\.google|google\.com/maps|maps\.app\.goo', raw, re.I))
    if has_map:
        score += 10; positives.append("Google Maps embedded or linked")
    else:
        issues.append({"severity": "low",
                       "issue": "No Google Maps embed or link",
                       "fix": "Embed a Google Map showing your location. It reinforces you're a real, established local business.",
                       "impact_key": "no_map"})

    return {"score": min(score, 100), "issues": issues, "positives": positives,
            "details": {"phone_found": bool(phones), "email_found": bool(emails),
                        "contact_form": has_form, "address_found": has_address,
                        "google_maps": has_map, "tel_link": has_tel,
                        "phone_number": best_phone, "email_address": best_email}}


# ─── CTA ANALYSIS (regex baseline) ──────────────────────────────────────────

def analyze_cta(soup: BeautifulSoup, raw_html: str = "") -> dict:
    issues, positives = [], []
    score = 0
    raw = raw_html if raw_html else str(soup)

    cta_keywords = ["book", "call us", "call now", "get quote", "free quote", "contact us",
                    "enquire", "enquiry", "schedule", "appointment", "get started", "sign up",
                    "register", "buy now", "order now", "free trial", "claim", "request",
                    "reserve", "get in touch", "speak to", "message us", "whatsapp", "chat",
                    "shop now", "add to cart", "subscribe", "join", "download", "learn more",
                    "find out more", "view", "explore", "discover", "start"]

    buttons = soup.find_all(["button", "a"])
    cta_found = []
    for b in buttons:
        text = b.get_text(strip=True).lower()
        if any(kw in text for kw in cta_keywords) and len(text) > 2 and len(text) < 50:
            cta_found.append(b.get_text(strip=True))

    _cta_list = _clean_ctas(cta_found)  # tidy labels for display (count unchanged)
    _cta_evidence = "CTAs detected: " + ", ".join(f'"{c}"' for c in _cta_list) if _cta_list else ""
    if len(cta_found) >= 3:
        score += 50; positives.append(f"{len(cta_found)} CTAs found throughout page")
    elif len(cta_found) == 2:
        score += 35
        issues.append({"severity": "medium", "issue": "Only 2 CTAs found — add more throughout the page",
                       "fix": "Place CTAs at top, middle, and bottom. Repeat your primary CTA at least 3 times on a homepage.",
                       "impact_key": "weak_cta", "evidence": _cta_evidence})
    elif len(cta_found) == 1:
        score += 20
        issues.append({"severity": "critical", "issue": "Only 1 CTA found — 70% of small business sites have this problem",
                       "fix": "Add clear CTA buttons at the top (hero section), after every service, and in the footer.",
                       "impact_key": "no_cta", "evidence": _cta_evidence})
    else:
        issues.append({"severity": "critical", "issue": "No call-to-action buttons found — visitors have no clear next step",
                       "fix": "Add prominent CTA buttons: 'Book Now', 'Get a Free Quote', 'Call Us'. Highest-ROI change you can make.",
                       "impact_key": "no_cta",
                       "evidence": "No action-oriented buttons/links detected (e.g. 'Book Now', 'Get a Quote')."})

    # Clickable phone as CTA
    tel_links = soup.find_all("a", href=re.compile(r"^tel:"))
    if tel_links:
        score += 20; positives.append("Clickable phone link present")

    # Booking / scheduling
    booking_keywords = ["book online", "schedule online", "book appointment", "online booking",
                        "calendly", "acuityscheduling", "acuity", "booker", "mindbody", "fresha",
                        "bookwell", "timely", "square appointments", "setmore", "simplybook",
                        "reserve", "reservation", "pick a time", "choose a time",
                        "book a session", "book a class", "book a table", "book a consultation"]
    html_str = raw.lower()
    has_booking = any(kw in html_str for kw in booking_keywords)
    if has_booking:
        score += 30; positives.append("Online booking / scheduling present")
    else:
        issues.append({"severity": "medium", "issue": "No online booking or scheduling system found",
                       "fix": "Integrate a free booking tool (Calendly, Fresha, or a simple form). Businesses with online booking convert 3x more website visitors.",
                       "impact_key": "no_booking"})

    return {"score": min(score, 100), "issues": issues, "positives": positives, "ctas_found": _cta_list}


# ─── TRUST ANALYSIS (regex baseline) ────────────────────────────────────────

def analyze_trust(soup: BeautifulSoup, raw_html: str = "") -> dict:
    issues, positives = [], []
    score = 0
    html_text = soup.get_text(" ", strip=True).lower()
    raw = (raw_html if raw_html else str(soup)).lower()

    # Reviews / testimonials — use STRONG signals only. Bare words like "review",
    # "rated", "recommend", "feedback" are too noisy (they appear in nav links,
    # policies, marketing copy) and caused false positives, so they're excluded.
    review_platforms = ["trustpilot", "elfsight", "reviews.io", "grade.us", "birdeye",
                        "podium", "widewail", "reviewsig", "stamped", "yotpo",
                        "feefo", "judge.me", "loox", "okendo", "trustindex", "reputon"]
    review_signals = review_platforms + [
        "testimonial", "customer review", "our reviews", "read our reviews",
        "client reviews", "patient reviews", "google review", "verified review",
        "5 star", "5-star", "five star", "star rating", "what our customers",
        "what our clients", "what our patients", "customers say", "clients say",
        "patients say", "happy customers", "aggregaterating", "ratingvalue", "reviewcount",
    ]
    has_reviews = any(kw in html_text for kw in review_signals) or \
                  any(kw in raw for kw in review_signals)
    # "…based on 1,240 reviews" style counts are a reliable review-section signal.
    if not has_reviews:
        has_reviews = bool(re.search(r'\b\d[\d,]{1,}\+?\s*reviews\b', raw))
    if has_reviews:
        score += 30; positives.append("Testimonials or reviews section found")
    else:
        issues.append({"severity": "critical", "issue": "No customer testimonials or reviews section",
                       "fix": "Add a dedicated testimonials section with 3–5 real customer quotes, names, and if possible, photos.",
                       "impact_key": "no_reviews"})

    # Google Reviews
    # Precise Google-Reviews signals only. The old `google.*review` wildcard
    # matched "google" (analytics/fonts) …anywhere… "review" across minified
    # HTML, producing false positives. Require an actual reviews link/widget.
    has_google_review = bool(re.search(
        r'g\.page/|/maps/place/|google\.com/maps/place|maps\.app\.goo\.gl|'
        r'place_id=|data-google-reviews|google-reviews|"google review|google\s+reviews',
        raw))
    if has_google_review:
        score += 25; positives.append("Google Reviews reference found")
    else:
        issues.append({"severity": "critical", "issue": "No Google Reviews link or widget — the most trusted review source is missing",
                       "fix": "Add a 'See Our Google Reviews' button linked to your Google Business Profile, or embed a Google Reviews widget.",
                       "impact_key": "no_google_reviews"})

    # Trust badges
    badge_keywords = ["certified", "accredited", "member of", "award", "award-winning", "licensed",
                      "insured", "guarantee", "money back", "registered", "qualified",
                      "years of experience", "years experience", "years in business",
                      "satisfaction guaranteed", "trusted", "verified", "bbb", "iso ",
                      "gphc", "pharmacy", "nhs", "cqc", "regulated"]
    has_badges = any(kw in html_text for kw in badge_keywords)
    if not has_badges:
        has_badges = any(kw in raw for kw in badge_keywords)
    if has_badges:
        score += 20; positives.append("Trust badges or credentials present")
    else:
        issues.append({"severity": "medium", "issue": "No licences, certifications, or trust badges visible",
                       "fix": "Display any professional licences, industry memberships, awards, or satisfaction guarantees.",
                       "impact_key": "no_trust_badges"})

    # Which review sources were detected (for evidence display).
    _rev_names = {"trustpilot": "Trustpilot", "reviews.io": "Reviews.io", "feefo": "Feefo",
                  "yotpo": "Yotpo", "judge.me": "Judge.me", "google review": "Google Reviews",
                  "trustindex": "Trustindex", "testimonial": "on-page testimonials"}
    review_sources = sorted({name for key, name in _rev_names.items() if key in raw})
    if has_google_review and "Google Reviews" not in review_sources:
        review_sources.append("Google Reviews")

    # Social media.
    # SCORING is unchanged (broad string match, same as baseline). Only the
    # DISPLAYED platform list is made accurate: it uses real profile <a href>
    # links, so tracking-script mentions of linkedin.com/tiktok.com no longer
    # show up as fake profiles in the evidence.
    social_pattern = re.compile(r'facebook\.com|instagram\.com|twitter\.com|x\.com|linkedin\.com|youtube\.com|tiktok\.com|pinterest\.com')
    social_links = _find_social_links(raw_html if raw_html else str(soup))
    social_platforms = sorted(social_links.keys())
    has_social = bool(social_pattern.search(raw))
    if has_social:
        score += 15; positives.append("Social media links present")
    else:
        issues.append({"severity": "medium", "issue": "No social media links — isolated from your biggest free marketing channels",
                       "fix": "Add visible links to your active social profiles (Facebook, Instagram).",
                       "impact_key": "no_social",
                       "evidence": "No links to Facebook, Instagram, LinkedIn, YouTube, TikTok or X detected."})

    # About section
    about_keywords = ["about us", "our team", "meet the team", "our story", "who we are",
                      "about me", "founder", "owner", "our mission", "our values",
                      "about the", "meet us", "our history"]
    has_about = any(kw in html_text for kw in about_keywords)
    if not has_about:
        has_about = any(kw in raw for kw in about_keywords)
    if has_about:
        score += 10; positives.append("About/team information present")
    else:
        issues.append({"severity": "low", "issue": "No 'About Us' or team information found",
                       "fix": "Add a short About section with your story, your team, or why you started the business.",
                       "impact_key": "no_about"})

    return {"score": min(score, 100), "issues": issues, "positives": positives,
            "review_sources": review_sources, "social_platforms": social_platforms,
            "has_google_reviews": has_google_review}


# ─── SEO ANALYSIS ────────────────────────────────────────────────────────────

def analyze_seo(soup: BeautifulSoup, url: str) -> dict:
    issues, positives = [], []
    score = 0

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    if title and 10 <= len(title) <= 60:
        score += 20; positives.append("Good title tag")
    elif title:
        score += 10
        issues.append({"severity": "medium", "issue": f"Page title is {len(title)} chars — outside the 10–60 range Google recommends",
                       "fix": "Rewrite the title tag to clearly describe the business in 10–60 characters.", "impact_key": "seo_title",
                       "evidence": f'Title tag ({len(title)} chars): "{title}"'})
    else:
        issues.append({"severity": "critical", "issue": "No page title found — you are invisible in Google search results",
                       "fix": "Add a <title> tag immediately.", "impact_key": "seo_title",
                       "evidence": "No <title> tag found in the page <head>."})

    meta = soup.find("meta", attrs={"name": "description"})
    desc = meta.get("content", "").strip() if meta else ""
    if desc and 80 <= len(desc) <= 160:
        score += 15; positives.append("Good meta description")
    elif desc:
        score += 7
        issues.append({"severity": "low", "issue": f"Meta description is {len(desc)} chars — should be 80–160",
                       "fix": "Rewrite your meta description to 120–155 characters.", "impact_key": "seo_meta",
                       "evidence": f'Meta description ({len(desc)} chars): "{desc}"'})
    else:
        issues.append({"severity": "medium", "issue": "Missing meta description — Google writes one for you (usually badly)",
                       "fix": "Add a compelling 120–155 character meta description.", "impact_key": "seo_meta",
                       "evidence": "No <meta name=\"description\"> tag found."})

    h1s = soup.find_all("h1")
    h1_texts = [h.get_text(" ", strip=True) for h in h1s if h.get_text(strip=True)]
    if len(h1s) == 1:
        score += 15; positives.append("One clean H1 heading")
    elif len(h1s) > 1:
        score += 7
        issues.append({"severity": "low", "issue": f"{len(h1s)} H1 headings found — Google expects only one per page",
                       "fix": "Keep one H1 that describes the page. Convert extras to H2 or H3.", "impact_key": "seo_h1",
                       "evidence": "H1s found: " + " | ".join(f'"{t}"' for t in h1_texts[:5])})
    else:
        issues.append({"severity": "critical", "issue": "No H1 heading — Google has no clear signal about what your page is about",
                       "fix": "Add one H1 heading that clearly states your main service or product.", "impact_key": "seo_h1",
                       "evidence": "No <h1> heading found on the page."})

    all_imgs = soup.find_all("img")
    no_alt = [i for i in all_imgs if not i.get("alt", "").strip()]
    missing_alt_files = _img_files(no_alt)
    if all_imgs and not no_alt:
        score += 10; positives.append("All images have alt text")
    elif no_alt:
        score += max(0, 10 - len(no_alt) * 2)
        _shown = ", ".join(missing_alt_files[:6]) or "(inline/background images)"
        _more = f" +{len(missing_alt_files) - 6} more" if len(missing_alt_files) > 6 else ""
        issues.append({"severity": "medium", "issue": f"{len(no_alt)} of {len(all_imgs)} images missing alt text",
                       "fix": "Add descriptive alt text to every image.", "impact_key": "seo_images",
                       "evidence": f"Images without alt text: {_shown}{_more}"})

    if soup.find("link", rel="canonical"):
        score += 5; positives.append("Canonical tag present")
    else:
        issues.append({"severity": "low", "issue": "No canonical tag — risk of duplicate content penalties",
                       "fix": "Add a canonical URL tag.", "impact_key": "seo_canonical"})

    schema = soup.find("script", type="application/ld+json")
    if schema:
        score += 10; positives.append("Structured data (Schema) present")
    else:
        issues.append({"severity": "medium", "issue": "No structured data (Schema.org) — missing rich results eligibility",
                       "fix": "Add LocalBusiness JSON-LD schema.", "impact_key": "no_schema"})

    og_title = soup.find("meta", property="og:title")
    if og_title:
        score += 5; positives.append("Open Graph tags present")
    else:
        issues.append({"severity": "low", "issue": "Missing Open Graph tags — poor social media sharing appearance",
                       "fix": "Add og:title, og:description, and og:image tags.", "impact_key": "seo_og"})

    return {"score": min(score, 100), "issues": issues, "positives": positives,
            "title": title, "meta_description": desc, "h1_count": len(h1s),
            "h1_texts": h1_texts, "total_images": len(all_imgs),
            "images_missing_alt": missing_alt_files}


# ─── SECURITY ANALYSIS ──────────────────────────────────────────────────────

def analyze_security(fetch_result: dict, soup: BeautifulSoup) -> dict:
    issues, positives = [], []
    score = 0

    if fetch_result.get("is_https"):
        score += 50; positives.append("HTTPS / SSL enabled")
    else:
        issues.append({"severity": "critical",
                       "issue": "Site is NOT on HTTPS — browsers show 'Not Secure' to every visitor",
                       "fix": "Install an SSL certificate immediately. Free via Let's Encrypt.",
                       "impact_key": "no_ssl"})

    headers = {k.lower(): v for k, v in fetch_result.get("headers", {}).items()}
    header_score = 0
    if "x-frame-options" in headers: header_score += 10
    if "x-content-type-options" in headers: header_score += 10
    if "strict-transport-security" in headers: header_score += 10
    score += header_score
    if header_score < 20:
        issues.append({"severity": "low", "issue": "Missing security response headers (X-Frame-Options, HSTS)",
                       "fix": "Configure your web server to send security headers.",
                       "impact_key": "no_security_headers"})

    has_form = bool(soup.find("form"))
    if has_form and fetch_result.get("is_https"):
        score += 20; positives.append("Forms served over HTTPS")
    elif has_form and not fetch_result.get("is_https"):
        issues.append({"severity": "critical", "issue": "Contact forms transmitting data over unencrypted HTTP",
                       "fix": "All forms MUST be on HTTPS.",
                       "impact_key": "form_on_http"})

    return {"score": min(score, 100), "issues": issues, "positives": positives,
            "is_https": fetch_result.get("is_https", False)}


# ─── PERFORMANCE ANALYSIS ───────────────────────────────────────────────────

def analyze_performance(fetch_result: dict, soup: BeautifulSoup) -> dict:
    issues, positives = [], []
    score = 0
    rt = fetch_result.get("response_time", 0)
    size = fetch_result.get("page_size_kb", 0)

    if rt < 0.8:
        score += 40; positives.append(f"Excellent response time ({rt}s)")
    elif rt < 1.5:
        score += 30; positives.append(f"Good response time ({rt}s)")
    elif rt < 2.5:
        score += 15
        issues.append({"severity": "medium", "issue": f"Page response time is {rt}s — above the 1.5s recommended threshold",
                       "fix": "Enable server-side caching, compress images to WebP format, and consider upgrading hosting.",
                       "impact_key": "slow_load"})
    else:
        issues.append({"severity": "critical", "issue": f"Page is very slow — {rt}s response time (Google recommends under 1.5s)",
                       "fix": "Urgent: compress all images, enable CDN, upgrade hosting plan, and minify CSS/JS.",
                       "impact_key": "slow_load"})

    if size < 500:
        score += 20; positives.append(f"Lightweight page ({size}KB)")
    elif size < 1500:
        score += 12
    elif size < 3000:
        score += 5
        issues.append({"severity": "medium", "issue": f"Large page size ({size}KB) — slow to load on mobile data",
                       "fix": "Compress images (use WebP format), remove unused CSS/JS, lazy-load images below the fold.",
                       "impact_key": "large_page"})
    else:
        issues.append({"severity": "critical", "issue": f"Very large page ({size}KB) — critically slow on mobile",
                       "fix": "Urgent: Remove unused scripts, compress all images, implement lazy loading.",
                       "impact_key": "large_page"})

    imgs = soup.find_all("img")
    unoptimized = [i for i in imgs if i.get("src", "") and not any(ext in i.get("src", "").lower() for ext in [".webp", ".avif", ".svg"])]
    if not unoptimized or len(unoptimized) < 3:
        score += 20; positives.append("Images appear optimized")
    else:
        score += 8
        # List the actual files so the fix is concrete, not "convert all images".
        _files = _img_files(unoptimized)
        _shown = ", ".join(_files[:6]) or "(see page source)"
        _more = f" +{len(_files) - 6} more" if len(_files) > 6 else ""
        issues.append({"severity": "medium", "issue": f"{len(unoptimized)} images not in modern WebP/AVIF format",
                       "fix": "Convert these to WebP/AVIF (e.g. via Squoosh or an image CDN) to cut load time.",
                       "impact_key": "unoptimized_images",
                       "evidence": f"Non-optimised images: {_shown}{_more}"})

    cache_headers = fetch_result.get("headers", {})
    cache_control = cache_headers.get("cache-control", cache_headers.get("Cache-Control", ""))
    if "max-age" in cache_control or "public" in cache_control:
        score += 20; positives.append("Browser caching enabled")
    else:
        issues.append({"severity": "low", "issue": "Browser caching not configured",
                       "fix": "Add cache-control headers to your server config.",
                       "impact_key": "no_cache"})

    return {"score": min(score, 100), "issues": issues, "positives": positives,
            "response_time": rt, "page_size_kb": size}


# ─── MOBILE ANALYSIS ────────────────────────────────────────────────────────

def analyze_mobile(soup: BeautifulSoup, fetch_result: dict) -> dict:
    issues, positives = [], []
    score = 0

    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport and "width=device-width" in viewport.get("content", ""):
        score += 40; positives.append("Proper viewport meta tag")
    elif viewport:
        score += 20
        issues.append({"severity": "medium", "issue": "Viewport tag present but may not be configured correctly",
                       "fix": "Use: <meta name='viewport' content='width=device-width, initial-scale=1'>",
                       "impact_key": "bad_viewport"})
    else:
        issues.append({"severity": "critical", "issue": "Missing viewport meta tag — site displays as desktop on mobile phones",
                       "fix": "Add <meta name='viewport' content='width=device-width, initial-scale=1'> to your <head> immediately.",
                       "impact_key": "no_viewport"})

    small_text = soup.find_all(style=re.compile(r'font-size:\s*([0-9]+)px'))
    too_small = [t for t in small_text if int(re.search(r'font-size:\s*([0-9]+)px', t.get("style", "")).group(1)) < 12
                 if re.search(r'font-size:\s*([0-9]+)px', t.get("style", ""))]
    if not too_small:
        score += 20; positives.append("Text sizes appear mobile-friendly")
    else:
        score += 5
        issues.append({"severity": "medium", "issue": f"{len(too_small)} elements with font size under 12px",
                       "fix": "Set minimum font size to 14–16px for body text.",
                       "impact_key": "small_text"})

    fixed = soup.find_all(style=re.compile(r'width:\s*\d{4,}px'))
    if not fixed:
        score += 20; positives.append("No oversized fixed-width elements")
    else:
        score += 5
        issues.append({"severity": "medium", "issue": f"{len(fixed)} elements with fixed large pixel widths",
                       "fix": "Replace fixed pixel widths with max-width or percentage values.",
                       "impact_key": "fixed_width"})

    rt = fetch_result.get("response_time", 0)
    if rt < 2.0:
        score += 20; positives.append("Acceptable mobile load speed")
    else:
        issues.append({"severity": "medium" if rt < 3 else "critical",
                       "issue": f"Load time of {rt}s is unacceptable for mobile users",
                       "fix": "Mobile users are often on slower connections. Target under 2 seconds.",
                       "impact_key": "mobile_slow"})

    return {"score": min(score, 100), "issues": issues, "positives": positives}


def get_psi_scores(url: str) -> dict:
    if not PSI_API_KEY:
        return {"available": False}
    try:
        r = requests.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                         params={"url": url, "key": PSI_API_KEY, "strategy": "mobile"}, timeout=30)
        data = r.json()
        cats = data.get("lighthouseResult", {}).get("categories", {})
        audits = data.get("lighthouseResult", {}).get("audits", {})
        return {
            "available": True,
            "performance": round((cats.get("performance", {}).get("score", 0) or 0) * 100),
            "seo":         round((cats.get("seo", {}).get("score", 0) or 0) * 100),
            "accessibility": round((cats.get("accessibility", {}).get("score", 0) or 0) * 100),
            "best_practices": round((cats.get("best-practices", {}).get("score", 0) or 0) * 100),
            "lcp": audits.get("largest-contentful-paint", {}).get("displayValue", "N/A"),
            "cls": audits.get("cumulative-layout-shift", {}).get("displayValue", "N/A"),
            "fcp": audits.get("first-contentful-paint", {}).get("displayValue", "N/A"),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


# ─── AI ENHANCEMENT (overlay on top of regex) ───────────────────────────────

def _merge_ai_results(regex_result: dict, ai_result: dict, category: str) -> dict:
    """Merge AI findings into deterministic results — AI can only ADD findings, never remove them."""
    if not ai_result:
        return regex_result

    if category == "contact":
        ai_contact = ai_result.get("contact", {})
        details = regex_result.get("details", {})
        # If AI found something regex missed, upgrade the result
        if ai_contact.get("phone_found") and not details.get("phone_found"):
            # AI found a phone that regex missed — fix the result
            regex_result["issues"] = [i for i in regex_result["issues"] if i.get("impact_key") != "no_phone"]
            regex_result["positives"].append("Phone number found (AI detected)")
            regex_result["score"] = min(regex_result["score"] + 30, 100)
            details["phone_found"] = True
        if ai_contact.get("email_found") and not details.get("email_found"):
            regex_result["issues"] = [i for i in regex_result["issues"] if i.get("impact_key") != "no_email"]
            regex_result["positives"].append("Email address found (AI detected)")
            regex_result["score"] = min(regex_result["score"] + 15, 100)
            details["email_found"] = True
        if ai_contact.get("contact_form_found") and not details.get("contact_form"):
            regex_result["issues"] = [i for i in regex_result["issues"] if i.get("impact_key") != "no_contact_form"]
            regex_result["positives"].append("Contact form found (AI detected)")
            regex_result["score"] = min(regex_result["score"] + 25, 100)
            details["contact_form"] = True
        if ai_contact.get("address_found") and not details.get("address_found"):
            regex_result["issues"] = [i for i in regex_result["issues"] if i.get("impact_key") != "no_address"]
            regex_result["positives"].append("Address found (AI detected)")
            regex_result["score"] = min(regex_result["score"] + 10, 100)
            details["address_found"] = True
        regex_result["details"] = details

    elif category == "cta":
        ai_cta = ai_result.get("cta", {})
        ai_ctas = ai_cta.get("ctas_found", [])
        existing_ctas = regex_result.get("ctas_found", [])
        if len(ai_ctas) > len(existing_ctas):
            # AI found more CTAs — use AI count for scoring
            combined = list(set(existing_ctas + ai_ctas))
            regex_result["ctas_found"] = combined[:8]
            if len(combined) >= 3 and regex_result["score"] < 50:
                regex_result["issues"] = [i for i in regex_result["issues"] if i.get("impact_key") not in ("no_cta", "weak_cta")]
                regex_result["positives"].append(f"{len(combined)} CTAs found (AI enhanced)")
                regex_result["score"] = min(regex_result["score"] + 30, 100)

    elif category == "trust":
        ai_trust = ai_result.get("trust", {})
        if ai_trust.get("has_reviews") and not any("review" in p.lower() or "testimonial" in p.lower() for p in regex_result.get("positives", [])):
            regex_result["issues"] = [i for i in regex_result["issues"] if i.get("impact_key") != "no_reviews"]
            regex_result["positives"].append("Reviews found (AI detected)")
            regex_result["score"] = min(regex_result["score"] + 30, 100)
        if ai_trust.get("has_trust_badges") and not any("trust" in p.lower() or "badge" in p.lower() or "credential" in p.lower() for p in regex_result.get("positives", [])):
            regex_result["issues"] = [i for i in regex_result["issues"] if i.get("impact_key") != "no_trust_badges"]
            regex_result["positives"].append("Trust badges found (AI detected)")
            regex_result["score"] = min(regex_result["score"] + 20, 100)

    return regex_result


# ─── MASTER RUNNER ───────────────────────────────────────────────────────────

_PARKING_SIGNS = ["forsale", "godaddy.com/forsale", "sedoparking", "parkingcrew",
                  "bodis.com", "afternic", "hugedomains", "domain for sale",
                  "buy this domain", "domain is for sale", "access denied",
                  "this domain may be for sale"]


def _looks_parked_or_dead(fetch: dict) -> bool:
    """True if the fetch is too thin to be a real site, or is a parking/for-sale page."""
    html = fetch.get("html", "") or ""
    if len(html) < 1000:  # a real business homepage is never this small
        return True
    blob = (fetch.get("final_url", "") + " " + html[:3000]).lower()
    return any(sign in blob for sign in _PARKING_SIGNS)


def run_audit(url: str) -> dict:
    """Run the full website audit — regex baseline + AI enhancement."""
    print(f"[Audit] Fetching: {url}")
    fetch = fetch_page(url)
    if fetch.get("error"):
        return {"error": fetch["error"], "url": url}
    if _looks_parked_or_dead(fetch):
        return {"error": ("This site could not be loaded for a real audit — it looks offline, "
                          "parked, for sale, or is blocking automated access."), "url": url}

    full_html = fetch.get("full_html", fetch["html"])
    soup = BeautifulSoup(fetch["html"], "lxml")
    domain = urlparse(fetch["final_url"]).netloc.replace("www.", "")

    # ── REGEX BASELINE (always works) ───────────────────────────────────────
    seo      = analyze_seo(soup, url)
    contact  = analyze_contact(soup, raw_html=full_html)
    cta      = analyze_cta(soup, raw_html=full_html)
    trust    = analyze_trust(soup, raw_html=full_html)
    security = analyze_security(fetch, soup)
    perf     = analyze_performance(fetch, soup)
    mobile   = analyze_mobile(soup, fetch)
    psi      = get_psi_scores(fetch["final_url"])

    # ── BUSINESS TYPE (deterministic — always works) ────────────────────────
    from ai_engine import detect_business_type, ai_audit_page
    page_text = soup.get_text(" ", strip=True)[:6000]
    business_type = detect_business_type(seo["title"], seo["meta_description"], page_text)

    # ── OPTIONAL AI OVERLAY (only if a valid key is present) ─────────────────
    # Returns {} when AI is disabled, so the deterministic result stands untouched.
    try:
        ai_result = ai_audit_page(full_html, domain)
        if ai_result:
            ai_btype = str(ai_result.get("business_type", "")).strip()
            if ai_btype and ai_btype.lower() != "local business":
                business_type = ai_btype
            print(f"[Audit] AI overlay refined business type: {business_type}")
            contact = _merge_ai_results(contact, ai_result, "contact")
            cta = _merge_ai_results(cta, ai_result, "cta")
            trust = _merge_ai_results(trust, ai_result, "trust")
    except Exception as e:
        print(f"[Audit] AI overlay skipped: {e}")

    # ── WEIGHTED OVERALL SCORE ──────────────────────────────────────────────
    weights = {"seo": 0.15, "contact": 0.20, "cta": 0.18, "trust": 0.18,
               "security": 0.15, "performance": 0.09, "mobile": 0.05}
    overall = round(
        seo["score"]      * weights["seo"] +
        contact["score"]  * weights["contact"] +
        cta["score"]      * weights["cta"] +
        trust["score"]    * weights["trust"] +
        security["score"] * weights["security"] +
        perf["score"]     * weights["performance"] +
        mobile["score"]   * weights["mobile"]
    )

    sev_order = {"critical": 0, "medium": 1, "low": 2}
    all_issues = []
    for cat, result in [("SEO", seo), ("Contact", contact), ("CTA & Conversion", cta),
                        ("Trust & Reviews", trust), ("Security", security),
                        ("Performance", perf), ("Mobile", mobile)]:
        for issue in result.get("issues", []):
            all_issues.append({**issue, "category": cat})
    all_issues.sort(key=lambda x: sev_order.get(x["severity"], 9))

    all_positives = []
    for result in [seo, contact, cta, trust, security, perf, mobile]:
        all_positives.extend(result.get("positives", []))

    biz_name = domain.split(".")[0].replace("-", " ").replace("_", " ").title()

    return {
        "url": fetch["final_url"], "domain": domain, "business_name": biz_name,
        "business_type": business_type, "overall_score": overall,
        "is_https": fetch["is_https"], "response_time": fetch["response_time"],
        "page_size_kb": fetch["page_size_kb"],
        "scores": {
            "seo": seo["score"], "contact": contact["score"],
            "cta": cta["score"], "trust": trust["score"],
            "security": security["score"], "performance": perf["score"],
            "mobile": mobile["score"],
        },
        "seo_details": {"title": seo["title"], "meta_description": seo["meta_description"],
                        "h1_count": seo["h1_count"], "h1_texts": seo.get("h1_texts", []),
                        "total_images": seo.get("total_images", 0),
                        "images_missing_alt": seo.get("images_missing_alt", [])},
        "contact_details": contact.get("details", {}),
        "ctas_found": cta.get("ctas_found", []),
        # ── Evidence facts: exactly what the tool detected, for the report/UI. ──
        "detected": {
            "title": seo["title"],
            "meta_description": seo["meta_description"],
            "h1_count": seo["h1_count"],
            "h1_texts": seo.get("h1_texts", []),
            "total_images": seo.get("total_images", 0),
            "images_missing_alt": seo.get("images_missing_alt", []),
            "phone_number": contact.get("details", {}).get("phone_number", ""),
            "email_address": contact.get("details", {}).get("email_address", ""),
            "tel_link": contact.get("details", {}).get("tel_link", False),
            "contact_form": contact.get("details", {}).get("contact_form", False),
            "address_found": contact.get("details", {}).get("address_found", False),
            "ctas_found": cta.get("ctas_found", []),
            "social_platforms": trust.get("social_platforms", []),
            "review_sources": trust.get("review_sources", []),
            "is_https": fetch["is_https"],
            "response_time": fetch["response_time"],
        },
        "all_issues": all_issues,
        "all_positives": all_positives,
        "psi": psi,
    }
