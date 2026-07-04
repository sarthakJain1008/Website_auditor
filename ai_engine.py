"""
ai_engine.py — Rebuilt with business-type-aware AI.
Generates: personalized summary, per-issue business impact, service map, outreach email.
"""
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

load_dotenv()
_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))

def _generate(prompt: str) -> str:
    response = _client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    return response.text.strip()
AGENCY = os.getenv("AGENCY_NAME", "Ryotech")


RYOTECH_SERVICES = [
    {
        "name": "Website Security & SSL Setup",
        "triggers": ["ssl", "https", "not secure", "security", "http"],
        "description": "Install SSL certificate, configure HTTPS, set security headers",
        "outcome": "Browser 'Not Secure' warning removed, customer trust restored immediately"
    },
    {
        "name": "Performance Optimisation",
        "triggers": ["slow", "load time", "response time", "page size", "cache", "webp", "image"],
        "description": "Image compression, CDN setup, caching, code minification",
        "outcome": "Target sub-1.5s load time — directly reduces bounce rate and increases enquiries"
    },
    {
        "name": "Google Reviews & Reputation Management",
        "triggers": ["review", "testimonial", "google review", "trust", "social proof"],
        "description": "Google Reviews widget, automated review request system, review response strategy",
        "outcome": "Visible star ratings on site, automated email/SMS asking happy customers for reviews"
    },
    {
        "name": "Lead Capture & Contact Form Setup",
        "triggers": ["contact form", "email", "phone", "enquiry", "form", "lead"],
        "description": "Custom contact form, CRM integration, email notifications, lead tracking",
        "outcome": "24/7 lead capture — enquiries come in while you sleep"
    },
    {
        "name": "Local SEO Package",
        "triggers": ["seo", "title", "meta", "schema", "canonical", "local", "google", "map pack", "google business"],
        "description": "On-page SEO, Google Business Profile optimisation, local citations, schema markup",
        "outcome": "Rank higher in local Google search and Google Maps for your key services"
    },
    {
        "name": "Conversion Rate Optimisation (CRO)",
        "triggers": ["cta", "call-to-action", "booking", "convert", "enquiry", "button", "book"],
        "description": "CTA redesign, A/B testing, booking system integration, landing page optimisation",
        "outcome": "More of your existing visitors turn into paying customers without spending more on ads"
    },
    {
        "name": "Mobile-First Responsive Redesign",
        "triggers": ["mobile", "viewport", "responsive", "phone", "tap", "font size", "horizontal scroll"],
        "description": "Full mobile-responsive design, viewport configuration, mobile UX audit",
        "outcome": "Perfect experience on every device — capturing 60%+ of traffic that comes from phones"
    },
    {
        "name": "Online Booking Integration",
        "triggers": ["booking", "appointment", "schedule", "calendar", "reserve", "reservation"],
        "description": "Calendly / custom booking system, automated reminders, calendar sync",
        "outcome": "Customers book 24/7 without calling — 3x more conversions than phone-only"
    },
    {
        "name": "Social Media Setup & Management",
        "triggers": ["social", "instagram", "facebook", "linkedin", "tiktok"],
        "description": "Social profile setup, content strategy, cross-linking from website",
        "outcome": "Active social presence that drives local awareness and recurring traffic"
    },
    {
        "name": "Website Copywriting & Messaging",
        "triggers": ["title", "headline", "content", "copy", "description", "message", "value"],
        "description": "Rewrite homepage copy to pass the 5-second test, benefit-led headlines, clear value proposition",
        "outcome": "Visitors instantly understand what you do and why they should choose you"
    },
    {
        "name": "Structured Data & Rich Snippets Setup",
        "triggers": ["schema", "structured data", "rich result", "og tag", "open graph"],
        "description": "LocalBusiness schema, FAQ schema, product/service schema, OG tags",
        "outcome": "Google shows your business with star ratings, address, hours directly in search results"
    },
    {
        "name": "Full Website Redesign",
        "triggers": ["outdated", "design", "old", "unprofessional", "branding", "rebuild"],
        "description": "Complete modern redesign built for conversion, trust, and speed",
        "outcome": "A site that works as a 24/7 salesperson — professional, fast, and optimised to convert"
    },
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
    # Sort: critical issues first
    sev_order = {"critical": 0, "medium": 1, "low": 2}
    result = sorted(matched_services.values(), key=lambda x: sev_order.get(x["severity"], 9))
    return result[:8]



def detect_exact_business(audit: dict) -> str:
    domain = audit.get("domain", "")
    title = audit.get("seo_details", {}).get("title", "")
    desc = audit.get("seo_details", {}).get("meta_description", "")
    
    prompt = f"""Analyze this local business website and tell me EXACTLY what type of business it is in 2-4 words.
Domain: {domain}
Title: {title}
Description: {desc}

Rules:
- Be precise (e.g. "Commercial Plumber", "Boutique Pharmacy", "AI Automation Agency", "Martial Arts Gym")
- Do not use generic terms like "Local Business" unless you have absolutely no idea.
- Output ONLY the 2-4 word description. Nothing else."""
    try:
        res = _generate(prompt)
        return res if res else "Local Business"
    except:
        return "Local Business"

def generate_summary(audit: dict) -> str:
    score = audit["overall_score"]
    btype = audit.get("business_type", "default")
    btype_label = btype
    domain = audit["domain"]
    issues = audit["all_issues"]
    positives = audit.get("all_positives", [])
    critical = [i for i in issues if i["severity"] == "critical"]
    rt = audit.get("response_time", 0)
    is_https = audit.get("is_https", True)

    crit_text = "\n".join([f"- {i['issue']}" for i in critical[:4]]) or "No critical issues"
    pos_text = "\n".join([f"- {p}" for p in positives[:4]]) or "No standout positives"

    prompt = f"""You are a senior web consultant writing a website audit summary for a {btype_label}.
The business website is {domain}. Overall score: {score}/100.

Critical issues:
{crit_text}

What's working:
{pos_text}

Additional facts: HTTPS = {is_https}, Response time = {rt}s

Write exactly 2 paragraphs in plain English:
Paragraph 1 (2-3 sentences): Honest overall assessment. Mention their score and what it means for their business specifically as a {btype_label}.
Paragraph 2 (2-3 sentences): The most urgent problem and specifically how it is costing this {btype_label} customers right now. Be direct and specific — use real language a business owner understands.

Strict rules:
- NO bullet points — prose only
- NO words: "crucial", "leverage", "paramount", "delve", "furthermore", "in conclusion", "it's worth noting"
- Short direct sentences. Business owner language.
- Reference the specific business type ({btype_label}) in your impact statements
- Do NOT mention the word "audit"
"""
    try:
        return _generate(prompt)
    except Exception as e:
        return f"This website scored {score}/100. There are {len(critical)} critical problems that need immediate attention to stop losing customers."


def generate_issue_impact(issue: dict, btype: str, business_name: str) -> str:
    """Generate a bold, specific business impact statement for each critical/medium issue."""
    if issue.get("business_impact"):
        return issue["business_impact"]

    btype_label = btype
    prompt = f"""Write ONE bold, specific sentence (max 25 words) explaining exactly how this website issue costs a {btype_label} called {business_name} real money or real customers.

Issue: {issue['issue']}

Rules:
- Specific to a {btype_label}, not generic
- Include a stat or specific consequence if natural
- Start with "This means" or use direct cause-effect language
- NO fluff, NO corporate speak
- Sound like a straight-talking consultant, not a salesperson
"""
    try:
        return _generate(prompt)
    except:
        return ""


def generate_outreach_email(audit: dict, services: list) -> str:
    domain = audit["domain"]
    biz = audit["business_name"]
    score = audit["overall_score"]
    btype = audit.get("business_type", "default")
    btype_label = btype
    critical = [i for i in audit["all_issues"] if i["severity"] == "critical"]
    top_2 = critical[:2]
    issue_lines = "\n".join([f"- {i['issue']}" for i in top_2])
    top_services = ", ".join([s["service"] for s in services[:2]])

    prompt = f"""Write a short outreach email from {AGENCY} to the owner of {biz} ({domain}).
They run a {btype_label}. Their site scored {score}/100.

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
    except Exception as e:
        return f"Hi,\n\nI came across {biz} online and wanted to reach out about a couple of things I noticed on your site.\n\nWould you be open to a 15-minute call this week?\n\n— [Your Name], {AGENCY}"


def enrich_audit(audit: dict) -> dict:
    print("[AI] Detecting exact business type...")
    audit["business_type"] = detect_exact_business(audit)
    print("[AI] Detected as:", audit["business_type"])
    
    print("[AI] Generating summary...")
    audit["ai_summary"] = generate_summary(audit)

    print("[AI] Mapping services...")
    audit["recommended_services"] = map_issues_to_services(
        audit["all_issues"], audit.get("business_type", "Local Business")
    )

    print("[AI] Generating issue impacts...")
    btype = audit.get("business_type", "Local Business")
    biz = audit.get("business_name", "this business")
    for issue in audit["all_issues"]:
        if not issue.get("business_impact"):
            issue["business_impact"] = generate_issue_impact(issue, btype, biz)

    print("[AI] Writing outreach email...")
    audit["outreach_email"] = generate_outreach_email(audit, audit["recommended_services"])
    
    # Also generate customer expectations
    print("[AI] Generating customer expectations...")
    try:
        cex_prompt = f"""List 3 specific things that customers of a {btype} specifically look for on a website before choosing them.
Format EXACTLY as JSON:
{{
  "label": "{btype}",
  "headline_stat": "A realistic but punchy statistic about {btype} customers online (e.g. 78% of people research...).",
  "missing": [
      {{"name": "Missing Expectation 1", "why": "Why it matters", "stat": "A specific stat"}}
  ],
  "met": []
}}
"""
        res = _generate(cex_prompt)
        if "{" in res and "}" in res:
            import json
            json_str = res[res.find("{"):res.rfind("}")+1]
            audit["customer_expectations"] = json.loads(json_str)
    except:
        pass
        
    return audit
