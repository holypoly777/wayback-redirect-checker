import csv
import html
import io
import re
import time
from urllib.parse import urlparse, unquote

import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# Wayback Redirect Checker - Polished UI
# Full Scan = recommended/default
# Quick Scan = secondary option
# ============================================================

CDX = "https://web.archive.org/cdx/search/cdx"
WAYBACK = "https://web.archive.org/web"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

st.set_page_config(
    page_title="Wayback Redirect Checker",
    page_icon="🔎",
    layout="wide",
)

# -------------------------
# Styling
# -------------------------

st.markdown(
    """
<style>
    :root {
        --bg: #f6f8fc;
        --surface: #ffffff;
        --surface-soft: #fbfcff;
        --text: #172033;
        --muted: #6b7589;
        --line: #dfe5ef;
        --blue: #315bc8;
        --blue-2: #6558db;
        --red: #ff4d57;
        --green: #18a56f;
        --amber: #d99012;
        --shadow: 0 10px 30px rgba(29, 42, 78, .06);
    }

    html, body, [class*="css"] {
        font-family: Inter, "Noto Sans Thai", system-ui, -apple-system, BlinkMacSystemFont,
                     "Segoe UI", sans-serif;
    }

    .stApp {
        background:
            radial-gradient(circle at 8% 0%, rgba(76,110,245,.08), transparent 24%),
            radial-gradient(circle at 96% 5%, rgba(123,92,246,.065), transparent 22%),
            linear-gradient(180deg, #fbfcff 0%, #f6f8fc 58%, #f4f6fa 100%);
        color: var(--text);
    }

    .block-container {
        max-width: 1120px;
        padding-top: 1.45rem;
        padding-bottom: 2.2rem;
    }

    h1, h2, h3, h4 {
        color: var(--text);
        letter-spacing: -.025em;
    }

    p, label, .stMarkdown {
        color: #2b354d;
    }

    /* ---------------- Hero ---------------- */
    .hero {
        position: relative;
        overflow: hidden;
        padding: 24px 26px;
        border: 1px solid rgba(205,214,230,.92);
        border-radius: 20px;
        background: linear-gradient(135deg, rgba(255,255,255,.99), rgba(247,249,255,.96));
        margin-bottom: 20px;
        box-shadow: var(--shadow);
    }

    .hero::after {
        content: "";
        position: absolute;
        width: 220px;
        height: 220px;
        right: -72px;
        top: -115px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(82,113,215,.14), transparent 70%);
        pointer-events: none;
    }

    .hero-title {
        position: relative;
        z-index: 1;
        margin: 0;
        font-size: 2rem;
        line-height: 1.15;
        font-weight: 850;
        background: linear-gradient(90deg, #22479f 0%, #4769d9 50%, #7558d7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-sub {
        position: relative;
        z-index: 1;
        margin-top: 8px;
        color: #6a7488;
        font-size: .95rem;
    }

    /* ---------------- Section label ---------------- */
    .section-kicker {
        margin: 2px 0 5px;
        font-size: 1.16rem;
        font-weight: 820;
        color: var(--text);
    }

    .section-sub {
        margin: 0 0 11px;
        color: #7a8498;
        font-size: .86rem;
    }

    /* ---------------- Domain input ---------------- */
    [data-testid="stTextInput"] input {
        min-height: 49px;
        border-radius: 12px;
        border: 1px solid #d5ddeb;
        background: linear-gradient(180deg, #ffffff, #fbfcff);
        color: var(--text);
        box-shadow: inset 0 1px 0 rgba(255,255,255,.9);
        transition: border-color .14s ease, box-shadow .14s ease;
    }

    [data-testid="stTextInput"] input:hover {
        border-color: #c7d1e5;
    }

    [data-testid="stTextInput"] input:focus {
        border-color: #5570d8;
        box-shadow: 0 0 0 4px rgba(85,112,216,.09);
        transform: none;
    }

    [data-testid="stTextInput"] input::placeholder {
        color: #9aa3b4;
    }

    /* ---------------- Scan mode cards ---------------- */
    .scan-mode-box div[data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid var(--line) !important;
        border-radius: 16px !important;
        background: linear-gradient(155deg, rgba(255,255,255,.99), rgba(249,251,255,.97)) !important;
        box-shadow:
            0 8px 20px rgba(32,45,81,.038),
            0 1px 2px rgba(32,45,81,.02) !important;
        transition: none !important;
        overflow: hidden !important;
        min-height: 152px;
    }

    .scan-mode-box.selected div[data-testid="stVerticalBlockBorderWrapper"] {
        border: 1.5px solid rgba(78,105,210,.80) !important;
        background: linear-gradient(145deg, #ffffff 0%, #f7f9ff 60%, #f2f5ff 100%) !important;
        box-shadow:
            0 11px 25px rgba(65,91,190,.075),
            inset 0 1px 0 rgba(255,255,255,.95) !important;
    }

    .scan-mode-box div[data-testid="stVerticalBlockBorderWrapper"]:hover,
    .scan-mode-box.selected div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: none !important;
        filter: none !important;
    }

    .scan-mode-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 1.04rem;
        font-weight: 820;
        color: #25304a;
    }

    .scan-mode-desc {
        margin-top: 9px;
        color: #5f6b80;
        font-size: .90rem;
        line-height: 1.55;
    }

    .scan-mode-meta {
        margin-top: 9px;
        color: #7c8699;
        font-size: .84rem;
    }

    .badge {
        display: inline-block;
        font-size: .70rem;
        font-weight: 780;
        padding: 4px 8px;
        border-radius: 999px;
        margin-left: 4px;
        vertical-align: middle;
    }

    .badge-recommended {
        background: linear-gradient(90deg, #edf2ff, #f3edff);
        color: #4058b8;
        border: 1px solid #cfdbff;
    }

    /* Tiny selector INSIDE card, no hover animation */
    .scan-radio-inside div.stButton {
        display: flex !important;
        justify-content: flex-end !important;
    }

    .scan-radio-inside div.stButton > button {
        width: 24px !important;
        min-width: 24px !important;
        height: 24px !important;
        min-height: 24px !important;
        padding: 0 !important;
        margin: 0 !important;
        border-radius: 999px !important;
        box-shadow: none !important;
        transition: none !important;
        font-size: 0 !important;
        line-height: 1 !important;
    }

    .scan-radio-inside div.stButton > button:hover,
    .scan-radio-inside div.stButton > button:focus,
    .scan-radio-inside div.stButton > button:active {
        transform: none !important;
        filter: none !important;
        box-shadow: none !important;
    }

    .scan-radio-inside div.stButton > button[kind="primary"] {
        position: relative !important;
        background: var(--red) !important;
        border: 1px solid var(--red) !important;
        color: transparent !important;
    }

    .scan-radio-inside div.stButton > button[kind="primary"]::after {
        content: "✓";
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        font-size: 13px;
        font-weight: 900;
    }

    .scan-radio-inside div.stButton > button[kind="secondary"] {
        background: #ffffff !important;
        border: 2px solid #d6deeb !important;
        color: transparent !important;
    }

    .scan-radio-inside div.stButton > button p,
    .scan-radio-inside div.stButton > button span {
        font-size: 0 !important;
        color: transparent !important;
        -webkit-text-fill-color: transparent !important;
    }

    /* ---------------- Mode note ---------------- */
    .mode-note {
        margin: 11px 0 14px;
        padding: 11px 13px;
        border-radius: 11px;
        border: 1px solid #d7e5ff;
        background: linear-gradient(180deg, #f5f9ff, #edf5ff);
        color: #3d5f9f;
        font-size: .86rem;
        line-height: 1.45;
    }

    .mode-note strong {
        color: #285ac7;
    }

    /* ---------------- Main button ---------------- */
    div.stButton > button[kind="primary"] {
        min-height: 49px;
        border: none;
        border-radius: 12px;
        background: linear-gradient(90deg, #315bc8 0%, #4f67dc 52%, #6d5bd9 100%);
        color: #ffffff;
        font-weight: 780;
        letter-spacing: .005em;
        box-shadow: 0 9px 20px rgba(64,82,190,.18);
        transition: none !important;
    }

    div.stButton > button[kind="primary"]:hover,
    div.stButton > button[kind="primary"]:focus {
        transform: none !important;
        filter: none !important;
        box-shadow: 0 9px 20px rgba(64,82,190,.18) !important;
        color: #ffffff !important;
    }

    /* ---------------- Alerts / metrics ---------------- */
    [data-testid="stAlert"] {
        border-radius: 12px;
        border-width: 1px;
        box-shadow: 0 4px 12px rgba(28,40,72,.028);
    }

    div[data-testid="stMetric"] {
        position: relative;
        overflow: hidden;
        padding: 15px 16px;
        border: 1px solid #e0e6ef;
        border-radius: 14px;
        background: linear-gradient(150deg, #ffffff 0%, #fbfcff 100%);
        box-shadow: 0 7px 18px rgba(32,45,81,.038);
    }

    div[data-testid="stMetricLabel"] {
        color: #6c768a;
        font-weight: 620;
    }

    div[data-testid="stMetricValue"] {
        color: var(--text);
        font-weight: 830;
    }

    /* ---------------- Evidence ---------------- */
    .evidence {
        position: relative;
        overflow: hidden;
        margin: 12px 0;
        padding: 18px;
        border: 1px solid #efc9cf;
        border-left: 4px solid #d94b5b;
        border-radius: 14px;
        background: linear-gradient(145deg, #fffefe 0%, #fff7f8 100%);
        box-shadow: 0 9px 22px rgba(140,35,50,.05);
    }

    .evidence div {
        color: #293247 !important;
    }

    .evidence div[style*="color:#ff8899"] {
        color: #c53c4c !important;
        font-weight: 700;
    }

    .evidence div[style*="color:#9aa6c3"] {
        color: #747f91 !important;
    }

    /* ---------------- Expanders / secondary actions ---------------- */
    [data-testid="stExpander"] {
        border-color: #e0e6ee;
        border-radius: 12px;
        background: linear-gradient(180deg, rgba(255,255,255,.97), rgba(250,251,254,.97));
        box-shadow: 0 4px 12px rgba(28,40,72,.022);
    }

    [data-testid="stDownloadButton"] button,
    [data-testid="stLinkButton"] a {
        border-radius: 10px !important;
        background: linear-gradient(180deg, #ffffff, #f8faff) !important;
        color: #26334d !important;
        border: 1px solid #d7deea !important;
        box-shadow: none !important;
        transition: none !important;
    }

    [data-testid="stDownloadButton"] button:hover,
    [data-testid="stLinkButton"] a:hover {
        transform: none !important;
        border-color: #c3cce0 !important;
        box-shadow: none !important;
    }

    .footer-note {
        color: #8a94a6;
        text-align: center;
        font-size: .80rem;
        margin-top: 25px;
        padding-top: 8px;
    }

    hr {
        border-color: #e7ebf2;
    }

    /* ---------------- Mobile ---------------- */
    @media (max-width: 768px) {
        .block-container {
            padding-top: .8rem;
            padding-left: .85rem;
            padding-right: .85rem;
        }

        .hero {
            padding: 20px 18px;
            border-radius: 16px;
            margin-bottom: 16px;
        }

        .hero-title {
            font-size: 1.62rem;
        }

        .hero-sub {
            font-size: .88rem;
        }

        .scan-mode-box div[data-testid="stVerticalBlockBorderWrapper"] {
            min-height: auto;
        }

        div[data-testid="stMetric"] {
            padding: 13px 14px;
        }
    }
</style>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# HTTP
# -------------------------

def make_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=2,
        backoff_factor=0.7,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers.update(HEADERS)
    return session

SESSION = make_session()

# -------------------------
# Helpers
# -------------------------

def normalize_domain(value):
    value = value.strip().lower()
    value = re.sub(r"^https?://", "", value)
    value = value.split("/")[0]
    return value.strip(".")

def hostname(url):
    try:
        h = (urlparse(url).hostname or "").lower().strip(".")
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""

def clean_location(loc):
    if not loc:
        return ""
    loc = html.unescape(loc).strip()
    m = re.search(
        r'(?:https?://web\.archive\.org)?/web/\d+(?:[a-z_]+)?/(https?://.+)$',
        loc,
        re.I,
    )
    return unquote(m.group(1)) if m else loc

def extract_target_from_page(text):
    if not text:
        return ""

    patterns = [
        r'Redirecting\s+to.*?(https?://[^\s<>"\']+)',
        r'Got an HTTP 30\d response.*?(https?://[^\s<>"\']+)',
        r'window\.location(?:\.href)?\s*=\s*["\'](https?://[^"\']+)',
        r'url\s*=\s*(https?://[^\s"\'<>]+)',
    ]

    for pat in patterns:
        m = re.search(pat, text, re.I | re.S)
        if m:
            return html.unescape(m.group(1)).rstrip(".,);")
    return ""

def evidence_url(timestamp, original):
    return f"{WAYBACK}/{timestamp}/{original}"

def inspect_capture(timestamp, original):
    candidates = [
        f"{WAYBACK}/{timestamp}id_/{original}",
        f"{WAYBACK}/{timestamp}/{original}",
        f"{WAYBACK}/{timestamp}if_/{original}",
    ]

    errors = []
    last_status = ""

    for replay in candidates:
        try:
            r = SESSION.get(
                replay,
                timeout=25,
                allow_redirects=False,
            )
            last_status = r.status_code

            target = clean_location(r.headers.get("Location", ""))

            if target and hostname(target) == "web.archive.org":
                target = ""

            if not target:
                target = extract_target_from_page(r.text[:350000])

            if target:
                return target, replay, "", r.status_code

            errors.append(f"{r.status_code}: no destination")

        except Exception as e:
            errors.append(str(e))

    return "", candidates[-1], " | ".join(errors), last_status

def classify(source, target, queried_domain):
    if not target:
        return "UNKNOWN"

    src = hostname(source)
    dst = hostname(target)
    q = queried_domain[4:] if queried_domain.startswith("www.") else queried_domain

    if not dst:
        return "INTERNAL" if target.startswith("/") else "UNKNOWN"

    if dst == src:
        return "SAME-DOMAIN"

    if dst == q or dst.endswith("." + q):
        return "INTERNAL"

    return "CROSS-DOMAIN"

# -------------------------
# CDX
# -------------------------

@st.cache_data(ttl=300, show_spinner=False)
def get_all_3xx_captures(domain):
    params = {
        "url": domain,
        "output": "json",
        "fl": "timestamp,original,statuscode",
        "filter": "statuscode:3..",
        "matchType": "domain",
    }

    r = requests.get(
        CDX,
        params=params,
        headers=HEADERS,
        timeout=60,
    )
    r.raise_for_status()

    data = r.json()

    if not data or len(data) <= 1:
        return []

    header = data[0]
    rows = [dict(zip(header, row)) for row in data[1:]]

    seen = set()
    result = []

    for row in rows:
        key = (
            row.get("timestamp"),
            row.get("original"),
            row.get("statuscode"),
        )
        if key not in seen:
            seen.add(key)
            result.append(row)

    result.sort(key=lambda x: x.get("timestamp", ""))
    return result

# -------------------------
# Scan plans
# -------------------------

def build_quick_order(captures, max_checks=160):
    """
    Quick Scan:
    - เน้น newest ก่อน
    - เก็บ oldest บางส่วน
    - กระจายตัวอย่างทั่ว timeline
    - เจอ cross-domain แล้วหยุดทันที
    """
    n = len(captures)

    if n <= max_checks:
        return list(reversed(captures))

    indexes = []
    seen = set()

    def add(i):
        if 0 <= i < n and i not in seen and len(indexes) < max_checks:
            seen.add(i)
            indexes.append(i)

    # newest 80
    for i in range(n - 1, max(-1, n - 81), -1):
        add(i)

    # oldest 20
    for i in range(min(20, n)):
        add(i)

    # evenly distributed remaining
    remaining = max_checks - len(indexes)
    if remaining > 0:
        for j in range(remaining):
            if remaining == 1:
                add(n // 2)
            else:
                add(round(j * (n - 1) / (remaining - 1)))

    return [captures[i] for i in indexes]

def scan(domain, mode):
    captures = get_all_3xx_captures(domain)

    if not captures:
        return [], 0

    full = mode == "Full Scan"

    if full:
        todo = captures
    else:
        todo = build_quick_order(captures, max_checks=160)

    results = []
    progress = st.progress(0, text="กำลังตรวจ Wayback captures...")
    status_box = st.empty()

    for i, row in enumerate(todo, 1):
        ts = row.get("timestamp", "")
        source = row.get("original", "")
        archived_status = row.get("statuscode", "")

        try:
            target, replay, error, replay_http = inspect_capture(ts, source)
        except Exception as e:
            target, replay, error, replay_http = "", "", str(e), ""

        kind = classify(source, target, domain)

        date = (
            f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            if len(ts) >= 8
            else ts
        )

        item = {
            "date": date,
            "timestamp": ts,
            "source": source,
            "archived_status": archived_status,
            "replay_http_status": replay_http,
            "target": target,
            "classification": kind,
            "evidence_url": evidence_url(ts, source),
            "replay_url": replay,
            "error": error,
        }

        results.append(item)

        progress.progress(
            i / len(todo),
            text=f"กำลังตรวจ {i:,}/{len(todo):,}"
        )

        status_box.caption(
            f"ล่าสุด: {date} · HTTP {archived_status} · {kind}"
        )

        if not full and kind == "CROSS-DOMAIN":
            break

        time.sleep(0.12)

    progress.empty()
    status_box.empty()

    return results, len(captures)

def to_csv_bytes(rows):
    output = io.StringIO()
    fields = [
        "date",
        "timestamp",
        "source",
        "archived_status",
        "replay_http_status",
        "target",
        "classification",
        "evidence_url",
        "replay_url",
        "error",
    ]

    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")

# ============================================================
# UI
# ============================================================

st.markdown(
    """
    <div class="hero">
      <div class="hero-title">🔎 Wayback Redirect Checker</div>
      <div class="hero-sub">
        ตรวจประวัติ HTTP 3xx และ Cross-Domain Redirect จาก Internet Archive / Wayback Machine
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-kicker">ตรวจสอบ Domain</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-sub">กรอก Domain ที่ต้องการตรวจสอบ เช่น example.com</div>',
    unsafe_allow_html=True,
)

