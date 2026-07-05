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
# ─── MULTI-PAGE CRAWL ────────────────────────────────────────────────────────
# We audit the WHOLE site, not just the homepage: pages are discovered from
# sitemap.xml (authoritative) plus the homepage's internal links, then fetched
# and their content folded into full_html so contact/CTA/trust checks see info
# that lives on any page. Capped in count AND wall-time so a huge site can never
# OOM the small (512MB) host or make an audit crawl forever.
_MAX_CRAWL_PAGES = 20          # local-business sites are ~5-20 pages; covers most fully
_CRAWL_TIME_BUDGET = 90        # seconds; hard stop on total crawl time
_SKIP_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
             ".zip", ".rar", ".mp4", ".mp3", ".avi", ".mov", ".doc", ".docx",
             ".xls", ".xlsx", ".ppt", ".pptx", ".css", ".js", ".json", ".xml", ".rss")
# Pages worth auditing first when the cap forces a choice.
_PRIORITY_KW = ("contact", "about", "service", "book", "enquir", "quote", "review",
                "team", "pricing", "price", "faq", "product", "shop")


def _discover_page_urls(base_url: str, homepage_html: str, cap: int) -> list:
    """Same-domain page URLs to audit, sitemap-first then homepage links.
    Returns up to `cap` URLs (excluding the homepage), most audit-relevant first."""
    root = urlparse(base_url)
    host = root.netloc.replace("www.", "")
    base_norm = base_url.rstrip("/")
    seen, found = set(), []

    def add(u: str):
        u = (u or "").split("#")[0].strip().rstrip("/")
        if not u or u in seen:
            return
        p = urlparse(u)
        if p.scheme not in ("http", "https") or p.netloc.replace("www.", "") != host:
            return
        if any(u.lower().endswith(ext) for ext in _SKIP_EXT):
            return
        seen.add(u)
        found.append(u)

    # 1. sitemap.xml — fast and authoritative (handles nested sitemap indexes).
    try:
        sm = requests.get(f"{root.scheme}://{root.netloc}/sitemap.xml", timeout=8,
                          headers={"User-Agent": _DESKTOP_UA}, allow_redirects=True)
        if sm.status_code == 200 and "<" in sm.text:
            locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm.text, re.I)
            child_maps = [l for l in locs if l.lower().endswith(".xml")]
            for l in locs:
                if not l.lower().endswith(".xml"):
                    add(l)
            for cs in child_maps[:5]:                    # cap nested sitemaps
                try:
                    r2 = requests.get(cs, timeout=6, headers={"User-Agent": _DESKTOP_UA})
                    for l in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r2.text, re.I):
                        if not l.lower().endswith(".xml"):
                            add(l)
                except Exception:
                    pass
    except Exception:
        pass

    # 2. Internal links from the homepage — covers sites with no sitemap.
    for m in re.findall(r'href=["\']([^"\']+)["\']', homepage_html or "", re.I):
        add(urljoin(base_url, m))

    found = [u for u in found if u != base_norm]
    found.sort(key=lambda u: next((i for i, kw in enumerate(_PRIORITY_KW)
                                    if kw in u.lower()), len(_PRIORITY_KW)))
    return found[:cap]


