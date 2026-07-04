"""
ai_engine.py — AI-first audit engine.
Gemini reads the actual HTML and audits contact info, CTAs, trust signals,
and business type — replacing fragile regex/keyword matching.
Python still handles: SEO tags, security headers, performance timing, mobile viewport.
"""
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import re
import json

load_dotenv()
_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
AGENCY = os.getenv("AGENCY_NAME", "Ryotech")


def _generate(prompt: str) -> str:
    response = _client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    return response.text.strip()


def _clean_html_for_ai(raw_html: str, max_chars: int = 18000) -> str:
    """Strip noise from HTML but keep meaningful structure for AI to read."""
    # Remove script, style, svg, noscript blocks
    cleaned = re.sub(r'<script[^>]*>.*?</script>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<style[^>]*>.*?</style>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<svg[^>]*>.*?</svg>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<noscript[^>]*>.*?</noscript>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML comments
    cleaned = re.sub(r'<!--.*?-->', '', cleaned, flags=re.DOTALL)
    # Collapse whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # Truncate to stay within token limits
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars]
    return cleaned.strip()


# ─── CORE AI AUDIT ───────────────────────────────────────────────────────────
# One Gemini call that reads the HTML and audits contact, CTA, trust signals.

def ai_audit_page(full_html: str, domain: str) -> dict:
    """Send cleaned HTML to Gemini for a full content audit.
    Returns structured dict with contact, CTA, trust findings + business type.
    """
    cleaned = _clean_html_for_ai(full_html)

    prompt = f"""You are a senior website auditor. Analyze this website's HTML and report what you find.
Website domain: {domain}

HTML content:
{cleaned}

Analyze the HTML carefully and return a JSON object with these EXACT keys:

{{
  "business_type": "Exact business type in 2-4 words (e.g. 'Online Pharmacy', 'AI Automation Agency', 'Martial Arts Gym')",

  "contact": {{
    "phone_found": true/false,
    "phone_number": "the actual phone number found, or empty string",
    "phone_clickable": true/false (is there a tel: link?),
    "email_found": true/false,
    "email_address": "the actual email found, or empty string",
    "contact_form_found": true/false,
    "address_found": true/false,
    "address_text": "the actual address found, or empty string",
    "google_maps_found": true/false
  }},

  "cta": {{
    "ctas_found": ["list of CTA button texts found, e.g. 'Book Now', 'Get a Quote'"],
    "has_booking_system": true/false,
    "booking_platform": "name of booking platform if detected, or empty string"
  }},

  "trust": {{
    "has_reviews": true/false,
    "review_platforms": ["list of review platforms found, e.g. 'Trustpilot', 'Google Reviews'"],
    "has_google_reviews": true/false,
    "has_trust_badges": true/false,
    "trust_badges_found": ["e.g. 'Licensed', 'Insured', 'BBB Accredited'"],
    "has_social_links": true/false,
    "social_platforms": ["e.g. 'Facebook', 'Instagram'"],
    "has_about_section": true/false
  }}
}}

Rules:
- Look at BOTH visible text AND HTML attributes (href, src, data attributes, JSON-LD schema, meta tags)
- For phone: check tel: links, href attributes, visible text, JSON-LD
- For email: check mailto: links, visible text, Cloudflare-protected emails (__cf_email__)
- For contact form: check <form> tags, embedded platforms (Typeform, HubSpot, JotForm, WPForms)
- For address: check visible text, JSON-LD streetAddress/addressLocality, footer content
- For CTAs: look at <button> and <a> tags with action-oriented text
- For booking: check for Calendly, Fresha, MindBody, Acuity, OpenTable, or similar
- For reviews: check for review widgets, testimonial sections, star ratings
- For social: check for links to Facebook, Instagram, LinkedIn, Twitter/X, YouTube, TikTok
- Be accurate. Only report things you actually find in the HTML. Do NOT guess.
- Output ONLY the JSON object. No markdown formatting, no backticks, no explanation."""

    try:
        raw_response = _generate(prompt)
        # Extract JSON from response
        json_str = raw_response
        if "```" in json_str:
            json_str = re.sub(r'```json?\s*', '', json_str)
            json_str = re.sub(r'```', '', json_str)
        json_str = json_str.strip()
        result = json.loads(json_str)
        print(f"[AI Audit] Business type: {result.get('business_type', 'unknown')}")
        return result
    except json.JSONDecodeError as e:
        print(f"[AI Audit] JSON parse error: {e}")
        print(f"[AI Audit] Raw response: {raw_response[:200]}")
        return _fallback_result()
    except Exception as e:
        print(f"[AI Audit] API error: {e}")
        return _fallback_result()


