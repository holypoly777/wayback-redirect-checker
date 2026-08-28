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
    .stApp {
        background:
          radial-gradient(circle at top left, rgba(78,91,255,.10), transparent 32%),
          radial-gradient(circle at top right, rgba(176,70,255,.08), transparent 30%),
          #0b1020;
        color: #f5f7ff;
    }

    .block-container {
        max-width: 1240px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    h1, h2, h3 {
        letter-spacing: -0.02em;
    }

    [data-testid="stTextInput"] input {
        background: #12182b;
        border: 1px solid #2e3a63;
        border-radius: 12px;
        color: #fff;
        min-height: 48px;
    }

    [data-testid="stTextInput"] input:focus {
        border-color: #6f7cff;
        box-shadow: 0 0 0 1px #6f7cff;
    }

    .hero {
        padding: 22px 24px;
        border: 1px solid rgba(116,130,255,.25);
        border-radius: 18px;
        background: linear-gradient(180deg, rgba(20,27,48,.94), rgba(13,18,33,.94));
        margin-bottom: 18px;
        box-shadow: 0 18px 60px rgba(0,0,0,.16);
    }

    .hero-title {
        font-size: 2.1rem;
        font-weight: 800;
        margin: 0;
        background: linear-gradient(90deg,#77a7ff,#8b7cff,#b772ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-sub {
        margin-top: 8px;
        color: #aeb7d0;
        font-size: .98rem;
    }

    .scan-card {
        border: 1px solid rgba(116,130,255,.22);
        background: rgba(16,23,42,.86);
        border-radius: 16px;
        padding: 16px 18px;
        min-height: 132px;
    }

    .scan-card-primary {
        border: 1px solid rgba(111,124,255,.72);
        background: linear-gradient(135deg,rgba(46,55,115,.48),rgba(35,27,76,.38));
        box-shadow: inset 0 0 0 1px rgba(111,124,255,.12);
    }

    .badge {
        display: inline-block;
        font-size: .72rem;
        font-weight: 700;
        padding: 4px 9px;
        border-radius: 999px;
        margin-left: 7px;
        vertical-align: middle;
    }

    .badge-recommended {
        background: rgba(116,130,255,.16);
        color: #aeb6ff;
        border: 1px solid rgba(116,130,255,.35);
    }

    .metric-card {
        border: 1px solid rgba(111,124,255,.18);
        border-radius: 14px;
        padding: 14px;
        background: rgba(14,20,36,.82);
    }

    div[data-testid="stMetric"] {
        background: rgba(14,20,36,.72);
        border: 1px solid rgba(111,124,255,.18);
        padding: 16px;
        border-radius: 14px;
    }

    div[data-testid="stMetricLabel"] {
        color: #9ca8c7;
    }

    .evidence {
        border: 1px solid rgba(255,86,108,.35);
        border-radius: 16px;
        padding: 18px;
        background: linear-gradient(180deg,rgba(72,20,34,.40),rgba(30,15,22,.55));
        margin: 12px 0;
    }

    .footer-note {
        color: #7e88a7;
        text-align: center;
        font-size: .82rem;
        margin-top: 26px;
    }

    div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg,#5868ff,#7b5cff);
        border: none;
        border-radius: 12px;
        min-height: 48px;
        font-weight: 700;
    }

    div.stButton > button[kind="primary"]:hover {
        filter: brightness(1.08);
    }

    [data-testid="stDownloadButton"] button,
    [data-testid="stLinkButton"] a {
        border-radius: 11px !important;
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

c1, c2 = st.columns(2)

with c1:
    st.markdown(
        """
        <div class="scan-card scan-card-primary">
          <div style="font-size:1.05rem;font-weight:800;">
            🔍 Full Scan <span class="badge badge-recommended">แนะนำ</span>
          </div>
          <div style="margin-top:8px;color:#aeb7d0;">
            ตรวจทุก 3xx capture ของ Domain และเก็บ Cross-domain ทุกเหตุการณ์
          </div>
          <div style="margin-top:8px;color:#7f8bab;font-size:.88rem;">
            แม่นยำที่สุด · ใช้เวลามากกว่า
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        """
        <div class="scan-card">
          <div style="font-size:1.05rem;font-weight:800;">⚡ Quick Scan</div>
          <div style="margin-top:8px;color:#aeb7d0;">
            ตรวจตัวอย่างสูงสุด 160 captures โดยเน้นช่วงล่าสุดและกระจายทั่ว timeline
          </div>
          <div style="margin-top:8px;color:#7f8bab;font-size:.88rem;">
            เร็วกว่า · เจอ Cross-domain แล้วหยุดทันที
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

mode = st.radio(
    "โหมด",
    ["Full Scan", "Quick Scan"],
    horizontal=True,
    index=0,
    label_visibility="collapsed",
)

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