# ─── BLOCK / ANTI-BOT DETECTION (Tier 0 honesty guard) ───────────────────────
# A WAF/anti-bot challenge (Cloudflare "Just a moment", Imperva "Robot Challenge
# Screen", Akamai, DataDome, …) returns a LARGE, valid-looking HTML page that is
# NOT the real site. Without this guard the tool "audits" the block page and
# reports a fake low score (every content check reads as missing). This detects
# that case so we can fail honestly instead of lying to a prospect.
_BLOCK_STATUS = {401, 403, 406, 429, 503}
_BLOCK_TITLE_SIGNS = (
    "just a moment", "attention required", "robot challenge", "access denied",
    "403 forbidden", "403 - forbidden", "forbidden", "security check",
    "are you a robot", "are you human", "verifying you are human", "human verification",
    "request unsuccessful", "bot verification", "ddos protection", "please wait",
    "checking your browser", "unusual traffic", "captcha", "site is protected",
)
# STRONG body markers — phrases that essentially never appear as real homepage
# content, so they flag a block regardless of page size. Imperva/Incapsula and
# generic WAF "Access Denied" interstitials are often served with HTTP 200, so
# status alone misses them — and they must read as BLOCKED, not "parked".
_BLOCK_BODY_STRONG = (
    "access denied", "you don't have permission to access", "you have been blocked",
    "sorry, you have been blocked", "powered by imperva", "/cdn-cgi/challenge-platform/",
    "cf-challenge", "_incapsula_", "px-captcha", "perimeterx", "datadome", "kasada",
)
# WEAK markers — trusted only when the page is thin OR a WAF is fingerprinted in
# headers, so a normal page merely mentioning one in its footer isn't flagged.
_BLOCK_BODY_SIGNS = (
    "checking your browser before accessing", "enable javascript and cookies to continue",
    "cf_chl_", "please enable cookies", "ddos protection by",
    "performance & security by cloudflare", "verify you are human", "incident id",
    "this request was blocked", "your request has been blocked", "request unsuccessful",
    "reference #", "error code 15", "error code 16", "error code 1020", "unauthorized access",
)


def _blocker_vendor(headers: dict, body_low: str) -> str:
    """Best-effort name of the WAF/anti-bot service, for an honest error message."""
    hv = " ".join(str(k).lower() + " " + str(v).lower() for k, v in (headers or {}).items())
    if "cf-ray" in hv or "cloudflare" in hv or "/cdn-cgi/" in body_low:
        return "Cloudflare"
    if "x-datadome" in hv or "datadome" in body_low:
        return "DataDome"
    if "_abck" in hv or "akamai" in hv or "akamai" in body_low:
        return "Akamai"
    if "x-iinfo" in hv or "incap_ses" in hv or "incapsula" in body_low or "imperva" in body_low:
        return "Imperva/Incapsula"
    if "_px" in hv or "perimeterx" in body_low or "px-captcha" in body_low:
        return "PerimeterX/HUMAN"
    if "x-kpsdk" in hv or "kasada" in body_low:
        return "Kasada"
    return ""


def _detect_block(fetch: dict):
    """Return {vendor, reason, status} if this fetch is a WAF/anti-bot block or
    challenge page rather than the real site — else None."""
    status = fetch.get("status_code", 0) or 0
    html = fetch.get("html", "") or ""
    low = html[:6000].lower()
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = (m.group(1).strip().lower() if m else "")
    vendor = _blocker_vendor(fetch.get("headers", {}), low)

    # 1. A blocking status code is never a real business homepage.
    if status in _BLOCK_STATUS:
        return {"vendor": vendor, "reason": f"HTTP {status}", "status": status}
    # 2. A challenge title is high-confidence even on HTTP 200 (JS shells return 200).
    if any(s in title for s in _BLOCK_TITLE_SIGNS):
        return {"vendor": vendor, "reason": f"challenge page (“{title[:50]}”)", "status": status}
    # 3. Strong body markers ("Access Denied", vendor challenge scripts) — these
    #    never appear on a real homepage, so they flag a block at any page size.
    if any(s in low for s in _BLOCK_BODY_STRONG):
        return {"vendor": vendor, "reason": "access blocked by security", "status": status}
    # 4. Weak body markers — trusted only when the page is thin (real content
    #    wouldn't be) OR a known WAF is fingerprinted in the response headers, so a
    #    normal page merely mentioning "cloudflare" in its footer is not flagged.
    if any(s in low for s in _BLOCK_BODY_SIGNS) and (len(html) < 15000 or vendor):
        return {"vendor": vendor, "reason": "anti-bot challenge markers", "status": status}
    return None


# ─── FREE STEALTH + COOKIE-CONSENT (no paid proxy needed) ────────────────────
# Two free upgrades that reduce how often we get blocked or read incomplete pages:
#  1. Stealth: mask the headless-automation fingerprint so basic/misconfigured
#     bot checks (a lot of Cloudflare setups) let us through. Not enough for
#     enterprise WAF (Imperva/DataDome) — that still needs the paid unblocker.
#  2. Cookie-consent auto-dismiss: click "Accept" so content behind a GDPR wall
#     actually renders — critical for UK/EU local-business sites.

