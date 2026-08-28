import csv
import html
import io
import re
import time
from urllib.parse import urlparse, unquote

import requests
import streamlit as st

CDX = "https://web.archive.org/cdx/search/cdx"
WAYBACK = "https://web.archive.org/web"
UA = "Mozilla/5.0 (Wayback Redirect Checker)"

st.set_page_config(
    page_title="Wayback Redirect Checker",
    page_icon="🔎",
    layout="wide",
)

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
        loc, re.I
    )
    return unquote(m.group(1)) if m else loc

def extract_target(text):
    if not text:
        return ""
    for pat in [
        r'Redirecting\s+to.*?(https?://[^\s<>"\']+)',
        r'Got an HTTP 30\d response.*?(https?://[^\s<>"\']+)',
    ]:
        m = re.search(pat, text, re.I | re.S)
        if m:
            return html.unescape(m.group(1)).rstrip(".,)")
    return ""

def inspect_capture(timestamp, original):
    candidates = [
        f"{WAYBACK}/{timestamp}id_/{original}",
        f"{WAYBACK}/{timestamp}/{original}",
    ]
    last_error = ""
    last_status = ""
    for replay in candidates:
        try:
            r = requests.get(
                replay,
                headers={"User-Agent": UA},
                timeout=20,
                allow_redirects=False,
            )
            last_status = r.status_code
            target = clean_location(r.headers.get("Location", ""))
            if not target:
                target = extract_target(r.text[:250000])
            if target:
                return target, replay, "", r.status_code
            last_error = f"HTTP {r.status_code}; no destination found"
        except Exception as e:
            last_error = str(e)
    return "", candidates[-1], last_error, last_status

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

@st.cache_data(ttl=600, show_spinner=False)
def get_captures(domain):
    params = {
        "url": domain,
        "output": "json",
        "fl": "timestamp,original,statuscode",
        "filter": "statuscode:3..",
        "matchType": "domain",
    }
    r = requests.get(CDX, params=params, headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    data = r.json()
    if not data or len(data) <= 1:
        return []
    header = data[0]
    rows = [dict(zip(header, row)) for row in data[1:]]
    seen, result = set(), []
    for row in rows:
        key = (row.get("timestamp"), row.get("original"), row.get("statuscode"))
        if key not in seen:
            seen.add(key)
            result.append(row)
    return sorted(result, key=lambda x: x.get("timestamp", ""))

def quick_sample(rows, limit=80):
    n = len(rows)
    if n <= limit:
        return rows
    indexes = {round(i * (n - 1) / (limit - 1)) for i in range(limit)}
    return [rows[i] for i in sorted(indexes)]

def evidence_url(ts, source):
    return f"{WAYBACK}/{ts}/{source}"

def scan(domain, full=False):
    rows = get_captures(domain)
    if not rows:
        return [], 0

    todo = rows if full else quick_sample(rows, 80)
    results = []
    progress = st.progress(0, text="กำลังตรวจ Wayback captures...")

    for i, row in enumerate(todo, 1):
        ts = row["timestamp"]
        source = row["original"]
        try:
            target, replay, error, replay_http = inspect_capture(ts, source)
        except Exception as e:
            target, replay, error, replay_http = "", "", str(e), ""

        kind = classify(source, target, domain)
        date = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"

        item = {
            "date": date,
            "timestamp": ts,
            "source": source,
            "archived_status": row.get("statuscode", ""),
            "target": target,
            "classification": kind,
            "evidence_url": evidence_url(ts, source),
            "replay_url": replay,
            "error": error,
        }
        results.append(item)

        progress.progress(i / len(todo), text=f"ตรวจ {i:,}/{len(todo):,}")

        # Quick mode: เจอ cross-domain แล้วหยุดทันที
        if not full and kind == "CROSS-DOMAIN":
            break

        time.sleep(0.08)

    progress.empty()
    return results, len(rows)

def to_csv_bytes(rows):
    output = io.StringIO()
    fields = [
        "date", "timestamp", "source", "archived_status",
        "target", "classification", "evidence_url",
        "replay_url", "error"
    ]
    w = csv.DictWriter(output, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return output.getvalue().encode("utf-8-sig")

st.title("🔎 Wayback Redirect Checker")
st.caption("ตรวจประวัติ HTTP 3xx และหา Cross-Domain Redirect จาก Internet Archive / Wayback Machine")

domain_input = st.text_input(
    "Domain",
    placeholder="เช่น idea.me หรือ ufa365.ltd",
)

mode = st.radio(
    "Scan mode",
    ["Quick Scan", "Full Scan"],
    horizontal=True,
    help="Quick ตรวจ sample สูงสุด 80 จุดทั่ว timeline / Full ตรวจ 3xx captures ทั้งหมด",
)

if st.button("เริ่มตรวจ", type="primary", use_container_width=True):
    domain = normalize_domain(domain_input)

    if not domain or "." not in domain:
        st.error("กรุณาใส่ Domain ให้ถูกต้อง เช่น idea.me")
    else:
        full = mode == "Full Scan"

        try:
            with st.spinner(f"กำลังโหลดประวัติ 3xx ของ {domain}..."):
                results, total = scan(domain, full=full)

            if total == 0:
                st.warning("ไม่พบ 3xx capture ใน Wayback Machine")
            else:
                cross = [x for x in results if x["classification"] == "CROSS-DOMAIN"]
                unknown = [x for x in results if x["classification"] == "UNKNOWN"]

                c1, c2, c3 = st.columns(3)
                c1.metric("3xx ทั้งหมด", f"{total:,}")
                c2.metric("ตรวจแล้ว", f"{len(results):,}")
                c3.metric("Cross-domain", f"{len(cross):,}")

                if cross:
                    st.error(f"🚨 พบ CROSS-DOMAIN REDIRECT {len(cross)} รายการ")

                    for x in cross:
                        with st.container(border=True):
                            st.subheader(f"{x['source']}  →  {x['target']}")
                            st.write(
                                f"**วันที่:** {x['date']}  |  "
                                f"**HTTP:** {x['archived_status']}"
                            )
                            st.link_button(
                                "🔗 เปิดหลักฐาน Wayback",
                                x["evidence_url"],
                            )
                            with st.expander("ดูรายละเอียด"):
                                st.code(x["evidence_url"], language=None)
                                st.write("Replay URL:")
                                st.code(x["replay_url"], language=None)
                else:
                    st.success("ยังไม่พบ Cross-domain จาก captures ที่ตรวจ")
                    if not full and total > len(results):
                        st.info(
                            "Quick Scan เป็นการสุ่มตัวอย่างทั่ว timeline "
                            "จึงยังไม่ใช่การยืนยันว่าไม่เคยมี Cross-domain "
                            "หากต้องการตรวจละเอียดให้ใช้ Full Scan"
                        )

                if unknown:
                    st.warning(
                        f"มี {len(unknown)} capture ที่อ่านปลายทางไม่ได้ (UNKNOWN)"
                    )

                with st.expander("ดูผลการตรวจทั้งหมด"):
                    st.dataframe(results, use_container_width=True)

                st.download_button(
                    "⬇️ ดาวน์โหลดผลเป็น CSV",
                    data=to_csv_bytes(results),
                    file_name=f"{domain}_wayback_redirects.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

        except requests.HTTPError as e:
            st.error(f"Wayback/CDX ตอบกลับผิดพลาด: {e}")
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")

st.divider()
st.caption(
    "หมายเหตุ: ข้อมูลขึ้นอยู่กับ captures ที่ Internet Archive เก็บไว้ "
    "และบาง snapshot อาจไม่สามารถ replay ได้"
)
