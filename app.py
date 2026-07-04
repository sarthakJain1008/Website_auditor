"""
Ryotech AI Website Auditor — v3 Complete UI Redesign
Aesthetic: Precision dark · Sharp edges · Teal accent
Typography: Space Grotesk + JetBrains Mono
Research-backed — Nebula Explorer UI Report 2026-07-02
"""
import streamlit as st
import time
from dotenv import load_dotenv
import os

load_dotenv()

st.set_page_config(
    page_title="Ryotech — AI Website Auditor",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── DESIGN SYSTEM ───────────────────────────────────────────────────────────
# Sharp edges (border-radius: 0–2px) · Space Grotesk · JetBrains Mono data
# Deep navy base · Teal accent · 1px borders · Zero shadows
STYLES = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

  html, body, [class*="css"] {
    font-family: 'Space Grotesk', system-ui, sans-serif !important;
  }
  .stApp { background-color: #FFFFFF !important; color: #0F172A !important; }
  
  /* Make full width instead of centered */
  .block-container {
    padding: 2rem 2.5rem 4rem !important;
    max-width: 100% !important; /* Full width */
  }
  #MainMenu, footer, header { visibility: hidden !important; }
  .stDeployButton { display: none !important; }

  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: #F1F5F9; }
  ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 0; }

  /* ── Typography Tokens ── */
  .ryo-eyebrow {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; font-weight: 700; color: #1D4ED8; /* Navy/Blue */
    letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 6px;
  }
  .ryo-display {
    font-size: 32px; font-weight: 700; color: #0F172A;
    line-height: 1.15; margin: 0; letter-spacing: -0.02em;
  }
  .ryo-subtitle { font-size: 14px; color: #475569; font-weight: 500; margin-top: 6px; }
  .ryo-label {
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.1em;
  }

  /* ── Header ── */
  .ryo-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 0 24px 0; border-bottom: 2px solid #0F172A; margin-bottom: 32px;
  }
  .ryo-logo { display: flex; align-items: center; gap: 12px; }
  .ryo-logo-mark {
    width: 34px; height: 34px;
    background: #0F172A; color: #FFFFFF;
    border-radius: 0;
    display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 700;
  }
  .ryo-logo-name { font-size: 16px; font-weight: 800; color: #0F172A; }
  .ryo-logo-tag {
    font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #0F172A;
    background: #FFFFFF; border: 1px solid #0F172A; font-weight: 600;
    padding: 2px 8px; border-radius: 0; margin-left: 8px;
  }
  .ryo-version {
    font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #0F172A; font-weight: 600;
    padding: 4px 10px; border: 1px solid #0F172A; border-radius: 0;
  }

  /* ── Bento Score Card ── */
  .ryo-score-card {
    background: #FFFFFF; border: 2px solid #0F172A; border-radius: 0;
    padding: 28px 24px; display: flex; flex-direction: column;
    align-items: center; justify-content: center; text-align: center;
    position: relative; overflow: hidden;
  }
  .ryo-score-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px;
  }
  .ryo-score-card.critical::before { background: #DC2626; }
  .ryo-score-card.warning::before  { background: #D97706; }
  .ryo-score-card.good::before     { background: #16A34A; }
  
  .ryo-score-number {
    font-family: 'JetBrains Mono', monospace; font-size: 64px;
    font-weight: 800; line-height: 1; margin-bottom: 6px;
  }
  .ryo-score-domain {
    font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #0F172A; font-weight: 600;
    margin-top: 10px; padding: 3px 10px; background: #F1F5F9;
    border: 1px solid #0F172A; border-radius: 0;
  }

  /* ── Stat Chip ── */
  .ryo-stat {
    background: #FFFFFF; border: 2px solid #0F172A; border-radius: 0;
    padding: 20px 18px; display: flex; flex-direction: column; justify-content: space-between;
  }
  .ryo-stat-value {
    font-family: 'JetBrains Mono', monospace; font-size: 28px;
    font-weight: 800; line-height: 1; margin-bottom: 8px; color: #0F172A;
  }

  /* ── Tab Navigation ── */
  .stTabs [data-baseweb="tab-list"] {
    gap: 0 !important; background: transparent !important;
    border-bottom: 2px solid #E2E8F0 !important;
    padding-bottom: 0 !important; margin-bottom: 28px !important;
  }
  .stTabs [data-baseweb="tab"] {
    font-family: 'Space Grotesk', sans-serif !important; font-size: 14px !important;
    font-weight: 600 !important; color: #64748B !important;
    background: transparent !important; border: none !important;
    border-radius: 0 !important; padding: 10px 24px !important;
    border-bottom: 3px solid transparent !important; margin-bottom: -2px !important;
  }
  .stTabs [data-baseweb="tab"]:hover { color: #0F172A !important; }
  .stTabs [aria-selected="true"] {
    color: #1D4ED8 !important; border-bottom: 3px solid #1D4ED8 !important;
    background: transparent !important;
  }
  .stTabs [data-baseweb="tab-panel"] { padding: 0 !important; }
  .stTabs [data-baseweb="tab-highlight"] { display: none !important; }

  /* ── Bars ── */
  .ryo-bar-wrap {
    background: #FFFFFF; border: 1px solid #CBD5E1;
    border-radius: 0; padding: 14px 18px; margin-bottom: 8px;
  }
  .ryo-bar-track { height: 4px; background: #E2E8F0; border-radius: 0; margin-top: 10px; }

  /* ── Service ── */
  .ryo-service {
    background: #FFFFFF; border: 1px solid #CBD5E1;
    border-radius: 0; padding: 20px; height: 100%;
  }
  .ryo-service:hover { border-color: #0F172A; }

  /* ── Quick Win ── */
  .ryo-win {
    background: #F0FDF4; border: 1px solid #BBF7D0;
    border-left: 4px solid #16A34A; border-radius: 0;
    padding: 12px 16px; margin-bottom: 6px; font-size: 14px; color: #166534; font-weight: 500;
  }

  /* ── Missing / Met ── */
  .ryo-missing {
    background: #FEF2F2; border: 1px solid #FECACA;
    border-left: 4px solid #DC2626; border-radius: 0;
    padding: 16px 18px; margin-bottom: 8px;
  }
  .ryo-met {
    background: #F0FDF4; border: 1px solid #BBF7D0;
    border-left: 4px solid #16A34A;
    border-radius: 0; padding: 12px 16px; margin-bottom: 6px;
    display: flex; align-items: center; gap: 12px;
  }

  /* ── Pill ── */
  .ryo-pill {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 10px; background: #DBEAFE;
    border: 1px solid #93C5FD; border-radius: 0;
    font-size: 12px; color: #1D4ED8; font-weight: 600; margin: 3px 4px 3px 0;
  }

  /* ── Check Row ── */
  .ryo-check {
    background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 0;
    padding: 12px 16px; display: flex; align-items: center; gap: 12px;
    margin-bottom: 6px; font-size: 14px; font-weight: 600; color: #0F172A;
  }

  /* ── Divider ── */
  .ryo-divider { height: 1px; background: #E2E8F0; margin: 28px 0; }

  /* ── Section ── */
  .ryo-section-title {
    font-size: 18px; font-weight: 700; color: #0F172A;
    margin-bottom: 16px; letter-spacing: -0.01em;
  }
  .ryo-section-sub { font-size: 14px; color: #475569; margin-top: -10px; margin-bottom: 18px; font-weight: 500; }

  /* ── Impact ── */
  .ryo-issue-impact {
    margin-top: 10px; background: #FEF2F2; border: 1px solid #FECACA;
    border-left: 3px solid #DC2626; border-radius: 0; padding: 10px 14px;
  }

  /* ── Overrides ── */
  .stTextInput input {
    background: #FFFFFF !important; border: 2px solid #0F172A !important;
    border-radius: 0 !important; color: #0F172A !important;
    font-family: 'Space Grotesk', sans-serif !important; font-size: 16px !important; font-weight: 500 !important;
  }
  .stTextInput input:focus {
    border-color: #1D4ED8 !important;
    box-shadow: 4px 4px 0px #1D4ED8 !important;
  }
  .stTextArea textarea {
    background: #FFFFFF !important; border: 2px solid #0F172A !important;
    border-radius: 0 !important; color: #0F172A !important;
    font-family: 'JetBrains Mono', monospace !important; font-size: 13px !important;
  }
  .stTextArea textarea:focus {
    border-color: #1D4ED8 !important; box-shadow: 4px 4px 0px #1D4ED8 !important;
  }
  .stButton > button {
    font-family: 'Space Grotesk', sans-serif !important; font-weight: 700 !important;
    font-size: 15px !important; background: #0F172A !important;
    color: #FFFFFF !important; border: 2px solid #0F172A !important;
    border-radius: 0 !important; padding: 10px 24px !important; text-transform: uppercase;
  }
  .stButton > button:hover { background: #1D4ED8 !important; border-color: #1D4ED8 !important; }
  .stDownloadButton > button {
    font-family: 'Space Grotesk', sans-serif !important; font-weight: 700 !important;
    background: #FFFFFF !important; color: #0F172A !important;
    border: 2px solid #0F172A !important; border-radius: 0 !important; text-transform: uppercase;
  }
  .stDownloadButton > button:hover {
    background: #F1F5F9 !important; box-shadow: 4px 4px 0px #0F172A !important;
  }
  .stProgress > div > div { background: #0F172A !important; }
  .streamlit-expanderHeader {
    background: #FFFFFF !important; border: 1px solid #CBD5E1 !important;
    border-radius: 0 !important; font-family: 'Space Grotesk', sans-serif !important;
    font-size: 15px !important; font-weight: 700 !important; color: #0F172A !important;
  }
  .streamlit-expanderContent {
    background: #FFFFFF !important; border: 1px solid #CBD5E1 !important;
    border-top: none !important; border-radius: 0 !important;
  }
</style>
"""
st.markdown(STYLES, unsafe_allow_html=True)

# ─── HEADER ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="ryo-header">
  <div class="ryo-logo">
    <div class="ryo-logo-mark">◈</div>
    <div class="ryo-logo-name">Ryotech<span style="color:#1D4ED8">.</span></div>
    <span class="ryo-logo-tag">AI Website Auditor</span>
  </div>
  <div class="ryo-version">v3.0</div>
</div>
""", unsafe_allow_html=True)

# ─── HERO ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="ryo-eyebrow">Website Intelligence</div>
<div class="ryo-display">Audit any local business<br>in under 60 seconds.</div>
<div class="ryo-subtitle">Enter a URL · Get scores, issues, customer intelligence, and a ready-to-send outreach email.</div>
<br>
""", unsafe_allow_html=True)

# ─── SESSION STATE ────────────────────────────────────────────────────────────
if "audit_result" not in st.session_state:
    st.session_state.audit_result = None
if "last_url" not in st.session_state:
    st.session_state.last_url = ""

# ─── INPUT ROW ───────────────────────────────────────────────────────────────
col_input, col_btn = st.columns([5, 1])
with col_input:
    url_input = st.text_input(
        "url", placeholder="→  bronxjiujitsu.com  or  milehighplumbing.com",
        label_visibility="collapsed", key="url_field"
    )
with col_btn:
    run_btn = st.button("Run Audit →", type="primary", use_container_width=True)

st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

# ─── TRIGGER AUDIT ───────────────────────────────────────────────────────────
if run_btn and url_input.strip():
    url = url_input.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    st.session_state.audit_result = None
    st.session_state.last_url = url

    progress = st.progress(0, text="◌  Connecting...")
    time.sleep(0.3)

    try:
        from audit_engine import run_audit
        progress.progress(15, text="◌  Fetching page...")
        audit = run_audit(url)
        progress.progress(50, text="◌  Analysing SEO, security, contacts, trust signals...")

        if audit.get("error"):
            st.error(f"Could not reach **{url}**: {audit['error']}")
            progress.empty()
            st.stop()

        progress.progress(70, text="◌  Running Gemini analysis...")
        from ai_engine import enrich_audit
        audit = enrich_audit(audit)

        progress.progress(95, text="◌  Building report...")
        time.sleep(0.3)
        progress.progress(100, text="✓  Done")
        time.sleep(0.4)
        progress.empty()

        st.session_state.audit_result = audit

    except Exception as e:
        st.error(f"Audit failed: {str(e)}")
        if "progress" in locals():
            progress.empty()
        st.stop()

elif run_btn and not url_input.strip():
    st.warning("Enter a URL to begin.")

# ─── RESULTS ─────────────────────────────────────────────────────────────────
audit = st.session_state.audit_result
if not audit:
    st.stop()

overall   = audit["overall_score"]
scores    = audit["scores"]
issues    = audit["all_issues"]
positives = audit.get("all_positives", [])
services  = audit.get("recommended_services", [])
contact   = audit.get("contact_details", {})
btype     = audit.get("business_type", "default")
cex       = audit.get("customer_expectations", {})

btype_label = btype.title()

if overall >= 75:   ov_color = "#10B981"; ov_status = "GOOD";       ov_cls = "good"
elif overall >= 45: ov_color = "#F59E0B"; ov_status = "NEEDS WORK"; ov_cls = "warning"
else:               ov_color = "#F43F5E"; ov_status = "CRITICAL";   ov_cls = "critical"

def sc(s):
    if s >= 75: return "#10B981"
    if s >= 45: return "#F59E0B"
    return "#F43F5E"

critical_n = len([i for i in issues if i["severity"] == "critical"])
medium_n   = len([i for i in issues if i["severity"] == "medium"])

# ── SUCCESS BAR ──
st.markdown(f"""
<div style="background:#DBEAFE;border:1px solid #93C5FD;
  border-radius:0;padding:10px 16px;margin-bottom:28px;
  display:flex;align-items:center;gap:12px">
  <span style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#1D4ED8">
    ✓ AUDIT COMPLETE
  </span>
  <span style="font-size:13px;color:#475569;font-weight:500">{audit['domain']}</span>
  <span style="font-family:'JetBrains Mono',monospace;font-size:10px;
    background:#FFFFFF;border:1px solid #CBD5E1;color:#64748B;
    padding:2px 8px;border-radius:0">{btype_label.upper()}</span>
</div>
""", unsafe_allow_html=True)

# ── CIRCULAR SCORE ROW ──
col_score, col_s1, col_s2, col_s3, col_s4 = st.columns([2, 1.1, 1.1, 1.1, 1.1])

with col_score:
    st.markdown(f"""
    <div style="display:flex;flex-direction:column;align-items:center;margin-top:10px">
      <div style="width:140px;height:140px;border-radius:50%;border:8px solid {ov_color};display:flex;flex-direction:column;align-items:center;justify-content:center">
        <div style="font-size:46px;font-weight:700;color:{ov_color};line-height:1;margin-bottom:2px">{overall}</div>
        <div style="font-size:14px;color:#9CA3AF">/100</div>
      </div>
      <div style="font-size:14px;font-weight:700;color:{ov_color};margin-top:16px;letter-spacing:0.05em">{ov_status}</div>
      <div style="font-size:13px;color:#9CA3AF;margin-top:4px">{btype_label}</div>
    </div>
    """, unsafe_allow_html=True)

https_val   = "✓ HTTPS" if audit.get("is_https") else "✗ NO SSL"
https_color = "#10B981" if audit.get("is_https") else "#EF4444"
https_bg    = "#F0FDF4" if audit.get("is_https") else "#FEE2E2"
rt = audit.get('response_time', '?')

for col, val, name, color, bg in [
    (col_s1, str(critical_n), "CRITICAL",  "#EF4444", "#FEE2E2"),
    (col_s2, str(medium_n),   "MEDIUM",    "#F59E0B", "#FEF3C7"),
    (col_s3, https_val,       "SECURITY",  https_color, https_bg),
    (col_s4, f"{rt}s",        "LOAD TIME", "#0EA5E9", "#F0F9FF"),
]:
    with col:
        st.markdown(f"""
        <div style="background:{bg};border-radius:12px;height:120px;display:flex;flex-direction:column;align-items:center;justify-content:center;margin-top:20px">
          <div style="font-size:28px;font-weight:700;color:{color};line-height:1;margin-bottom:8px">{val}</div>
          <div style="font-size:11px;font-weight:700;color:{color};text-transform:uppercase;letter-spacing:0.05em">{name}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown('<div style="height:36px"></div>', unsafe_allow_html=True)

# ── TABBED NAVIGATION ──
tab_overview, tab_issues, tab_contact, tab_intel, tab_services, tab_email = st.tabs([
    "Overview", "Issues", "Contact", "Customer Intel", "Services", "Outreach Email"
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
with tab_overview:

    st.markdown('<div class="ryo-section-title">AI Analysis</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="background:#FFFFFF;border:1px solid #CBD5E1;border-left:2px solid #1D4ED8;
      border-radius:0;padding:20px 22px;
      font-size:14px;color:#475569;line-height:1.8">
      {audit.get('ai_summary','').replace(chr(10),'<br>')}
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="ryo-divider"></div>', unsafe_allow_html=True)

    st.markdown('<div class="ryo-section-title">Score Breakdown</div>', unsafe_allow_html=True)
    score_labels = {
        "seo": "On-Page SEO", "contact": "Contact Info",
        "cta": "CTA & Conversion", "trust": "Trust & Reviews",
        "security": "Security", "performance": "Page Speed", "mobile": "Mobile"
    }
    for key, lbl in score_labels.items():
        s = scores.get(key, 0)
        c = sc(s)
        st.markdown(f"""
        <div class="ryo-bar-wrap">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="font-size:13px;font-weight:500;color:#1E293B">{lbl}</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:14px;
              font-weight:700;color:{c}">{s}</span>
          </div>
          <div class="ryo-bar-track">
            <div style="height:3px;background:{c};border-radius:0;width:{s}%"></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    quick_wins = [i for i in issues if i["severity"] == "low" and "Add" in i.get("fix", "")][:4]
    if quick_wins:
        st.markdown('<div class="ryo-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="ryo-section-title">Quick Wins — Under 30 Minutes</div>', unsafe_allow_html=True)
        for qw in quick_wins:
            st.markdown(f"""
            <div class="ryo-win">
              <strong>{qw['issue']}</strong> — {qw.get('fix','')}
            </div>
            """, unsafe_allow_html=True)

    if positives:
        st.markdown('<div class="ryo-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="ryo-section-title">Already Working</div>', unsafe_allow_html=True)
        pills = "".join([f'<span class="ryo-pill">✓ {p}</span>' for p in positives])
        st.markdown(f'<div>{pills}</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ISSUES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_issues:
    sev_colors = {
        "critical": "#F43F5E",
        "medium":   "#F59E0B",
        "low":      "#3B82F6",
    }
    sev_label = {"critical": "CRIT", "medium": "MED", "low": "LOW"}

    st.markdown(f'<div class="ryo-section-title">{len(issues[:14])} Issues Found</div>', unsafe_allow_html=True)
    st.markdown('<div class="ryo-section-sub">Ranked by severity · Business impact shown for each</div>', unsafe_allow_html=True)

    for issue in issues[:14]:
        sev = issue["severity"]
        color = sev_colors.get(sev, "#475569")
        badge = sev_label.get(sev, "INFO")
        impact = issue.get("business_impact", "")

        with st.expander(f"{issue['issue']}", expanded=(sev == "critical")):
            col_a, col_b = st.columns([4, 1])
            with col_a:
                st.markdown(f"**Category:** `{issue.get('category', '')}`")
                st.markdown(f"**Fix:** {issue.get('fix', '')}")
                if impact:
                    st.markdown(f"""
                    <div class="ryo-issue-impact">
                      <span style="font-family:'JetBrains Mono',monospace;font-size:9px;
                        font-weight:600;color:#F43F5E;letter-spacing:0.1em">REVENUE IMPACT</span><br>
                      <span style="font-size:12px;color:#475569">{impact}</span>
                    </div>
                    """, unsafe_allow_html=True)
            with col_b:
                st.markdown(f"""
                <div style="text-align:right">
                  <span style="font-family:'JetBrains Mono',monospace;font-size:9px;
                    font-weight:700;color:{color};border:1px solid {color}40;
                    padding:3px 8px;border-radius:0;letter-spacing:0.1em">{badge}</span>
                </div>
                """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — CONTACT
# ═══════════════════════════════════════════════════════════════════════════════
with tab_contact:
    st.markdown('<div class="ryo-section-title">Contact & Lead Capture</div>', unsafe_allow_html=True)
    st.markdown('<div class="ryo-section-sub">How well this site captures potential customers</div>', unsafe_allow_html=True)

    contact_checks = [
        (contact.get("phone_found"),   "Phone number visible on page"),
        (contact.get("tel_link"),      "Phone is tap-to-call on mobile"),
        (contact.get("email_found"),   "Email address visible"),
        (contact.get("contact_form"),  "Contact / enquiry form present"),
        (contact.get("address_found"), "Physical address listed"),
        (contact.get("google_maps"),   "Google Maps embedded"),
    ]

    col_c1, col_c2 = st.columns(2)
    for i, (ok, label) in enumerate(contact_checks):
        col = col_c1 if i % 2 == 0 else col_c2
        icon   = "✓" if ok else "✗"
        color  = "#10B981" if ok else "#F43F5E"
        bg     = "#F0FDF4" if ok else "#FEF2F2"
        border = "#BBF7D0" if ok else "#FECACA"
        with col:
            st.markdown(f"""
            <div class="ryo-check" style="background:{bg};border-color:{border}">
              <span style="font-family:'JetBrains Mono',monospace;font-weight:700;
                font-size:13px;color:{color}">{icon}</span>
              <span style="color:#1E293B">{label}</span>
            </div>
            """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — CUSTOMER INTEL
# ═══════════════════════════════════════════════════════════════════════════════
with tab_intel:
    if cex:
        missing_items = cex.get("missing", [])
        met_items     = cex.get("met", [])
        headline      = cex.get("headline_stat", "")
        cex_label     = cex.get("label", btype_label)

        st.markdown(f'<div class="ryo-section-title">{cex_label} — Customer Behaviour Intelligence</div>', unsafe_allow_html=True)

        if headline:
            st.markdown(f"""
            <div style="background:#FFFFFF;border:1px solid #CBD5E1;border-left:2px solid #F43F5E;
              border-radius:0;padding:16px 20px;margin-bottom:24px">
              <div style="font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:600;
                color:#F43F5E;letter-spacing:0.15em;margin-bottom:8px">RESEARCH INSIGHT</div>
              <div style="font-size:15px;font-weight:600;color:#0F172A;line-height:1.5">{headline}</div>
              <div style="font-size:12px;color:#64748B;margin-top:6px">
                Checked against what {cex_label} customers specifically look for.
              </div>
            </div>
            """, unsafe_allow_html=True)

        if missing_items:
            st.markdown(f"""
            <div style="font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:600;
              color:#F43F5E;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:14px">
              {len(missing_items)} Critical Expectations Missing
            </div>
            """, unsafe_allow_html=True)

            for item in missing_items:
                st.markdown(f"""
                <div class="ryo-missing">
                  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
                    <span style="font-family:'JetBrains Mono',monospace;font-size:9px;
                      font-weight:700;color:#F43F5E;background:#FECACA;
                      padding:2px 8px;border-radius:0;letter-spacing:0.08em">MISSING</span>
                    <span style="font-size:14px;font-weight:600;color:#0F172A">{item['name']}</span>
                  </div>
                  <div style="font-size:13px;color:#475569;margin-bottom:10px;line-height:1.6">
                    {item['why']}
                  </div>
                  <div style="font-family:'JetBrains Mono',monospace;font-size:11px;
                    color:#F43F5E;font-weight:500">↳ {item['stat']}</div>
                </div>
                """, unsafe_allow_html=True)

        if met_items:
            st.markdown("""
            <div style="font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:600;
              color:#10B981;letter-spacing:0.1em;text-transform:uppercase;margin:20px 0 12px">
              Already Present
            </div>
            """, unsafe_allow_html=True)
            for item in met_items:
                st.markdown(f"""
                <div class="ryo-met">
                  <span style="font-family:'JetBrains Mono',monospace;color:#10B981;font-weight:700">✓</span>
                  <div>
                    <div style="font-size:13px;font-weight:600;color:#1E293B;margin-bottom:2px">
                      {item['name']}
                    </div>
                    <div style="font-size:12px;color:#64748B">{item['why']}</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;color:#374151">
          <div style="font-family:'JetBrains Mono',monospace;font-size:28px;margin-bottom:12px">◌</div>
          <div style="font-size:13px;color:#64748B">No customer intelligence data for this business type.</div>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — SERVICES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_services:
    st.markdown('<div class="ryo-section-title">How Ryotech Can Help</div>', unsafe_allow_html=True)
    st.markdown('<div class="ryo-section-sub">Services matched to this site\'s specific issues</div>', unsafe_allow_html=True)

    svc_colors = {
        "critical": "#F43F5E",
        "medium":   "#F59E0B",
        "low":      "#3B82F6",
    }
    svc_tag = {"critical": "HIGH PRIORITY", "medium": "MEDIUM", "low": "LOW"}

    if services:
        top = services[:3]
        svc_cols = st.columns(3)
        for i, svc in enumerate(top):
            sev = svc.get("severity", "medium")
            color = svc_colors.get(sev, "#3B82F6")
            tag = svc_tag.get(sev, "")
            with svc_cols[i]:
                st.markdown(f"""
                <div class="ryo-service" style="border-top:2px solid {color}">
                  <div style="font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:600;
                    color:{color};letter-spacing:0.1em;margin-bottom:12px">{tag}</div>
                  <div style="font-size:15px;font-weight:700;color:#0F172A;
                    margin-bottom:8px;letter-spacing:-0.01em">{svc['service']}</div>
                  <div style="font-size:12px;color:#64748B;margin-bottom:14px;line-height:1.6">
                    {svc.get('description','')}
                  </div>
                  <div style="font-size:12px;color:#1D4ED8;font-style:italic">
                    → {svc.get('outcome','')}
                  </div>
                </div>
                """, unsafe_allow_html=True)

        remaining = services[3:]
        if remaining:
            st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
            for svc in remaining:
                sev = svc.get("severity", "low")
                color = svc_colors.get(sev, "#3B82F6")
                tag = svc_tag.get(sev, "")
                col_sn, col_out, col_tg = st.columns([3, 3, 1])
                with col_sn:
                    st.markdown(f"""
                    <div style="background:#FFFFFF;border:1px solid #CBD5E1;
                      border-radius:0;padding:12px 16px">
                      <div style="font-size:13px;font-weight:600;color:#1E293B;margin-bottom:3px">
                        {svc['service']}
                      </div>
                      <div style="font-size:11px;color:#64748B">
                        {svc.get('triggered_by','')[:60]}{'…' if len(svc.get('triggered_by',''))>60 else ''}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_out:
                    st.markdown(f"""
                    <div style="background:#FFFFFF;border:1px solid #CBD5E1;
                      border-radius:0;padding:12px 16px;
                      font-size:12px;color:#1D4ED8;font-style:italic">→ {svc.get('outcome','')}</div>
                    """, unsafe_allow_html=True)
                with col_tg:
                    st.markdown(f"""
                    <div style="background:#FFFFFF;border:1px solid #CBD5E1;
                      border-radius:0;padding:12px 16px;text-align:center">
                      <span style="font-family:'JetBrains Mono',monospace;font-size:9px;
                        font-weight:600;color:{color};letter-spacing:0.08em">{tag}</span>
                    </div>
                    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6 — OUTREACH EMAIL
# ═══════════════════════════════════════════════════════════════════════════════
with tab_email:
    st.markdown('<div class="ryo-section-title">Personalised Outreach Email</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="background:#F1F5F9;border:1px solid #CBD5E1;
      border-radius:0;padding:10px 16px;margin-bottom:20px;
      font-size:12px;color:#64748B">
      Written specifically for
      <span style="color:#1D4ED8;font-weight:600">{audit['business_name']}</span>
      ({btype_label}) — copy and send directly.
    </div>
    """, unsafe_allow_html=True)

    email_text = audit.get("outreach_email", "")
    st.text_area("", value=email_text, height=280, key="email_box", label_visibility="collapsed")

    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

    col_dl, col_hint = st.columns([1, 2])
    with col_dl:
        from report_generator import generate_report
        html_report = generate_report(audit)
        st.download_button(
            label="↓  Download HTML Report",
            data=html_report.encode("utf-8"),
            file_name=f"{audit['domain'].replace('.','_')}_ryotech_audit.html",
            mime="text/html",
            use_container_width=True
        )
    with col_hint:
        st.markdown("""
        <div style="font-size:12px;color:#64748B;padding-top:10px">
          Open in Chrome →
          <span style="font-family:'JetBrains Mono',monospace;background:#FFFFFF;
            border:1px solid #CBD5E1;padding:1px 6px;border-radius:0;
            font-size:11px;color:#475569">Cmd+P</span>
          → Save as PDF
        </div>
        """, unsafe_allow_html=True)
