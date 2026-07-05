"""
report_generator.py — Clean, client-facing HTML audit report.

Design goals (Workstream B):
  - Tidy, consistent, professional layout (one accent colour, restrained palette,
    consistent spacing/borders, no clashing gradients).
  - EVIDENCE everywhere: each issue shows exactly what the tool found, plus a
    dedicated "What We Detected" facts section.
  - All dynamic text is HTML-escaped so a title/CTA containing < > & can't break
    the layout.
"""
import os
import html as _html
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
    "retail": "Retail Store", "default": "Local Business",
}

# ── Palette ──
INK = "#0f172a"; SLATE = "#475569"; MUTE = "#94a3b8"; LINE = "#e5e7eb"; SOFT = "#f8fafc"
ACCENT = "#1d4ed8"
SEV = {  # label, text colour, soft bg
    "critical": ("Critical", "#dc2626", "#fef2f2", "#fecaca"),
    "medium":   ("Medium",   "#b45309", "#fffbeb", "#fde68a"),
    "low":      ("Low",      "#1d4ed8", "#eff6ff", "#bfdbfe"),
}


def _esc(s) -> str:
    return _html.escape(str(s if s is not None else ""))


def _score_color(s):
    if s >= 75: return "#16a34a", "#dcfce7", "Good"
    if s >= 45: return "#d97706", "#fef3c7", "Needs Work"
    return "#dc2626", "#fee2e2", "Poor"


def _bar(s, color):
    w = min(max(s, 0), 100)
    return (f'<div style="height:5px;background:#eef2f6;border-radius:3px;margin-top:10px">'
            f'<div style="height:5px;background:{color};border-radius:3px;width:{w}%"></div></div>')


def _section(title, inner, sub=""):
    sub_html = (f'<div style="font-size:12.5px;color:{SLATE};margin:-8px 0 16px 16px">{_esc(sub)}</div>'
                if sub else "")
    return (
        f'<section style="padding:26px 44px;border-top:1px solid #eef2f6">'
        f'<div style="display:flex;align-items:center;gap:9px;margin-bottom:14px">'
        f'<span style="width:6px;height:6px;background:{ACCENT};border-radius:50%;display:inline-block"></span>'
        f'<h2 style="font-size:15px;font-weight:700;color:{INK};letter-spacing:-.01em;margin:0">{_esc(title)}</h2>'
        f'</div>{sub_html}{inner}</section>'
    )


# ─── EVIDENCE: "What We Detected" facts grid ─────────────────────────────────

def _fact_card(label, value):
    has = bool(value)
    val = _esc(value) if has else "&mdash;"
    vcolor = INK if has else MUTE
    return (
        f'<div style="border:1px solid {LINE};border-radius:8px;padding:11px 14px;background:#fff">'
        f'<div style="font-size:9.5px;font-weight:700;color:{MUTE};letter-spacing:.09em;'
        f'text-transform:uppercase;margin-bottom:5px">{_esc(label)}</div>'
        f'<div style="font-size:12.5px;color:{vcolor};word-break:break-word;line-height:1.5">{val}</div></div>'
    )


def _build_detected(detected):
    if not detected:
        return ""
    phone = detected.get("phone_number", "")
    if phone:
        phone += " · tap-to-call" if detected.get("tel_link") else " · not a tel: link"
    ctas = ", ".join(f'"{c}"' for c in detected.get("ctas_found", [])[:5])
    social = ", ".join(detected.get("social_platforms", []))
    reviews = ", ".join(detected.get("review_sources", []))
    miss = detected.get("images_missing_alt", [])
    total_img = detected.get("total_images", 0)
    imgs = (f"{len(miss)} of {total_img} missing alt — " + ", ".join(miss[:5])) if miss else (
        f"All {total_img} images have alt text" if total_img else "")
    facts = [
        ("Title tag", detected.get("title", "")),
        ("Phone number", phone),
        ("Email address", detected.get("email_address", "")),
        ("CTAs detected", ctas),
        ("Social profiles", social),
        ("Review sources", reviews),
        ("Images missing alt", imgs),
        ("Meta description", detected.get("meta_description", "")),
    ]
    cards = "".join(_fact_card(l, v) for l, v in facts)
    return f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">{cards}</div>'


# ─── ISSUES (with evidence) ──────────────────────────────────────────────────