def _fallback_result() -> dict:
    """Fallback when AI is unavailable — returns conservative defaults."""
    return {
        "business_type": "Local Business",
        "contact": {
            "phone_found": False, "phone_number": "",
            "phone_clickable": False,
            "email_found": False, "email_address": "",
            "contact_form_found": False,
            "address_found": False, "address_text": "",
            "google_maps_found": False,
        },
        "cta": {
            "ctas_found": [],
            "has_booking_system": False,
            "booking_platform": "",
        },
        "trust": {
            "has_reviews": False, "review_platforms": [],
            "has_google_reviews": False,
            "has_trust_badges": False, "trust_badges_found": [],
            "has_social_links": False, "social_platforms": [],
            "has_about_section": False,
        },
    }


# ─── SCORING FROM AI RESULTS ────────────────────────────────────────────────

def score_contact(ai_contact: dict) -> dict:
    """Convert AI contact findings into score, issues, positives."""
    issues, positives = [], []
    score = 0

    if ai_contact.get("phone_found"):
        score += 30
        phone = ai_contact.get("phone_number", "")
        positives.append(f"Phone number found{': ' + phone if phone else ''}")
    else:
        issues.append({"severity": "critical",
                       "issue": "No phone number found on the website",
                       "fix": "Add your phone number to the header AND footer. Make it a clickable tel: link for mobile users.",
                       "impact_key": "no_phone"})

    if ai_contact.get("phone_clickable"):
        score += 10
        positives.append("Phone is clickable (tel: link)")
    elif ai_contact.get("phone_found"):
        issues.append({"severity": "medium",
                       "issue": "Phone number exists but is NOT clickable on mobile",
                       "fix": "Wrap your phone number in <a href='tel:+1...'> so mobile visitors can tap-to-call instantly.",
                       "impact_key": "no_tel_link"})

    if ai_contact.get("email_found"):
        score += 15
        positives.append("Email address found")
    else:
        issues.append({"severity": "medium",
                       "issue": "No email address visible on the site",
                       "fix": "Add a contact email address. Use a professional domain email (you@yourbusiness.com) not Gmail or Hotmail.",
                       "impact_key": "no_email"})

    if ai_contact.get("contact_form_found"):
        score += 25
        positives.append("Contact / enquiry form present")
    else:
        issues.append({"severity": "critical",
                       "issue": "No contact form found — you are only reachable when you can answer the phone",
                       "fix": "Add a simple contact form: Name, Email, Phone, Message. This captures leads 24/7 including nights and weekends.",
                       "impact_key": "no_contact_form"})

    if ai_contact.get("address_found"):
        score += 10
        positives.append("Physical address visible")
    else:
        issues.append({"severity": "medium",
                       "issue": "Physical address not clearly visible — hurts local SEO and trust",
                       "fix": "Show your full street address in the footer. Required for Google Business Profile consistency and local search rankings.",
                       "impact_key": "no_address"})

    if ai_contact.get("google_maps_found"):
        score += 10
        positives.append("Google Maps embedded or linked")
    else:
        issues.append({"severity": "low",
                       "issue": "No Google Maps embed or link",
                       "fix": "Embed a Google Map showing your location. It reinforces you're a real, established local business.",
                       "impact_key": "no_map"})

    return {"score": min(score, 100), "issues": issues, "positives": positives,
            "details": {
                "phone_found": ai_contact.get("phone_found", False),
                "email_found": ai_contact.get("email_found", False),
                "contact_form": ai_contact.get("contact_form_found", False),
                "address_found": ai_contact.get("address_found", False),
                "google_maps": ai_contact.get("google_maps_found", False),
                "tel_link": ai_contact.get("phone_clickable", False),
            }}


