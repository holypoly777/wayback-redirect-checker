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
    /* =========================================================
       Premium Light UI
       Clean + subtle gradient + depth + modern UX
       ========================================================= */

    .stApp {
        background:
            radial-gradient(circle at 10% 0%, rgba(76, 110, 245, .10), transparent 24%),
            radial-gradient(circle at 92% 8%, rgba(141, 96, 255, .08), transparent 22%),
            linear-gradient(180deg, #fbfcff 0%, #f6f8fc 48%, #f4f6fa 100%);
        color: #172033;
    }

    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    h1, h2, h3, h4 {
        color: #172033;
        letter-spacing: -0.025em;
    }

    p, label, .stMarkdown {
        color: #27324a;
    }

    /* -------------------------
       Header / Hero
       ------------------------- */

    .hero {
        position: relative;
        overflow: hidden;
        padding: 26px 28px;
        border: 1px solid rgba(205, 214, 230, .92);
        border-radius: 20px;
        background:
            linear-gradient(135deg, rgba(255,255,255,.98), rgba(247,249,255,.94));
        margin-bottom: 24px;
        box-shadow:
            0 18px 45px rgba(34, 49, 91, .07),
            0 2px 8px rgba(34, 49, 91, .03);
        backdrop-filter: blur(10px);
    }

    .hero::before {
        content: "";
        position: absolute;
        width: 260px;
        height: 260px;
        right: -90px;
        top: -125px;
        border-radius: 50%;
        background:
            radial-gradient(circle, rgba(93, 108, 255, .20), rgba(93, 108, 255, 0) 68%);
        pointer-events: none;
    }

    .hero::after {
        content: "";
        position: absolute;
        width: 180px;
        height: 180px;
        left: -80px;
        bottom: -120px;
        border-radius: 50%;
        background:
            radial-gradient(circle, rgba(140, 87, 255, .10), rgba(140, 87, 255, 0) 70%);
        pointer-events: none;
    }

    .hero-title {
        position: relative;
        z-index: 1;
        font-size: 2.05rem;
        font-weight: 850;
        margin: 0;
        background: linear-gradient(90deg, #22479f 0%, #4769d9 48%, #7d55d9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-sub {
        position: relative;
        z-index: 1;
        margin-top: 9px;
        color: #667085;
        font-size: .98rem;
    }

    /* -------------------------
       Domain input
       ------------------------- */

    [data-testid="stTextInput"] input {
        background:
            linear-gradient(180deg, #ffffff, #fbfcff);
        border: 1px solid #d8dfeb;
        border-radius: 12px;
        color: #172033;
        min-height: 50px;
        box-shadow:
            inset 0 1px 0 rgba(255,255,255,.85),
            0 4px 12px rgba(35, 50, 90, .035);
        transition: all .18s ease;
    }

    [data-testid="stTextInput"] input:hover {
        border-color: #c7d1e5;
    }

    [data-testid="stTextInput"] input:focus {
        border-color: #5570d8;
        box-shadow:
            0 0 0 4px rgba(85,112,216,.10),
            0 8px 18px rgba(35, 50, 90, .05);
        transform: translateY(-1px);
    }

    [data-testid="stTextInput"] input::placeholder {
        color: #929bad;
    }

    /* -------------------------
       Scan cards
       ------------------------- */

    .scan-card {
        position: relative;
        overflow: hidden;
        border: 1px solid #dfe5ef;
        background:
            linear-gradient(155deg, rgba(255,255,255,.98), rgba(248,250,255,.94));
        border-radius: 16px;
        padding: 18px 19px;
        min-height: 138px;
        box-shadow:
            0 8px 22px rgba(32, 45, 81, .045),
            0 1px 2px rgba(32, 45, 81, .02);
        transition:
            transform .18s ease,
            box-shadow .18s ease,
            border-color .18s ease;
    }

    .scan-card:hover {
        transform: translateY(-2px);
        border-color: #cbd5e7;
        box-shadow:
            0 14px 28px rgba(32, 45, 81, .07),
            0 2px 5px rgba(32, 45, 81, .03);
    }

    .scan-card::after {
        content: "";
        position: absolute;
        width: 110px;
        height: 110px;
        right: -45px;
        top: -42px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(82,113,215,.08), transparent 68%);
        pointer-events: none;
    }

    .scan-card-primary {
        border: 1.5px solid rgba(78, 105, 210, .78);
        background:
            linear-gradient(145deg, #ffffff 0%, #f7f9ff 58%, #f2f5ff 100%);
        box-shadow:
            0 12px 28px rgba(65, 91, 190, .09),
            inset 0 1px 0 rgba(255,255,255,.95);
    }

    .scan-card-primary::before {
        content: "";
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 4px;
        background: linear-gradient(180deg, #5271d7, #745de1);
        border-radius: 16px 0 0 16px;
    }

    .scan-card div {
        color: #25304a !important;
    }

    .scan-card div[style*="color:#aeb7d0"] {
        color: #5f6b80 !important;
    }

    .scan-card div[style*="color:#7f8bab"] {
        color: #7c8699 !important;
    }

    .badge {
        display: inline-block;
        font-size: .72rem;
        font-weight: 750;
        padding: 4px 9px;
        border-radius: 999px;
        margin-left: 7px;
        vertical-align: middle;
    }

    .badge-recommended {
        background:
            linear-gradient(90deg, #edf2ff, #f3edff);
        color: #4058b8;
        border: 1px solid #cfdbff;
        box-shadow: 0 2px 6px rgba(75, 95, 180, .06);
    }

    /* -------------------------
       Radio
       ------------------------- */

    [data-testid="stRadio"] {
        background: transparent;
    }

    [data-testid="stRadio"] label {
        color: #25304a !important;
        font-weight: 550;
    }

    /* -------------------------
       Main button
       ------------------------- */

    div.stButton > button[kind="primary"] {
        background:
            linear-gradient(90deg, #315bc8 0%, #4f67dc 52%, #6d5bd9 100%);
        color: #ffffff;
        border: none;
        border-radius: 12px;
        min-height: 50px;
        font-weight: 750;
        letter-spacing: .01em;
        box-shadow:
            0 10px 22px rgba(64, 82, 190, .20),
            inset 0 1px 0 rgba(255,255,255,.25);
        transition: all .18s ease;
    }

    div.stButton > button[kind="primary"]:hover {
        filter: brightness(1.035);
        transform: translateY(-1px);
        box-shadow:
            0 14px 28px rgba(64, 82, 190, .24),
            inset 0 1px 0 rgba(255,255,255,.28);
        color: #ffffff;
    }

    div.stButton > button[kind="primary"]:active {
        transform: translateY(0px);
    }

    /* -------------------------
       Info / Alerts
       ------------------------- */

    [data-testid="stAlert"] {
        border-radius: 13px;
        box-shadow: 0 5px 14px rgba(28, 40, 72, .035);
        border-width: 1px;
    }

    /* -------------------------
       Metric cards
       ------------------------- */

    div[data-testid="stMetric"] {
        position: relative;
        overflow: hidden;
        background:
            linear-gradient(150deg, #ffffff 0%, #fbfcff 100%);
        border: 1px solid #e0e6ef;
        padding: 17px;
        border-radius: 15px;
        box-shadow:
            0 8px 22px rgba(32, 45, 81, .045),
            0 1px 2px rgba(32, 45, 81, .02);
    }

    div[data-testid="stMetric"]::after {
        content: "";
        position: absolute;
        width: 70px;
        height: 70px;
        top: -35px;
        right: -30px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(75,105,210,.08), transparent 70%);
        pointer-events: none;
    }

    div[data-testid="stMetricLabel"] {
        color: #6c768a;
        font-weight: 600;
    }

    div[data-testid="stMetricValue"] {
        color: #172033;
        font-weight: 800;
    }

    /* -------------------------
       Cross-domain evidence
       ------------------------- */

    .evidence {
        position: relative;
        overflow: hidden;
        border: 1px solid #efc9cf;
        border-left: 4px solid #d94b5b;
        border-radius: 14px;
        padding: 19px;
        background:
            linear-gradient(145deg, #fffefe 0%, #fff7f8 100%);
        margin: 13px 0;
        box-shadow:
            0 10px 24px rgba(140, 35, 50, .055);
    }

    .evidence::after {
        content: "";
        position: absolute;
        width: 120px;
        height: 120px;
        right: -55px;
        top: -55px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(217,75,91,.10), transparent 68%);
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

    /* -------------------------
       Expanders / Table
       ------------------------- */

    [data-testid="stExpander"] {
        background:
            linear-gradient(180deg, rgba(255,255,255,.96), rgba(250,251,254,.96));
        border-color: #e0e6ee;
        border-radius: 13px;
        box-shadow: 0 5px 14px rgba(28, 40, 72, .025);
    }

    /* -------------------------
       Secondary buttons
       ------------------------- */

    [data-testid="stDownloadButton"] button,
    [data-testid="stLinkButton"] a {
        border-radius: 11px !important;
        background:
            linear-gradient(180deg, #ffffff, #f8faff) !important;
        color: #26334d !important;
        border: 1px solid #d7deea !important;
        box-shadow: 0 4px 10px rgba(31, 46, 84, .035);
        transition: all .16s ease;
    }

    [data-testid="stDownloadButton"] button:hover,
    [data-testid="stLinkButton"] a:hover {
        border-color: #bbc7df !important;
        transform: translateY(-1px);
        box-shadow: 0 8px 16px rgba(31, 46, 84, .055);
    }

    /* -------------------------
       Footer
       ------------------------- */

    .footer-note {
        color: #8a94a6;
        text-align: center;
        font-size: .82rem;
        margin-top: 30px;
        padding-top: 8px;
    }

    hr {
        border-color: #e7ebf2;
    }
    
    /* =========================================================
       Scan selector UX — controls stay INSIDE each card
       No hover animation / no separate radio row
       ========================================================= */

    .scan-choice-label {
        font-size: 1.05rem;
        font-weight: 800;
        color: #25304a;
        margin-bottom: 4px;
    }

    .scan-choice-copy {
        color: #5f6b80;
        line-height: 1.62;
        font-size: .92rem;
        min-height: 74px;
    }

    .scan-choice-meta {
        color: #7c8699;
        font-size: .84rem;
        margin-top: 8px;
    }

    .scan-choice-selected {
        display: inline-block;
        padding: 4px 9px;
        border-radius: 999px;
        background: linear-gradient(90deg, #edf2ff, #f3edff);
        color: #4058b8;
        border: 1px solid #cfdbff;
        font-size: .72rem;
        font-weight: 800;
        margin-left: 6px;
    }

    /* Bordered Streamlit containers become the scan cards */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 16px !important;
        background: linear-gradient(155deg, rgba(255,255,255,.98), rgba(248,250,255,.94)) !important;
        border: 1px solid #dfe5ef !important;
        box-shadow:
            0 8px 22px rgba(32,45,81,.045),
            0 1px 2px rgba(32,45,81,.02) !important;
        transition: none !important;
    }

    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: none !important;
        border-color: #dfe5ef !important;
        box-shadow:
            0 8px 22px rgba(32,45,81,.045),
            0 1px 2px rgba(32,45,81,.02) !important;
    }

    /* Buttons inside scan cards */
    .scan-select-button div.stButton > button {
        min-height: 44px !important;
        border-radius: 11px !important;
        font-weight: 800 !important;
        box-shadow: none !important;
        transition: none !important;
    }

    .scan-select-button div.stButton > button:hover {
        transform: none !important;
        filter: none !important;
    }

    /* Unselected */
    .scan-select-button div.stButton > button[kind="secondary"] {
        background: #ffffff !important;
        color: #25304a !important;
        border: 1px solid #d7deea !important;
    }

    .scan-select-button div.stButton > button[kind="secondary"] *,
    .scan-select-button div.stButton > button[kind="secondary"] p,
    .scan-select-button div.stButton > button[kind="secondary"] span {
        color: #25304a !important;
        -webkit-text-fill-color: #25304a !important;
    }

    /* Selected */
    .scan-select-button div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #315bc8 0%, #4f67dc 52%, #6d5bd9 100%) !important;
        color: #ffffff !important;
        border: none !important;
    }

    .scan-select-button div.stButton > button[kind="primary"] *,
    .scan-select-button div.stButton > button[kind="primary"] p,
    .scan-select-button div.stButton > button[kind="primary"] span {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
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

st.subheader("ตรวจสอบ Domain")

domain_input = st.text_input(
    "Domain",
    placeholder="เช่น idea.me หรือ footballgibraltar.com",
    label_visibility="collapsed",
)

st.markdown("#### เลือกโหมดการสแกน")

if "scan_mode" not in st.session_state:
    st.session_state.scan_mode = "Full Scan"

c1, c2 = st.columns(2, gap="medium")

with c1:
    with st.container(border=True):
        st.markdown(
            """
            <div class="scan-choice-label">
                🔍 Full Scan
                <span class="scan-choice-selected">แนะนำ</span>
            </div>
            <div class="scan-choice-copy">
                ตรวจทุก 3xx capture ของ Domain และเก็บ Cross-domain ทุกเหตุการณ์
                <div class="scan-choice-meta">แม่นยำที่สุด · ใช้เวลามากกว่า</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="scan-select-button">', unsafe_allow_html=True)
        full_selected = st.session_state.scan_mode == "Full Scan"
        if st.button(
            "✓ Full Scan" if full_selected else "○ เลือก Full Scan",
            key="select_full_scan",
            type="primary" if full_selected else "secondary",
            use_container_width=True,
        ):
            st.session_state.scan_mode = "Full Scan"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

with c2:
    with st.container(border=True):
        st.markdown(
            """
            <div class="scan-choice-label">⚡ Quick Scan</div>
            <div class="scan-choice-copy">
                ตรวจตัวอย่างสูงสุด 160 captures โดยเน้นช่วงล่าสุดและกระจายทั่ว timeline
                <div class="scan-choice-meta">เร็วกว่า · เจอ Cross-domain แล้วหยุดทันที</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="scan-select-button">', unsafe_allow_html=True)
        quick_selected = st.session_state.scan_mode == "Quick Scan"
        if st.button(
            "✓ Quick Scan" if quick_selected else "○ เลือก Quick Scan",
            key="select_quick_scan",
            type="primary" if quick_selected else "secondary",
            use_container_width=True,
        ):
            st.session_state.scan_mode = "Quick Scan"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

mode = st.session_state.scan_mode

if mode == "Full Scan":
    st.info("Full Scan เป็นโหมดแนะนำ: ตรวจทุก 3xx capture ที่ Wayback/CDX ส่งกลับมา")
else:
    st.caption(
        "Quick Scan เหมาะสำหรับเช็กเบื้องต้น หากไม่พบ Cross-domain "
        "ยังควรใช้ Full Scan เพื่อยืนยัน"
    )

if st.button("เริ่มตรวจสอบ", type="primary", use_container_width=True):
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
