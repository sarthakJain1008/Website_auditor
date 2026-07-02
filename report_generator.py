"""
report_generator.py — Full redesign matching the Streamlit dark UI.
All HTML sections pre-built as variables to avoid f-string nesting issues.
"""
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
AGENCY = os.getenv("AGENCY_NAME", "Ryotech")

BTYPE_LABELS = {
    "gym": "Gym / Martial Arts Studio", "restaurant": "Restaurant / Café",
    "plumber": "Plumbing Business", "dentist": "Dental Practice",
    "salon": "Hair & Beauty Salon", "lawyer": "Law Firm",
    "real_estate": "Real Estate Agency", "medical": "Medical Clinic",
    "accountant": "Accounting Firm", "tradie": "Trade Business",
    "retail": "Retail Store", "default": "Local Business"
}


def _score_color(s):
    if s >= 75: return "#16a34a", "#dcfce7", "Good"
    if s >= 45: return "#d97706", "#fef3c7", "Needs Work"
    return "#dc2626", "#fee2e2", "Poor"


def _bar(s, color):
    w = min(s, 100)
    return (
        '<div style="height:5px;background:#e5e7eb;border-radius:3px;margin-top:10px">'
        '<div style="height:5px;background:' + color + ';border-radius:3px;width:' + str(w) + '%"></div>'
        '</div>'
    )


def _section(icon, title, inner_html):
    return (
        '<div style="padding:28px 48px;border-bottom:1px solid #f0f1f3">'
        '<div style="font-size:10px;font-weight:700;color:#9ca3af;text-transform:uppercase;'
        'letter-spacing:.12em;margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid #f3f4f6">'
        + icon + '&nbsp; ' + title +
        '</div>'
        + inner_html +
        '</div>'
    )


def _build_customer_expectations(cex, btype_label):
    if not cex:
        return ""

    missing_items = cex.get("missing", [])
    met_items     = cex.get("met", [])
    headline      = cex.get("headline_stat", "")
    cex_label     = cex.get("label", btype_label)

    html = (
        '<div style="background:linear-gradient(135deg,#1a0505 0%,#2d0a0a 100%);'
        'border:1px solid #dc2626;border-radius:12px;padding:20px 24px;margin-bottom:20px">'
        '<div style="font-size:10px;font-weight:700;color:#f87171;text-transform:uppercase;'
        'letter-spacing:.12em;margin-bottom:6px">&#128204; Research Insight</div>'
        '<div style="font-size:15px;font-weight:700;color:#fff;line-height:1.55">' + headline + '</div>'
        '<div style="font-size:12px;color:#fca5a5;margin-top:6px">We checked this site against what '
        + cex_label + ' customers specifically look for before choosing a business.</div>'
        '</div>'
    )

    if missing_items:
        count = len(missing_items)
        s_char = "s" if count > 1 else ""
        html += (
            '<div style="background:#fff1f2;border:1px solid #fecaca;border-radius:10px;'
            'padding:14px 18px;margin-bottom:16px">'
            '<div style="font-size:13px;font-weight:700;color:#dc2626;margin-bottom:4px">'
            '&#128680; ' + str(count) + ' Critical Customer Expectation' + s_char + ' Missing</div>'
            '<div style="font-size:12px;color:#991b1b">These are things ' + cex_label +
            ' customers specifically check before deciding. Each gap is costing this business '
            'real customers right now.</div>'
            '</div>'
        )
        for item in missing_items:
            html += (
                '<div style="background:linear-gradient(135deg,#fff1f2 0%,#fef2f2 100%);'
                'border:1px solid #fecaca;border-left:4px solid #dc2626;border-radius:8px;'
                'padding:14px 16px;margin-bottom:12px">'
                '<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">'
                '<span style="font-size:16px">&#10060;</span>'
                '<span style="font-size:14px;font-weight:700;color:#991b1b">' + item["name"] + '</span>'
                '<span style="background:#fee2e2;color:#dc2626;font-size:9px;font-weight:700;'
                'padding:2px 8px;border-radius:4px;text-transform:uppercase;letter-spacing:.06em">MISSING</span>'
                '</div>'
                '<div style="font-size:13px;color:#374151;margin-bottom:10px;line-height:1.5">'
                + item["why"] + '</div>'
                '<div style="background:#fff;border:1px solid #fecaca;border-radius:6px;'
                'padding:9px 13px;font-size:12.5px;color:#dc2626;font-weight:600;line-height:1.5">'
                '&#128201; <strong>The cost of this gap:</strong> ' + item["stat"] + '</div>'
                '</div>'
            )

    if met_items:
        html += (
            '<div style="font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;'
            'letter-spacing:.08em;margin:16px 0 10px">&#9989; Already Present on This Site</div>'
        )
        for item in met_items:
            html += (
                '<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;'
                'padding:10px 14px;margin-bottom:8px;display:flex;align-items:flex-start;gap:12px">'
                '<span style="font-size:15px;margin-top:1px">&#9989;</span>'
                '<div>'
                '<div style="font-size:13px;font-weight:600;color:#166534">' + item["name"] + '</div>'
                '<div style="font-size:11.5px;color:#4b7a62;margin-top:2px">' + item["why"] + '</div>'
                '</div>'
                '</div>'
            )

    return html


