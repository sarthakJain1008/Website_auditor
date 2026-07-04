"""
ai_engine.py — Optional AI polish + deterministic content generation.

Design principle (senior-dev decision):
  The AUDIT SCORING is 100% deterministic and lives in audit_engine.py.
  This module NEVER decides pass/fail — it only:
    1. (optional) Uses Gemini to read the HTML as a second opinion that can
       ADD findings the deterministic pass missed (never remove them).
    2. Writes the plain-English summary + outreach email.

  Gemini is OPTIONAL. If no valid API key is present, every function here
  falls back to a strong deterministic template. The tool stays precise and
  fast whether or not an API key exists — a broken key can never break the audit.
"""
from dotenv import load_dotenv
import os
import re
import json

load_dotenv()

AGENCY = os.getenv("AGENCY_NAME", "Ryotech")
_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# A real Google AI Studio / Gemini key starts with "AIza". Anything else
# (OAuth tokens, blanks, placeholders) is treated as "no AI" so we skip the
# network calls entirely instead of hanging 15s per call on a doomed request.
AI_ENABLED = _API_KEY.startswith("AIza")

_client = None
if AI_ENABLED:
    try:
        from google import genai
        _client = genai.Client(api_key=_API_KEY)
    except Exception as e:
        print(f"[AI] Gemini client init failed, running deterministic-only: {e}")
        AI_ENABLED = False

if not AI_ENABLED:
    print("[AI] No valid GEMINI_API_KEY (expected 'AIza...') — running in "
          "deterministic mode. Audit is fully accurate; prose uses templates.")


def _generate(prompt: str) -> str:
    """Call Gemini. Raises if AI is disabled so callers use their fallback."""
    if not AI_ENABLED or _client is None:
        raise RuntimeError("AI disabled")
    response = _client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return response.text.strip()


def _clean_html_for_ai(raw_html: str, max_chars: int = 18000) -> str:
    """Strip noise from HTML but keep meaningful structure for AI to read."""
    cleaned = re.sub(r'<script[^>]*>.*?</script>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<style[^>]*>.*?</style>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<svg[^>]*>.*?</svg>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<noscript[^>]*>.*?</noscript>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<!--.*?-->', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars]
    return cleaned.strip()


# ─── BUSINESS TYPE ───────────────────────────────────────────────────────────
# Deterministic classifier from title/meta/visible text. Used always; the AI
# overlay can refine it to a more exact label when a key is present.

# Ordered most-specific first. Keywords are matched on WORD BOUNDARIES so short
# tokens can't false-match inside other words (e.g. "spa" must not hit "space").
# Title/meta are weighted heavily; a hit there is more reliable than body text.
_BTYPE_KEYWORDS = [
    ("Gym / Fitness Studio", ["jiu jitsu", "jiu-jitsu", "martial arts", "brazilian jiu",
                              "bjj", "mma", "kickbox", "boxing gym", "crossfit", "gym",
                              "fitness", "personal trainer", "yoga studio", "pilates"]),
    ("Pharmacy", ["pharmacy", "chemist", "prescription", "gphc", "dispensing"]),
    ("Dental Practice", ["dentist", "dental", "orthodontist", "teeth whitening"]),
    ("Veterinary Practice", ["veterinary", "veterinarian", "animal hospital"]),
    ("Medical Clinic", ["gp surgery", "medical centre", "medical center", "physiotherapy",
                        "physio clinic", "health clinic"]),
    ("Law Firm", ["solicitor", "law firm", "lawyer", "conveyancing", "legal advice", "attorney"]),
    ("Accounting Firm", ["accountant", "accounting", "bookkeeping", "tax return"]),
    ("Plumbing Business", ["plumber", "plumbing", "boiler", "heating engineer", "drainage"]),
    ("Electrician", ["electrician", "electrical contractor", "rewire", "fuse box"]),
    ("Roofing / Trade", ["roofer", "roofing", "builder", "bricklayer", "landscaping", "scaffolding"]),
    ("Hair & Beauty Salon", ["hair salon", "barber", "barbershop", "hairdresser", "hairdressing",
                             "beauty salon", "nail salon", "day spa", "beauty clinic"]),
    ("Restaurant / Café", ["restaurant", "bistro", "brasserie", "takeaway", "book a table",
                           "our menu", "café", "coffee shop"]),
    ("Estate Agency", ["estate agent", "lettings", "property for sale", "real estate"]),
    ("Automotive / Garage", ["mot test", "car repair", "car servicing", "mechanic", "tyres", "auto repair"]),
    ("Cleaning Service", ["cleaning service", "carpet cleaning", "domestic cleaning", "office cleaning"]),
    ("Retail Store", ["boutique", "add to cart", "add to basket", "online store", "free shipping"]),
]


