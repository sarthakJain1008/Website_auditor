"""
audit_engine.py — AI-first website auditor.
Contact, CTA, and Trust analysis are done by Gemini AI (see ai_engine.py).
Python handles: SEO tags, security headers, performance timing, mobile viewport.
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv
import os

load_dotenv()
PSI_API_KEY = os.getenv("PSI_API_KEY", "")


# ─── PAGE FETCH ─────────────────────────────────────────────────────────────

def fetch_page(url: str) -> dict:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    start = time.time()
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        r = requests.get(url, timeout=15, headers=headers, allow_redirects=True)
        elapsed = round(time.time() - start, 2)
        html = r.text

        # Also fetch contact/about pages for more signal
        base = r.url.rstrip("/")
        extra_html = ""
        for path in ["/contact", "/contact-us", "/about", "/about-us", "/enquiry", "/support"]:
            try:
                sub = requests.get(base + path, timeout=8, headers=headers, allow_redirects=True)
                if sub.status_code == 200 and len(sub.text) > 500:
                    extra_html += " " + sub.text
            except Exception:
                pass

        return {
            "html": html,
            "extra_html": extra_html,
            "full_html": html + extra_html,
            "status_code": r.status_code,
            "response_time": elapsed, "final_url": r.url,
            "is_https": r.url.startswith("https://"),
            "headers": dict(r.headers),
            "page_size_kb": round(len(r.content) / 1024, 1),
            "error": None
        }
    except Exception as e:
        return {"html": "", "extra_html": "", "full_html": "", "error": str(e),
                "is_https": False, "response_time": 0, "final_url": url,
                "headers": {}, "page_size_kb": 0, "status_code": 0}


# ─── PYTHON-BASED CHECKS (things code is better at) ─────────────────────────

def analyze_seo(soup: BeautifulSoup, url: str) -> dict:
    issues, positives = [], []
    score = 0

    # Title (max 20 pts)
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    if title and 10 <= len(title) <= 60:
        score += 20; positives.append("Good title tag")
    elif title:
        score += 10
        issues.append({"severity": "medium", "issue": f"Page title is {len(title)} chars — outside the 10–60 range Google recommends",
                       "fix": "Rewrite the title tag to clearly describe the business in 10–60 characters.", "impact_key": "seo_title"})
    else:
        issues.append({"severity": "critical", "issue": "No page title found — you are invisible in Google search results",
                       "fix": "Add a <title> tag immediately. Without it, Google won't rank your page meaningfully.", "impact_key": "seo_title"})

    # Meta description (max 15 pts)
    meta = soup.find("meta", attrs={"name": "description"})
    desc = meta.get("content", "").strip() if meta else ""
    if desc and 80 <= len(desc) <= 160:
        score += 15; positives.append("Good meta description")
    elif desc:
        score += 7
        issues.append({"severity": "low", "issue": f"Meta description is {len(desc)} chars — should be 80–160 for best Google display",
                       "fix": "Rewrite your meta description to 120–155 characters.", "impact_key": "seo_meta"})
    else:
        issues.append({"severity": "medium", "issue": "Missing meta description — Google writes one for you (usually badly)",
                       "fix": "Add a compelling 120–155 character meta description.", "impact_key": "seo_meta"})

    # H1 (max 15 pts)
    h1s = soup.find_all("h1")
    if len(h1s) == 1:
        score += 15; positives.append("One clean H1 heading")
    elif len(h1s) > 1:
        score += 7
        issues.append({"severity": "low", "issue": f"{len(h1s)} H1 headings found — Google expects only one per page",
                       "fix": "Keep one H1 that describes the page. Convert extras to H2 or H3.", "impact_key": "seo_h1"})
    else:
        issues.append({"severity": "critical", "issue": "No H1 heading — Google has no clear signal about what your page is about",
                       "fix": "Add one H1 heading that clearly states your main service or product.", "impact_key": "seo_h1"})

    # Images alt (max 10 pts)
    all_imgs = soup.find_all("img")
    no_alt = [i for i in all_imgs if not i.get("alt", "").strip()]
    if all_imgs and not no_alt:
        score += 10; positives.append("All images have alt text")
    elif no_alt:
        score += max(0, 10 - len(no_alt) * 2)
        issues.append({"severity": "medium", "issue": f"{len(no_alt)} of {len(all_imgs)} images missing alt text",
                       "fix": "Add descriptive alt text to every image.", "impact_key": "seo_images"})

    # Canonical (max 5 pts)
    if soup.find("link", rel="canonical"):
        score += 5; positives.append("Canonical tag present")
    else:
        issues.append({"severity": "low", "issue": "No canonical tag — risk of duplicate content penalties",
                       "fix": "Add a canonical URL tag.", "impact_key": "seo_canonical"})

    # Structured data (max 10 pts)
    schema = soup.find("script", type="application/ld+json")
    if schema:
        score += 10; positives.append("Structured data (Schema) present")
    else:
        issues.append({"severity": "medium", "issue": "No structured data (Schema.org) — missing rich results eligibility",
                       "fix": "Add LocalBusiness JSON-LD schema.", "impact_key": "no_schema"})

    # OG tags (max 5 pts)
    og_title = soup.find("meta", property="og:title")
    if og_title:
        score += 5; positives.append("Open Graph tags present")
    else:
        issues.append({"severity": "low", "issue": "Missing Open Graph tags — poor social media sharing appearance",
                       "fix": "Add og:title, og:description, and og:image tags.", "impact_key": "seo_og"})

    return {"score": min(score, 100), "issues": issues, "positives": positives,
            "title": title, "meta_description": desc, "h1_count": len(h1s)}


def analyze_security(fetch_result: dict, soup: BeautifulSoup) -> dict:
    issues, positives = [], []
    score = 0

    if fetch_result.get("is_https"):
        score += 50; positives.append("HTTPS / SSL enabled")
    else:
        issues.append({"severity": "critical",
                       "issue": "Site is NOT on HTTPS — browsers show 'Not Secure' to every visitor",
                       "fix": "Install an SSL certificate immediately. Free via Let's Encrypt.",
                       "impact_key": "no_ssl",
                       "business_impact": "Chrome marks your site 'Not Secure' in the address bar. 85% of people will abandon a purchase if they see this warning."})

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
        issues.append({"severity": "medium", "issue": f"{len(unoptimized)} images not in modern WebP/AVIF format",
                       "fix": "Convert all images to WebP format.",
                       "impact_key": "unoptimized_images"})

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


# ─── MASTER RUNNER ───────────────────────────────────────────────────────────

def run_audit(url: str) -> dict:
    """Run the full website audit — AI for content analysis, Python for technical checks."""
    from ai_engine import ai_audit_page, score_contact, score_cta, score_trust

    print(f"[Audit] Fetching: {url}")
    fetch = fetch_page(url)
    if fetch.get("error"):
        return {"error": fetch["error"], "url": url}

    full_html = fetch.get("full_html", fetch["html"])
    soup = BeautifulSoup(fetch["html"], "lxml")
    domain = urlparse(fetch["final_url"]).netloc.replace("www.", "")

    # ── AI-POWERED ANALYSIS (contact, CTA, trust, business type) ────────────
    print("[Audit] Running AI analysis...")
    ai_result = ai_audit_page(full_html, domain)
    business_type = ai_result.get("business_type", "Local Business")
    print(f"[Audit] AI detected business type: {business_type}")

    # Convert AI findings to scored results
    contact = score_contact(ai_result.get("contact", {}))
    cta = score_cta(ai_result.get("cta", {}))
    trust = score_trust(ai_result.get("trust", {}))

    # ── PYTHON-BASED TECHNICAL CHECKS ───────────────────────────────────────
    seo = analyze_seo(soup, url)
    security = analyze_security(fetch, soup)
    perf = analyze_performance(fetch, soup)
    mobile = analyze_mobile(soup, fetch)
    psi = get_psi_scores(fetch["final_url"])

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

    # ── MERGE AND SORT ALL ISSUES ───────────────────────────────────────────
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
        "seo_details": {"title": seo["title"], "meta_description": seo["meta_description"], "h1_count": seo["h1_count"]},
        "contact_details": contact.get("details", {}),
        "ctas_found": cta.get("ctas_found", []),
        "all_issues": all_issues,
        "all_positives": all_positives,
        "psi": psi,
    }