def score_cta(ai_cta: dict) -> dict:
    """Convert AI CTA findings into score, issues, positives."""
    issues, positives = [], []
    score = 0

    ctas = ai_cta.get("ctas_found", [])
    if len(ctas) >= 3:
        score += 50
        positives.append(f"{len(ctas)} CTAs found throughout page")
    elif len(ctas) == 2:
        score += 35
        issues.append({"severity": "medium",
                       "issue": "Only 2 CTAs found — add more throughout the page",
                       "fix": "Place CTAs at top, middle, and bottom. Repeat your primary CTA at least 3 times on a homepage.",
                       "impact_key": "weak_cta"})
    elif len(ctas) == 1:
        score += 20
        issues.append({"severity": "critical",
                       "issue": "Only 1 CTA found — 70% of small business sites have this problem",
                       "fix": "Add clear CTA buttons at the top (hero section), after every service, and in the footer.",
                       "impact_key": "no_cta"})
    else:
        issues.append({"severity": "critical",
                       "issue": "No call-to-action buttons found — visitors have no clear next step",
                       "fix": "Add prominent CTA buttons: 'Book Now', 'Get a Free Quote', 'Call Us'. Highest-ROI change you can make.",
                       "impact_key": "no_cta"})

    if ai_cta.get("has_booking_system"):
        score += 30
        platform = ai_cta.get("booking_platform", "")
        positives.append(f"Online booking present{' (' + platform + ')' if platform else ''}")
    else:
        issues.append({"severity": "medium",
                       "issue": "No online booking or scheduling system found",
                       "fix": "Integrate a free booking tool (Calendly, Fresha, or a simple form). Businesses with online booking convert 3x more website visitors.",
                       "impact_key": "no_booking"})

    # Phone CTA bonus (max 20 pts) — handled in contact scoring
    return {"score": min(score, 100), "issues": issues, "positives": positives,
            "ctas_found": ctas[:5]}


def score_trust(ai_trust: dict) -> dict:
    """Convert AI trust findings into score, issues, positives."""
    issues, positives = [], []
    score = 0

    if ai_trust.get("has_reviews"):
        score += 30
        platforms = ai_trust.get("review_platforms", [])
        positives.append(f"Reviews/testimonials found{' (' + ', '.join(platforms) + ')' if platforms else ''}")
    else:
        issues.append({"severity": "critical",
                       "issue": "No customer testimonials or reviews section",
                       "fix": "Add a dedicated testimonials section with 3-5 real customer quotes, names, and if possible, photos.",
                       "impact_key": "no_reviews"})

    if ai_trust.get("has_google_reviews"):
        score += 25
        positives.append("Google Reviews reference found")
    else:
        issues.append({"severity": "critical",
                       "issue": "No Google Reviews link or widget — the most trusted review source is missing",
                       "fix": "Add a 'See Our Google Reviews' button linked to your Google Business Profile, or embed a Google Reviews widget.",
                       "impact_key": "no_google_reviews"})

    if ai_trust.get("has_trust_badges"):
        score += 20
        badges = ai_trust.get("trust_badges_found", [])
        positives.append(f"Trust badges/credentials present{' (' + ', '.join(badges[:3]) + ')' if badges else ''}")
    else:
        issues.append({"severity": "medium",
                       "issue": "No licences, certifications, or trust badges visible",
                       "fix": "Display any professional licences, industry memberships, awards, or satisfaction guarantees.",
                       "impact_key": "no_trust_badges"})

    if ai_trust.get("has_social_links"):
        score += 15
        socials = ai_trust.get("social_platforms", [])
        positives.append(f"Social media links present{' (' + ', '.join(socials[:3]) + ')' if socials else ''}")
    else:
        issues.append({"severity": "medium",
                       "issue": "No social media links — isolated from your biggest free marketing channels",
                       "fix": "Add visible links to your active social profiles (Facebook, Instagram).",
                       "impact_key": "no_social"})

    if ai_trust.get("has_about_section"):
        score += 10
        positives.append("About/team information present")
    else:
        issues.append({"severity": "low",
                       "issue": "No 'About Us' or team information found",
                       "fix": "Add a short About section with your story, your team, or why you started the business.",
                       "impact_key": "no_about"})

    return {"score": min(score, 100), "issues": issues, "positives": positives}