def _kw_hit(hay: str, kw: str) -> bool:
    # Word-boundary match that also allows a trailing plural 's'
    # ("restaurants" matches "restaurant") but not other letters ("space").
    return re.search(r'(?<![a-z])' + re.escape(kw) + r's?(?![a-z])', hay) is not None


def detect_business_type(title: str, meta: str, text: str = "") -> str:
    """Best-effort deterministic business type from page signals.
    A hit in the title/meta wins over a hit deep in body text."""
    strong = f"{title} {meta}".lower()   # title + meta description
    weak = f"{title} {meta} {text}".lower()
    for hay in (strong, weak):            # prefer strong signals first
        for label, kws in _BTYPE_KEYWORDS:
            if any(_kw_hit(hay, kw) for kw in kws):
                return label
    return "Local Business"


# ─── OPTIONAL AI OVERLAY (reads HTML as a second opinion) ────────────────────

def ai_audit_page(full_html: str, domain: str) -> dict:
    """Optional: ask Gemini to read the HTML and report content signals.
    Returns {} when AI is unavailable so the caller keeps its deterministic result."""
    if not AI_ENABLED:
        return {}

    cleaned = _clean_html_for_ai(full_html)
    prompt = f"""You are a senior website auditor. Read this website's HTML and report what you find.
Website domain: {domain}

HTML content:
{cleaned}

Return ONLY a JSON object (no markdown, no backticks) with these EXACT keys:
{{
  "business_type": "Exact business type in 2-4 words",
  "contact": {{
    "phone_found": true/false, "phone_clickable": true/false,
    "email_found": true/false, "contact_form_found": true/false,
    "address_found": true/false, "google_maps_found": true/false
  }},
  "cta": {{ "ctas_found": ["button texts"], "has_booking_system": true/false }},
  "trust": {{
    "has_reviews": true/false, "has_google_reviews": true/false,
    "has_trust_badges": true/false, "has_social_links": true/false,
    "has_about_section": true/false
  }}
}}
Rules: Check BOTH visible text AND attributes (href, mailto:, tel:, JSON-LD, meta).
Only report what you actually find. Do NOT guess."""
    try:
        raw = _generate(prompt)
        if "```" in raw:
            raw = re.sub(r'```json?\s*', '', raw)
            raw = re.sub(r'```', '', raw)
        return json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
    except Exception as e:
        print(f"[AI Audit] overlay unavailable: {e}")
        return {}


# ─── SERVICE MAPPING (deterministic) ─────────────────────────────────────────

