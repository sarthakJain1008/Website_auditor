"""
audit_engine.py — Complete rebuild.
Business logic: Score from ZERO (additive model), detect business type,
generate personalized impact statements per issue.
Research findings applied:
- 53% mobile users leave if > 3s load
- 70% small biz have no effective CTA
- 61% won't return after bad mobile experience
- 7% conversion drop per second of delay
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

# ─── BUSINESS TYPE DETECTION ─────────────────────────────────────────────────

BUSINESS_TYPES = {
    "gym": ["gym", "fitness", "jiu-jitsu", "jiujitsu", "martial arts", "boxing", "crossfit", "yoga", "pilates", "workout", "personal trainer", "bjj", "mma", "kickboxing", "karate", "wrestling"],
    "restaurant": ["restaurant", "cafe", "diner", "bistro", "pizza", "sushi", "burger", "menu", "dining", "eatery", "food", "cuisine", "takeaway", "takeout", "delivery", "reservation", "reservations"],
    "plumber": ["plumb", "plumber", "drain", "pipe", "leak", "hot water", "blocked", "sewer", "gas fitting", "gasfitting", "water heater", "tap", "toilet", "bathroom renovation"],
    "dentist": ["dental", "dentist", "teeth", "orthodont", "braces", "implant", "whitening", "crown", "root canal", "gum", "smile", "oral", "invisalign", "checkup"],
    "salon": ["hair", "salon", "beauty", "nails", "manicure", "pedicure", "wax", "colour", "color", "haircut", "stylist", "blowout", "lash", "brow", "spa", "barber", "barbershop", "barbers", "shave", "fade", "trim", "grooming"],
    "lawyer": ["law", "legal", "attorney", "solicitor", "barrister", "lawyer", "litigation", "counsel", "firm", "injury", "divorce", "criminal", "property law"],
    "real_estate": ["real estate", "realty", "property", "homes for sale", "rent", "lease", "agent", "apartment", "listings", "mortgage", "landlord"],
    "medical": ["clinic", "doctor", "physician", "gp", "health", "medical", "surgery", "patient", "appointment", "specialist", "hospital", "urgent care", "telehealth"],
    "accountant": ["accountant", "accounting", "tax", "bookkeeping", "cpa", "financial", "payroll", "audit", "irs", "bas", "xero", "quickbooks"],
    "tradie": ["electrician", "electric", "carpenter", "carpentry", "builder", "builder", "painting", "painter", "roof", "roofer", "tiler", "landscap", "garden", "cleaning", "cleaner", "pest control", "locksmith"],
    "retail": ["shop", "store", "buy", "purchase", "product", "collection", "fashion", "clothing", "shoes", "accessories", "jewellery", "jewelry", "gifts"],
}

BUSINESS_IMPACT = {
    "gym": {
        "no_phone": "Potential members who want to ask about class times or pricing will call a competitor instead — gyms live and die by the phone.",
        "no_email": "Parents enrolling children in classes often prefer email first. No email = lost family sign-ups.",
        "no_contact_form": "Your trial offer is on the page but there's no way to claim it online. You're forcing people to call when many won't.",
        "no_ssl": "When someone enters their name and phone for a 'Free Trial', a browser security warning kills that conversion instantly.",
        "slow_load": "63% of your potential members are searching on mobile. A slow site means they've already called the gym down the road before your page loads.",
        "no_reviews": "Before joining a gym, people read every review. No visible reviews = no social proof = they choose a gym they've heard about.",
        "no_cta": "You have a trial offer but no obvious button to claim it. That's leaving money on the table every single day.",
        "no_google_reviews": "Local gym searches on Google show star ratings. Without reviews showing on your site, you look less established than you are.",
        "no_booking": "Gyms with online trial booking convert 3x more leads than those requiring a call. Every day without it is lost members.",
        "no_social": "Instagram is where people discover gyms. No social links = missing your biggest free marketing channel.",
    },
    "restaurant": {
        "no_phone": "Customers wanting to make a reservation or ask about specials will call whoever is first — that's not you.",
        "no_email": "Event bookings, large groups, and corporate catering all start with an email. You're missing this revenue stream.",
        "no_contact_form": "No online reservation system means you're losing bookings every night to competitors with OpenTable or a simple form.",
        "no_ssl": "If you take online orders or reservations, a 'Not Secure' warning stops customers mid-checkout.",
        "slow_load": "Hungry people search fast and decide fast. A 3+ second load time means they're ordering from a competitor before your menu appears.",
        "no_reviews": "92% of diners read online reviews before choosing a restaurant. No testimonials on your site weakens trust.",
        "no_cta": "No 'Book a Table' or 'Order Online' button above the fold means visitors leave without acting.",
        "no_social": "Food photos on Instagram drive foot traffic. No social links = invisible to food-discovery audiences.",
    },
    "plumber": {
        "no_phone": "Plumbing emergencies happen at 2am. If your phone number isn't the first thing visible, customers call someone else — permanently.",
        "no_email": "Commercial clients and property managers send quote requests by email. No email address = you're invisible to this high-value segment.",
        "no_contact_form": "A 24/7 quote request form captures leads while you sleep. Without it, you only get enquiries during business hours.",
        "no_ssl": "Customers entering their address and contact details for a job quote will abandon if they see 'Not Secure'.",
        "slow_load": "Emergency plumbing is time-critical. If your page takes 3+ seconds, the customer has already called your competitor.",
        "no_reviews": "Tradies live by word-of-mouth. Without reviews on your site, new customers have no proof you're reliable.",
        "no_cta": "No clear 'Get a Free Quote' button means you're getting traffic but no enquiries. Your site is a digital billboard, not a lead machine.",
    },
    "dentist": {
        "no_phone": "Patients in pain call immediately. If your number isn't prominent, they call the first dentist they find — losing you an emergency appointment worth $300+.",
        "no_email": "New patient registration and appointment requests via email are standard. Missing this means losing patients to practices with online booking.",
        "no_contact_form": "Without an appointment request form, you're forcing patients to call during clinic hours — you lose everyone who browses after-hours.",
        "no_ssl": "Patients entering health information, insurance details, or personal data on a non-HTTPS site face a browser warning. This destroys trust for a health provider.",
        "slow_load": "Patients comparing dentists will click back immediately if your site is slow. Dental anxiety is real — a frustrating website reinforces it.",
        "no_reviews": "For dentists, trust is everything. No reviews = patients choose the practice with 150 five-star reviews over yours.",
        "no_cta": "No 'Book Appointment' button means your marketing spend is bringing visitors who leave without booking. Your cost-per-acquisition is needlessly high.",
    },
    "salon": {
        "no_phone": "Clients wanting to book a colour appointment will text or call whoever responds fastest — and that's not you without a visible number.",
        "no_email": "Bridal parties and group bookings start with an email. No email address = missing your highest-revenue bookings.",
        "no_contact_form": "No online booking = clients go to Bookwell, Fresha, or StyleSeat and book your competitor instead.",
        "no_ssl": "When clients enter payment details for deposits, a 'Not Secure' warning makes them close the tab immediately.",
        "slow_load": "Salon discovery happens on mobile, on Instagram, then Google. A slow website after a social click loses the conversion at the last step.",
        "no_reviews": "Before anyone sits in your chair for a $200 colour job, they read reviews. No visible testimonials = no bookings from cold traffic.",
        "no_cta": "No 'Book Now' button above the fold is costing you bookings every hour. Salon clients are impulse-bookers.",
        "no_social": "Before/after photos drive salon bookings. No Instagram link = disconnected from your primary discovery channel.",
    },
    "tradie": {
        "no_phone": "Customers needing urgent work call the first person with a visible number. If it's not you, you lost the job before they read a word.",
        "no_email": "Builders, property managers, and strata companies send quote requests by email. No email = invisible to commercial work.",
        "no_contact_form": "A quote request form that works 24/7 is your best sales tool. Without it, you only get leads when you can answer the phone.",
        "no_ssl": "Customers entering their home address and contact details expect security. 'Not Secure' warnings make them question your professionalism.",
        "slow_load": "Trade services searches happen on job sites. If your page is slow, the customer calls your competitor while your page is still loading.",
        "no_reviews": "Homeowners spend thousands on trade work. Without reviews, you're asking them to trust a stranger with their biggest asset.",
        "no_cta": "No 'Get a Free Quote' or 'Book a Job' button means your site is not working for you. You're missing leads every single day.",
    },
    "default": {
        "no_phone": "Customers ready to buy need your phone number immediately. Every second they spend searching for it increases the chance they leave.",
        "no_email": "Many customers prefer to enquire by email first. No email address means losing this segment entirely.",
        "no_contact_form": "A contact form captures leads 24/7 — without one, you only hear from people willing to call during business hours.",
        "no_ssl": "A 'Not Secure' browser warning before a customer shares their details is a trust-killer. It directly reduces enquiries.",
        "slow_load": "A 1-second delay reduces conversions by 7%. At 3+ seconds, 53% of mobile visitors leave — permanently.",
        "no_reviews": "92% of consumers read reviews before making a decision. No visible social proof means customers choose competitors.",
        "no_cta": "70% of small business websites lack an effective call-to-action. Without it, visitors leave having done nothing.",
        "no_google_reviews": "Google Reviews are the first thing people see in local search results. Without them showing on your site, you lose trust immediately.",
        "no_booking": "Online booking converts more leads than phone-only. Without it, you're losing enquiries made outside business hours.",
        "no_social": "Social media presence builds ongoing brand awareness. Missing social links disconnects your site from your audience.",
    }
}


def detect_business_type(soup: BeautifulSoup, url: str) -> str:
    text = soup.get_text(" ", strip=True).lower() + " " + url.lower()
    scores = {btype: 0 for btype in BUSINESS_TYPES}
    for btype, keywords in BUSINESS_TYPES.items():
        for kw in keywords:
            if kw in text:
                scores[btype] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "default"


def get_impact(btype: str, issue_key: str) -> str:
    impacts = BUSINESS_IMPACT.get(btype, BUSINESS_IMPACT["default"])
    return impacts.get(issue_key, BUSINESS_IMPACT["default"].get(issue_key, ""))


# ─── PAGE FETCH ─────────────────────────────────────────────────────────────

def fetch_page(url: str) -> dict:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    start = time.time()
    try:
        r = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        }, allow_redirects=True)
        elapsed = round(time.time() - start, 2)
        return {
            "html": r.text, "status_code": r.status_code,
            "response_time": elapsed, "final_url": r.url,
            "is_https": r.url.startswith("https://"),
            "headers": dict(r.headers),
            "page_size_kb": round(len(r.content) / 1024, 1),
            "error": None
        }
    except Exception as e:
        return {"html": "", "error": str(e), "is_https": False,
                "response_time": 0, "final_url": url, "headers": {},
                "page_size_kb": 0, "status_code": 0}


# ─── ADDITIVE SCORING MODEL ─────────────────────────────────────────────────
# Starts from 0, earns points for each thing done RIGHT.
# This naturally differentiates good sites (many points) from bad ones (few points).

def analyze_seo(soup: BeautifulSoup, url: str) -> dict:
    issues, positives = [], []
    score = 0  # ADDITIVE from 0

    # Title (max 20 pts)
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    if title and 10 <= len(title) <= 60:
        score += 20; positives.append("Good title tag")
    elif title:
        score += 10
        issues.append({"severity": "medium", "issue": f"Page title is {len(title)} chars — outside the 10–60 range Google recommends",
                       "fix": "Rewrite the title tag to clearly describe the business in 10–60 characters. This directly affects your Google search listing.", "impact_key": "seo_title"})
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
                       "fix": "Rewrite your meta description to 120–155 characters. This is the text that appears under your link in Google.", "impact_key": "seo_meta"})
    else:
        issues.append({"severity": "medium", "issue": "Missing meta description — Google writes one for you (usually badly)",
                       "fix": "Add a compelling 120–155 character meta description. It's the first thing people read before clicking your Google listing.", "impact_key": "seo_meta"})

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
                       "fix": "Add one H1 heading that clearly states your main service or product. This is a fundamental SEO requirement.", "impact_key": "seo_h1"})

    # Images alt (max 10 pts)
    all_imgs = soup.find_all("img")
    no_alt = [i for i in all_imgs if not i.get("alt", "").strip()]
    if all_imgs and not no_alt:
        score += 10; positives.append("All images have alt text")
    elif no_alt:
        score += max(0, 10 - len(no_alt) * 2)
        issues.append({"severity": "medium", "issue": f"{len(no_alt)} of {len(all_imgs)} images missing alt text",
                       "fix": "Add descriptive alt text to every image. Google uses this to understand your images — it impacts both search and accessibility.", "impact_key": "seo_images"})

    # Canonical (max 5 pts)
    if soup.find("link", rel="canonical"):
        score += 5; positives.append("Canonical tag present")
    else:
        issues.append({"severity": "low", "issue": "No canonical tag — risk of duplicate content penalties",
                       "fix": "Add a canonical URL tag. This tells Google which version of your URL is the 'real' one and prevents ranking splits.", "impact_key": "seo_canonical"})

    # Structured data / Schema (max 10 pts)
    schema = soup.find("script", type="application/ld+json")
    if schema:
        score += 10; positives.append("Structured data (Schema) present")
    else:
        issues.append({"severity": "medium", "issue": "No structured data (Schema.org) — missing rich results eligibility",
                       "fix": "Add LocalBusiness JSON-LD schema. This gives Google your business name, address, hours, and type — enabling rich results and map pack visibility.", "impact_key": "no_schema"})

    # OG tags (max 5 pts)
    og_title = soup.find("meta", property="og:title")
    if og_title:
        score += 5; positives.append("Open Graph tags present")
    else:
        issues.append({"severity": "low", "issue": "Missing Open Graph tags — poor social media sharing appearance",
                       "fix": "Add og:title, og:description, and og:image tags. These control how your page looks when shared on Facebook, LinkedIn, and iMessage.", "impact_key": "seo_og"})

    return {"score": min(score, 100), "issues": issues, "positives": positives,
            "title": title, "meta_description": desc, "h1_count": len(h1s)}


def analyze_contact(soup: BeautifulSoup, btype: str) -> dict:
    issues, positives = [], []
    score = 0  # Additive

    html_text = soup.get_text(" ", strip=True)

    # Phone (max 30 pts — most critical for local biz)
    phone_pattern = re.compile(r'(\+?[\d][\d\s\(\)\-\.]{7,}[\d])')
    phones = [p for p in phone_pattern.findall(html_text) if len(re.sub(r'\D', '', p)) >= 7]
    if phones:
        score += 30; positives.append("Phone number visible")
    else:
        issues.append({"severity": "critical",
                       "issue": "No phone number found on the page",
                       "fix": "Add your phone number to the header AND footer. Make it a clickable tel: link for mobile users.",
                       "impact_key": "no_phone",
                       "business_impact": get_impact(btype, "no_phone")})

    # Clickable tel: link (max 10 pts)
    tel_links = soup.find_all("a", href=re.compile(r"^tel:"))
    if tel_links:
        score += 10; positives.append("Phone is clickable (tel: link)")
    elif phones:
        issues.append({"severity": "medium",
                       "issue": "Phone number exists but is NOT clickable on mobile",
                       "fix": "Wrap your phone number in <a href='tel:+1...'> so mobile visitors can tap-to-call instantly.",
                       "impact_key": "no_tel_link",
                       "business_impact": "Mobile users (60%+ of your traffic) can't tap your number to call. They have to manually type it — most won't bother."})

    # Email (max 15 pts)
    email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    emails = [e for e in email_pattern.findall(html_text) if not e.endswith((".png", ".jpg", ".gif", ".svg"))]
    if emails:
        score += 15; positives.append("Email address visible")
    else:
        issues.append({"severity": "medium",
                       "issue": "No email address visible on the site",
                       "fix": "Add a contact email address. Use a professional domain email (you@yourbusiness.com) not Gmail or Hotmail.",
                       "impact_key": "no_email",
                       "business_impact": get_impact(btype, "no_email")})

    # Contact form (max 25 pts)
    forms = soup.find_all("form")
    has_form = any(
        any(kw in str(f).lower() for kw in ["contact", "name", "message", "email", "enquir", "inquiry", "quote", "book", "appointment", "input"])
        for f in forms
    )
    if has_form:
        score += 25; positives.append("Contact / enquiry form present")
    else:
        issues.append({"severity": "critical",
                       "issue": "No contact form found — you are only reachable during hours when you can answer the phone",
                       "fix": "Add a simple contact form: Name, Email, Phone, Message. This captures leads 24/7 including nights and weekends.",
                       "impact_key": "no_contact_form",
                       "business_impact": get_impact(btype, "no_contact_form")})

    # Address (max 10 pts)
    address_keywords = ["street", "st ", "ave", "avenue", "road", "rd,", "blvd", "lane", "suite", " ny ", " ca ", " tx ", " fl ", " wa ", "nsw", "vic", "qld", "ontario", "london", "manchester", "bronx", "brooklyn", "queens"]
    has_address = any(kw in html_text.lower() for kw in address_keywords)
    if has_address:
        score += 10; positives.append("Address visible")
    else:
        issues.append({"severity": "medium",
                       "issue": "Physical address not clearly visible — hurts local SEO and trust",
                       "fix": "Show your full street address in the footer. This is required for Google Business Profile consistency and local search rankings.",
                       "impact_key": "no_address",
                       "business_impact": "Google's local ranking algorithm uses NAP (Name, Address, Phone) consistency. Missing address = lower map pack ranking."})

    # Google Maps (max 10 pts)
    has_map = bool(soup.find("iframe", src=re.compile(r"maps\.google|google\.com/maps")))
    if has_map:
        score += 10; positives.append("Google Maps embedded")
    else:
        issues.append({"severity": "low",
                       "issue": "No Google Maps embed",
                       "fix": "Embed a Google Map showing your location. It reinforces you're a real, established local business.",
                       "impact_key": "no_map",
                       "business_impact": "A map embed signals legitimacy and helps customers find you. Sites with maps have 25% higher trust scores in user studies."})

    return {"score": min(score, 100), "issues": issues, "positives": positives,
            "details": {"phone_found": bool(phones), "email_found": bool(emails),
                        "contact_form": has_form, "address_found": has_address,
                        "google_maps": has_map, "tel_link": bool(tel_links)}}


def analyze_cta(soup: BeautifulSoup, btype: str) -> dict:
    issues, positives = [], []
    score = 0

    cta_keywords = ["book", "call us", "call now", "get quote", "free quote", "contact us",
                    "enquire", "enquiry", "schedule", "appointment", "get started", "sign up",
                    "register", "buy now", "order now", "free trial", "claim", "request",
                    "reserve", "get in touch", "speak to", "message us", "whatsapp", "chat"]

    buttons = soup.find_all(["button", "a"])
    cta_found = []
    for b in buttons:
        text = b.get_text(strip=True).lower()
        if any(kw in text for kw in cta_keywords) and len(text) > 2:
            cta_found.append(b.get_text(strip=True))

    if len(cta_found) >= 3:
        score += 50; positives.append(f"{len(cta_found)} CTAs found throughout page")
    elif len(cta_found) == 2:
        score += 35
        issues.append({"severity": "medium", "issue": "Only 2 CTAs found — add more throughout the page",
                       "fix": "Place CTAs at top, middle, and bottom. Repeat your primary CTA at least 3 times on a homepage.",
                       "impact_key": "weak_cta", "business_impact": "Visitors who don't act in the first scroll rarely scroll back up. Missing CTAs in the middle and bottom loses these people."})
    elif len(cta_found) == 1:
        score += 20
        issues.append({"severity": "critical", "issue": "Only 1 CTA found — 70% of small business sites have this problem",
                       "fix": "Add clear CTA buttons at the top (hero section), after every service, and in the footer.",
                       "impact_key": "no_cta", "business_impact": get_impact(btype, "no_cta")})
    else:
        issues.append({"severity": "critical", "issue": "No call-to-action buttons found — visitors have no clear next step",
                       "fix": "Add prominent CTA buttons: 'Book Now', 'Get a Free Quote', 'Call Us'. This is the single highest-ROI change you can make.",
                       "impact_key": "no_cta", "business_impact": get_impact(btype, "no_cta")})

    # Clickable phone as CTA (max 20 pts)
    tel_links = soup.find_all("a", href=re.compile(r"^tel:"))
    if tel_links:
        score += 20; positives.append("Clickable phone link present")

    # Booking / online scheduling (max 30 pts)
    booking_keywords = ["book online", "schedule online", "book appointment", "online booking",
                        "calendly", "acuity", "booker", "mindbody", "fresha", "bookwell",
                        "reserve", "reservation", "pick a time", "choose a time"]
    html_str = str(soup).lower()
    has_booking = any(kw in html_str for kw in booking_keywords)
    if has_booking:
        score += 30; positives.append("Online booking / scheduling present")
    else:
        issues.append({"severity": "medium", "issue": "No online booking or scheduling system found",
                       "fix": "Integrate a free booking tool (Calendly, Fresha, or a simple form). Businesses with online booking convert 3x more website visitors.",
                       "impact_key": "no_booking", "business_impact": get_impact(btype, "no_booking")})

    return {"score": min(score, 100), "issues": issues, "positives": positives, "ctas_found": list(set(cta_found))[:5]}


def analyze_trust(soup: BeautifulSoup, btype: str) -> dict:
    issues, positives = [], []
    score = 0
    html_text = soup.get_text(" ", strip=True).lower()
    html_str = str(soup).lower()

    # Testimonials / reviews section (max 30 pts)
    review_keywords = ["testimonial", "review", "what our", "what clients", "what customers",
                       "5 star", "five star", "our clients say", "they say", "feedback",
                       "verified review", "happy customer", "satisfied", "recommend"]
    has_reviews = any(kw in html_text for kw in review_keywords)
    if has_reviews:
        score += 30; positives.append("Testimonials or reviews section found")
    else:
        issues.append({"severity": "critical", "issue": "No customer testimonials or reviews section",
                       "fix": "Add a dedicated testimonials section with 3–5 real customer quotes, names, and if possible, photos.",
                       "impact_key": "no_reviews", "business_impact": get_impact(btype, "no_reviews")})

    # Google review link / embed (max 25 pts)
    has_google_review = bool(re.search(r'google\.com/maps|maps\.google|g\.page|google.*review', html_str))
    if has_google_review:
        score += 25; positives.append("Google Reviews reference found")
    else:
        issues.append({"severity": "critical", "issue": "No Google Reviews link or widget — the most trusted review source is missing",
                       "fix": "Add a 'See Our Google Reviews' button linked to your Google Business Profile, or embed a Google Reviews widget.",
                       "impact_key": "no_google_reviews", "business_impact": get_impact(btype, "no_google_reviews")})

    # Trust badges / credentials (max 20 pts)
    badge_keywords = ["certified", "accredited", "member of", "award", "award-winning", "licensed",
                      "insured", "guarantee", "money back", "registered", "qualified", "years of experience",
                      "years experience", "abf", "hia", "master builder", "jcpa"]
    has_badges = any(kw in html_text for kw in badge_keywords)
    if has_badges:
        score += 20; positives.append("Trust badges or credentials present")
    else:
        issues.append({"severity": "medium", "issue": "No licences, certifications, or trust badges visible",
                       "fix": "Display any professional licences, industry memberships, awards, or satisfaction guarantees. Even '10 Years in Business' builds trust.",
                       "impact_key": "no_trust_badges", "business_impact": "Without credentials, customers have no way to verify your legitimacy. First-time visitors need reassurance before spending money."})

    # Social media presence (max 15 pts)
    social_pattern = re.compile(r'facebook\.com|instagram\.com|twitter\.com|linkedin\.com|youtube\.com|tiktok\.com')
    has_social = bool(social_pattern.search(html_str))
    if has_social:
        score += 15; positives.append("Social media links present")
    else:
        issues.append({"severity": "medium", "issue": "No social media links — isolated from your biggest free marketing channels",
                       "fix": "Add visible links to your active social profiles (Facebook, Instagram). Even having them listed signals that you're active and reachable.",
                       "impact_key": "no_social", "business_impact": get_impact(btype, "no_social")})

    # About / team page (max 10 pts)
    about_keywords = ["about us", "our team", "meet the team", "our story", "who we are", "about me", "founder", "owner"]
    has_about = any(kw in html_text for kw in about_keywords)
    if has_about:
        score += 10; positives.append("About/team information present")
    else:
        issues.append({"severity": "low", "issue": "No 'About Us' or team information found",
                       "fix": "Add a short About section with your story, your team, or why you started the business. People buy from people they feel they know.",
                       "impact_key": "no_about", "business_impact": "Local businesses that show the people behind them convert 40% better than anonymous business sites."})

    return {"score": min(score, 100), "issues": issues, "positives": positives}


def analyze_security(fetch_result: dict, soup: BeautifulSoup) -> dict:
    issues, positives = [], []
    score = 0

    # HTTPS (max 50 pts — non-negotiable in 2025)
    if fetch_result.get("is_https"):
        score += 50; positives.append("HTTPS / SSL enabled")
    else:
        issues.append({"severity": "critical",
                       "issue": "Site is NOT on HTTPS — browsers show 'Not Secure' to every visitor",
                       "fix": "Install an SSL certificate immediately. Free via Let's Encrypt, takes minutes. Without it, you're losing trust before customers read a word.",
                       "impact_key": "no_ssl",
                       "business_impact": "Chrome marks your site 'Not Secure' in the address bar. Studies show 85% of people will abandon a purchase if they see this warning. For any business collecting contact details, this is a conversion killer."})

    # Security headers (max 30 pts)
    headers = {k.lower(): v for k, v in fetch_result.get("headers", {}).items()}
    header_score = 0
    if "x-frame-options" in headers: header_score += 10
    if "x-content-type-options" in headers: header_score += 10
    if "strict-transport-security" in headers: header_score += 10
    score += header_score
    if header_score < 20:
        issues.append({"severity": "low", "issue": "Missing security response headers (X-Frame-Options, HSTS)",
                       "fix": "Configure your web server to send X-Frame-Options, X-Content-Type-Options, and Strict-Transport-Security headers.",
                       "impact_key": "no_security_headers", "business_impact": "Missing security headers leave your site vulnerable to clickjacking and data sniffing attacks. If a customer's data is compromised, the liability is yours."})

    # Login forms on HTTP (max 20 pts)
    has_form = bool(soup.find("form"))
    if has_form and fetch_result.get("is_https"):
        score += 20; positives.append("Forms served over HTTPS")
    elif has_form and not fetch_result.get("is_https"):
        issues.append({"severity": "critical", "issue": "Contact forms transmitting data over unencrypted HTTP",
                       "fix": "All forms MUST be on HTTPS. Customer data entered on HTTP forms can be intercepted by attackers.",
                       "impact_key": "form_on_http",
                       "business_impact": "Any name, phone, or message submitted through your contact form travels unencrypted. This is a GDPR/privacy liability and a customer trust disaster."})

    return {"score": min(score, 100), "issues": issues, "positives": positives,
            "is_https": fetch_result.get("is_https", False)}


def analyze_performance(fetch_result: dict, soup: BeautifulSoup) -> dict:
    issues, positives = [], []
    score = 0
    rt = fetch_result.get("response_time", 0)
    size = fetch_result.get("page_size_kb", 0)

    # Response time (max 40 pts)
    if rt < 0.8:
        score += 40; positives.append(f"Excellent response time ({rt}s)")
    elif rt < 1.5:
        score += 30; positives.append(f"Good response time ({rt}s)")
    elif rt < 2.5:
        score += 15
        issues.append({"severity": "medium", "issue": f"Page response time is {rt}s — above the 1.5s recommended threshold",
                       "fix": "Enable server-side caching, compress images to WebP format, and consider upgrading hosting.",
                       "impact_key": "slow_load", "business_impact": f"Research shows a 1-second delay reduces conversions by 7%. At {rt}s, you're already losing enquiries to faster competitors."})
    else:
        issues.append({"severity": "critical", "issue": f"Page is very slow — {rt}s response time (Google recommends under 1.5s)",
                       "fix": "This requires immediate attention: compress all images, enable CDN, upgrade hosting plan, and minify CSS/JS.",
                       "impact_key": "slow_load", "business_impact": get_impact("default", "slow_load") + f" At {rt} seconds, you're in the danger zone — 53% of mobile visitors have already left before your page finishes loading."})

    # Page size (max 20 pts)
    if size < 500:
        score += 20; positives.append(f"Lightweight page ({size}KB)")
    elif size < 1500:
        score += 12
    elif size < 3000:
        score += 5
        issues.append({"severity": "medium", "issue": f"Large page size ({size}KB) — slow to load on mobile data",
                       "fix": "Compress images (use WebP format), remove unused CSS/JS, lazy-load images below the fold.",
                       "impact_key": "large_page", "business_impact": "On a standard 4G connection, a 2MB page takes 4+ seconds to load. 73% of mobile users will abandon it."})
    else:
        issues.append({"severity": "critical", "issue": f"Very large page ({size}KB) — critically slow on mobile",
                       "fix": "Urgent: Remove unused scripts, compress all images, implement lazy loading. Target under 1MB total.",
                       "impact_key": "large_page", "business_impact": "A page this large will load in 6–10 seconds on mobile. You are losing the majority of mobile visitors before they see your business."})

    # Image optimization check (max 20 pts)
    imgs = soup.find_all("img")
    unoptimized = [i for i in imgs if i.get("src", "") and not any(ext in i.get("src", "").lower() for ext in [".webp", ".avif", ".svg"])]
    if not unoptimized or len(unoptimized) < 3:
        score += 20; positives.append("Images appear optimized")
    else:
        score += 8
        issues.append({"severity": "medium", "issue": f"{len(unoptimized)} images not in modern WebP/AVIF format",
                       "fix": "Convert all images to WebP format. WebP is 25–34% smaller than JPEG with the same quality, directly improving load speed.",
                       "impact_key": "unoptimized_images", "business_impact": "Unoptimized images are the #1 cause of slow websites. Fixing this alone can cut your load time by 40%."})

    # Caching headers (max 20 pts)
    cache_headers = fetch_result.get("headers", {})
    cache_control = cache_headers.get("cache-control", cache_headers.get("Cache-Control", ""))
    if "max-age" in cache_control or "public" in cache_control:
        score += 20; positives.append("Browser caching enabled")
    else:
        issues.append({"severity": "low", "issue": "Browser caching not configured",
                       "fix": "Add cache-control headers to your server config. Return visitors will load your site instantly instead of re-downloading everything.",
                       "impact_key": "no_cache", "business_impact": "Without caching, every page visit re-downloads all your images and scripts. Return visitors experience the same slow load as first-timers."})

    return {"score": min(score, 100), "issues": issues, "positives": positives,
            "response_time": rt, "page_size_kb": size}


def analyze_mobile(soup: BeautifulSoup, fetch_result: dict) -> dict:
    issues, positives = [], []
    score = 0

    # Viewport meta (max 40 pts — critical)
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport and "width=device-width" in viewport.get("content", ""):
        score += 40; positives.append("Proper viewport meta tag")
    elif viewport:
        score += 20
        issues.append({"severity": "medium", "issue": "Viewport tag present but may not be configured correctly",
                       "fix": "Use: <meta name='viewport' content='width=device-width, initial-scale=1'>",
                       "impact_key": "bad_viewport", "business_impact": "An improperly configured viewport causes pinch-zoom issues on mobile, frustrating 60%+ of your visitors."})
    else:
        issues.append({"severity": "critical", "issue": "Missing viewport meta tag — site displays as desktop on mobile phones",
                       "fix": "Add <meta name='viewport' content='width=device-width, initial-scale=1'> to your <head> immediately.",
                       "impact_key": "no_viewport", "business_impact": "Without a viewport tag, your site displays as a tiny desktop page on phones. 73% of mobile users will NOT return after a bad mobile experience."})

    # Font size check (max 20 pts)
    small_text = soup.find_all(style=re.compile(r'font-size:\s*([0-9]+)px'))
    too_small = [t for t in small_text if int(re.search(r'font-size:\s*([0-9]+)px', t.get("style","")).group(1)) < 12
                 if re.search(r'font-size:\s*([0-9]+)px', t.get("style",""))]
    if not too_small:
        score += 20; positives.append("Text sizes appear mobile-friendly")
    else:
        score += 5
        issues.append({"severity": "medium", "issue": f"{len(too_small)} elements with font size under 12px — too small to read on mobile",
                       "fix": "Set minimum font size to 14–16px for body text. Users should never need to pinch-zoom to read content.",
                       "impact_key": "small_text", "business_impact": "Unreadable text on mobile is an immediate bounce trigger. Google's mobile-first indexing also penalises this."})

    # Fixed-width elements (max 20 pts)
    fixed = soup.find_all(style=re.compile(r'width:\s*\d{4,}px'))
    if not fixed:
        score += 20; positives.append("No oversized fixed-width elements")
    else:
        score += 5
        issues.append({"severity": "medium", "issue": f"{len(fixed)} elements with fixed large pixel widths — causes horizontal scrolling on mobile",
                       "fix": "Replace fixed pixel widths with max-width or percentage values. Horizontal scrolling on mobile is a UX failure.",
                       "impact_key": "fixed_width", "business_impact": "Horizontal scrolling on mobile increases bounce rate by 60%+. It signals an unprofessional, broken site."})

    # Response time on mobile (max 20 pts)
    rt = fetch_result.get("response_time", 0)
    if rt < 2.0:
        score += 20; positives.append("Acceptable mobile load speed")
    else:
        issues.append({"severity": "medium" if rt < 3 else "critical",
                       "issue": f"Load time of {rt}s is unacceptable for mobile users",
                       "fix": "Mobile users are often on slower connections. Target under 2 seconds. Compress images, enable caching, use a CDN.",
                       "impact_key": "mobile_slow", "business_impact": "53% of mobile users abandon sites that take over 3 seconds to load. Mobile is where 60%+ of local searches happen."})

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
    print(f"[Audit] Fetching: {url}")
    fetch = fetch_page(url)
    if fetch.get("error"):
        return {"error": fetch["error"], "url": url}

    soup = BeautifulSoup(fetch["html"], "lxml")
    btype = detect_business_type(soup, url)
    print(f"[Audit] Business type detected: {btype}")

    seo      = analyze_seo(soup, url)
    contact  = analyze_contact(soup, btype)
    cta      = analyze_cta(soup, btype)
    trust    = analyze_trust(soup, btype)
    security = analyze_security(fetch, soup)
    perf     = analyze_performance(fetch, soup)
    mobile   = analyze_mobile(soup, fetch)
    psi      = get_psi_scores(fetch["final_url"])

    # Weighted overall — business-logic weights
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

    # Merge and sort all issues
    sev_order = {"critical": 0, "medium": 1, "low": 2}
    all_issues = []
    for cat, result in [("SEO", seo), ("Contact", contact), ("CTA & Conversion", cta),
                        ("Trust & Reviews", trust), ("Security", security),
                        ("Performance", perf), ("Mobile", mobile)]:
        for issue in result.get("issues", []):
            all_issues.append({**issue, "category": cat})
    all_issues.sort(key=lambda x: sev_order.get(x["severity"], 9))

    # Collect positives across all
    all_positives = []
    for result in [seo, contact, cta, trust, security, perf, mobile]:
        all_positives.extend(result.get("positives", []))

    domain = urlparse(fetch["final_url"]).netloc.replace("www.", "")
    biz_name = domain.split(".")[0].replace("-", " ").replace("_", " ").title()

    return {
        "url": fetch["final_url"], "domain": domain, "business_name": biz_name,
        "business_type": btype, "overall_score": overall,
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
        "customer_expectations": check_customer_expectations(soup, btype, html_text=fetch["html"]),
    }


# ─── CUSTOMER BEHAVIOR INTELLIGENCE ─────────────────────────────────────────
# What customers of each business type specifically look for before choosing.
# Each expectation includes: name, why it matters, a real % stat, and how to detect it.

CUSTOMER_EXPECTATIONS = {
    "salon": {
        "label": "Hair & Beauty Salon",
        "headline_stat": "78% of salon clients research a business online before ever stepping through the door.",
        "expectations": [
            {
                "name": "Photo gallery of work (before/after)",
                "why": "Clients choose their stylist based on seeing actual results — not words.",
                "stat": "67% of salon customers won't book without seeing real photo examples of past work.",
                "keywords": ["gallery", "portfolio", "before", "after", "our work", "transformations", "results"],
            },
            {
                "name": "Online booking system",
                "why": "Modern clients want to book a time that suits them — on their own schedule, not yours.",
                "stat": "62% of salon clients prefer online booking over calling. Miss this and you lose them to whoever has it.",
                "keywords": ["book online", "book now", "schedule", "fresha", "bookwell", "mindbody", "calendly", "online appointment"],
            },
            {
                "name": "Price list / service menu",
                "why": "Price anxiety is the #1 reason customers don't walk in or book. They need to know what to expect.",
                "stat": "54% of people will leave a salon website if they can't find pricing — and go straight to a competitor.",
                "keywords": ["price", "pricing", "from $", "from £", "cost", "rates", "packages", "services"],
            },
            {
                "name": "Opening hours clearly displayed",
                "why": "Walk-in clients decide in seconds whether to come in. No hours = missed walk-ins every day.",
                "stat": "41% of salon visits are same-day decisions — customers need to see your hours instantly.",
                "keywords": ["monday", "tuesday", "open", "hours", "9am", "10am", "closed", "trading hours"],
            },
            {
                "name": "Google Reviews or testimonials",
                "why": "For a salon, reviews are everything — customers are trusting you with their appearance.",
                "stat": "92% of new salon clients read reviews before their first visit. No reviews = no new clients.",
                "keywords": ["review", "testimonial", "star", "rated", "google", "trustpilot", "5 star"],
            },
        ],
    },
    "gym": {
        "label": "Gym / Martial Arts Studio",
        "headline_stat": "81% of gym-goers research studios online before visiting — and 63% won't join without seeing a class schedule.",
        "expectations": [
            {
                "name": "Free trial or intro offer",
                "why": "People won't commit money to a gym they've never tried. A free trial removes that barrier completely.",
                "stat": "Gyms with a visible free trial offer convert 3x more website visitors into paying members.",
                "keywords": ["free trial", "free class", "intro offer", "first class free", "try us", "introductory", "trial"],
            },
            {
                "name": "Class schedule / timetable",
                "why": "Before joining, every potential member checks: 'Are there classes that fit my life?'",
                "stat": "63% won't enquire without seeing a schedule — they assume it won't fit and move on.",
                "keywords": ["schedule", "timetable", "class times", "monday", "tuesday", "classes", "calendar"],
            },
            {
                "name": "Pricing / membership options",
                "why": "Gym pricing varies wildly. Hiding it creates anxiety and drives people to competitors who are transparent.",
                "stat": "71% of gym enquiries are about price. Not showing it means you answer the same question endlessly — or lose the lead.",
                "keywords": ["price", "pricing", "membership", "per month", "weekly", "rates", "plans", "$/week"],
            },
            {
                "name": "Photos or videos of the facility",
                "why": "People want to visualise themselves training there before driving across town to check it out.",
                "stat": "Gyms with facility photos get 45% more enquiries than those without.",
                "keywords": ["gallery", "our gym", "facility", "equipment", "mat", "ring", "studio", "floor"],
            },
            {
                "name": "Instructor / coach profiles",
                "why": "For martial arts especially, the coach is the product. Parents and adults choose the person, not just the gym.",
                "stat": "For martial arts studios, instructor credibility is the #1 trust factor for new member sign-ups.",
                "keywords": ["coach", "instructor", "trainer", "sensei", "professor", "belt", "credentials", "experience"],
            },
        ],
    },
    "restaurant": {
        "label": "Restaurant / Café",
        "headline_stat": "92% of diners look at a restaurant's website before choosing where to eat — and the menu is the first thing they look for.",
        "expectations": [
            {
                "name": "Full menu with prices",
                "why": "Customers decide where to eat based on the menu. No menu online = no visit.",
                "stat": "86% of diners abandon a restaurant website that has no menu. They choose somewhere else.",
                "keywords": ["menu", "starter", "main", "dessert", "pizza", "burger", "pasta", "soup", "price"],
            },
            {
                "name": "Online reservation or booking",
                "why": "Customers plan meals in advance and want to secure a table without picking up the phone.",
                "stat": "Restaurants with online booking get 40% more reservations than phone-only. OpenTable alone drives billions in revenue.",
                "keywords": ["reserve", "reservation", "book a table", "opentable", "resy", "book now"],
            },
            {
                "name": "Food photos",
                "why": "Food is a visual decision. Seeing a photo of a dish is the #1 factor that triggers a craving and a booking.",
                "stat": "Restaurants with professional food photography on their site see 30% higher reservation rates.",
                "keywords": ["gallery", "food", "photo", "dish", "cuisine"],
            },
            {
                "name": "Opening hours and address",
                "why": "'Are they open right now?' is the most common restaurant Google search. If your site doesn't answer instantly, they leave.",
                "stat": "43% of restaurant visitors bounce immediately if they can't find hours within 5 seconds.",
                "keywords": ["monday", "open", "hours", "closed", "lunch", "dinner", "address", "located"],
            },
        ],
    },
    "plumber": {
        "label": "Plumbing Business",
        "headline_stat": "In a plumbing emergency, 88% of customers call the first plumber whose website clearly shows availability and phone number.",
        "expectations": [
            {
                "name": "24/7 emergency availability",
                "why": "Plumbing emergencies don't follow business hours. If you offer emergency callouts and don't say so, you lose those jobs.",
                "stat": "Emergency plumbing jobs are worth 2-3x normal rates. Not advertising availability loses you your most profitable work.",
                "keywords": ["24/7", "emergency", "after hours", "anytime", "available", "urgent", "same day"],
            },
            {
                "name": "Service area clearly listed",
                "why": "Before calling, customers check: 'Do they cover my area?' No list = they assume you don't and call someone else.",
                "stat": "Plumbers who list their service suburbs get 58% more local calls than those who don't.",
                "keywords": ["service area", "we service", "areas we cover", "suburb", "locations", "nearby"],
            },
            {
                "name": "Free quote or upfront pricing",
                "why": "Plumbers have a reputation for surprise bills. Offering a free quote removes the #1 objection.",
                "stat": "Plumbers offering free quotes get 44% more enquiries from new customers than those without.",
                "keywords": ["free quote", "no call-out fee", "free estimate", "fixed price", "upfront"],
            },
            {
                "name": "Licence and insurance info",
                "why": "Homeowners are handing you access to their home and water system. They need proof you're legit.",
                "stat": "61% of homeowners won't hire a tradie who doesn't display licence/insurance information online.",
                "keywords": ["licence", "licensed", "insured", "insurance", "registered", "certified"],
            },
        ],
    },
    "dentist": {
        "label": "Dental Practice",
        "headline_stat": "77% of patients research a new dental practice online before booking — and trust signals are the deciding factor.",
        "expectations": [
            {
                "name": "Online appointment booking",
                "why": "Patients dread calling a dental office. Online booking removes that anxiety completely.",
                "stat": "Dental practices with online booking see 35% more new patient appointments from their website.",
                "keywords": ["book appointment", "book online", "schedule online", "calendly", "request appointment"],
            },
            {
                "name": "Insurance / health fund info",
                "why": "'Do they accept my insurance?' is the first question every new patient asks. If your site doesn't answer it, they call a competitor who does.",
                "stat": "55% of patients choose a dentist based on insurance compatibility. Not listing yours costs you half your potential patients.",
                "keywords": ["insurance", "health fund", "medibank", "bupa", "nib", "hcf", "gap", "bulk bill"],
            },
            {
                "name": "Before/after treatment photos",
                "why": "For cosmetic or orthodontic treatments, patients need visual proof that you deliver results.",
                "stat": "Dental practices showing before/after photos convert 2.4x more cosmetic treatment enquiries.",
                "keywords": ["before", "after", "results", "transformation", "case", "gallery"],
            },
            {
                "name": "New patient specials or offers",
                "why": "Dental anxiety is real. A new patient special (e.g., free checkup) removes the financial barrier to that first visit.",
                "stat": "Practices offering a new patient special see 28% more first-time appointments from web traffic.",
                "keywords": ["new patient", "first visit", "special offer", "free checkup", "gap-free", "no gap"],
            },
            {
                "name": "Dentist credentials and team page",
                "why": "Patients want to know who will be working in their mouth. A team page builds trust before the first appointment.",
                "stat": "Practices with visible dentist bios have 40% lower patient no-show rates — trust is built before arrival.",
                "keywords": ["dr.", "doctor", "dentist", "team", "meet", "qualifications", "experience", "about our"],
            },
        ],
    },
    "lawyer": {
        "label": "Law Firm",
        "headline_stat": "74% of legal clients research multiple firms online before making contact — and most choose based on specialisation clarity and trust signals.",
        "expectations": [
            {
                "name": "Practice areas clearly listed",
                "why": "Clients need to know immediately if you handle their specific legal issue. Vague firms get skipped.",
                "stat": "Law firms with clear practice area pages get 3x more targeted enquiries than generic 'we do everything' firms.",
                "keywords": ["practice area", "family law", "criminal", "personal injury", "conveyancing", "immigration", "employment", "wills"],
            },
            {
                "name": "Free consultation offer",
                "why": "Legal services are expensive and high-stakes. A free initial consultation removes the biggest barrier to enquiry.",
                "stat": "Law firms offering a free consultation get 52% more initial enquiries than those who don't.",
                "keywords": ["free consultation", "free advice", "no obligation", "initial consultation", "speak to us"],
            },
            {
                "name": "Lawyer profiles with credentials",
                "why": "Clients are choosing someone to represent their most critical life issues. They need to know who you are.",
                "stat": "68% of legal clients say lawyer credentials on the website were a deciding factor in choosing the firm.",
                "keywords": ["solicitor", "barrister", "attorney", "llb", "admitted", "qualified", "experience", "year"],
            },
        ],
    },
    "medical": {
        "label": "Medical / Health Clinic",
        "headline_stat": "80% of patients search online for a new doctor or clinic before booking — availability and trust are the top factors.",
        "expectations": [
            {
                "name": "Online appointment booking",
                "why": "Patients expect to book a GP appointment the same way they book a restaurant — online, instantly.",
                "stat": "Clinics with online booking see 45% more new patient appointments than phone-only practices.",
                "keywords": ["book appointment", "book online", "schedule", "healthengine", "hotdoc", "book now"],
            },
            {
                "name": "Bulk billing / fee information",
                "why": "Patients choose their clinic based on cost. Not listing your billing policy loses you patients before they call.",
                "stat": "57% of Australians choose a GP based on bulk billing availability. Not stating it costs you these patients.",
                "keywords": ["bulk bill", "bulk billing", "fee", "cost", "medicare", "gap payment"],
            },
            {
                "name": "Doctor profiles",
                "why": "Patients build a relationship with their doctor. Seeing who's available helps them choose and commit.",
                "stat": "Clinics with doctor profile pages have 35% lower patient dropout rates between first enquiry and first appointment.",
                "keywords": ["dr.", "doctor", "gp", "physician", "specialist", "team", "meet our"],
            },
        ],
    },
    "tradie": {
        "label": "Trade Business",
        "headline_stat": "73% of homeowners search Google to find a local tradie — and the winner is whoever has the most trustworthy online presence.",
        "expectations": [
            {
                "name": "Free quote offer",
                "why": "The biggest reason homeowners don't call a tradie is fear of being overcharged. A free quote removes that wall.",
                "stat": "Tradies offering a visible free quote get 44% more website enquiries than those without.",
                "keywords": ["free quote", "free estimate", "no call-out fee", "get a quote", "obligation free"],
            },
            {
                "name": "Licence and insurance display",
                "why": "Homeowners are trusting you with their biggest asset. Licence and insurance info is non-negotiable for their peace of mind.",
                "stat": "61% of homeowners won't hire a tradie who doesn't show licence or insurance details online.",
                "keywords": ["licence", "licensed", "insured", "insurance", "registered", "accredited"],
            },
            {
                "name": "Portfolio / past work photos",
                "why": "Before & after photos prove your quality better than any description. They remove doubt at the consideration stage.",
                "stat": "Tradies showing work photos get 51% more qualified enquiries — customers self-qualify based on seeing the standard of work.",
                "keywords": ["gallery", "our work", "portfolio", "project", "before", "after", "photos", "completed"],
            },
            {
                "name": "Response time / availability promise",
                "why": "For urgent jobs, speed matters. Advertising a response time ('Same-day quotes') wins emergency work.",
                "stat": "Tradies who advertise same-day response get 38% more emergency/urgent enquiries from their website.",
                "keywords": ["same day", "24 hour", "fast response", "quick", "prompt", "emergency", "available now"],
            },
        ],
    },
    "accountant": {
        "label": "Accounting Firm",
        "headline_stat": "69% of businesses choose their accountant based on online research — specialisation and trust are the deciding factors.",
        "expectations": [
            {
                "name": "Services and specialisations listed",
                "why": "Clients want an accountant who understands their specific situation — not a generalist.",
                "stat": "Accounting firms with specific service pages get 2.8x more targeted enquiries than generalist firms.",
                "keywords": ["tax return", "bas", "bookkeeping", "business tax", "self-employed", "smsf", "gst", "payroll"],
            },
            {
                "name": "Pricing or package information",
                "why": "Accounting fees vary enormously. Giving even a price range removes the biggest barrier to enquiry.",
                "stat": "Firms showing pricing get 46% more initial enquiries — clients hate not knowing what they'll pay.",
                "keywords": ["price", "pricing", "package", "from $", "fixed fee", "cost", "rates"],
            },
            {
                "name": "Team credentials and experience",
                "why": "Clients are entrusting you with their financial health. Seeing CPA, CA or experience years builds trust.",
                "stat": "68% of accounting clients say visible professional credentials on the website were a key trust factor.",
                "keywords": ["cpa", "ca", "chartered", "qualified", "cfa", "registered tax", "experience"],
            },
        ],
    },
    "retail": {
        "label": "Retail Store",
        "headline_stat": "76% of in-store shoppers research online before visiting — your website is the first impression, not the store.",
        "expectations": [
            {
                "name": "Product catalogue or shop online",
                "why": "Customers want to browse before committing to a trip. No products shown = no reason to visit.",
                "stat": "Retail stores with online catalogues drive 34% more foot traffic than stores without any online product display.",
                "keywords": ["shop", "products", "catalogue", "collection", "range", "buy", "add to cart", "store"],
            },
            {
                "name": "Store hours and location",
                "why": "Before making the trip, every customer checks: 'Are they open? Where exactly are they?'",
                "stat": "Missing store hours is the #1 reason retail websites lose foot traffic — 43% of shoppers check hours before visiting.",
                "keywords": ["monday", "open", "hours", "saturday", "located", "address", "find us", "parking"],
            },
            {
                "name": "New arrivals or featured products",
                "why": "Returning customers want to know what's new. Without it, your site feels stale and there's no reason to return.",
                "stat": "Retail sites that update product highlights monthly have 3x higher return visitor rates.",
                "keywords": ["new arrival", "new in", "featured", "trending", "season", "latest", "just arrived"],
            },
        ],
    },
    "real_estate": {
        "label": "Real Estate Agency",
        "headline_stat": "97% of property buyers and renters start their search online — your website is your most powerful sales tool.",
        "expectations": [
            {
                "name": "Property listings / search tool",
                "why": "Without searchable listings, property seekers have zero reason to use your site over Domain or REA.",
                "stat": "Agencies with direct listing search on their site retain 4x more repeat visitors than those without.",
                "keywords": ["listings", "properties", "for sale", "for rent", "search", "bedrooms", "price range"],
            },
            {
                "name": "Agent profiles",
                "why": "Sellers choose an agent, not just an agency. Profiles with track record and results win listings.",
                "stat": "Agencies with detailed agent profiles (including sales history) win 37% more appraisal requests.",
                "keywords": ["agent", "team", "sales", "expertise", "sold", "listed", "profile"],
            },
            {
                "name": "Free property appraisal offer",
                "why": "A free appraisal is the #1 lead magnet for real estate agencies. Without it, you're missing your primary acquisition tool.",
                "stat": "Agencies with a visible free appraisal CTA get 3.2x more vendor enquiries from their website.",
                "keywords": ["free appraisal", "property appraisal", "market appraisal", "estimate", "value"],
            },
        ],
    },
    "default": {
        "label": "Local Business",
        "headline_stat": "85% of consumers research a local business online before making contact — your website is your first impression.",
        "expectations": [
            {
                "name": "Clear contact information",
                "why": "Customers ready to buy need to reach you immediately. Hard-to-find contact info loses warm leads.",
                "stat": "46% of consumers lose trust in a business if they can't easily find contact information on their website.",
                "keywords": ["phone", "contact", "email", "address", "reach us"],
            },
            {
                "name": "Customer reviews or testimonials",
                "why": "Social proof is the #1 trust factor for new customers making a first purchase or enquiry.",
                "stat": "92% of consumers read reviews before choosing a local business. No reviews = choosing a competitor instead.",
                "keywords": ["review", "testimonial", "star", "rated", "customer", "client says"],
            },
            {
                "name": "Clear call-to-action",
                "why": "Visitors need to know exactly what to do next. Without a CTA, they leave having done nothing.",
                "stat": "70% of small business websites lack an effective call-to-action — this is the single biggest conversion leak.",
                "keywords": ["book", "call", "get quote", "enquire", "contact us", "get started", "buy now"],
            },
        ],
    },
}


def check_customer_expectations(soup: BeautifulSoup, btype: str, html_text: str = "") -> dict:
    """Check which customer expectations are met vs. missing for this business type."""
    expectations_data = CUSTOMER_EXPECTATIONS.get(btype, CUSTOMER_EXPECTATIONS["default"])
    page_text = soup.get_text(" ", strip=True).lower()
    page_html = str(soup).lower()
    full_text = (page_text + " " + page_html + " " + html_text.lower())[:200000]

    met = []
    missing = []

    for exp in expectations_data["expectations"]:
        found = any(kw.lower() in full_text for kw in exp["keywords"])
        entry = {
            "name": exp["name"],
            "why": exp["why"],
            "stat": exp["stat"],
        }
        if found:
            met.append(entry)
        else:
            missing.append(entry)

    return {
        "label": expectations_data["label"],
        "headline_stat": expectations_data["headline_stat"],
        "met": met,
        "missing": missing,
    }
