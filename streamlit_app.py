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
    --text: #182033;
    --muted: #667085;
    --line: #dde3ee;
    --blue: #2f5bd3;
    --blue2: #466ee8;
    --red: #ff4d57;
    --red2: #f32655;
    --amber: #f3a51f;
}

.stApp {
    background:
        radial-gradient(circle at 92% 4%, rgba(74,110,232,.10), transparent 22%),
        radial-gradient(circle at 7% 0%, rgba(120,93,220,.07), transparent 20%),
        linear-gradient(180deg, #fbfcff 0%, #f6f8fc 52%, #f4f6fa 100%);
    color: var(--text);
}

.block-container {
    max-width: 1180px;
    padding-top: 1.8rem;
    padding-bottom: 3rem;
}

h1,h2,h3,h4 {
    color: var(--text);
    letter-spacing: -.025em;
}

/* HERO */
.hero {
    position: relative;
    overflow: hidden;
    padding: 26px 28px;
    border: 1px solid #dfe5ef;
    border-radius: 20px;
    background: linear-gradient(135deg, rgba(255,255,255,.99), rgba(247,249,255,.97));
    box-shadow: 0 18px 45px rgba(33,48,90,.07);
    margin-bottom: 26px;
}
.hero::after {
    content:"";
    position:absolute;
    width:320px;
    height:220px;
    right:-100px;
    top:-120px;
    border-radius:50%;
    background: radial-gradient(circle, rgba(70,110,232,.17), transparent 68%);
}
.hero-title {
    position: relative;
    z-index: 1;
    font-size: 2rem;
    font-weight: 850;
    background: linear-gradient(90deg,#20439b,#466ee8,#7658d8);
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
}
.hero-sub {
    position: relative;
    z-index: 1;
    margin-top: 8px;
    color:#68748a;
}

/* DOMAIN */
.domain-shell {
    padding: 21px 22px 16px;
    border: 1px solid #dde4ef;
    border-radius: 17px;
    background: rgba(255,255,255,.94);
    box-shadow: 0 10px 26px rgba(33,48,90,.045);
    margin-bottom: 22px;
}
.domain-title {
    font-size: 1.15rem;
    font-weight: 800;
    color:#1c2740;
}
.domain-desc {
    color:#7a8496;
    font-size:.87rem;
    margin:5px 0 13px;
}

[data-testid="stTextInput"] input {
    background:#fff;
    color:#172033;
    min-height:50px;
    border:1px solid #cfd7e5;
    border-radius:11px;
    box-shadow:0 4px 12px rgba(35,50,90,.03);
}
[data-testid="stTextInput"] input:focus {
    border-color:#3f69df;
    box-shadow:0 0 0 4px rgba(63,105,223,.10);
}

/* MODE HEADING */
.mode-heading {
    display:flex;
    align-items:center;
    gap:10px;
    margin: 4px 0 13px;
}
.mode-icon {
    width:38px;height:38px;
    display:flex;align-items:center;justify-content:center;
    border-radius:10px;
    background:linear-gradient(145deg,#fff0f2,#ffe4e8);
    color:#ef4052;
    font-size:1.05rem;
}
.mode-title {
    font-weight:850;
    font-size:1.22rem;
    color:#1b263d;
}
.mode-sub {
    color:#798396;
    font-size:.84rem;
}

/* STREAMLIT BORDERED CONTAINERS USED AS SCAN CARDS */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius:16px !important;
    background:linear-gradient(145deg,#ffffff,#fbfcff) !important;
    border:1px solid #dfe5ee !important;
    box-shadow:0 9px 24px rgba(34,47,80,.045) !important;
    transition:transform .16s ease, box-shadow .16s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    transform:translateY(-2px);
    box-shadow:0 14px 30px rgba(34,47,80,.07) !important;
}

/* MODE BUTTONS */
div.stButton > button {
    border-radius:12px;
    min-height:50px;
    font-weight:800;
    transition:all .16s ease;
}
div.stButton > button[kind="secondary"] {
    background:linear-gradient(180deg,#ffffff,#f8faff);
    color:#26334d !important;
    border:1px solid #d4dce9;
    box-shadow:0 5px 13px rgba(35,49,85,.035);
}
div.stButton > button[kind="secondary"]:hover {
    border-color:#b9c5da;
    transform:translateY(-1px);
}

/* Selected scan mode + main CTA both use primary.
   High contrast is forced here. */
div.stButton > button[kind="primary"] {
    background:linear-gradient(90deg,#ff4d57 0%,#f32655 100%);
    border:none !important;
    color:#fff !important;
    box-shadow:0 10px 22px rgba(243,38,85,.18);
}
div.stButton > button[kind="primary"] *,
div.stButton > button[kind="primary"] p,
div.stButton > button[kind="primary"] span {
    color:#fff !important;
    -webkit-text-fill-color:#fff !important;
}
div.stButton > button[kind="primary"]:hover {
    filter:brightness(1.035);
    transform:translateY(-1px);
    box-shadow:0 14px 27px rgba(243,38,85,.22);
}

.scan-copy {
    padding: 2px 4px 5px;
    color:#516076;
    line-height:1.65;
    font-size:.92rem;
}
.scan-copy b {
    color:#29364d;
}
.scan-note {
    color:#858fa1;
    font-size:.82rem;
    margin-top:5px;
}
.recommend-badge {
    display:inline-block;
    padding:3px 8px;
    margin-left:5px;
    border-radius:999px;
    background:#ffe7ea;
    border:1px solid #ffd0d5;
    color:#e3384a;
    font-size:.72rem;
    font-weight:800;
}

/* SELECTED STATUS */
.selected-mode {
    display:inline-flex;
    align-items:center;
    gap:7px;
    padding:7px 11px;
    margin:10px 0 12px;
    border-radius:999px;
    background:linear-gradient(90deg,#fff0f2,#fff6f7);
    border:1px solid #ffd4d9;
    color:#d93b4c;
    font-size:.83rem;
    font-weight:800;
}

/* INFO / METRIC / RESULTS */
[data-testid="stAlert"] {
    border-radius:12px;
}
div[data-testid="stMetric"] {
    background:linear-gradient(145deg,#fff,#fbfcff);
    border:1px solid #e0e6ef;
    border-radius:14px;
    padding:16px;
    box-shadow:0 8px 20px rgba(32,45,81,.04);
}
div[data-testid="stMetricLabel"] { color:#6c768a; }
div[data-testid="stMetricValue"] { color:#172033; font-weight:800; }

.evidence {
    border:1px solid #efc8ce;
    border-left:4px solid #dd4858;
    border-radius:14px;
    padding:18px;
    background:linear-gradient(145deg,#fff,#fff6f7);
    margin:12px 0;
    box-shadow:0 10px 24px rgba(140,35,50,.05);
}
.evidence div { color:#293247 !important; }
.evidence div[style*="color:#ff8899"] { color:#c53c4c !important; }
.evidence div[style*="color:#9aa6c3"] { color:#747f91 !important; }

[data-testid="stExpander"] {
    background:#fff;
    border-color:#e0e6ee;
    border-radius:12px;
}
[data-testid="stDownloadButton"] button,
[data-testid="stLinkButton"] a {
    border-radius:10px !important;
}

.footer-note {
    color:#8a94a6;
    text-align:center;
    font-size:.82rem;
    margin-top:28px;
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

st.markdown(
    """
    <div class="domain-shell">
        <div class="domain-title">🌐 ตรวจสอบ Domain</div>
        <div class="domain-desc">กรอกชื่อ Domain ที่ต้องการตรวจสอบ เช่น idea.me หรือ footballgibraltar.com</div>
    </div>
    """,
    unsafe_allow_html=True,
)

domain_input = st.text_input(
    "Domain",
    placeholder="เช่น idea.me หรือ footballgibraltar.com",
    label_visibility="collapsed",
)

st.markdown(
    """
    <div class="mode-heading">
        <div class="mode-icon">🎯</div>
        <div>
            <div class="mode-title">เลือกโหมดการสแกน</div>
            <div class="mode-sub">เลือกโหมดที่เหมาะกับความต้องการของคุณ</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# เก็บโหมดที่เลือกไว้ใน session
if "scan_mode" not in st.session_state:
    st.session_state.scan_mode = "Full Scan"

full_col, quick_col = st.columns(2, gap="medium")

with full_col:
    with st.container(border=True):
        full_selected = st.session_state.scan_mode == "Full Scan"

        if st.button(
            "🔍 Full Scan  ·  แนะนำ",
            key="choose_full_scan",
            type="primary" if full_selected else "secondary",
            use_container_width=True,
            help="ตรวจทุก 3xx capture และเก็บ Cross-domain ทุกเหตุการณ์",
        ):
            st.session_state.scan_mode = "Full Scan"
            st.rerun()

        st.markdown(
            """
            <div class="scan-copy">
                ตรวจทุก 3xx capture ของ Domain และเก็บหลักฐาน
                <b>Cross-domain ทุกเหตุการณ์</b>
                <div class="scan-note">⭐ ละเอียดที่สุด · ใช้เวลามากกว่า</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with quick_col:
    with st.container(border=True):
        quick_selected = st.session_state.scan_mode == "Quick Scan"

        if st.button(
            "⚡ Quick Scan",
            key="choose_quick_scan",
            type="primary" if quick_selected else "secondary",
            use_container_width=True,
            help="ตรวจตัวอย่างสูงสุด 160 captures และหยุดเมื่อเจอ Cross-domain",
        ):
            st.session_state.scan_mode = "Quick Scan"
            st.rerun()

        st.markdown(
            """
            <div class="scan-copy">
                ตรวจตัวอย่างสูงสุด 160 captures โดยเน้นช่วงล่าสุด
                และกระจายทั่ว timeline
                <div class="scan-note">🕘 เร็วกว่า · เหมาะสำหรับเช็กเบื้องต้น</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

mode = st.session_state.scan_mode

if mode == "Full Scan":
    st.markdown(
        '<div class="selected-mode">✓ Full Scan เป็นโหมดที่เลือก · แนะนำสำหรับผลละเอียด</div>',
        unsafe_allow_html=True,
    )
    st.info("Full Scan จะตรวจทุก 3xx capture ที่ Wayback/CDX ส่งกลับมา")
else:
    st.markdown(
        '<div class="selected-mode">⚡ Quick Scan เป็นโหมดที่เลือก · ตรวจแบบเร็ว</div>',
        unsafe_allow_html=True,
    )
    st.info(
        "Quick Scan จะตรวจสูงสุด 160 captures หากไม่พบ Cross-domain "
        "แนะนำให้ใช้ Full Scan เพื่อยืนยัน"
    )

if st.button("🚀 เริ่มตรวจสอบ", type="primary", use_container_width=True):
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