RYOTECH_SERVICES = [
    {"name": "Website Security & SSL Setup",
     "triggers": ["ssl", "https", "not secure", "security", "http"],
     "description": "Install SSL certificate, configure HTTPS, set security headers",
     "outcome": "Browser 'Not Secure' warning removed, customer trust restored immediately"},
    {"name": "Performance Optimisation",
     "triggers": ["slow", "load time", "response time", "page size", "cache", "webp", "image"],
     "description": "Image compression, CDN setup, caching, code minification",
     "outcome": "Target sub-1.5s load time — directly reduces bounce rate and increases enquiries"},
    {"name": "Google Reviews & Reputation Management",
     "triggers": ["review", "testimonial", "google review", "trust", "social proof"],
     "description": "Google Reviews widget, automated review request system, review response strategy",
     "outcome": "Visible star ratings on site, automated email/SMS asking happy customers for reviews"},
    {"name": "Lead Capture & Contact Form Setup",
     "triggers": ["contact form", "email", "phone", "enquiry", "form", "lead"],
     "description": "Custom contact form, CRM integration, email notifications, lead tracking",
     "outcome": "24/7 lead capture — enquiries come in while you sleep"},
    {"name": "Local SEO Package",
     "triggers": ["seo", "title", "meta", "schema", "canonical", "local", "google", "map pack"],
     "description": "On-page SEO, Google Business Profile optimisation, local citations, schema markup",
     "outcome": "Rank higher in local Google search and Google Maps for your key services"},
    {"name": "Conversion Rate Optimisation (CRO)",
     "triggers": ["cta", "call-to-action", "booking", "convert", "enquiry", "button", "book"],
     "description": "CTA redesign, A/B testing, booking system integration, landing page optimisation",
     "outcome": "More of your existing visitors turn into paying customers without spending more on ads"},
    {"name": "Mobile-First Responsive Redesign",
     "triggers": ["mobile", "viewport", "responsive", "phone", "tap", "font size", "horizontal scroll"],
     "description": "Full mobile-responsive design, viewport configuration, mobile UX audit",
     "outcome": "Perfect experience on every device — capturing 60%+ of traffic that comes from phones"},
    {"name": "Online Booking Integration",
     "triggers": ["booking", "appointment", "schedule", "calendar", "reserve", "reservation"],
     "description": "Calendly / custom booking system, automated reminders, calendar sync",
     "outcome": "Customers book 24/7 without calling — 3x more conversions than phone-only"},
    {"name": "Social Media Setup & Management",
     "triggers": ["social", "instagram", "facebook", "linkedin", "tiktok"],
     "description": "Social profile setup, content strategy, cross-linking from website",
     "outcome": "Active social presence that drives local awareness and recurring traffic"},
    {"name": "Website Copywriting & Messaging",
     "triggers": ["title", "headline", "content", "copy", "description", "message", "value"],
     "description": "Rewrite homepage copy to pass the 5-second test, benefit-led headlines",
     "outcome": "Visitors instantly understand what you do and why they should choose you"},
    {"name": "Structured Data & Rich Snippets Setup",
     "triggers": ["schema", "structured data", "rich result", "og tag", "open graph"],
     "description": "LocalBusiness schema, FAQ schema, product/service schema, OG tags",
     "outcome": "Google shows your business with star ratings, address, hours directly in search results"},
    {"name": "Full Website Redesign",
     "triggers": ["outdated", "design", "old", "unprofessional", "branding", "rebuild"],
     "description": "Complete modern redesign built for conversion, trust, and speed",
     "outcome": "A site that works as a 24/7 salesperson — professional, fast, and optimised to convert"},
]


def map_issues_to_services(issues: list, btype: str) -> list:
    """Map each detected issue to a Ryotech service with specific ROI outcome."""
    matched_services = {}
    for issue in issues:
        text = (issue.get("issue", "") + " " + issue.get("impact_key", "") + " " +
                issue.get("category", "") + " " + issue.get("fix", "")).lower()
        for service in RYOTECH_SERVICES:
            if service["name"] not in matched_services:
                if any(trigger in text for trigger in service["triggers"]):
                    matched_services[service["name"]] = {
                        "service": service["name"],
                        "description": service["description"],
                        "outcome": service["outcome"],
                        "triggered_by": issue["issue"][:80],
                        "severity": issue["severity"],
                    }
    sev_order = {"critical": 0, "medium": 1, "low": 2}
    result = sorted(matched_services.values(), key=lambda x: sev_order.get(x["severity"], 9))
    return result[:8]


# ─── PLAIN-ENGLISH SUMMARY (AI polish → deterministic fallback) ──────────────

def _score_verdict(score: int) -> str:
    if score >= 75:
        return "in good shape"
    if score >= 45:
        return "doing some things right but leaking potential customers"
    return "losing customers it should be winning"