domain_input = st.text_input(
    "Domain",
    placeholder="เช่น idea.me หรือ footballgibraltar.com",
    label_visibility="collapsed",
)

st.markdown('<div class="section-kicker" style="margin-top:14px;">เลือกโหมดการสแกน</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-sub">เลือกตามความละเอียดที่ต้องการ — Full Scan เหมาะสำหรับการตรวจยืนยัน</div>',
    unsafe_allow_html=True,
)

if "scan_mode" not in st.session_state:
    st.session_state.scan_mode = "Full Scan"

c1, c2 = st.columns(2, gap="medium")

with c1:
    full_selected = st.session_state.scan_mode == "Full Scan"
    st.markdown(
        f'<div class="scan-mode-box {"selected" if full_selected else ""}">',
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        text_col, select_col = st.columns([9, 1], vertical_alignment="top")

        with text_col:
            st.markdown(
                """
                <div class="scan-mode-title">
                    🔍 Full Scan <span class="badge badge-recommended">แนะนำ</span>
                </div>
                <div class="scan-mode-desc">
                    ตรวจทุก 3xx capture ของ Domain และเก็บ Cross-domain ทุกเหตุการณ์
                </div>
                <div class="scan-mode-meta">
                    ⭐ ละเอียดที่สุด · เหมาะสำหรับตรวจยืนยัน
                </div>
                """,
                unsafe_allow_html=True,
            )

        with select_col:
            st.markdown('<div class="scan-radio-inside">', unsafe_allow_html=True)
            if st.button(
                " ",
                key="scan_full_inside",
                type="primary" if full_selected else "secondary",
                help="เลือก Full Scan",
            ):
                st.session_state.scan_mode = "Full Scan"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with c2:
    quick_selected = st.session_state.scan_mode == "Quick Scan"
    st.markdown(
        f'<div class="scan-mode-box {"selected" if quick_selected else ""}">',
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        text_col, select_col = st.columns([9, 1], vertical_alignment="top")

        with text_col:
            st.markdown(
                """
                <div class="scan-mode-title">
                    ⚡ Quick Scan
                </div>
                <div class="scan-mode-desc">
                    ตรวจตัวอย่างสูงสุด 160 captures โดยเน้นช่วงล่าสุดและกระจายทั่ว timeline
                </div>
                <div class="scan-mode-meta">
                    🕘 เร็วกว่า · เหมาะสำหรับเช็กเบื้องต้น
                </div>
                """,
                unsafe_allow_html=True,
            )

        with select_col:
            st.markdown('<div class="scan-radio-inside">', unsafe_allow_html=True)
            if st.button(
                " ",
                key="scan_quick_inside",
                type="primary" if quick_selected else "secondary",
                help="เลือก Quick Scan",
            ):
                st.session_state.scan_mode = "Quick Scan"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

mode = st.session_state.scan_mode

if mode == "Full Scan":
    st.markdown(
        '<div class="mode-note">ℹ️ <strong>Full Scan กำลังใช้งาน</strong> — ตรวจทุก 3xx capture ที่ Wayback/CDX ส่งกลับมา</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="mode-note">⚡ <strong>Quick Scan กำลังใช้งาน</strong> — เหมาะสำหรับเช็กเบื้องต้น; หากไม่พบ Cross-domain ควรใช้ Full Scan เพื่อยืนยัน</div>',
        unsafe_allow_html=True,
    )

if st.button("🔎 เริ่มตรวจสอบ Domain", type="primary", use_container_width=True):
    domain = normalize_domain(domain_input)

    if not domain or "." not in domain:
        st.error("กรุณาใส่ Domain ให้ถูกต้อง เช่น footballgibraltar.com")

    else:
        try:
            with st.spinner(f"กำลังโหลดประวัติ 3xx ของ {domain}..."):
                results, total = scan(domain, mode)

            if total == 0:
                st.warning("ไม่พบ 3xx capture ใน Wayback Machine")

            else:
                cross = [x for x in results if x["classification"] == "CROSS-DOMAIN"]
                unknown = [x for x in results if x["classification"] == "UNKNOWN"]
                successful = len(results) - len(unknown)

                st.markdown("### สรุปผลการตรวจ")

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("3xx ทั้งหมด", f"{total:,}")
                m2.metric("ตรวจแล้ว", f"{len(results):,}")
                m3.metric("Cross-domain", f"{len(cross):,}")
                m4.metric("UNKNOWN", f"{len(unknown):,}")

                if cross:
                    st.error(f"🚨 พบ CROSS-DOMAIN REDIRECT {len(cross):,} รายการ")

                    for x in cross:
                        st.markdown(
                            f"""
                            <div class="evidence">
                              <div style="font-weight:800;font-size:1.05rem;">
                                {html.escape(x['source'])}
                              </div>
                              <div style="margin:7px 0;color:#ff8899;">↓ REDIRECT</div>
                              <div style="font-weight:800;font-size:1.05rem;">
                                {html.escape(x['target'])}
                              </div>
                              <div style="margin-top:10px;color:#9aa6c3;">
                                วันที่ {x['date']} · Archived HTTP {x['archived_status']}
                              </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        st.link_button(
                            "🔗 เปิดหลักฐาน Wayback",
                            x["evidence_url"],
                            use_container_width=True,
                        )

                        with st.expander("ดูรายละเอียดทางเทคนิค"):
                            st.write("Evidence URL")
                            st.code(x["evidence_url"], language=None)
                            st.write("Replay URL")
                            st.code(x["replay_url"], language=None)
                            if x["error"]:
                                st.write("Error / fallback info")
                                st.code(x["error"], language=None)

                else:
                    st.success("ไม่พบ Cross-domain จาก captures ที่ตรวจสำเร็จ")

                    if mode == "Quick Scan" and total > len(results):
                        st.info(
                            f"Quick Scan ตรวจ {len(results):,} จากทั้งหมด {total:,} captures "
                            "หากต้องการยืนยันให้ใช้ Full Scan"
                        )

                if unknown:
                    ratio = len(unknown) / max(1, len(results))
                    if ratio >= 0.5:
                        st.warning(
                            f"⚠️ UNKNOWN สูง: {len(unknown):,}/{len(results):,} "
                            "Wayback replay อ่านปลายทางไม่ได้หลายรายการ "
                            "ผล 'ไม่พบ' ยังไม่ควรถือเป็นข้อสรุป"
                        )
                    else:
                        st.warning(
                            f"มี {len(unknown):,} capture ที่อ่านปลายทางไม่ได้ (UNKNOWN)"
                        )

                with st.expander(f"ดูรายละเอียดการตรวจทั้งหมด ({len(results):,} รายการ)"):
                    st.dataframe(
                        results,
                        use_container_width=True,
                        hide_index=True,
                    )

                st.download_button(
                    "⬇️ ดาวน์โหลดผลเป็น CSV",
                    data=to_csv_bytes(results),
                    file_name=f"{domain}_wayback_redirects.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        except requests.HTTPError as e:
            st.error(f"Wayback/CDX ตอบกลับผิดพลาด: {e}")

        except requests.ConnectionError as e:
            st.error(
                "เชื่อมต่อ Wayback ไม่สำเร็จจาก Server นี้ "
                f"({e})"
            )

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")

st.markdown(
    """
    <div class="footer-note">
      ข้อมูลมาจาก Internet Archive / Wayback Machine ·
      บาง snapshot อาจ replay ไม่ได้หรือถูกจำกัด request ชั่วคราว
    </div>
    """,
    unsafe_allow_html=True,
)