# ─── SERVICE MAPPING ─────────────────────────────────────────────────────────

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
                        "severity": issue["severity"]
                    }
    sev_order = {"critical": 0, "medium": 1, "low": 2}
    result = sorted(matched_services.values(), key=lambda x: sev_order.get(x["severity"], 9))
    return result[:8]


# ─── AI TEXT GENERATION ──────────────────────────────────────────────────────

def generate_summary(audit: dict) -> str:
    score = audit["overall_score"]
    btype = audit.get("business_type", "Local Business")
    domain = audit["domain"]
    issues = audit["all_issues"]
    positives = audit.get("all_positives", [])
    critical = [i for i in issues if i["severity"] == "critical"]
    rt = audit.get("response_time", 0)
    is_https = audit.get("is_https", True)

    crit_text = "\n".join([f"- {i['issue']}" for i in critical[:4]]) or "No critical issues"
    pos_text = "\n".join([f"- {p}" for p in positives[:4]]) or "No standout positives"

    prompt = f"""You are a senior web consultant writing a website audit summary for a {btype}.
The business website is {domain}. Overall score: {score}/100.

Critical issues:
{crit_text}

What's working:
{pos_text}

Additional facts: HTTPS = {is_https}, Response time = {rt}s

Write exactly 2 paragraphs in plain English:
Paragraph 1 (2-3 sentences): Honest overall assessment. Mention their score and what it means for their business specifically as a {btype}.
Paragraph 2 (2-3 sentences): The most urgent problem and specifically how it is costing this {btype} customers right now. Be direct and specific.

Strict rules:
- NO bullet points — prose only
- NO words: "crucial", "leverage", "paramount", "delve", "furthermore", "in conclusion", "it's worth noting"
- Short direct sentences. Business owner language.
- Reference the specific business type ({btype}) in your impact statements
- Do NOT mention the word "audit"
"""
    try:
        return _generate(prompt)
    except Exception:
        return f"This website scored {score}/100. There are {len(critical)} critical problems that need immediate attention to stop losing customers."


def generate_issue_impact(issue: dict, btype: str, business_name: str) -> str:
    """Generate a bold, specific business impact statement for each issue."""
    if issue.get("business_impact"):
        return issue["business_impact"]

    prompt = f"""Write ONE bold, specific sentence (max 25 words) explaining exactly how this website issue costs a {btype} called {business_name} real money or real customers.

Issue: {issue['issue']}

Rules:
- Specific to a {btype}, not generic
- Include a stat or specific consequence if natural
- Start with "This means" or use direct cause-effect language
- NO fluff, NO corporate speak
- Sound like a straight-talking consultant, not a salesperson
"""
    try:
        return _generate(prompt)
    except Exception:
        return ""