def _fallback_summary(audit: dict) -> str:
    score = audit["overall_score"]
    btype = audit.get("business_type", "Local Business")
    critical = [i for i in audit["all_issues"] if i["severity"] == "critical"]
    verdict = _score_verdict(score)

    p1 = (f"This {btype.lower()} website scored {score} out of 100, which means it's "
          f"{verdict}. ")
    if critical:
        p1 += (f"We found {len(critical)} critical problem"
               f"{'s' if len(critical) != 1 else ''} standing between visitors "
               f"and making an enquiry.")
    else:
        p1 += "The fundamentals are solid, with only smaller refinements left to make."

    if critical:
        top = critical[0]["issue"].rstrip(".")
        p2 = (f"The most urgent one: {top.lower()}. For a {btype.lower()}, most people "
              f"decide in seconds whether to trust you and get in touch — every gap here "
              f"is a visitor who quietly leaves for a competitor instead of picking up the "
              f"phone or filling in a form.")
    else:
        p2 = (f"With the basics in place, the next wins are about polish and conversion — "
              f"making it even easier and faster for a visitor to become an enquiry.")
    return p1 + "\n\n" + p2


def generate_summary(audit: dict) -> str:
    if not AI_ENABLED:
        return _fallback_summary(audit)

    score = audit["overall_score"]
    btype = audit.get("business_type", "Local Business")
    domain = audit["domain"]
    critical = [i for i in audit["all_issues"] if i["severity"] == "critical"]
    positives = audit.get("all_positives", [])
    crit_text = "\n".join([f"- {i['issue']}" for i in critical[:4]]) or "No critical issues"
    pos_text = "\n".join([f"- {p}" for p in positives[:4]]) or "No standout positives"

    prompt = f"""You are a senior web consultant writing a website audit summary for a {btype}.
The business website is {domain}. Overall score: {score}/100.

Critical issues:
{crit_text}

What's working:
{pos_text}

Write exactly 2 short paragraphs in plain English:
Paragraph 1: Honest overall assessment tied to their score and what it means for a {btype}.
Paragraph 2: The single most urgent problem and how it costs this {btype} customers right now.

Rules: prose only, no bullet points, short direct sentences, business-owner language.
Do NOT use: "crucial", "leverage", "delve", "furthermore", "in conclusion". Do NOT use the word "audit"."""
    try:
        return _generate(prompt)
    except Exception:
        return _fallback_summary(audit)


# ─── PER-ISSUE BUSINESS IMPACT (AI polish → deterministic lookup) ────────────

_IMPACT_MAP = {
    "no_phone": "This means anyone ready to buy right now can't call you — and most won't hunt for another way.",
    "no_tel_link": "This means mobile visitors have to copy your number by hand, and many give up before they do.",
    "no_email": "This means people who prefer to write rather than call have no way to reach you at all.",
    "no_contact_form": "This means every enquiry outside business hours is lost — nights and weekends included.",
    "no_address": "This means Google and customers can't confirm you're a real local business, hurting local rankings and trust.",
    "no_map": "This means new customers can't picture where you are, which quietly lowers confidence in booking.",
    "no_cta": "This means visitors reach your page, feel interested, then leave because nothing tells them what to do next.",
    "weak_cta": "This means your primary action is easy to miss, so interested visitors slip away instead of enquiring.",
    "no_booking": "This means every booking has to go through a phone call, and you lose the ones who'd rather book online at 11pm.",
    "no_reviews": "This means first-time visitors have no proof other people trusted you, the #1 reason locals choose one business over another.",
    "no_google_reviews": "This means your most trusted review source is invisible on your own site, so visitors go check competitors instead.",
    "no_trust_badges": "This means nothing on the page reassures a cautious buyer that you're qualified, insured, or established.",
    "no_social": "This means you're cut off from the free channels where locals discover and vet businesses like yours.",
    "no_about": "This means visitors can't see the people behind the business, which makes a first enquiry feel riskier.",
    "no_ssl": "This means every visitor sees a 'Not Secure' warning — an instant credibility killer before they read a word.",
    "no_security_headers": "This means the site is missing basic hardening that protects visitors and your reputation.",
    "form_on_http": "This means customer details are sent unencrypted, which is both a trust and a compliance problem.",
    "slow_load": "This means visitors on phones wait, get impatient, and bounce before your page even finishes loading.",
    "large_page": "This means the page is heavy on mobile data and slow to appear, costing you impatient visitors.",
    "unoptimized_images": "This means oversized images slow the page down, and speed directly affects how many people stay.",
    "no_cache": "This means repeat visitors re-download everything each time, making the site feel sluggish.",
    "no_viewport": "This means the site renders as a shrunken desktop page on phones — where most of your traffic is.",
    "bad_viewport": "This means the mobile layout can misbehave, frustrating the majority of visitors who arrive on a phone.",
    "small_text": "This means mobile visitors have to pinch and zoom to read, and many just leave instead.",
    "fixed_width": "This means parts of the page overflow the screen on mobile, forcing awkward sideways scrolling.",
    "mobile_slow": "This means phone users — usually your biggest audience — wait too long and give up.",
    "seo_title": "This means Google struggles to show you for the searches your customers actually type.",
    "seo_meta": "This means Google writes your search snippet for you, usually in a way that wins fewer clicks.",
    "seo_h1": "This means search engines get no clear signal about what this page is for, weakening your rankings.",
    "seo_images": "This means image search and screen readers can't understand your visuals, a small SEO and accessibility loss.",
    "seo_canonical": "This means duplicate versions of a page can compete with each other in Google.",
    "no_schema": "This means you miss out on rich Google results — stars, address, hours — that make listings stand out.",
    "seo_og": "This means links to your site look plain and unappealing when shared on social media.",
}