def _build_issues(issues):
    sev_map = {
        "critical": ("&#128308; Critical", "#fee2e2", "#dc2626", "#dc2626"),
        "medium":   ("&#128993; Medium",   "#fef3c7", "#d97706", "#d97706"),
        "low":      ("&#128309; Low",      "#dbeafe", "#2563eb", "#3b82f6"),
    }
    html = (
        '<div style="font-size:12px;color:#6b7280;margin-bottom:16px">Each issue includes the '
        '<strong>specific business impact</strong> — what it\'s costing in real terms.</div>'
    )
    for i in issues[:14]:
        sev = i["severity"]
        badge_text, badge_bg, badge_clr, border_clr = sev_map.get(sev, sev_map["low"])
        impact = i.get("business_impact", "")

        impact_html = ""
        if impact:
            impact_html = (
                '<div style="background:linear-gradient(135deg,#fff1f2 0%,#fff7ed 100%);'
                'border-left:4px solid #dc2626;border-radius:0 8px 8px 0;'
                'padding:11px 15px;margin-top:12px;box-shadow:0 1px 3px rgba(220,38,38,.1)">'
                '<div style="font-size:9px;font-weight:700;color:#dc2626;text-transform:uppercase;'
                'letter-spacing:.1em;margin-bottom:4px">&#9888;&#65039; Revenue Impact</div>'
                '<div style="font-size:13px;color:#7f1d1d;font-weight:600;line-height:1.55">'
                + impact + '</div>'
                '</div>'
            )

        html += (
            '<div style="border:1px solid #e5e7eb;border-left:4px solid ' + border_clr + ';'
            'border-radius:8px;padding:15px 17px;margin-bottom:12px;background:#fff">'
            '<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">'
            '<span style="background:' + badge_bg + ';color:' + badge_clr + ';font-size:9px;'
            'font-weight:700;padding:2px 9px;border-radius:4px;text-transform:uppercase;'
            'letter-spacing:.06em">' + badge_text + '</span>'
            '<span style="font-size:10px;color:#9ca3af;font-weight:700;text-transform:uppercase;'
            'letter-spacing:.06em">' + i.get("category", "") + '</span>'
            '</div>'
            '<div style="font-size:13.5px;font-weight:700;color:#111827;margin-bottom:5px">'
            + i["issue"] + '</div>'
            '<div style="font-size:12.5px;color:#6b7280"><strong style="color:#374151">Fix:</strong> '
            + i.get("fix", "") + '</div>'
            + impact_html +
            '</div>'
        )
    return html


def _build_score_cards(scores):
    labels = {
        "seo": "On-Page SEO", "contact": "Contact Info", "cta": "CTA & Conversion",
        "trust": "Trust & Reviews", "security": "Security / SSL",
        "performance": "Page Speed", "mobile": "Mobile"
    }
    cards = ""
    for key, lbl in labels.items():
        s = scores.get(key, 0)
        c, bg, l = _score_color(s)
        cards += (
            '<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;'
            'padding:16px 12px;text-align:center">'
            '<div style="font-size:11px;color:#6b7280;font-weight:500;margin-bottom:8px">' + lbl + '</div>'
            '<div style="font-size:28px;font-weight:700;color:' + c + '">' + str(s) + '</div>'
            '<div style="font-size:10px;color:' + c + ';font-weight:700;margin-top:2px;'
            'text-transform:uppercase;letter-spacing:.04em">' + l + '</div>'
            + _bar(s, c) +
            '</div>'
        )
    return '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">' + cards + '</div>'