# Dependency-free baseline stealth; always applied even if the library is absent.
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-GB','en']});
window.chrome = window.chrome || { runtime: {} };
"""

try:
    from playwright_stealth import Stealth as _PWStealth   # optional, heavier evasions
except Exception:
    _PWStealth = None


def _apply_page_stealth(page) -> None:
    """Best-effort stealth on a page BEFORE navigation. Degrades silently."""
    try:
        page.add_init_script(_STEALTH_JS)
    except Exception:
        pass
    if _PWStealth is not None:
        try:
            _PWStealth().apply_stealth_sync(page)
        except Exception:
            pass


# Consent frameworks (OneTrust, Cookiebot, …) + generic accept controls, tried
# in order. Strong, specific matches first to avoid clicking the wrong button.
_COOKIE_SELECTORS = (
    "#onetrust-accept-btn-handler",
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#CybotCookiebotDialogBodyButtonAccept",
    "button#accept-recommended-btn-handler",
    "#hs-eu-confirmation-button",
    ".cc-allow", ".cookie-accept", ".accept-cookies", "#accept-cookies",
    "[aria-label='Accept all']", "[aria-label='Accept cookies']",
)
_COOKIE_TEXTS = ("accept all", "allow all", "accept cookies", "i accept",
                 "i agree", "agree and close", "accept", "agree", "got it")


def _dismiss_cookie_banner(page) -> bool:
    """Click a cookie-consent 'accept' so content behind the wall renders."""
    try:
        for sel in _COOKIE_SELECTORS:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click(timeout=1500)
                    page.wait_for_timeout(400)
                    return True
            except Exception:
                pass
        for t in _COOKIE_TEXTS:
            try:
                btn = page.get_by_role("button", name=re.compile(t, re.I))
                if btn.count() > 0:
                    btn.first.click(timeout=1500)
                    page.wait_for_timeout(400)
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


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
        _apply_page_stealth(page)
        resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass  # some sites never go idle; the DOM is already good enough
        _dismiss_cookie_banner(page)      # reveal content behind GDPR consent walls

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

        # Crawl the WHOLE site (not just the homepage) so info living on any page
        # — contact, about, services, reviews — is seen. Pages are discovered from
        # sitemap.xml + homepage links. CRITICAL: Cloudflare rate-limits reused
        # sessions, so each page is fetched in a FRESH context (new session), which
        # passes the challenge like a first visit. Capped by count AND wall-time.
        base = final_url.rstrip("/")
        page_urls = _discover_page_urls(base, html, _MAX_CRAWL_PAGES)
        seen_urls, extra_html = {base}, ""
        pages_audited = [final_url]
        crawl_deadline = time.time() + _CRAWL_TIME_BUDGET
        for target in page_urls:
            if len(pages_audited) > _MAX_CRAWL_PAGES or time.time() > crawl_deadline:
                break
            sc = None
            try:
                sc = browser.new_context(user_agent=_DESKTOP_UA,
                                         viewport={"width": 1366, "height": 900}, locale="en-GB")
                sp = sc.new_page()
                _apply_page_stealth(sp)
                r2 = sp.goto(target, wait_until="domcontentloaded", timeout=12000)
                try:
                    sp.wait_for_load_state("networkidle", timeout=3000)
                except Exception:
                    pass
                _dismiss_cookie_banner(sp)
                final = sp.url.rstrip("/")
                sub = sp.content()
                low = sub[:2500].lower()
                is_challenge = any(m in low for m in ("just a moment", "checking your browser",
                                                      "cf-challenge", "enable javascript to",
                                                      "attention required"))
                ok = (sub and len(sub) > 2000 and final not in seen_urls
                      and (r2 is None or r2.status < 400) and not is_challenge)
                if ok:
                    seen_urls.add(final)
                    extra_html += " " + sub
                    pages_audited.append(sp.url)
            except Exception:
                pass
            finally:
                if sc is not None:
                    try:
                        sc.close()
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
        "pages_audited": pages_audited,
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
        pages_audited = [r.url]
        deadline = time.time() + _CRAWL_TIME_BUDGET
        for target in _discover_page_urls(base, r.text, _MAX_CRAWL_PAGES):
            if len(pages_audited) > _MAX_CRAWL_PAGES or time.time() > deadline:
                break
            try:
                sub = requests.get(target, timeout=8, headers=headers, allow_redirects=True)
                if sub.status_code == 200 and len(sub.text) > 500:
                    extra_html += " " + sub.text
                    pages_audited.append(sub.url)
            except Exception:
                pass
        return {
            "html": r.text, "extra_html": extra_html, "full_html": r.text + extra_html,
            "status_code": r.status_code, "response_time": elapsed, "final_url": r.url,
            "is_https": r.url.startswith("https://"), "headers": {k.lower(): v for k, v in r.headers.items()},
            "page_size_kb": round(len(r.content) / 1024, 1), "pages_audited": pages_audited,
            "fetch_method": "requests", "error": None,
        }
    except Exception as e:
        return {"html": "", "extra_html": "", "full_html": "", "error": str(e),
                "is_https": False, "response_time": 0, "final_url": url,
                "headers": {}, "page_size_kb": 0, "status_code": 0,
                "pages_audited": [], "fetch_method": "requests"}


def _fetch_with_unblocker(url: str):
    """Tier-1 paid fallback: fetch through a residential-IP unblocker that defeats
    WAF/anti-bot challenges our own browser can't pass (Cloudflare/Imperva/etc.).

    DORMANT BY DEFAULT — returns None unless UNBLOCKER_PROVIDER + its key are set,
    so with no paid key the tool behaves exactly as before (honest 'blocked'). Only
    the homepage is fetched here to keep paid cost to one request per blocked site."""
    provider = os.getenv("UNBLOCKER_PROVIDER", "").strip().lower()
    if not provider:
        return None
    country = os.getenv("UNBLOCKER_COUNTRY", "gb").strip().lower()
    start = time.time()
    try:
        if provider == "scrapingbee":
            key = os.getenv("SCRAPINGBEE_API_KEY", "").strip()
            if not key:
                return None
            r = requests.get("https://app.scrapingbee.com/api/v1/", timeout=75, params={
                "api_key": key, "url": url, "render_js": "true",
                "premium_proxy": "true", "country_code": country})
            html, status, final = r.text, r.status_code, url
        elif provider == "brightdata":
            # Full proxy URL incl. auth, e.g. http://brd-customer-..-zone-..:pass@brd.superproxy.io:22225
            proxy = os.getenv("BRIGHTDATA_PROXY", "").strip()
            if not proxy:
                return None
            import urllib3
            urllib3.disable_warnings()  # unblocker proxies use their own TLS chain
            r = requests.get(url, timeout=75, verify=False,
                             proxies={"http": proxy, "https": proxy},
                             headers={"User-Agent": _DESKTOP_UA})
            html, status, final = r.text, r.status_code, r.url
        else:
            print(f"[unblocker] unknown UNBLOCKER_PROVIDER='{provider}'")
            return None
    except Exception as e:
        print(f"[unblocker] {provider} failed: {e}")
        return None

    elapsed = round(time.time() - start, 2)
    return {
        "html": html, "extra_html": "", "full_html": html,
        "status_code": status, "response_time": elapsed, "final_url": final,
        "is_https": str(final).startswith("https://"), "headers": {},
        "page_size_kb": round(len(html.encode()) / 1024, 1),
        "pages_audited": [final], "fetch_method": f"unblocker:{provider}", "error": None,
    }


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

    # Accept the browser render only if it's big enough AND not a block/challenge
    # page. A WAF block page is large and valid-looking, so the size check alone
    # (the old bug) would wave it through and audit the block page.
    if (browser_result and len(browser_result.get("html", "")) >= _MIN_USABLE_HTML
            and not _detect_block(browser_result)):
        return browser_result

    req_result = _fetch_with_requests(url)
    candidates = [r for r in (browser_result, req_result) if r and r.get("html")]
    if not candidates:
        return req_result  # carries the real error message

    # A candidate is usable only if it has REAL content AND isn't a block page.
    # (Requiring size stops a thin 'Access Denied' shell that slipped past block
    #  detection from being returned and later mislabelled as 'parked'.)
    good = [r for r in candidates
            if len(r.get("html", "")) >= _MIN_USABLE_HTML and not _detect_block(r)]
    if good:
        return max(good, key=lambda r: len(r["html"]))

    # Nothing readable from our own fetchers. Last resort: a paid residential-IP
    # unblocker, IF one is configured (dormant otherwise).
    ub = _fetch_with_unblocker(url)
    if ub and len(ub.get("html", "")) >= _MIN_USABLE_HTML and not _detect_block(ub):
        print(f"[fetch] recovered a blocked site via {ub['fetch_method']}")
        return ub

    # If ANY attempt was a real WAF/anti-bot block, report it honestly as blocked
    # (never let it fall through to the 'parked/for sale' path).
    best = max(candidates, key=lambda r: len(r["html"]))
    block = next((_detect_block(r) for r in candidates if _detect_block(r)), None) or {}
    best["blocked"] = bool(block)
    best["block_vendor"] = block.get("vendor", "")
    best["block_reason"] = block.get("reason", "anti-bot protection")
    return best


# ─── EVIDENCE HELPERS ───────────────────────────────────────────────────────

def _img_name(src: str) -> str:
    """A readable label for an <img> src. A clean filename when there is one;
    otherwise the CDN host (base64 / query-hashed CDN paths have no filename and
    would just clutter the evidence with an unreadable blob)."""
    src = (src or "").split("?")[0].split("#")[0].rstrip("/")
    name = src.rsplit("/", 1)[-1]
    # a real, short filename with an image-y extension
    if name and "." in name and len(name) <= 45 and not name.startswith("ey"):
        return name
    host = urlparse(src if "//" in src else "http://" + src).netloc.replace("www.", "")
    return host or name[:40]


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


# A phone number that sits right after a phone-context label. High precision —
# this is what a human reads as THE phone, not a random price/coordinate.
# STRONG = the business's own customer-facing label ("Phone Us", "Call us");
# WEAK = generic ("Tel:", "call") which on some sites points at 3rd-party lines.
_NUM = r'(\+?\(?\d[\d\s().\-]{7,14}\d)'
_PHONE_STRONG = re.compile(
    r'\b(?:phone\s*us|call\s*us(?:\s*on)?|call\s*now|phone\s*(?:number)?\s*[:.]?|telephone)'
    r'[^0-9+]{0,20}' + _NUM, re.I)
_PHONE_LABEL = re.compile(
    r'\b(?:phone|telephone|tel|call|mobile|hotline|contact\s*number)'
    r'[^0-9+]{0,20}' + _NUM, re.I)


def _valid_phone(cand: str):
    """Return a cleaned number if it looks like a real phone, else None."""
    s = _clean_phone(cand)
    d = re.sub(r'\D', '', s)
    if not (9 <= len(d) <= 13):
        return None
    if len(set(d)) <= 2:                       # 000-000-0000 / 111-1111 placeholders
        return None
    if d.startswith("00") and not s.startswith("+"):   # "0 0 1230…" junk, not a real prefix
        return None
    if re.search(r'\.\d(\D|$)', s):            # ".8 " / ".5-" = SVG/coord noise
        return None
    if re.search(r'[A-Za-z]', s):
        return None
    return s


def _extract_display_phone(full_text: str, tel_hrefs: list) -> str:
    """High-confidence phone for DISPLAY (never affects scoring):
    1) a tel: link value, else 2) a number next to a phone label. Else "" —
    we'd rather show nothing than a wrong number scraped from page noise."""
    # 1) A tel: link is the most reliable signal — the business's own click-to-call.
    for t in tel_hrefs:
        v = _valid_phone(t)
        if v:
            return v
    txt = full_text or ""
    # 2) Gather numbers that sit next to a phone label (excludes prices/codes).
    labeled = {}
    for rx in (_PHONE_STRONG, _PHONE_LABEL):
        for m in rx.finditer(txt):
            v = _valid_phone(m.group(1))
            if v:
                labeled.setdefault(re.sub(r'\D', '', v), v)
    if not labeled:
        return ""
    # 3) GENERAL rule: the real main number repeats across header/footer/contact,
    #    while incidental third-party numbers (e.g. a complaints line) appear once.
    #    So pick the labelled number that occurs most often on the page.
    digits_only = re.sub(r'\D', '', txt)
    best = max(labeled, key=lambda k: (digits_only.count(k), -len(k)))
    return labeled[best]


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

    # High-confidence number for DISPLAY: tel: link, or a number next to a phone
    # label in the full (home + contact page) visible text. Never affects scoring.
    full_text = BeautifulSoup(raw, "lxml").get_text(" ", strip=True) if raw else html_text
    best_phone = _extract_display_phone(full_text, tel_hrefs)
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

    # Pick a sensible email for DISPLAY (deterministic; never affects scoring):
    # prefer a real mailto: link, drop system addresses, and sort for stability.
    _EMAIL_JUNK = ("noreply", "no-reply", "donotreply", "do-not-reply", "sentry",
                   "wixpress", "@sentry", "example.", "@2x", "u003e")
    _clean = sorted({e for e in emails
                     if "cloudflare-protected-email" not in e
                     and not any(j in e.lower() for j in _EMAIL_JUNK)})
    best_email = ""
    for e in mailto_hrefs:                       # a mailto: link = real contact intent
        if e in _clean:
            best_email = e
            break
    if not best_email:
        best_email = _clean[0] if _clean else ("(Cloudflare-protected email)" if emails else "")

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