def generate_outreach_email(audit: dict, services: list) -> str:
    domain = audit["domain"]
    biz = audit["business_name"]
    score = audit["overall_score"]
    btype = audit.get("business_type", "Local Business")
    critical = [i for i in audit["all_issues"] if i["severity"] == "critical"]
    top_2 = critical[:2]
    issue_lines = "\n".join([f"- {i['issue']}" for i in top_2])
    top_services = ", ".join([s["service"] for s in services[:2]])

    prompt = f"""Write a short outreach email from {AGENCY} to the owner of {biz} ({domain}).
They run a {btype}. Their site scored {score}/100.

Two specific problems found:
{issue_lines}

Services that could help: {top_services}

Write a 150-180 word email that:
1. Opens with something genuine and specific about their business type (not generic "I was browsing the web")
2. Mentions exactly 2 specific problems from the list in natural, conversational language — NOT in bullet points
3. Does NOT use the word "audit", "report", or "analyse" — say "I had a look at your site"
4. Closes with a soft, non-pushy ask: offer a 15-minute call, no obligation
5. Signs off as "[Your Name], {AGENCY}"
6. Reads like a real person who genuinely noticed these things — NOT a sales pitch

Do NOT use: exclamation marks, "I hope this finds you well", "revolutionary", "game-changing", bullet points"""

    try:
        return _generate(prompt)
    except Exception:
        return f"Hi,\n\nI came across {biz} online and wanted to reach out about a couple of things I noticed on your site.\n\nWould you be open to a 15-minute call this week?\n\n— [Your Name], {AGENCY}"


# ─── ENRICHMENT PIPELINE ────────────────────────────────────────────────────

def enrich_audit(audit: dict) -> dict:
    """Add AI-generated content to audit results (summary, impacts, email, expectations)."""
    btype = audit.get("business_type", "Local Business")

    print("[AI] Generating summary...")
    audit["ai_summary"] = generate_summary(audit)

    print("[AI] Mapping services...")
    audit["recommended_services"] = map_issues_to_services(
        audit["all_issues"], btype
    )

    print("[AI] Generating issue impacts...")
    biz = audit.get("business_name", "this business")
    for issue in audit["all_issues"]:
        if not issue.get("business_impact"):
            issue["business_impact"] = generate_issue_impact(issue, btype, biz)

    print("[AI] Writing outreach email...")
    audit["outreach_email"] = generate_outreach_email(audit, audit["recommended_services"])

    # Generate customer expectations dynamically
    print("[AI] Generating customer expectations...")
    try:
        cex_prompt = f"""You are a business consultant. List 4 specific things that customers of a {btype} specifically look for on a website before choosing them.

For each item, check if it's likely present based on this info:
- Phone found: {audit.get('contact_details', {}).get('phone_found', False)}
- Email found: {audit.get('contact_details', {}).get('email_found', False)}
- Contact form: {audit.get('contact_details', {}).get('contact_form', False)}
- Has reviews: {any('review' in p.lower() or 'testimonial' in p.lower() for p in audit.get('all_positives', []))}
- Has booking: {any('booking' in p.lower() for p in audit.get('all_positives', []))}

Format EXACTLY as JSON (no markdown, no backticks):
{{
  "label": "{btype}",
  "headline_stat": "A realistic punchy statistic about {btype} customers researching online.",
  "missing": [
      {{"name": "Expectation Name", "why": "Why it matters in 1 sentence", "stat": "A specific stat"}}
  ],
  "met": [
      {{"name": "Expectation Name", "why": "Why it matters in 1 sentence", "stat": "A specific stat"}}
  ]
}}"""
        res = _generate(cex_prompt)
        if "{" in res and "}" in res:
            json_str = res
            if "```" in json_str:
                json_str = re.sub(r'```json?\s*', '', json_str)
                json_str = re.sub(r'```', '', json_str)
            json_str = json_str[json_str.find("{"):json_str.rfind("}") + 1]
            audit["customer_expectations"] = json.loads(json_str)
    except Exception:
        pass

    return audit