def _build_contact_grid(contact):
    items = [
        (contact.get("phone_found"),   "Phone number visible"),
        (contact.get("tel_link"),      "Tap-to-call on mobile"),
        (contact.get("email_found"),   "Email address visible"),
        (contact.get("contact_form"),  "Contact form present"),
        (contact.get("address_found"), "Physical address listed"),
        (contact.get("google_maps"),   "Google Maps embedded"),
    ]
    html = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">'
    for ok, label in items:
        icon = "&#9989;" if ok else "&#10060;"
        bg   = "#f0fdf4" if ok else "#fff1f2"
        bdr  = "#bbf7d0" if ok else "#fecaca"
        clr  = "#166534" if ok else "#991b1b"
        html += (
            '<div style="background:' + bg + ';border:1px solid ' + bdr + ';border-radius:8px;'
            'padding:10px 13px;display:flex;align-items:center;gap:9px">'
            '<span style="font-size:14px">' + icon + '</span>'
            '<span style="font-size:12.5px;color:' + clr + ';font-weight:500">' + label + '</span>'
            '</div>'
        )
    html += '</div>'
    return html


def _build_positives(positives):
    if not positives:
        return '<div style="color:#9ca3af;font-size:13px">No major strengths detected.</div>'
    html = ""
    for p in positives[:20]:
        html += (
            '<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;'
            'padding:9px 13px;margin-bottom:8px;display:flex;align-items:center;gap:9px">'
            '<span style="font-size:14px">&#9989;</span>'
            '<span style="font-size:13px;color:#166534;font-weight:500">' + p + '</span>'
            '</div>'
        )
    return html


def _build_services_table(services, agency):
    sev_pill = {
        "critical": '<span style="background:#fee2e2;color:#dc2626;font-size:9px;font-weight:700;padding:2px 8px;border-radius:4px">&#128308; High Priority</span>',
        "medium":   '<span style="background:#fef3c7;color:#d97706;font-size:9px;font-weight:700;padding:2px 8px;border-radius:4px">&#128993; Medium</span>',
        "low":      '<span style="background:#dbeafe;color:#2563eb;font-size:9px;font-weight:700;padding:2px 8px;border-radius:4px">&#128309; Low</span>',
    }
    rows = ""
    for s in services:
        pill = sev_pill.get(s.get("severity", "low"), sev_pill["low"])
        rows += (
            '<tr>'
            '<td style="padding:12px 14px;border-bottom:1px solid #f3f4f6;vertical-align:top">'
            '<div style="font-weight:700;font-size:13px;color:#111827;margin-bottom:3px">' + s["service"] + '</div>'
            '<div style="font-size:12px;color:#6b7280">' + s["description"] + '</div>'
            '</td>'
            '<td style="padding:12px 14px;border-bottom:1px solid #f3f4f6;font-size:12px;'
            'color:#059669;font-style:italic;vertical-align:top">' + s["outcome"] + '</td>'
            '<td style="padding:12px 14px;border-bottom:1px solid #f3f4f6;vertical-align:top;'
            'white-space:nowrap">' + pill + '</td>'
            '</tr>'
        )
    return (
        '<table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;'
        'border-radius:8px;overflow:hidden;font-size:13px">'
        '<thead><tr style="background:#0f1117">'
        '<th style="text-align:left;padding:10px 14px;font-size:10px;font-weight:700;'
        'color:#9ca3af;text-transform:uppercase;letter-spacing:.08em">Service</th>'
        '<th style="text-align:left;padding:10px 14px;font-size:10px;font-weight:700;'
        'color:#9ca3af;text-transform:uppercase;letter-spacing:.08em">Expected Outcome</th>'
        '<th style="text-align:left;padding:10px 14px;font-size:10px;font-weight:700;'
        'color:#9ca3af;text-transform:uppercase;letter-spacing:.08em">Priority</th>'
        '</tr></thead>'
        '<tbody>' + rows + '</tbody>'
        '</table>'
    )