def _build_issues(issues):
    html = (f'<div style="font-size:12.5px;color:{SLATE};margin-bottom:16px">'
            f'Each issue shows <strong>what the tool found</strong>, how to fix it, and the business impact.</div>')
    for i in issues[:14]:
        label, clr, bg, bd = SEV.get(i["severity"], SEV["low"])
        evidence = i.get("evidence", "")
        impact = i.get("business_impact", "")

        ev_html = ""
        if evidence:
            ev_html = (
                f'<div style="margin-top:10px;background:{SOFT};border:1px solid {LINE};'
                f'border-left:3px solid {ACCENT};border-radius:0 6px 6px 0;padding:9px 13px">'
                f'<div style="font-size:9px;font-weight:700;color:{ACCENT};letter-spacing:.09em;'
                f'text-transform:uppercase;margin-bottom:3px">What the tool found</div>'
                f'<div style="font-size:12px;color:{INK};line-height:1.5;word-break:break-word">{_esc(evidence)}</div></div>'
            )
        impact_html = ""
        if impact:
            impact_html = (
                f'<div style="margin-top:8px;background:#fef2f2;border-left:3px solid #dc2626;'
                f'border-radius:0 6px 6px 0;padding:9px 13px">'
                f'<div style="font-size:9px;font-weight:700;color:#dc2626;letter-spacing:.09em;'
                f'text-transform:uppercase;margin-bottom:3px">Business impact</div>'
                f'<div style="font-size:12px;color:#7f1d1d;line-height:1.5">{_esc(impact)}</div></div>'
            )
        html += (
            f'<div style="border:1px solid {LINE};border-left:4px solid {clr};border-radius:8px;'
            f'padding:14px 16px;margin-bottom:11px;background:#fff">'
            f'<div style="display:flex;align-items:center;gap:9px;margin-bottom:7px">'
            f'<span style="background:{bg};color:{clr};border:1px solid {bd};font-size:9px;font-weight:700;'
            f'padding:2px 8px;border-radius:4px;text-transform:uppercase;letter-spacing:.05em">{label}</span>'
            f'<span style="font-size:10px;color:{MUTE};font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.05em">{_esc(i.get("category", ""))}</span></div>'
            f'<div style="font-size:13.5px;font-weight:700;color:{INK};margin-bottom:6px">{_esc(i["issue"])}</div>'
            f'<div style="font-size:12.5px;color:{SLATE};line-height:1.55">'
            f'<strong style="color:{INK}">Fix:</strong> {_esc(i.get("fix", ""))}</div>'
            f'{ev_html}{impact_html}</div>'
        )
    return html


def _build_score_cards(scores):
    labels = {"seo": "On-Page SEO", "contact": "Contact Info", "cta": "CTA & Conversion",
              "trust": "Trust & Reviews", "security": "Security / SSL",
              "performance": "Page Speed", "mobile": "Mobile"}
    cards = ""
    for key, lbl in labels.items():
        s = scores.get(key, 0)
        c, _, l = _score_color(s)
        cards += (
            f'<div style="background:#fff;border:1px solid {LINE};border-radius:8px;padding:14px 12px">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline">'
            f'<span style="font-size:11.5px;color:{SLATE};font-weight:500">{lbl}</span>'
            f'<span style="font-size:18px;font-weight:800;color:{c}">{s}</span></div>'
            f'{_bar(s, c)}</div>'
        )
    return f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">{cards}</div>'


def _build_contact_grid(contact, detected):
    phone = detected.get("phone_number", "")
    email = detected.get("email_address", "")
    items = [
        (contact.get("phone_found"),   "Phone number visible", phone),
        (contact.get("tel_link"),      "Tap-to-call (tel: link)", ""),
        (contact.get("email_found"),   "Email address visible", email),
        (contact.get("contact_form"),  "Contact / enquiry form", ""),
        (contact.get("address_found"), "Physical address listed", ""),
        (contact.get("google_maps"),   "Google Maps embedded", ""),
    ]
    html = '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:9px">'
    for ok, label, val in items:
        icon = "&#10003;" if ok else "&#10007;"
        bg   = "#f0fdf4" if ok else "#fef2f2"
        bdr  = "#bbf7d0" if ok else "#fecaca"
        clr  = "#166534" if ok else "#b91c1c"
        val_html = (f'<div style="font-size:10.5px;color:{SLATE};margin-top:2px;word-break:break-word">{_esc(val)}</div>'
                    if (ok and val) else "")
        html += (
            f'<div style="background:{bg};border:1px solid {bdr};border-radius:8px;padding:10px 12px">'
            f'<div style="display:flex;align-items:center;gap:8px">'
            f'<span style="font-size:13px;color:{clr};font-weight:700">{icon}</span>'
            f'<span style="font-size:12px;color:{INK};font-weight:600">{_esc(label)}</span></div>'
            f'{val_html}</div>'
        )
    return html + "</div>"