def generate_issue_impact(issue: dict, btype: str, business_name: str) -> str:
    """Bold, specific impact line. Deterministic lookup, optionally refined by AI."""
    if issue.get("business_impact"):
        return issue["business_impact"]

    base = _IMPACT_MAP.get(issue.get("impact_key", ""), "")
    if not AI_ENABLED:
        return base

    prompt = f"""Write ONE bold, specific sentence (max 25 words) explaining exactly how this
website issue costs a {btype} called {business_name} real customers.

Issue: {issue['issue']}

Rules: specific to a {btype}, direct cause-effect, no corporate speak, no fluff.
Start with "This means" or similar."""
    try:
        return _generate(prompt) or base
    except Exception:
        return base


# ─── OUTREACH EMAIL (AI polish → deterministic template) ─────────────────────

def _fallback_outreach(audit: dict, services: list) -> str:
    biz = audit["business_name"]
    btype = audit.get("business_type", "Local Business")
    critical = [i for i in audit["all_issues"] if i["severity"] == "critical"]
    top = critical[:2] if critical else audit["all_issues"][:2]

    if len(top) >= 2:
        problems = (f"a couple of things stood out — {top[0]['issue'].lower().rstrip('.')}, "
                    f"and {top[1]['issue'].lower().rstrip('.')}")
    elif len(top) == 1:
        problems = f"one thing stood out — {top[0]['issue'].lower().rstrip('.')}"
    else:
        problems = "a few small things that could be tightened up"

    fix_line = ""
    if services:
        fix_line = (f" Both are quick wins we help {btype.lower()}s with all the time, and "
                    f"fixing them usually means more of your existing visitors actually get in touch.")

    return (
        f"Hi,\n\n"
        f"I came across {biz} while looking at local {btype.lower()} websites and had a proper look "
        f"at your site. It's clearly a real business, so I hope you don't mind me reaching out.\n\n"
        f"While I was there, {problems}.{fix_line}\n\n"
        f"No pitch and no obligation — if it's useful, I'm happy to jump on a quick 15-minute call "
        f"and walk you through exactly what I'd change and why. Totally up to you.\n\n"
        f"Either way, all the best with the business.\n\n"
        f"— [Your Name], {AGENCY}"
    )