# HARD signs — unambiguous parking / for-sale pages. Always mean "not a real site".
_PARKING_SIGNS = ["forsale", "godaddy.com/forsale", "sedoparking", "parkingcrew",
                  "bodis.com", "afternic", "hugedomains", "domain for sale",
                  "buy this domain", "domain is for sale",
                  "this domain may be for sale"]

# SOFT signs — placeholder / not-yet-live / server-default pages. These words can
# ALSO appear in a real homepage (e.g. "new service coming soon" in a promo), so
# they only count when the page is small. A full business homepage that merely
# mentions them is NOT dead. (Gating these to thin pages fixes the false-positive
# that mislabelled real sites like Auditel as "parked".)
_DEAD_SIGNS = ["access denied", "under construction", "coming soon",
               "site coming soon", "website coming soon", "account suspended",
               "site suspended", "this account has been suspended", "future home of",
               "default web page", "welcome to nginx", "apache2 ubuntu default",
               "site not found", "website disabled", "this site is temporarily unavailable"]


def _looks_parked_or_dead(fetch: dict) -> bool:
    """True if the fetch is too thin to be a real site, or is a parking/for-sale page.
    WAF 'Access Denied' blocks are handled earlier by _detect_block, not here."""
    html = fetch.get("html", "") or ""
    if len(html) < 1000:  # a real business homepage is never this small
        return True
    blob = (fetch.get("final_url", "") + " " + html[:3000]).lower()
    # Hard parking/for-sale signs — unambiguous, always mean "not a real site".
    if any(sign in blob for sign in _PARKING_SIGNS):
        return True
    # Soft placeholder signs count only on a SMALL page — a full real homepage
    # that merely mentions "coming soon" in a promo is NOT dead.
    if len(html) < 6000 and any(sign in blob for sign in _DEAD_SIGNS):
        return True
    return False