def _build_positives(positives):
    if not positives:
        return f'<div style="color:{MUTE};font-size:13px">No major strengths detected.</div>'
    chips = "".join(
        f'<span style="display:inline-block;background:#f0fdf4;border:1px solid #bbf7d0;color:#166534;'
        f'font-size:12px;font-weight:500;padding:5px 11px;border-radius:20px;margin:0 6px 8px 0">'
        f'&#10003; {_esc(p)}</span>'
        for p in positives[:20]
    )
    return f'<div>{chips}</div>'


def _build_services_table(services):
    rows = ""
    for s in services:
        label, clr, bg, bd = SEV.get(s.get("severity", "low"), SEV["low"])
        pill = (f'<span style="background:{bg};color:{clr};border:1px solid {bd};font-size:9px;font-weight:700;'
                f'padding:2px 8px;border-radius:4px;text-transform:uppercase">{label}</span>')
        rows += (
            f'<tr>'
            f'<td style="padding:12px 14px;border-bottom:1px solid #f1f5f9;vertical-align:top">'
            f'<div style="font-weight:700;font-size:13px;color:{INK};margin-bottom:3px">{_esc(s["service"])}</div>'
            f'<div style="font-size:12px;color:{SLATE};line-height:1.5">{_esc(s["description"])}</div></td>'
            f'<td style="padding:12px 14px;border-bottom:1px solid #f1f5f9;font-size:12px;'
            f'color:#059669;vertical-align:top;line-height:1.5">{_esc(s["outcome"])}</td>'
            f'<td style="padding:12px 14px;border-bottom:1px solid #f1f5f9;vertical-align:top;'
            f'white-space:nowrap">{pill}</td></tr>'
        )
    head = (f'<th style="text-align:left;padding:10px 14px;font-size:9.5px;font-weight:700;color:{MUTE};'
            f'text-transform:uppercase;letter-spacing:.07em">')
    return (
        f'<table style="width:100%;border-collapse:collapse;border:1px solid {LINE};border-radius:8px;'
        f'overflow:hidden;font-size:13px">'
        f'<thead><tr style="background:{SOFT}">{head}Service</th>{head}Expected Outcome</th>{head}Priority</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )


def _build_customer_expectations(cex, btype_label):
    if not cex:
        return ""
    missing = cex.get("missing", [])
    met = cex.get("met", [])
    headline = cex.get("headline_stat", "")
    label = cex.get("label", btype_label)

    html = (
        f'<div style="background:{SOFT};border:1px solid {LINE};border-left:3px solid {ACCENT};'
        f'border-radius:0 8px 8px 0;padding:14px 18px;margin-bottom:18px">'
        f'<div style="font-size:9px;font-weight:700;color:{ACCENT};letter-spacing:.1em;'
        f'text-transform:uppercase;margin-bottom:6px">Research insight</div>'
        f'<div style="font-size:14px;font-weight:600;color:{INK};line-height:1.5">{_esc(headline)}</div>'
        f'<div style="font-size:12px;color:{SLATE};margin-top:6px">Checked against what '
        f'{_esc(label)} customers look for before choosing a business.</div></div>'
    )
    if missing:
        html += (f'<div style="font-size:10px;font-weight:700;color:#dc2626;letter-spacing:.08em;'
                 f'text-transform:uppercase;margin-bottom:10px">{len(missing)} expectation'
                 f'{"s" if len(missing) != 1 else ""} missing</div>')
        for it in missing:
            html += (
                f'<div style="background:#fef2f2;border:1px solid #fecaca;border-left:3px solid #dc2626;'
                f'border-radius:0 6px 6px 0;padding:12px 15px;margin-bottom:10px">'
                f'<div style="font-size:13px;font-weight:700;color:#991b1b;margin-bottom:5px">'
                f'&#10007; {_esc(it["name"])}</div>'
                f'<div style="font-size:12.5px;color:{SLATE};line-height:1.5;margin-bottom:6px">{_esc(it["why"])}</div>'
                f'<div style="font-size:11.5px;color:#dc2626;font-weight:600">{_esc(it["stat"])}</div></div>'
            )
    if met:
        html += (f'<div style="font-size:10px;font-weight:700;color:#166534;letter-spacing:.08em;'
                 f'text-transform:uppercase;margin:16px 0 10px">Already present</div>')
        for it in met:
            html += (
                f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;'
                f'padding:10px 14px;margin-bottom:8px">'
                f'<div style="font-size:12.5px;font-weight:600;color:#166534">&#10003; {_esc(it["name"])}</div>'
                f'<div style="font-size:11.5px;color:#4b7a62;margin-top:2px">{_esc(it["why"])}</div></div>'
            )
    return html


def _build_psi(psi):
    if not psi or not psi.get("available"):
        return ""
    cells = ""
    for k, lbl in [("performance", "Performance"), ("seo", "SEO"),
                   ("accessibility", "Accessibility"), ("best_practices", "Best Practices")]:
        if isinstance(psi.get(k), int):
            c, _, _ = _score_color(psi[k])
            cells += (f'<div style="text-align:center;background:#fff;border:1px solid {LINE};'
                      f'border-radius:8px;padding:12px 8px">'
                      f'<div style="font-size:22px;font-weight:800;color:{c}">{psi[k]}</div>'
                      f'<div style="font-size:10px;color:{SLATE};margin-top:3px">{lbl}</div></div>')
    return (
        f'<div style="margin-top:16px;background:{SOFT};border:1px solid {LINE};border-radius:8px;padding:16px 18px">'
        f'<div style="font-size:9.5px;font-weight:700;color:{ACCENT};text-transform:uppercase;'
        f'letter-spacing:.09em;margin-bottom:12px">Google PageSpeed Insights — official mobile data</div>'
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px">{cells}</div>'
        f'<div style="font-size:12px;color:{SLATE};display:flex;gap:22px;flex-wrap:wrap">'
        f'<span>LCP: <strong>{_esc(psi.get("lcp", "N/A"))}</strong></span>'
        f'<span>CLS: <strong>{_esc(psi.get("cls", "N/A"))}</strong></span>'
        f'<span>FCP: <strong>{_esc(psi.get("fcp", "N/A"))}</strong></span></div></div>'
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
    detected    = audit.get("detected", {})
    cex         = audit.get("customer_expectations", {})
    btype       = audit.get("business_type", "default")
    btype_label = BTYPE_LABELS.get(btype) or (btype.title() if btype and btype != "default" else "Local Business")
    psi         = audit.get("psi", {})

    ov_color, _, ov_label = _score_color(overall)
    critical_n = len([i for i in issues if i["severity"] == "critical"])
    medium_n   = len([i for i in issues if i["severity"] == "medium"])
    https_ok   = audit.get("is_https", False)
    rt         = _esc(audit.get("response_time", "?"))

    https_color = "#16a34a" if https_ok else "#dc2626"
    https_bg    = "#f0fdf4" if https_ok else "#fef2f2"
    https_text  = "&#10003; HTTPS" if https_ok else "&#10007; No SSL"

    summary_inner = (f'<div style="font-size:13.5px;color:{SLATE};line-height:1.8;background:{SOFT};'
                     f'border:1px solid {LINE};border-left:3px solid {INK};border-radius:0 8px 8px 0;'
                     f'padding:16px 20px">{_esc(summary).replace(chr(10), "<br>")}</div>')
    email_inner = (f'<div style="background:{SOFT};border:1px solid {LINE};border-radius:8px;padding:18px 20px">'
                   f'<div style="font-size:9.5px;font-weight:700;color:{MUTE};text-transform:uppercase;'
                   f'letter-spacing:.08em;margin-bottom:10px">Personalised for {_esc(biz)} · {_esc(btype_label)}</div>'
                   f'<div style="font-size:13px;color:{INK};line-height:1.75;white-space:pre-wrap">'
                   f'{_esc(email_text)}</div></div>')

    def stat(bg, color, big, small):
        return (f'<div style="text-align:center;background:{bg};border-radius:8px;padding:13px 8px">'
                f'<div style="font-size:22px;font-weight:800;color:{color};line-height:1">{big}</div>'
                f'<div style="font-size:9px;color:{color};font-weight:700;text-transform:uppercase;'
                f'letter-spacing:.05em;margin-top:5px">{small}</div></div>')

    p = []
    p.append("<!DOCTYPE html><html lang='en'><head>")
    p.append("<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>")
    p.append(f"<title>Website Audit — {_esc(biz)} | {_esc(AGENCY)}</title>")
    p.append("<style>")
    p.append("@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');")
    p.append("*{margin:0;padding:0;box-sizing:border-box}")
    p.append(f"body{{font-family:'Inter',-apple-system,sans-serif;background:#eef2f6;color:{INK};font-size:14px;line-height:1.6}}")
    p.append(".page{max-width:900px;margin:0 auto;background:#fff}")
    p.append("*{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}")
    p.append("@media print{body{background:#fff}.page{max-width:100%}}")
    p.append("</style></head><body><div class='page'>")

    # Header
    p.append(f"<div style='background:{INK};padding:32px 44px 26px'>")
    p.append("<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:20px'>")
    p.append(f"<span style='font-size:11px;font-weight:700;color:{MUTE};letter-spacing:.14em;text-transform:uppercase'>{_esc(AGENCY)} · Website Audit</span>")
    p.append(f"<span style='font-size:11px;color:{MUTE}'>{date_str}</span></div>")
    p.append("<div style='display:flex;align-items:center;gap:12px;margin-bottom:6px;flex-wrap:wrap'>")
    p.append(f"<h1 style='font-size:25px;font-weight:800;color:#fff;letter-spacing:-.02em'>{_esc(biz)}</h1>")
    p.append(f"<span style='background:#1e293b;color:#cbd5e1;font-size:10px;font-weight:700;padding:4px 11px;border-radius:20px;text-transform:uppercase;letter-spacing:.05em'>{_esc(btype_label)}</span></div>")
    p.append(f"<div style='font-size:13px;color:{MUTE}'>{_esc(url)}</div></div>")

    # Score band
    p.append(f"<div style='background:{SOFT};border-bottom:1px solid {LINE};padding:26px 44px;display:flex;align-items:center;gap:34px'>")
    p.append("<div style='flex-shrink:0;text-align:center'>")
    p.append(f"<div style='width:116px;height:116px;border-radius:50%;border:7px solid {ov_color};display:flex;flex-direction:column;align-items:center;justify-content:center'>")
    p.append(f"<span style='font-size:38px;font-weight:800;color:{ov_color};line-height:1'>{overall}</span>")
    p.append(f"<span style='font-size:11px;color:{MUTE}'>/100</span></div>")
    p.append(f"<div style='font-size:11px;font-weight:700;color:{ov_color};text-transform:uppercase;letter-spacing:.06em;margin-top:8px'>{ov_label}</div></div>")
    p.append("<div style='flex:1'><div style='display:grid;grid-template-columns:repeat(4,1fr);gap:10px'>")
    p.append(stat("#fef2f2", "#dc2626", critical_n, "Critical"))
    p.append(stat("#fffbeb", "#b45309", medium_n, "Medium"))
    p.append(stat(https_bg, https_color, https_text, "Security"))
    p.append(stat("#eff6ff", "#1d4ed8", rt + "s", "Load Time"))
    p.append("</div></div></div>")

    # Sections
    p.append(_section("Executive Summary", summary_inner))
    if detected:
        p.append(_section("What We Detected", _build_detected(detected),
                          "The concrete evidence behind the scores in this report"))
    p.append(_section("Score Breakdown by Category", _build_score_cards(scores) + _build_psi(psi)))
    p.append(_section("Issues Found — " + str(len(issues[:14])) + " Items", _build_issues(issues)))
    p.append(_section("Contact & Lead Capture Health", _build_contact_grid(contact, detected)))
    cex_inner = _build_customer_expectations(cex, btype_label)
    if cex_inner:
        p.append(_section(btype_label + " — What Customers Look For", cex_inner))
    p.append(_section("What's Already Working", _build_positives(positives)))
    if services:
        p.append(_section("How " + AGENCY + " Can Help", _build_services_table(services)))
    if email_text:
        p.append(_section("Suggested Outreach Message", email_inner))

    # Footer
    p.append(f"<div style='background:{INK};padding:16px 44px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px'>")
    p.append(f"<span style='font-size:11px;color:{MUTE}'>Prepared by <strong style='color:#cbd5e1'>{_esc(AGENCY)}</strong> · {date_str}</span>")
    p.append(f"<span style='font-size:11px;color:{MUTE}'>{_esc(domain)} · Confidential</span></div>")
    p.append("</div></body></html>")
    return "".join(p)


def save_report(audit: dict, output_dir: str = "reports") -> str:
    os.makedirs(output_dir, exist_ok=True)
    domain   = audit["domain"].replace(".", "_").replace("/", "")
    filename = output_dir + "/" + domain + "_audit.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(generate_report(audit))
    return filename