def generate_outreach_email(audit: dict, services: list) -> str:
    if not AI_ENABLED:
        return _fallback_outreach(audit, services)

    domain = audit["domain"]
    biz = audit["business_name"]
    score = audit["overall_score"]
    btype = audit.get("business_type", "Local Business")
    critical = [i for i in audit["all_issues"] if i["severity"] == "critical"]
    issue_lines = "\n".join([f"- {i['issue']}" for i in critical[:2]])
    top_services = ", ".join([s["service"] for s in services[:2]])

    prompt = f"""Write a short outreach email from {AGENCY} to the owner of {biz} ({domain}).
They run a {btype}. Their site scored {score}/100.

Two specific problems found:
{issue_lines}

Services that could help: {top_services}

Write 150-180 words that:
1. Opens with something genuine about their specific business type.
2. Mentions exactly 2 specific problems in natural prose (NOT bullets).
3. Never uses the words "audit", "report", or "analyse" — say "I had a look at your site".
4. Closes with a soft, no-obligation offer of a 15-minute call.
5. Signs off as "[Your Name], {AGENCY}".
Do NOT use: exclamation marks, "I hope this finds you well", bullet points."""
    try:
        return _generate(prompt)
    except Exception:
        return _fallback_outreach(audit, services)


# ─── CUSTOMER EXPECTATIONS (deterministic, findings-driven) ──────────────────

def _has_positive(audit: dict, *needles: str) -> bool:
    pos = " ".join(audit.get("all_positives", [])).lower()
    return any(n in pos for n in needles)


def build_customer_expectations(audit: dict) -> dict:
    """Deterministic 'what your customers look for' panel, driven by real findings."""
    btype = audit.get("business_type", "Local Business")
    c = audit.get("contact_details", {})

    checks = [
        {"name": "Clear way to contact you",
         "present": bool(c.get("phone_found") or c.get("email_found") or c.get("contact_form")),
         "why": "People decide fast — if they can't see how to reach you, they move on.",
         "stat": "Most visitors leave within seconds if contact options aren't obvious."},
        {"name": "Proof other people trust you",
         "present": _has_positive(audit, "review", "testimonial"),
         "why": "Reviews and testimonials are the number one thing that turns a browser into an enquiry.",
         "stat": "The vast majority of people check reviews before choosing a local business."},
        {"name": "Works well on a phone",
         "present": audit.get("scores", {}).get("mobile", 0) >= 60,
         "why": "Most of your visitors arrive on a mobile — a clunky mobile page loses them.",
         "stat": "Over 60% of local searches happen on a phone."},
        {"name": "Loads quickly and feels secure",
         "present": bool(audit.get("is_https")) and audit.get("scores", {}).get("performance", 0) >= 50,
         "why": "A slow page or a 'Not Secure' warning kills trust before they read anything.",
         "stat": "Every extra second of load time measurably increases the number of people who leave."},
        {"name": "An easy next step (book / enquire)",
         "present": _has_positive(audit, "cta", "booking", "call-to-action") or bool(c.get("contact_form")),
         "why": "A clear 'Book Now' or 'Get a Quote' button removes the friction between interest and action.",
         "stat": "Sites with a clear primary action convert noticeably more visitors."},
    ]

    missing = [{"name": x["name"], "why": x["why"], "stat": x["stat"]} for x in checks if not x["present"]]
    met = [{"name": x["name"], "why": x["why"], "stat": x["stat"]} for x in checks if x["present"]]

    return {
        "label": btype,
        "headline_stat": (f"Before choosing a {btype.lower()}, most people quietly judge the "
                          f"website first — and decide in seconds whether you're worth an enquiry."),
        "missing": missing,
        "met": met,
    }


# ─── ENRICHMENT PIPELINE ─────────────────────────────────────────────────────

def enrich_audit(audit: dict) -> dict:
    """Add generated content to audit results (summary, impacts, email, expectations)."""
    btype = audit.get("business_type", "Local Business")
    biz = audit.get("business_name", "this business")

    audit["ai_summary"] = generate_summary(audit)
    audit["recommended_services"] = map_issues_to_services(audit["all_issues"], btype)

    for issue in audit["all_issues"]:
        if not issue.get("business_impact"):
            issue["business_impact"] = generate_issue_impact(issue, btype, biz)

    audit["outreach_email"] = generate_outreach_email(audit, audit["recommended_services"])
    audit["customer_expectations"] = build_customer_expectations(audit)
    return audit