def fetch_google_business(business_name: str, domain: str, hint: str = "") -> dict:
    """Real Google Business Profile data (rating, review count, hours, address).

    DORMANT BY DEFAULT — returns {} unless GOOGLE_PLACES_API_KEY is set, so the
    tool behaves exactly as before without a key. Uses Places API (New) Text
    Search, then confirms the match by comparing the result's website to the
    audited domain so we don't attach a different business's reviews."""
    key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not key:
        return {}
    region = os.getenv("GOOGLE_PLACES_REGION", "GB").strip().upper()
    query = " ".join(p for p in (business_name, hint) if p).strip() or domain
    try:
        r = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            timeout=15,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": ("places.id,places.displayName,places.rating,"
                    "places.userRatingCount,places.formattedAddress,"
                    "places.nationalPhoneNumber,places.internationalPhoneNumber,"
                    "places.regularOpeningHours.weekdayDescriptions,"
                    "places.websiteUri,places.googleMapsUri,places.businessStatus"),
            },
            json={"textQuery": query, "maxResultCount": 5, "regionCode": region},
        )
        if r.status_code != 200:
            print(f"[places] API {r.status_code}: {r.text[:160]}")
            return {}
        places = r.json().get("places", []) or []
    except Exception as e:
        print(f"[places] lookup failed: {e}")
        return {}
    if not places:
        return {}

    # Prefer the result whose website matches the audited domain (confident match);
    # otherwise fall back to the top result but flag it as unconfirmed.
    host = domain.replace("www.", "").lower()
    chosen, confident = places[0], False
    for pl in places:
        site = (pl.get("websiteUri", "") or "").lower()
        if host and host in site:
            chosen, confident = pl, True
            break

    return {
        "matched": True,
        "confident": confident,
        "name": (chosen.get("displayName", {}) or {}).get("text", ""),
        "rating": chosen.get("rating"),
        "review_count": chosen.get("userRatingCount", 0),
        "address": chosen.get("formattedAddress", ""),
        "phone": chosen.get("nationalPhoneNumber") or chosen.get("internationalPhoneNumber", ""),
        "hours": (chosen.get("regularOpeningHours", {}) or {}).get("weekdayDescriptions", []),
        "maps_uri": chosen.get("googleMapsUri", ""),
        "website": chosen.get("websiteUri", ""),
        "business_status": chosen.get("businessStatus", ""),
    }


