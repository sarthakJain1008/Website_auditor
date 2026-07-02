"""
Ryotech AI Website Auditor — Streamlit UI v2
Full redesign: session state for results, business-impact-first layout,
competitor benchmarks, quick wins, content health, and more.
"""
import streamlit as st
import time
from dotenv import load_dotenv
import os

load_dotenv()

st.set_page_config(
    page_title="Ryotech — AI Website Auditor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1100px; }

  .ryo-header {
    background: linear-gradient(135deg, #0f1117 0%, #1a2035 100%);
    border-radius: 14px; padding: 36px 40px; margin-bottom: 24px; color: white;
  }
  .ryo-header h1 { font-size: 26px; font-weight: 700; margin: 0 0 6px 0; }
  .ryo-header p  { color: #9ca3af; font-size: 14px; margin: 0; }

  .score-circle {
    width: 130px; height: 130px; border-radius: 50%;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center; margin: 0 auto 8px auto;
  }
  .impact-box {
    background: linear-gradient(135deg, #fff1f2 0%, #fff7ed 100%);
    border-left: 4px solid #dc2626;
    padding: 10px 14px; border-radius: 0 8px 8px 0;
    font-size: 13px; color: #7f1d1d; margin-top: 10px; font-weight: 600;
    box-shadow: 0 1px 3px rgba(220,38,38,0.1);
  }
  .expectation-missing {
    background: linear-gradient(135deg, #fff1f2 0%, #fef2f2 100%);
    border: 1px solid #fecaca;
    border-left: 4px solid #dc2626;
    border-radius: 8px; padding: 14px 16px; margin-bottom: 10px;
  }
  .expectation-met {
    background: #f0fdf4; border: 1px solid #bbf7d0;
    border-radius: 8px; padding: 10px 14px; margin-bottom: 8px;
    display: flex; align-items: center; gap: 10px;
  }
  .customer-intel-header {
    background: linear-gradient(135deg, #1a0505 0%, #2d0a0a 100%);
    border: 1px solid #dc2626;
    border-radius: 12px; padding: 18px 22px; margin-bottom: 16px;
    color: white;
  }
  .section-label {
    font-size: 11px; font-weight: 700; color: #9ca3af;
    text-transform: uppercase; letter-spacing: .1em; margin-bottom: 14px;
    padding-bottom: 8px; border-bottom: 1px solid #f0f1f3;
  }
  .positive-pill {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 12px; background: #f0fdf4; border: 1px solid #bbf7d0;
    border-radius: 20px; font-size: 12px; color: #166534; margin: 4px 4px 4px 0;
  }
  .quick-win {
    background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 3px solid #16a34a;
    border-radius: 8px; padding: 12px 16px; margin-bottom: 8px;
    font-size: 13px; color: #166534;
  }
</style>
""", unsafe_allow_html=True)

# ─── HEADER ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="ryo-header">
  <h1>🔍 Ryotech — AI Website Auditor</h1>
  <p>Enter any local business URL · Get real scores, real issues, and a ready-to-send outreach email.</p>
</div>
""", unsafe_allow_html=True)

# ─── SESSION STATE — store results so UI doesn't vanish on rerun ─────────────
if "audit_result" not in st.session_state:
    st.session_state.audit_result = None
if "last_url" not in st.session_state:
    st.session_state.last_url = ""

# ─── INPUT ROW ──────────────────────────────────────────────────────────────
col_input, col_btn = st.columns([4, 1])
with col_input:
    url_input = st.text_input(
        "Website URL", placeholder="e.g. bronxjiujitsu.com or milehighplumbing.com",
        label_visibility="collapsed", key="url_field"
    )
with col_btn:
    run_btn = st.button("Run Audit →", type="primary", use_container_width=True)

# ─── TRIGGER AUDIT ───────────────────────────────────────────────────────────
if run_btn and url_input.strip():
    url = url_input.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Reset previous result
    st.session_state.audit_result = None
    st.session_state.last_url = url

    progress = st.progress(0, text="🌐 Connecting to website...")
    time.sleep(0.3)

    try:
        from audit_engine import run_audit
        progress.progress(15, text="🕷️ Fetching page content...")
        audit = run_audit(url)
        progress.progress(50, text="🔍 Analysing SEO, security, contacts, trust signals...")

        if audit.get("error"):
            st.error(f"❌ Could not reach **{url}**: {audit['error']}")
            st.caption("Check the URL is correct and the site is online.")
            progress.empty()
            st.stop()

        progress.progress(70, text="🤖 Running Gemini AI analysis...")
        from ai_engine import enrich_audit
        audit = enrich_audit(audit)

        progress.progress(95, text="📊 Building report...")
        time.sleep(0.3)
        progress.progress(100, text="✅ Done!")
        time.sleep(0.4)
        progress.empty()

        st.session_state.audit_result = audit

    except Exception as e:
        st.error(f"Audit failed: {str(e)}")
        if "progress" in locals():
            progress.empty()
        st.stop()

elif run_btn and not url_input.strip():
    st.warning("Please enter a URL first.")

# ─── DISPLAY RESULTS (from session state) ────────────────────────────────────
audit = st.session_state.audit_result
if audit:
    overall   = audit["overall_score"]
    scores    = audit["scores"]
    issues    = audit["all_issues"]
    positives = audit.get("all_positives", [])
    services  = audit.get("recommended_services", [])
    contact   = audit.get("contact_details", {})
    btype     = audit.get("business_type", "default")

    btype_labels = {
        "gym": "Gym / Martial Arts", "restaurant": "Restaurant / Café",
        "plumber": "Plumbing Business", "dentist": "Dental Practice",
        "salon": "Hair & Beauty Salon", "lawyer": "Law Firm",
        "real_estate": "Real Estate Agency", "medical": "Medical Clinic",
        "accountant": "Accounting Firm", "tradie": "Trade Business",
        "retail": "Retail Store", "default": "Local Business"
    }
    btype_label = btype_labels.get(btype, "Local Business")

    if overall >= 75: ov_color = "#16a34a"; ov_label = "Good"
    elif overall >= 45: ov_color = "#d97706"; ov_label = "Needs Work"
    else: ov_color = "#dc2626"; ov_label = "Poor"

    def score_color(s):
        if s >= 75: return "#16a34a", "Good"
        if s >= 45: return "#d97706", "Needs Work"
        return "#dc2626", "Poor"

    critical_n = len([i for i in issues if i["severity"] == "critical"])
    medium_n   = len([i for i in issues if i["severity"] == "medium"])

    st.success(f"✅ Audit complete for **{audit['domain']}** · {btype_label}")

    # ── SECTION 1: OVERALL SCORE ──────────────────────────────────────────
    st.markdown('<div class="section-label">📊 Overall Score & At a Glance</div>', unsafe_allow_html=True)

    col_ov, col_m1, col_m2, col_m3, col_m4 = st.columns([2, 1, 1, 1, 1])
    with col_ov:
        st.markdown(f"""
        <div class="score-circle" style="border:7px solid {ov_color}">
          <span style="font-size:42px;font-weight:700;color:{ov_color};line-height:1">{overall}</span>
          <span style="font-size:12px;color:#9ca3af">/100</span>
        </div>
        <div style="text-align:center;font-size:12px;font-weight:700;color:{ov_color};text-transform:uppercase;letter-spacing:.06em">{ov_label}</div>
        <div style="text-align:center;font-size:11px;color:#9ca3af;margin-top:4px">{btype_label}</div>
        """, unsafe_allow_html=True)

    for col, val, lbl, color in [
        (col_m1, str(critical_n), "Critical Issues", "#dc2626"),
        (col_m2, str(medium_n),   "Medium Issues",   "#d97706"),
        (col_m3, "✅ HTTPS" if audit.get("is_https") else "❌ No SSL", "Security",    "#16a34a" if audit.get("is_https") else "#dc2626"),
        (col_m4, f"{audit.get('response_time','?')}s", "Load Time",  "#0369a1"),
    ]:
        with col:
            st.markdown(f"""
            <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:18px 12px;text-align:center;height:100px;display:flex;flex-direction:column;align-items:center;justify-content:center">
              <div style="font-size:22px;font-weight:700;color:{color}">{val}</div>
              <div style="font-size:11px;color:#9ca3af;margin-top:4px;text-transform:uppercase;letter-spacing:.05em">{lbl}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── SECTION 2: AI SUMMARY ────────────────────────────────────────────
    st.markdown('<div class="section-label">🧠 AI Summary</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="background:#f9fafb;border-left:3px solid #0f1117;padding:16px 20px;border-radius:0 8px 8px 0;font-size:14px;color:#374151;line-height:1.8">
      {audit.get('ai_summary','').replace(chr(10),'<br>')}
    </div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── SECTION 3: QUICK WINS ─────────────────────────────────────────────
    quick_wins = [i for i in issues if i["severity"] == "low" and "Add" in i.get("fix", "")][:4]
    if quick_wins:
        st.markdown('<div class="section-label">⚡ Quick Wins — Fix These in Under 30 Minutes</div>', unsafe_allow_html=True)
        for qw in quick_wins:
            st.markdown(f'<div class="quick-win">✅ <strong>{qw["issue"]}</strong> — {qw["fix"]}</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    # ── SECTION 4: SCORE BREAKDOWN ────────────────────────────────────────
    st.markdown('<div class="section-label">📈 Score Breakdown by Category</div>', unsafe_allow_html=True)
    score_labels = {
        "seo": "On-Page SEO", "contact": "Contact Info",
        "cta": "CTA & Conversion", "trust": "Trust & Reviews",
        "security": "Security / SSL", "performance": "Page Speed", "mobile": "Mobile"
    }
    cols = st.columns(len(scores))
    for col, (key, lbl) in zip(cols, score_labels.items()):
        s = scores.get(key, 0)
        c, l = score_color(s)
        with col:
            st.markdown(f"""
            <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:16px;text-align:center">
              <div style="font-size:11px;color:#6b7280;margin-bottom:8px;font-weight:500">{lbl}</div>
              <div style="font-size:28px;font-weight:700;color:{c}">{s}</div>
              <div style="font-size:10px;color:{c};margin-top:3px;font-weight:600">{l}</div>
              <div style="height:5px;background:#e5e7eb;border-radius:3px;margin-top:10px">
                <div style="height:5px;background:{c};border-radius:3px;width:{s}%"></div>
              </div>
            </div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── SECTION 4b: CUSTOMER BEHAVIOR INTELLIGENCE ───────────────────────
    cex = audit.get("customer_expectations", {})
    if cex:
        missing_items = cex.get("missing", [])
        met_items = cex.get("met", [])
        btype_label_cex = cex.get("label", btype_label)
        headline = cex.get("headline_stat", "")

        st.markdown(f'<div class="section-label">&#128565; {btype_label_cex} Customer Intelligence — What Your Customers Look For</div>', unsafe_allow_html=True)

        # Alarming header
        st.markdown(f"""
        <div class="customer-intel-header">
          <div style="font-size:11px;font-weight:700;color:#f87171;text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px">&#128204; Research Insight</div>
          <div style="font-size:15px;font-weight:600;color:#fff;line-height:1.5">{headline}</div>
          <div style="font-size:12px;color:#fca5a5;margin-top:6px">We checked your site against what {btype_label_cex} customers specifically look for before choosing a business.</div>
        </div>""", unsafe_allow_html=True)

        if missing_items:
            st.markdown(f"""
            <div style="background:#fff1f2;border:1px solid #fecaca;border-radius:10px;padding:14px 18px;margin-bottom:16px">
              <div style="font-size:13px;font-weight:700;color:#dc2626;margin-bottom:4px">&#128680; {len(missing_items)} Critical Customer Expectation{'s' if len(missing_items)>1 else ''} Missing from This Site</div>
              <div style="font-size:12px;color:#991b1b">These are things {btype_label_cex} customers specifically search for before deciding. Each gap below is costing this business real customers, right now.</div>
            </div>""", unsafe_allow_html=True)

            for item in missing_items:
                st.markdown(f"""
                <div class="expectation-missing">
                  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
                    <span style="font-size:18px">&#10060;</span>
                    <span style="font-size:14px;font-weight:700;color:#991b1b">{item['name']}</span>
                    <span style="background:#fee2e2;color:#dc2626;font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;text-transform:uppercase;letter-spacing:.05em">MISSING</span>
                  </div>
                  <div style="font-size:13px;color:#374151;margin-bottom:8px">{item['why']}</div>
                  <div style="background:#fff;border:1px solid #fecaca;border-radius:6px;padding:8px 12px;font-size:12.5px;color:#dc2626;font-weight:600">
                    &#128201; <strong>The cost of this gap:</strong> {item['stat']}
                  </div>
                </div>""", unsafe_allow_html=True)

        if met_items:
            st.markdown(f"<div style='font-size:12px;font-weight:600;color:#6b7280;margin:12px 0 8px;text-transform:uppercase;letter-spacing:.06em'>&#9989; Already Present on This Site</div>", unsafe_allow_html=True)
            for item in met_items:
                st.markdown(f"""
                <div class="expectation-met">
                  <span style="font-size:16px">&#9989;</span>
                  <div>
                    <div style="font-size:13px;font-weight:600;color:#166534">{item['name']}</div>
                    <div style="font-size:11.5px;color:#4b7a62">{item['why']}</div>
                  </div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

    # ── SECTION 5: CONTACT HEALTH ─────────────────────────────────────────
    st.markdown('<div class="section-label">📞 Contact & Lead Capture Health</div>', unsafe_allow_html=True)
    contact_items = [
        (contact.get("phone_found"),  "Phone number visible on page"),
        (contact.get("tel_link"),     "Phone is tap-to-call on mobile"),
        (contact.get("email_found"),  "Email address visible"),
        (contact.get("contact_form"), "Contact / enquiry form present"),
        (contact.get("address_found"),"Physical address listed"),
        (contact.get("google_maps"),  "Google Maps embedded"),
    ]
    contact_cols = st.columns(3)
    for i, (ok, label) in enumerate(contact_items):
        with contact_cols[i % 3]:
            icon = "✅" if ok else "❌"
            color = "#166534" if ok else "#991b1b"
            bg = "#f0fdf4" if ok else "#fef2f2"
            border = "#bbf7d0" if ok else "#fecaca"
            st.markdown(f"""
            <div style="background:{bg};border:1px solid {border};border-radius:8px;padding:12px 14px;margin-bottom:10px;display:flex;align-items:center;gap:10px">
              <span style="font-size:16px">{icon}</span>
              <span style="font-size:13px;color:{color};font-weight:500">{label}</span>
            </div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── SECTION 6: ISSUES WITH BUSINESS IMPACT ────────────────────────────
    st.markdown(f'<div class="section-label">🚨 Issues Found — {len(issues[:14])} Items (with Business Impact)</div>', unsafe_allow_html=True)
    st.caption("Each issue shows exactly what it's costing this business in real terms.")

    sev_badge = {
        "critical": ("🔴 Critical", "#fee2e2", "#dc2626", "#dc2626"),
        "medium":   ("🟡 Medium",   "#fef3c7", "#d97706", "#d97706"),
        "low":      ("🔵 Low",      "#dbeafe", "#2563eb", "#3b82f6"),
    }

    for issue in issues[:14]:
        sev = issue["severity"]
        label, bg, color, border_color = sev_badge.get(sev, ("⚪ Info", "#f3f4f6", "#6b7280", "#9ca3af"))
        impact = issue.get("business_impact", "")

        with st.expander(f"{label}  ·  {issue['issue']}", expanded=(sev == "critical")):
            st.markdown(f"**Category:** `{issue.get('category', '')}`")
            st.markdown(f"**Fix:** {issue.get('fix', '')}")
            if impact:
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#fff1f2 0%,#fff7ed 100%);border-left:4px solid #dc2626;padding:12px 16px;border-radius:0 8px 8px 0;margin-top:10px;box-shadow:0 1px 3px rgba(220,38,38,.1)">
                  <div style="font-size:11px;font-weight:700;color:#dc2626;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">&#9888;&#65039; Revenue Impact</div>
                  <div style="font-size:13px;color:#7f1d1d;font-weight:600;line-height:1.5">{impact}</div>
                </div>
                """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── SECTION 7: WHAT'S WORKING ─────────────────────────────────────────
    if positives:
        st.markdown('<div class="section-label">✅ What\'s Already Working</div>', unsafe_allow_html=True)
        pills = "".join([f'<span class="positive-pill">✅ {p}</span>' for p in positives])
        st.markdown(f'<div style="margin-bottom:20px">{pills}</div>', unsafe_allow_html=True)

    # ── SECTION 8: RYOTECH SERVICES ───────────────────────────────────────
    st.markdown('<div class="section-label">🛠️ How Ryotech Can Help — Matched to This Site\'s Issues</div>', unsafe_allow_html=True)

    sev_pill = {
        "critical": ("🔴 High Priority", "#fee2e2", "#dc2626"),
        "medium":   ("🟡 Medium", "#fef3c7", "#d97706"),
        "low":      ("🔵 Low", "#dbeafe", "#2563eb"),
    }

    if services:
        # Top 3 as highlighted cards
        top_services = services[:3]
        svc_cols = st.columns(3)
        for i, svc in enumerate(top_services):
            with svc_cols[i]:
                sev = svc.get("severity", "medium")
                lbl, bg, clr = sev_pill.get(sev, sev_pill["low"])
                triggered_by = svc.get("triggered_by", "")
                outcome = svc.get("outcome", "")
                desc = svc.get("description", "")
                st.markdown(f"""
                <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px;height:100%;border-top:3px solid {clr}">
                  <span style="background:{bg};color:{clr};font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px">{lbl}</span>
                  <div style="font-size:15px;font-weight:700;color:#0f1117;margin:10px 0 6px">{svc['service']}</div>
                  <div style="font-size:12px;color:#6b7280;margin-bottom:10px">{desc}</div>
                  <div style="font-size:12px;color:#059669;font-style:italic">→ {outcome}</div>
                </div>""", unsafe_allow_html=True)

        # Remaining as compact table
        remaining = services[3:]
        if remaining:
            st.markdown("<br>", unsafe_allow_html=True)
            table_rows = ""
            for svc in remaining:
                sev = svc.get("severity", "low")
                lbl, bg, clr = sev_pill.get(sev, sev_pill["low"])
                triggered_by = svc.get("triggered_by", "")[:70]
                outcome = svc.get("outcome", "")
                table_rows += f"""
                <tr>
                  <td style="padding:11px 14px;border-bottom:1px solid #f3f4f6">
                    <div style="font-weight:600;font-size:13px;color:#0f1117">{svc['service']}</div>
                    <div style="font-size:11px;color:#9ca3af;margin-top:2px">Triggered by: {triggered_by}{"…" if len(triggered_by)>=70 else ""}</div>
                  </td>
                  <td style="padding:11px 14px;border-bottom:1px solid #f3f4f6;font-size:12px;color:#059669;font-style:italic">{outcome}</td>
                  <td style="padding:11px 14px;border-bottom:1px solid #f3f4f6;white-space:nowrap"><span style="background:{bg};color:{clr};font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px">{lbl}</span></td>
                </tr>"""
            st.markdown(f"""
            <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden">
              <thead><tr style="background:#f9fafb">
                <th style="text-align:left;padding:10px 14px;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #e5e7eb">Service</th>
                <th style="text-align:left;padding:10px 14px;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #e5e7eb">What You Get</th>
                <th style="text-align:left;padding:10px 14px;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #e5e7eb">Priority</th>
              </tr></thead>
              <tbody>{table_rows}</tbody>
            </table>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── SECTION 9: OUTREACH EMAIL ─────────────────────────────────────────
    st.markdown('<div class="section-label">✉️ Personalised Outreach Email</div>', unsafe_allow_html=True)
    st.info(f"📋 This email was written specifically for **{audit['business_name']}** ({btype_label}). Copy and send.")
    email_text = audit.get("outreach_email", "")
    st.text_area("Email (click to copy):", value=email_text, height=220, key="email_box")

    # ── SECTION 10: DOWNLOAD REPORT ───────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-label">⬇️ Download Full PDF Report</div>', unsafe_allow_html=True)

    col_dl1, col_dl2 = st.columns([2, 3])
    with col_dl1:
        from report_generator import generate_report
        html_report = generate_report(audit)
        st.download_button(
            label="⬇️  Download HTML Report",
            data=html_report.encode("utf-8"),
            file_name=f"{audit['domain'].replace('.','_')}_ryotech_audit.html",
            mime="text/html",
            use_container_width=True
        )
    with col_dl2:
        st.caption("Open in Chrome → `Cmd+P` (Mac) or `Ctrl+P` (Windows) → **Save as PDF**. That's your client-ready PDF.")