def _build_psi(psi):
    if not psi or not psi.get("available"):
        return ""
    scores_html = ""
    for k, lbl in [("performance", "Performance"), ("seo", "SEO"),
                   ("accessibility", "Accessibility"), ("best_practices", "Best Practices")]:
        if isinstance(psi.get(k), int):
            c, _, _ = _score_color(psi[k])
            scores_html += (
                '<div style="text-align:center;background:#fff;border-radius:8px;padding:12px 8px;'
                'border:1px solid #e5e7eb">'
                '<div style="font-size:24px;font-weight:700;color:' + c + '">' + str(psi[k]) + '</div>'
                '<div style="font-size:10px;color:#6b7280;margin-top:3px">' + lbl + '</div>'
                '</div>'
            )
    return (
        '<div style="margin-top:20px;background:#f0f9ff;border:1px solid #bae6fd;'
        'border-radius:10px;padding:16px 20px">'
        '<div style="font-size:10px;font-weight:700;color:#0369a1;text-transform:uppercase;'
        'letter-spacing:.1em;margin-bottom:12px">&#128309; Google PageSpeed Insights — Official Mobile Data</div>'
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px">'
        + scores_html + '</div>'
        '<div style="font-size:12px;color:#4b5563;display:flex;gap:20px;flex-wrap:wrap">'
        '<span>&#9201; LCP: <strong>' + str(psi.get("lcp", "N/A")) + '</strong></span>'
        '<span>&#128208; CLS: <strong>' + str(psi.get("cls", "N/A")) + '</strong></span>'
        '<span>&#127912; FCP: <strong>' + str(psi.get("fcp", "N/A")) + '</strong></span>'
        '</div></div>'
    )


def generate_report(audit: dict) -> str:
    date_str    = datetime.now().strftime("%-d %B %Y")
    overall     = audit["overall_score"]
    domain      = audit["domain"]
    biz         = audit["business_name"]
    url         = audit["url"]
    scores      = audit["scores"]
    issues      = audit["all_issues"]
    positives   = audit.get("all_positives", [])
    services    = audit.get("recommended_services", [])
    summary     = audit.get("ai_summary", "")
    email_text  = audit.get("outreach_email", "")
    contact     = audit.get("contact_details", {})
    cex         = audit.get("customer_expectations", {})
    btype       = audit.get("business_type", "default")
    btype_label = BTYPE_LABELS.get(btype, "Local Business")
    psi         = audit.get("psi", {})

    ov_color, ov_bg, ov_label = _score_color(overall)
    critical_n = len([i for i in issues if i["severity"] == "critical"])
    medium_n   = len([i for i in issues if i["severity"] == "medium"])
    https_ok   = audit.get("is_https", False)
    rt         = audit.get("response_time", "?")

    # Pre-build all sections
    summary_section = _section("🧠", "Executive Summary",
        '<div style="font-size:14px;color:#374151;line-height:1.85;background:#f9fafb;'
        'border-left:4px solid #0f1117;padding:16px 20px;border-radius:0 8px 8px 0">'
        + summary + '</div>'
    )

    cex_html = _build_customer_expectations(cex, btype_label)
    cex_section = _section("😱", btype_label + " Customer Intelligence — What Your Customers Look For", cex_html) if cex_html else ""

    score_cards = _build_score_cards(scores)
    psi_block   = _build_psi(psi)
    score_section = _section("📊", "Score Breakdown by Category", score_cards + psi_block)

    contact_section = _section("📞", "Contact & Lead Capture Health", _build_contact_grid(contact))

    issues_count  = len(issues[:14])
    issues_section = _section(
        "🚨", "Issues Found — " + str(issues_count) + " Items",
        _build_issues(issues)
    )

    positives_section = _section("✅", "What's Already Working", _build_positives(positives))

    services_section = _section(
        "🛠️", "How " + AGENCY + " Can Fix This — Services Matched to This Site",
        _build_services_table(services, AGENCY)
    )

    email_section = _section("✉️", "Suggested Outreach Email",
        '<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:22px 24px">'
        '<div style="font-size:10px;font-weight:700;color:#6b7280;text-transform:uppercase;'
        'letter-spacing:.08em;margin-bottom:12px">&#9993; Personalised for ' + biz + ' (' + btype_label + ')</div>'
        '<hr style="border:none;border-top:1px dashed #e5e7eb;margin-bottom:14px">'
        '<div style="font-size:13.5px;color:#374151;line-height:1.85;white-space:pre-line">'
        + email_text + '</div>'
        '</div>'
    )

    # HTTPS badge
    https_color = "#16a34a" if https_ok else "#dc2626"
    https_bg    = "#f0fdf4" if https_ok else "#fee2e2"
    https_text  = "&#10003; HTTPS" if https_ok else "&#10007; No SSL"


