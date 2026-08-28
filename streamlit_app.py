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
# Wayback Redirect Checker - Streamlit FULL ONLY
# ใช้ redirect engine เดียวกับเวอร์ชัน IDLE และปรับ Quick Scan
# ให้ค้นหา cross-domain ได้ครอบคลุมกว่าเดิม
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
# HTTP session
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
        if h.startswith("www."):
            h = h[4:]
        return h
    except Exception:
        return ""


def clean_location(loc):
    if not loc:
        return ""

    loc = html.unescape(loc).strip()

    # Wayback อาจ rewrite Location ให้ผ่าน /web/TIMESTAMP.../
    m = re.search(
        r'(?:https?://web\.archive\.org)?/web/\d+(?:[a-z_]+)?/(https?://.+)$',
        loc,
        re.I,
    )
    if m:
        return unquote(m.group(1))

    return loc


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


def wayback_evidence_url(timestamp, original):
    return f"{WAYBACK}/{timestamp}/{original}"


# -------------------------
# Exact redirect inspection
# -------------------------

def inspect_capture(timestamp, original):
    """
    แนวเดียวกับตัว IDLE:
      1) id_ replay
      2) normal replay
      3) if_ replay fallback

    คืน:
      target, replay_url, error, replay_http_status
    """

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

            # วิธีหลัก: archived Location header
            target = clean_location(r.headers.get("Location", ""))

            # ป้องกัน Wayback redirect ภายในของตัวเองถูกนับเป็น target
            if target:
                target_host = hostname(target)
                if target_host == "web.archive.org":
                    target = ""

            # วิธีสำรอง: หน้า "Redirecting to..."
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
        if target.startswith("/"):
            return "INTERNAL"
        return "UNKNOWN"

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
# Quick ordering
# -------------------------

def build_quick_order(captures):
    """
    Quick Scan MAX:
    - ตรวจทุก 3xx capture ที่ CDX คืนมาสำหรับ domain นี้
    - ไม่มีเพดาน 80 / 300
    - เรียงจาก capture ใหม่ -> เก่า เพื่อมีโอกาสเจอ parked/expired redirect เร็ว
    - ถ้าเจอ CROSS-DOMAIN จะหยุดทันที
    - ถ้าไม่เจอ จะตรวจครบทุก capture เท่าที่ Wayback/CDX ส่งกลับมา
    """
    return list(reversed(captures))


# -------------------------
# Scan
# -------------------------

def scan(domain, full=False):
    captures = get_all_3xx_captures(domain)

    if not captures:
        return [], 0

    todo = captures if full else build_quick_order(captures)

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
            "evidence_url": wayback_evidence_url(ts, source),
            "replay_url": replay,
            "error": error,
        }

        results.append(item)

        progress.progress(
            i / len(todo),
            text=f"ตรวจ {i:,}/{len(todo):,}"
        )

        status_box.caption(
            f"ล่าสุด: {date} | HTTP {archived_status} | {kind}"
        )

        # Quick = เจอแล้วหยุดทันที เหมือน IDLE
        if not full and kind == "CROSS-DOMAIN":
            break

        # ลด rate เล็กน้อย ป้องกัน Wayback throttle
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

st.title("🔎 Wayback Redirect Checker")
st.caption(
    "ตรวจประวัติ HTTP 3xx และหา Cross-Domain Redirect "
    "จาก Internet Archive / Wayback Machine"
)
st.info(
    "Quick Scan MAX ไม่มีการจำกัดจำนวน capture: "
    "จะตรวจทุก 3xx ที่พบจนกว่าจะเจอ Cross-domain "
    "หรือจนตรวจครบทั้งหมด ดังนั้น domain ที่มีหลายหมื่น capture อาจใช้เวลานาน"
)

domain_input = st.text_input(
    "Domain",
    placeholder="เช่น idea.me หรือ footballgibraltar.com",
)

st.info(
    "FULL SCAN: ตรวจทุก 3xx capture ที่ Wayback/CDX พบสำหรับ domain นี้ "
    "และตรวจต่อจนจบแม้จะพบ Cross-domain เพื่อรวบรวมหลักฐานทั้งหมด"
)

if st.button("เริ่ม FULL SCAN", type="primary", use_container_width=True):
    domain = normalize_domain(domain_input)

    if not domain or "." not in domain:
        st.error("กรุณาใส่ Domain ให้ถูกต้อง เช่น footballgibraltar.com")

    else:
        full = True

        try:
            with st.spinner(f"กำลังโหลดประวัติ 3xx ของ {domain}..."):
                results, total = scan(domain, full=full)

            if total == 0:
                st.warning("ไม่พบ 3xx capture ใน Wayback Machine")

            else:
                cross = [
                    x for x in results
                    if x["classification"] == "CROSS-DOMAIN"
                ]

                unknown = [
                    x for x in results
                    if x["classification"] == "UNKNOWN"
                ]

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("3xx ทั้งหมด", f"{total:,}")
                c2.metric("ตรวจแล้ว", f"{len(results):,}")
                c3.metric("Cross-domain", f"{len(cross):,}")
                c4.metric("UNKNOWN", f"{len(unknown):,}")

                if cross:
                    st.error(
                        f"🚨 FOUND CROSS-DOMAIN REDIRECT "
                        f"{len(cross)} รายการ"
                    )

                    for x in cross:
                        with st.container(border=True):
                            st.subheader(
                                f"{x['source']}  →  {x['target']}"
                            )

                            st.write(
                                f"**วันที่:** {x['date']}  |  "
                                f"**Archived HTTP:** {x['archived_status']}  |  "
                                f"**Replay HTTP:** {x['replay_http_status']}"
                            )

                            st.success(
                                "พบหลักฐานว่า Wayback capture นี้ "
                                "redirect ไปคนละ domain"
                            )

                            st.link_button(
                                "🔗 เปิดหลักฐาน Wayback",
                                x["evidence_url"],
                                use_container_width=True,
                            )

                            st.write("**Evidence URL**")
                            st.code(x["evidence_url"], language=None)

                            with st.expander("ดูรายละเอียดทางเทคนิค"):
                                st.write("Source:")
                                st.code(x["source"], language=None)

                                st.write("Target:")
                                st.code(x["target"], language=None)

                                st.write("Raw replay:")
                                st.code(x["replay_url"], language=None)

                                if x["error"]:
                                    st.write("Error / fallback info:")
                                    st.code(x["error"], language=None)

                else:
                    st.success(
                        "ยังไม่พบ Cross-domain จาก captures ที่ตรวจสำเร็จ"
                    )


                if unknown:
                    ratio = len(unknown) / max(1, len(results))

                    if ratio >= 0.5:
                        st.warning(
                            f"⚠️ UNKNOWN สูง: {len(unknown):,}/"
                            f"{len(results):,} captures "
                            "แปลว่า Server อ่าน archived destination "
                            "จาก Wayback ไม่สำเร็จหลายรายการ "
                            "ผล 'ไม่พบ' จึงยังสรุปไม่ได้"
                        )
                    else:
                        st.warning(
                            f"มี {len(unknown):,} capture "
                            "ที่อ่านปลายทางไม่ได้ (UNKNOWN)"
                        )

                with st.expander("ดูผลการตรวจทั้งหมด"):
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

st.divider()
st.caption(
    "หมายเหตุ: ผลขึ้นอยู่กับ captures ที่ Internet Archive เก็บไว้ "
    "บาง snapshot อาจ replay ไม่ได้ หรือ Wayback อาจจำกัด request "
    "จาก cloud server ชั่วคราว"
)