def run_audit(url: str) -> dict:
    """Run the full website audit — regex baseline + AI enhancement."""
    print(f"[Audit] Fetching: {url}")
    fetch = fetch_page(url)

    # Diagnostics: exactly what the fetcher received. Surfaced on error screens so
    # a failure can be diagnosed from the live app instead of guessing.
    _m = re.search(r"<title[^>]*>(.*?)</title>", fetch.get("html", "") or "", re.I | re.S)
    diag = {"status": fetch.get("status_code"), "size_kb": fetch.get("page_size_kb"),
            "method": fetch.get("fetch_method"), "final_url": fetch.get("final_url"),
            "title": (_m.group(1).strip()[:80] if _m else "(none)")}

    if fetch.get("error"):
        return {"error": fetch["error"], "url": url, "diag": diag}
    if fetch.get("blocked"):
        vendor = fetch.get("block_vendor") or "a security / anti-bot service"
        reason = fetch.get("block_reason", "")
        return {"error": (f"This site is protected by {vendor} and blocked our automated "
                          f"access ({reason}), so we could not read the real page. No audit "
                          f"was run — scoring the block page would give false results. "
                          f"The site itself may be perfectly fine; try again later or from a "
                          f"residential connection."),
                "url": url, "blocked": True, "block_vendor": fetch.get("block_vendor", ""),
                "diag": diag}
    if _looks_parked_or_dead(fetch):
        return {"error": ("We couldn't read a real page here — the site may be blocking "
                          "automated access, or the page is empty, parked, or not yet live."),
                "url": url, "diag": diag}

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

    # ── OPTIONAL: real Google Business data (dormant unless GOOGLE_PLACES_API_KEY
    #    is set). Turns "we detected a reviews link" into "you have 87 reviews at
    #    4.2★" — and surfaces the strongest sales angle: real reviews the site
    #    doesn't show. Never affects behaviour when no key is configured.
    google_biz = fetch_google_business(biz_name, domain, seo.get("title", ""))
    if google_biz.get("matched"):
        rc = google_biz.get("review_count") or 0
        rating = google_biz.get("rating")
        shows_reviews = any("review" in p.lower() for p in all_positives)
        if rc and not shows_reviews:
            all_issues.insert(0, {
                "severity": "medium", "category": "Trust & Reviews",
                "issue": f"{rc} Google reviews ({rating}★) are not shown on the website",
                "fix": "Embed a Google reviews widget so visitors see your reputation "
                       "without leaving the site.",
                "impact_key": "reviews_not_displayed"})
        elif rc:
            all_positives.append(f"Strong Google presence — {rc} reviews ({rating}★)")

    return {
        "url": fetch["final_url"], "domain": domain, "business_name": biz_name,
        "business_type": business_type, "overall_score": overall,
        "is_https": fetch["is_https"], "response_time": fetch["response_time"],
        "page_size_kb": fetch["page_size_kb"],
        "pages_audited": fetch.get("pages_audited", [fetch["final_url"]]),
        "google_business": google_biz,
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
            "google_rating": google_biz.get("rating"),
            "google_review_count": google_biz.get("review_count"),
            "is_https": fetch["is_https"],
            "response_time": fetch["response_time"],
        },
        "all_issues": all_issues,
        "all_positives": all_positives,
        "psi": psi,
    }