def generate_report(audit: dict) -> str:
    date_str    = datetime.now().strftime("%-d %B %Y")
    overall     = audit["overall_score"]
    domain      = audit["domain"]
    biz         = audit["business_name"]
    url         = audit["url"]
    scores      = audit["scores"]
    issues      = audit["all_issues"]
    positives   = audit.get("all_positives", [])
    services    = audit.get("recommended_services", [])
    summary     = audit.get("ai_summary", "")
    email_text  = audit.get("outreach_email", "")
    contact     = audit.get("contact_details", {})
    cex         = audit.get("customer_expectations", {})
    btype       = audit.get("business_type", "default")
    btype_label = BTYPE_LABELS.get(btype, "Local Business")
    psi         = audit.get("psi", {})

    ov_color, _, ov_label = _score_color(overall)
    critical_n = len([i for i in issues if i["severity"] == "critical"])
    medium_n   = len([i for i in issues if i["severity"] == "medium"])
    https_ok   = audit.get("is_https", False)
    rt         = str(audit.get("response_time", "?"))

    https_color = "#16a34a" if https_ok else "#dc2626"
    https_bg    = "#f0fdf4" if https_ok else "#fee2e2"
    https_text  = "&#10003; HTTPS" if https_ok else "&#10007; No SSL"

    # Build all inner HTML
    summary_inner = (
        '<div style="font-size:14px;color:#374151;line-height:1.85;background:#f9fafb;' +
        'border-left:4px solid #0f1117;padding:16px 20px;border-radius:0 8px 8px 0">' +
        summary + '</div>'
    )
    cex_inner       = _build_customer_expectations(cex, btype_label)
    score_inner     = _build_score_cards(scores) + _build_psi(psi)
    contact_inner   = _build_contact_grid(contact)
    issues_inner    = _build_issues(issues)
    positives_inner = _build_positives(positives)
    services_inner  = _build_services_table(services, AGENCY)


    cex_sec = _section("&#128565;", btype_label + " Customer Intelligence — What Your Customers Look For", cex_inner) if cex_inner else ""

    parts = []
    parts.append("<!DOCTYPE html><html lang=\'en\'><head>")
    parts.append("<meta charset=\'UTF-8\'><meta name=\'viewport\' content=\'width=device-width,initial-scale=1\'>")
    parts.append("<title>Audit — " + biz + " | " + AGENCY + "</title>")
    parts.append("<style>")
    parts.append("@import url(\'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap\');")
    parts.append("*{margin:0;padding:0;box-sizing:border-box}")
    parts.append("body{font-family:\'Inter\',-apple-system,sans-serif;background:#f3f4f6;color:#1a1d23;font-size:14px;line-height:1.6}")
    parts.append(".page{max-width:960px;margin:0 auto;background:#fff;box-shadow:0 1px 6px rgba(0,0,0,.1)}")
    parts.append("*{-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;color-adjust:exact !important}")
    parts.append("@media print{body{background:#fff}.page{box-shadow:none;max-width:100%}}")
    parts.append("</style></head><body><div class=\'page\'>")

    # Header
    parts.append("<div style=\'background:linear-gradient(135deg,#0f1117 0%,#1a2035 100%);padding:36px 48px 28px\'>")
    parts.append("<div style=\'display:flex;justify-content:space-between;align-items:center;margin-bottom:22px\'>")
    parts.append("<span style=\'font-size:11px;font-weight:700;color:#6b7280;letter-spacing:.12em;text-transform:uppercase\'>" + AGENCY + " — AI Website Audit Report</span>")
    parts.append("<span style=\'font-size:11px;color:#6b7280\'>" + date_str + "</span></div>")
    parts.append("<div style=\'display:flex;align-items:center;gap:14px;margin-bottom:6px\'>")
    parts.append("<h1 style=\'font-size:26px;font-weight:800;color:#fff;letter-spacing:-.02em\'>" + biz + "</h1>")
    parts.append("<span style=\'background:#1e2433;color:#9ca3af;font-size:10px;font-weight:700;padding:4px 11px;border-radius:4px;text-transform:uppercase;letter-spacing:.06em\'>" + btype_label + "</span></div>")
    parts.append("<div style=\'font-size:13px;color:#9ca3af\'>" + url + "</div></div>")

    # Score banner
    parts.append("<div style=\'background:#f9fafb;border-bottom:1px solid #e5e7eb;padding:28px 48px;display:flex;align-items:flex-start;gap:36px\'>")
    parts.append("<div style=\'flex-shrink:0;text-align:center\'>")
    parts.append("<div style=\'width:120px;height:120px;border-radius:50%;border:7px solid " + ov_color + ";display:flex;flex-direction:column;align-items:center;justify-content:center;margin:0 auto\'>")
    parts.append("<span style=\'font-size:40px;font-weight:800;color:" + ov_color + ";line-height:1\'>" + str(overall) + "</span>")
    parts.append("<span style=\'font-size:11px;color:#9ca3af\'>/100</span></div>")
    parts.append("<div style=\'font-size:11px;font-weight:700;color:" + ov_color + ";text-transform:uppercase;letter-spacing:.06em;margin-top:8px\'>" + ov_label + "</div>")
    parts.append("<div style=\'font-size:10px;color:#9ca3af;margin-top:3px\'>" + btype_label + "</div></div>")
    parts.append("<div style=\'flex:1\'><div style=\'display:grid;grid-template-columns:repeat(4,1fr);gap:12px\'>")
    parts.append("<div style=\'text-align:center;background:#fee2e2;border-radius:8px;padding:12px 8px\'><div style=\'font-size:26px;font-weight:700;color:#dc2626\'>" + str(critical_n) + "</div><div style=\'font-size:9px;color:#dc2626;font-weight:700;text-transform:uppercase\'>Critical</div></div>")
    parts.append("<div style=\'text-align:center;background:#fef3c7;border-radius:8px;padding:12px 8px\'><div style=\'font-size:26px;font-weight:700;color:#d97706\'>" + str(medium_n) + "</div><div style=\'font-size:9px;color:#d97706;font-weight:700;text-transform:uppercase\'>Medium</div></div>")
    parts.append("<div style=\'text-align:center;background:" + https_bg + ";border-radius:8px;padding:12px 8px\'><div style=\'font-size:18px;font-weight:700;color:" + https_color + "\'>" + https_text + "</div><div style=\'font-size:9px;color:" + https_color + ";font-weight:700;text-transform:uppercase\'>Security</div></div>")
    parts.append("<div style=\'text-align:center;background:#f0f9ff;border-radius:8px;padding:12px 8px\'><div style=\'font-size:22px;font-weight:700;color:#0369a1\'>" + rt + "s</div><div style=\'font-size:9px;color:#0369a1;font-weight:700;text-transform:uppercase\'>Load Time</div></div>")
    parts.append("</div></div></div>")

    # Content sections
    parts.append(_section("&#129504;", "Executive Summary", summary_inner))
    parts.append(cex_sec)
    parts.append(_section("&#128202;", "Score Breakdown by Category", score_inner))
    parts.append(_section("&#128222;", "Contact &amp; Lead Capture Health", contact_inner))
    parts.append(_section("&#128680;", "Issues Found &#8212; " + str(len(issues[:14])) + " Items", issues_inner))
    parts.append(_section("&#9989;", "What&#39;s Already Working", positives_inner))
    parts.append(_section("&#128736;", "How " + AGENCY + " Can Fix This", services_inner))

    # Footer
    parts.append("<div style=\'background:#0f1117;padding:18px 48px;display:flex;justify-content:space-between;align-items:center\'>")
    parts.append("<span style=\'font-size:11px;color:#6b7280\'>Prepared by <strong style=\'color:#9ca3af\'>" + AGENCY + "</strong> &nbsp;&middot;&nbsp; " + date_str + "</span>")
    parts.append("<span style=\'font-size:11px;color:#6b7280\'>" + domain + " &nbsp;&middot;&nbsp; Confidential</span></div>")
    parts.append("</div></body></html>")

    return "".join(parts).replace("\'", "'")


def save_report(audit: dict, output_dir: str = "reports") -> str:
    os.makedirs(output_dir, exist_ok=True)
    domain   = audit["domain"].replace(".", "_").replace("/", "")
    filename = output_dir + "/" + domain + "_audit.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(generate_report(audit))
    return filename
