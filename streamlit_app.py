import csv
import html
import io
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, unquote

import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# Wayback Redirect Checker
# UI: white cards / soft lavender background / red CTA
# Full Scan = recommended (default), Quick Scan = secondary
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


def rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:  # Streamlit < 1.27
        st.experimental_rerun()


# ============================================================
# Styling
# ============================================================

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+Thai:wght@400;500;600;700;800&display=swap');

:root {
    --ink:        #16203c;
    --ink-soft:   #48526b;
    --muted:      #8b93a7;
    --line:       #ececf4;
    --blue:       #1d4ed8;
    --blue-dark:  #1743bd;
    --blue-soft:  #eaf0ff;
    --red:        #ef4444;
    --rose:       #e11d48;
    --rose-soft:  #ffeef1;
    --amber-soft: #fff4dd;
    --radius:     20px;
    --field-h:    58px;
}

html, body, .stApp, [class*="css"] {
    font-family: 'Inter', 'Noto Sans Thai', -apple-system, sans-serif;
}

.stApp {
    background: linear-gradient(180deg, #fdfcff 0%, #f8f7fd 45%, #f6f5fb 100%);
    color: var(--ink);
}

.block-container {
    max-width: 1120px;
    padding-top: 1.6rem;
    padding-bottom: 3.5rem;
}

/* hide default streamlit chrome */
#MainMenu, footer, header [data-testid="stStatusWidget"] { visibility: hidden; }

/* invisible layout markers */
[data-testid="stElementContainer"]:has(.mk),
.element-container:has(.mk),
.stMarkdown:has(.mk) { display: none !important; }
.mk, .card-mark { display: none !important; }

/* ---------------------------------------------------------
   Shared pieces
   --------------------------------------------------------- */

.ic {
    width: 54px;
    height: 54px;
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.4rem;
    flex: none;
}
.ic-sm { width: 46px; height: 46px; border-radius: 14px; font-size: 1.2rem; }
.ic-blue  { background: var(--blue-soft); }
.ic-pink  { background: var(--rose-soft); }
.ic-amber { background: var(--amber-soft); }

.head-row {
    display: flex;
    align-items: center;
    gap: 16px;
}

.head-title {
    font-size: 1.42rem;
    font-weight: 800;
    color: var(--ink);
    letter-spacing: -0.02em;
    line-height: 1.5;
}

.head-sub {
    margin-top: 2px;
    font-size: .93rem;
    line-height: 1.6;
    color: var(--muted);
}

/* ---------------------------------------------------------
   Hero
   --------------------------------------------------------- */

.hero {
    position: relative;
    overflow: hidden;
    background: #ffffff;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 26px 28px 24px;
    margin-bottom: 22px;
    box-shadow: 0 12px 34px rgba(22, 32, 60, .05);
}

.hero-wave {
    position: absolute;
    right: 0;
    top: 0;
    height: 100%;
    width: 58%;
    pointer-events: none;
}

.hero-title {
    position: relative;
    z-index: 1;
    font-size: 2.15rem;
    font-weight: 800;
    letter-spacing: -0.035em;
    color: var(--ink);
    line-height: 1.35;
}

.hero-sub {
    position: relative;
    z-index: 1;
    margin-top: 12px;
    color: var(--ink-soft);
    font-size: 1rem;
    line-height: 1.7;
}

/* ---------------------------------------------------------
   Container -> white card
   (child combinator keeps ancestor blocks from matching)
   --------------------------------------------------------- */

[data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .card-mark),
[data-testid="stVerticalBlock"]:has(> .element-container .card-mark),
[data-testid="stVerticalBlockBorderWrapper"]:has(.card-mark) {
    background: #ffffff !important;
    border: 1px solid var(--line) !important;
    border-radius: var(--radius) !important;
    padding: 24px 26px 26px !important;
    box-shadow: 0 12px 34px rgba(22, 32, 60, .05) !important;
}

/* if both wrapper and inner block matched, keep only the outer frame */
[data-testid="stVerticalBlockBorderWrapper"]:has(.card-mark)
  [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .card-mark) {
    border: none !important;
    padding: 0 !important;
    box-shadow: none !important;
    background: transparent !important;
}

/* ---------------------------------------------------------
   Domain input + attached search button
   --------------------------------------------------------- */

[data-testid="stHorizontalBlock"]:has(.q-input) {
    gap: 0 !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    margin-top: 20px;
    width: 100%;
}

[data-testid="stHorizontalBlock"]:has(.q-input) [data-testid="stColumn"] {
    min-width: 0 !important;
}

[data-testid="stHorizontalBlock"]:has(.q-input) [data-testid="stElementContainer"],
[data-testid="stHorizontalBlock"]:has(.q-input) .element-container,
[data-testid="stHorizontalBlock"]:has(.q-input) [data-testid="stWidgetLabel"] {
    margin: 0 !important;
}

/* the visible field frame lives on the outer wrapper only */
[data-testid="stTextInput"],
[data-testid="stTextInput"] * {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    outline: none !important;
    color: var(--ink) !important;
    -webkit-text-fill-color: var(--ink) !important;
}

[data-testid="stTextInput"] > div {
    display: flex !important;
    align-items: center !important;
    background: #ffffff !important;
    background-color: #ffffff !important;
    border: 1.5px solid #cfd8ea !important;
    border-right: none !important;
    border-radius: 14px 0 0 14px !important;
    height: var(--field-h) !important;
    min-height: var(--field-h) !important;
    max-height: var(--field-h) !important;
    overflow: hidden !important;
    transition: border-color .16s ease, box-shadow .16s ease;
}

[data-testid="stTextInput"] > div > div,
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stTextInput"] [data-baseweb="base-input"] {
    width: 100% !important;
    height: 100% !important;
    min-height: 0 !important;
    display: flex !important;
    align-items: center !important;
    padding: 0 !important;
}

[data-testid="stTextInput"] input {
    width: 100% !important;
    height: 100% !important;
    min-height: 0 !important;
    padding: 0 18px !important;

    font-family: 'Inter', 'Noto Sans Thai', -apple-system, sans-serif !important;
    font-size: 1rem !important;
    font-weight: 500 !important;
    line-height: 1.6 !important;

    color: #16203c !important;
    -webkit-text-fill-color: #16203c !important;
    caret-color: #1d4ed8 !important;

    background: transparent !important;
    border: 0 !important;
    outline: 0 !important;
    box-shadow: none !important;
}

[data-testid="stTextInput"] > div:focus-within {
    border-color: #1d4ed8 !important;
    box-shadow: 0 0 0 3px rgba(29, 78, 216, .09) !important;
}

[data-testid="stTextInput"] input::placeholder {
    color: #9aa3b5 !important;
    -webkit-text-fill-color: #9aa3b5 !important;
    opacity: 1 !important;
    font-weight: 400 !important;
}

[data-testid="stTextInput"] input::selection {
    background: rgba(29, 78, 216, .16) !important;
    color: #16203c !important;
    -webkit-text-fill-color: #16203c !important;
}

[data-testid="stColumn"]:has(.q-btn) .stButton,
[data-testid="stColumn"]:has(.q-btn) .stButton > button,
[data-testid="stColumn"]:has(.q-btn) button {
    width: 100% !important;
    max-width: 100% !important;
    height: var(--field-h) !important;
    min-height: var(--field-h) !important;
    max-height: var(--field-h) !important;
    margin: 0 !important;
    padding: 0 !important;
}

[data-testid="stColumn"]:has(.q-btn) button {
    border-radius: 0 14px 14px 0 !important;
    background: var(--blue) !important;
    border: 1.5px solid var(--blue) !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    line-height: 1.6 !important;
    box-shadow: none !important;
    transition: background .16s ease;
}

[data-testid="stColumn"]:has(.q-btn) button p,
[data-testid="stColumn"]:has(.q-btn) button div {
    color: #ffffff !important;
    font-weight: 700 !important;
    line-height: 1.6 !important;
}

[data-testid="stColumn"]:has(.q-btn) button:hover {
    background: var(--blue-dark) !important;
    border-color: var(--blue-dark) !important;
}

/* ---------------------------------------------------------
   Scan mode section
   --------------------------------------------------------- */

.scan-head { margin: 34px 0 18px; }

.scan-card {
    position: relative;
    border: 1.5px solid var(--line);
    background: #ffffff;
    border-radius: 18px;
    padding: 20px 22px 18px;
    min-height: 210px;
    box-shadow: 0 10px 26px rgba(22, 32, 60, .04);
    transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
}

.scan-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 16px 32px rgba(22, 32, 60, .08);
}

.scan-card.is-active {
    border-color: #f26a6a;
    background: linear-gradient(160deg, #ffffff 0%, #fffaf9 60%, #fff6f5 100%);
    box-shadow: 0 14px 32px rgba(226, 60, 80, .10);
}

.scan-top {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    padding-right: 40px;
}

.scan-title {
    font-size: 1.22rem;
    font-weight: 800;
    color: var(--ink);
    letter-spacing: -0.02em;
    line-height: 1.5;
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.badge {
    font-size: .78rem;
    font-weight: 700;
    padding: 4px 11px;
    border-radius: 999px;
    background: var(--rose-soft);
    color: var(--rose);
}

.scan-desc {
    margin-top: 10px;
    color: var(--ink-soft);
    font-size: .97rem;
    line-height: 1.6;
}

.scan-foot {
    margin-top: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: .93rem;
    color: #6b7488;
}

.pick {
    position: absolute;
    top: 20px;
    right: 20px;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    border: 2px solid #dfe3ee;
    background: #ffffff;
}

.pick.on {
    border-color: var(--red);
    background: var(--red);
    display: flex;
    align-items: center;
    justify-content: center;
}

.pick.on::after {
    content: "";
    width: 9px;
    height: 5px;
    border-left: 2.4px solid #fff;
    border-bottom: 2.4px solid #fff;
    transform: rotate(-45deg) translate(1px, -1px);
}

/* clickable overlay on each scan card */
[data-testid="stColumn"]:has(.scan-card) { position: relative; }

[data-testid="stColumn"]:has(.scan-card) [data-testid="stElementContainer"]:has(div.stButton) {
    position: absolute;
    inset: 0;
    margin: 0;
}

[data-testid="stColumn"]:has(.scan-card) div.stButton,
[data-testid="stColumn"]:has(.scan-card) div.stButton > button {
    width: 100%;
    height: 100%;
    margin: 0;
}

[data-testid="stColumn"]:has(.scan-card) div.stButton > button {
    opacity: 0;
    background: transparent;
    border: none;
    cursor: pointer;
}

[data-testid="stColumn"]:has(.scan-card) div.stButton > button:focus-visible {
    opacity: 1;
    outline: 3px solid rgba(29, 78, 216, .45);
    outline-offset: -3px;
    color: transparent;
}

/* ---------------------------------------------------------
   Note banner
   --------------------------------------------------------- */

.note {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin: 20px 0 22px;
    padding: 16px 18px;
    border-radius: 14px;
    font-size: .97rem;
    line-height: 1.55;
}

.note-blue {
    background: #f0f5ff;
    border: 1px solid #dbe6fd;
    color: var(--ink-soft);
}
.note-blue b { color: var(--blue); }

.note-amber {
    background: #fff9ec;
    border: 1px solid #f7e6c2;
    color: #6b5a37;
}
.note-amber b { color: #b4761a; }

.note-ic {
    flex: none;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    border: 1.6px solid currentColor;
    color: var(--blue);
    font-size: .8rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 1px;
}
.note-amber .note-ic { color: #b4761a; }

/* ---------------------------------------------------------
   Primary CTA
   --------------------------------------------------------- */

div.stButton > button[kind="primary"],
div.stButton > button[data-testid="baseButton-primary"] {
    background: linear-gradient(90deg, #e2124f 0%, #f0294a 45%, #ff5334 100%);
    color: #ffffff;
    border: none;
    border-radius: 16px;
    min-height: 64px;
    font-size: 1.08rem;
    font-weight: 800;
    line-height: 1.6;
    letter-spacing: .01em;
    box-shadow: 0 14px 30px rgba(232, 30, 76, .26);
    transition: transform .16s ease, box-shadow .16s ease, filter .16s ease;
}

div.stButton > button[kind="primary"]:hover,
div.stButton > button[data-testid="baseButton-primary"]:hover {
    color: #ffffff;
    filter: brightness(1.04);
    transform: translateY(-1px);
    box-shadow: 0 18px 36px rgba(232, 30, 76, .30);
}

div.stButton > button[kind="primary"]:active { transform: translateY(0); }

/* ---------------------------------------------------------
   Results
   --------------------------------------------------------- */

.section-title {
    font-size: 1.3rem;
    font-weight: 800;
    color: var(--ink);
    letter-spacing: -0.02em;
    margin: 34px 0 14px;
}

div[data-testid="stMetric"] {
    background: #ffffff !important;
    border: 1px solid var(--line) !important;
    padding: 18px 20px;
    border-radius: 16px;
    box-shadow: 0 10px 26px rgba(22, 32, 60, .04);
}

/* safety net when the running theme is dark-based */
.stApp, .stApp p, .stApp li, .stApp label, .stApp .stMarkdown {
    color: var(--ink-soft);
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] p,
[data-testid="stExpander"] label { color: var(--ink) !important; }

div[data-testid="stMetricLabel"] { color: var(--muted); font-weight: 600; }
div[data-testid="stMetricValue"] { color: var(--ink); font-weight: 800; }

.evidence {
    border: 1px solid #f7d3d8;
    border-left: 4px solid var(--red);
    border-radius: 16px;
    padding: 20px 22px;
    background: linear-gradient(160deg, #ffffff 0%, #fff7f7 100%);
    margin: 14px 0 10px;
    box-shadow: 0 10px 26px rgba(200, 40, 60, .06);
}

.evidence .ev-url {
    font-weight: 700;
    font-size: 1.02rem;
    color: var(--ink);
    word-break: break-all;
}

.evidence .ev-arrow {
    margin: 8px 0;
    color: var(--rose);
    font-weight: 700;
    font-size: .9rem;
    letter-spacing: .04em;
}

.evidence .ev-meta {
    margin-top: 12px;
    color: var(--muted);
    font-size: .9rem;
}

[data-testid="stAlert"] {
    border-radius: 14px;
    border-width: 1px;
}

[data-testid="stExpander"] {
    background: #ffffff;
    border-color: var(--line);
    border-radius: 14px;
    box-shadow: 0 8px 20px rgba(22, 32, 60, .035);
}

[data-testid="stDownloadButton"] button,
[data-testid="stLinkButton"] a {
    border-radius: 12px !important;
    background: #ffffff !important;
    color: var(--ink) !important;
    border: 1px solid #dbe0ec !important;
    font-weight: 600;
    min-height: 48px;
    box-shadow: 0 6px 16px rgba(22, 32, 60, .04);
}

[data-testid="stDownloadButton"] button:hover,
[data-testid="stLinkButton"] a:hover {
    border-color: #c2cadd !important;
    color: var(--blue) !important;
}

[data-testid="stProgress"] > div > div > div > div {
    background: linear-gradient(90deg, #e2124f, #ff5334);
}

.footer-note {
    color: #a1a8ba;
    text-align: center;
    font-size: .85rem;
    margin-top: 38px;
}

@media (max-width: 640px) {
    .hero-title { font-size: 1.55rem; }
    .hero-wave { display: none; }
    .scan-card { min-height: 0; }
    [data-testid="stHorizontalBlock"]:has(.q-input) { flex-wrap: wrap !important; gap: 10px !important; }
    [data-testid="stTextInput"] > div,
    [data-testid="stTextInput"] [data-baseweb="input"] {
        border-radius: 14px !important;
        border-right: 1.5px solid #cfd8ea !important;
    }
    [data-testid="stColumn"]:has(.q-btn) button { border-radius: 14px !important; }
}

@media (prefers-reduced-motion: reduce) {
    * { transition: none !important; animation: none !important; }
}

/* ============================================================
   DOMAIN INPUT ONLY — keep typed domain as normal visible text
   and hide Streamlit/BaseWeb "Press Enter to apply" helper.
   ============================================================ */

[data-testid="stTextInput"] input,
[data-testid="stTextInput"] input:focus,
[data-testid="stTextInput"] input:active {
    color: #16203c !important;
    -webkit-text-fill-color: #16203c !important;
    opacity: 1 !important;
    font-family: 'Inter', 'Noto Sans Thai', -apple-system, sans-serif !important;
    font-size: 16px !important;
    font-weight: 500 !important;
    text-shadow: none !important;
}

/* BaseWeb/Streamlit instruction overlay shown while editing */
[data-testid="stTextInput"] [data-baseweb="input"] > div:not(:has(input)),
[data-testid="stTextInput"] [data-baseweb="base-input"] > div:not(:has(input)) {
    display: none !important;
}

/* Some Streamlit versions expose the instruction as a small status/helper node */
[data-testid="stTextInput"] [role="status"],
[data-testid="stTextInput"] [aria-live="polite"],
[data-testid="stTextInput"] small {
    display: none !important;
}

/* Do not let any overlay cover the actual text field */
[data-testid="stTextInput"] input {
    position: relative !important;
    z-index: 5 !important;
    background: transparent !important;
}


/* DOMAIN INPUT ONLY:
   Hide Streamlit's keyboard hint ("Press Enter to apply") completely. */
[data-testid="stTextInput"] [data-testid="InputInstructions"],
[data-testid="stTextInput"] div[data-testid="InputInstructions"],
[data-testid="stTextInput"] [data-testid="InputInstructions"] *,
div[data-testid="InputInstructions"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    width: 0 !important;
    height: 0 !important;
    min-width: 0 !important;
    min-height: 0 !important;
    overflow: hidden !important;
    pointer-events: none !important;
}


/* Wayback retry button: keep text/background stable on hover */
div[data-testid="stElementContainer"]:has(.wayback-refresh)
+ div[data-testid="stElementContainer"] button,
div[data-testid="stElementContainer"]:has(.wayback-refresh)
+ div[data-testid="stElementContainer"] button:hover,
div[data-testid="stElementContainer"]:has(.wayback-refresh)
+ div[data-testid="stElementContainer"] button:focus,
div[data-testid="stElementContainer"]:has(.wayback-refresh)
+ div[data-testid="stElementContainer"] button:active {
    background: #ffffff !important;
    background-color: #ffffff !important;
    color: #16203c !important;
    -webkit-text-fill-color: #16203c !important;
    border: 1px solid #e2e4ec !important;
    box-shadow: none !important;
}

div[data-testid="stElementContainer"]:has(.wayback-refresh)
+ div[data-testid="stElementContainer"] button *,
div[data-testid="stElementContainer"]:has(.wayback-refresh)
+ div[data-testid="stElementContainer"] button:hover *,
div[data-testid="stElementContainer"]:has(.wayback-refresh)
+ div[data-testid="stElementContainer"] button:focus *,
div[data-testid="stElementContainer"]:has(.wayback-refresh)
+ div[data-testid="stElementContainer"] button:active * {
    color: #16203c !important;
    -webkit-text-fill-color: #16203c !important;
}

</style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HTTP
# ============================================================

def make_session():
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=1,
        backoff_factor=0.25,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=24,
        pool_maxsize=24,
        pool_block=False,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


SESSION = make_session()
_THREAD_LOCAL = threading.local()

def get_thread_session():
    if not hasattr(_THREAD_LOCAL, "session"):
        _THREAD_LOCAL.session = make_session()
    return _THREAD_LOCAL.session


# ============================================================
# Helpers
# ============================================================

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
    session = get_thread_session()

    for replay in candidates:
        try:
            # Shorter timeout keeps dead/slow Wayback snapshots from blocking the scan.
            r = session.get(replay, timeout=(3.5, 7), allow_redirects=False)
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


# ============================================================
# CDX
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_all_3xx_captures(domain):
    params = {
        "url": domain,
        "output": "json",
        "fl": "timestamp,original,statuscode",
        "filter": "statuscode:3..",
        "matchType": "domain",
    }

    r = requests.get(CDX, params=params, headers=HEADERS, timeout=60)
    r.raise_for_status()

    data = r.json()

    if not data or len(data) <= 1:
        return []

    header = data[0]
    rows = [dict(zip(header, row)) for row in data[1:]]

    seen = set()
    result = []

    for row in rows:
        key = (row.get("timestamp"), row.get("original"), row.get("statuscode"))
        if key not in seen:
            seen.add(key)
            result.append(row)

    result.sort(key=lambda x: x.get("timestamp", ""))
    return result


# ============================================================
# Scan plans
# ============================================================

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
    todo = captures if full else build_quick_order(captures, max_checks=10000)

    progress = st.progress(0, text="กำลังเตรียม Wayback captures...")
    status_box = st.empty()

    # Conservative concurrency: much faster than sequential requests while
    # avoiding an unnecessarily aggressive burst toward Internet Archive.
    max_workers = 12 if full else 16
    completed = 0
    results_by_index = {}
    cross_found = False

    def inspect_row(index, row):
        ts = row.get("timestamp", "")
        source = row.get("original", "")
        archived_status = row.get("statuscode", "")

        try:
            target, replay, error, replay_http = inspect_capture(ts, source)
        except Exception as e:
            target, replay, error, replay_http = "", "", str(e), ""

        kind = classify(source, target, domain)
        date = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}" if len(ts) >= 8 else ts

        return index, {
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

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(inspect_row, index, row): index
            for index, row in enumerate(todo)
        }

        for future in as_completed(futures):
            index, item = future.result()
            results_by_index[index] = item
            completed += 1

            progress.progress(
                completed / len(todo),
                text=f"กำลังตรวจ {completed:,}/{len(todo):,}"
            )

            mode_label = "Full Scan" if full else "Quick Scan"
            status_box.info(
                f"🔄 กำลังสแกน {mode_label} · "
                f"{completed:,}/{len(todo):,} captures · "
                f"ล่าสุด {item['date']} · HTTP {item['archived_status']} · "
                f"{item['classification']}"
            )

            # Quick Scan still stops as soon as a cross-domain result is found.
            if not full and item["classification"] == "CROSS-DOMAIN":
                cross_found = True
                for pending in futures:
                    if not pending.done():
                        pending.cancel()
                break

    progress.empty()
    status_box.empty()

    results = [results_by_index[i] for i in sorted(results_by_index)]

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

if "scan_mode" not in st.session_state:
    st.session_state["scan_mode"] = "Full Scan"

# ---------- Hero ----------

st.markdown(
    """
    <div class="hero">
      <svg class="hero-wave" viewBox="0 0 600 200" preserveAspectRatio="none">
        <path d="M0,118 C120,34 250,178 410,86 C512,28 556,58 600,44 L600,200 L0,200 Z"
              fill="rgba(99,102,241,.075)"/>
        <path d="M0,152 C140,84 278,198 438,120 C540,72 572,96 600,86 L600,200 L0,200 Z"
              fill="rgba(120,110,235,.05)"/>
      </svg>
      <div class="head-row">
        <div class="ic ic-blue">🔎</div>
        <div class="hero-title">Wayback Redirect Checker</div>
      </div>
      <div class="hero-sub">
        ตรวจประวัติ HTTP 3xx และ Cross-Domain Redirect จาก Internet Archive / Wayback Machine
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- Domain card ----------

with st.container():
    st.markdown(
        """
        <span class="card-mark"></span>
        <div class="head-row">
          <div class="ic ic-sm ic-blue">🌐</div>
          <div>
            <div class="head-title">ตรวจสอบ Domain</div>
            <div class="head-sub">กรอก Domain ที่ต้องการตรวจสอบ</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    q1, q2 = st.columns([0.76, 0.24])

    def _submit_domain():
        st.session_state["enter_search_clicked"] = True

    with q1:
        st.markdown('<span class="mk q-input"></span>', unsafe_allow_html=True)
        domain_input = st.text_input(
            "Domain",
            placeholder="เช่น UFABET.com หรือ footballgibraltar.com",
            label_visibility="collapsed",
            key="domain_input",
            on_change=_submit_domain,
        )

    with q2:
        st.markdown('<span class="mk q-btn"></span>', unsafe_allow_html=True)
        search_clicked = st.button("ตรวจสอบ", key="search_btn", use_container_width=True)

    enter_search_clicked = st.session_state.pop("enter_search_clicked", False)
    retry_wayback_scan = st.session_state.pop("retry_wayback_scan", False)
    search_clicked = search_clicked or enter_search_clicked or retry_wayback_scan

# ---------- Scan mode ----------

st.markdown(
    """
    <div class="head-row scan-head">
      <div class="ic ic-sm ic-pink">🎯</div>
      <div>
        <div class="head-title">เลือกโหมดการสแกน</div>
        <div class="head-sub">เลือกโหมดที่เหมาะสมกับความต้องการของคุณ</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

mode = st.session_state["scan_mode"]


def scan_card(icon, icon_class, title, badge, desc, foot, active):
    badge_html = f'<span class="badge">{badge}</span>' if badge else ""
    return f"""
    <div class="scan-card{' is-active' if active else ''}">
      <div class="pick{' on' if active else ''}"></div>
      <div class="scan-top">
        <div class="ic ic-sm {icon_class}">{icon}</div>
        <div>
          <div class="scan-title">{title}{badge_html}</div>
          <div class="scan-desc">{desc}</div>
        </div>
      </div>
      <div class="scan-foot">{foot}</div>
    </div>
    """


s1, s2 = st.columns(2, gap="medium")

with s1:
    st.markdown(
        scan_card(
            "🔍",
            "ic-pink",
            "Full Scan",
            "แนะนำ",
            "ตรวจทุก 3xx capture ของ Domain และเก็บหลักฐาน Cross-domain ทุกเหตุการณ์",
            "⭐ ละเอียดที่สุด · ใช้เวลามากกว่า",
            mode == "Full Scan",
        ),
        unsafe_allow_html=True,
    )
    if st.button("เลือก Full Scan", key="pick_full", use_container_width=True):
        st.session_state["scan_mode"] = "Full Scan"
        rerun()

with s2:
    st.markdown(
        scan_card(
            "⚡",
            "ic-amber",
            "Quick Scan",
            "",
            "ตรวจตัวอย่างสูงสุด 10,000 captures โดยเน้นช่วงล่าสุดและกระจายทั่ว timeline",
            "🕐 เร็วกว่า · เหมาะสำหรับเช็กเบื้องต้น",
            mode == "Quick Scan",
        ),
        unsafe_allow_html=True,
    )
    if st.button("เลือก Quick Scan", key="pick_quick", use_container_width=True):
        st.session_state["scan_mode"] = "Quick Scan"
        rerun()

# ---------- Mode note ----------

if mode == "Full Scan":
    st.markdown(
        """
        <div class="note note-blue">
          <div class="note-ic">i</div>
          <div><b>Full Scan เป็นโหมดแนะนำ:</b> ตรวจทุก 3xx capture ที่ Wayback/CDX ส่งกลับมา</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <div class="note note-amber">
          <div class="note-ic">i</div>
          <div><b>Quick Scan เหมาะสำหรับเช็กเบื้องต้น:</b>
          หากไม่พบ Cross-domain ยังควรใช้ Full Scan เพื่อยืนยันอีกครั้ง</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

start_clicked = False

# ---------- Run ----------

if start_clicked or search_clicked:
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

                st.markdown('<div class="section-title">สรุปผลการตรวจ</div>', unsafe_allow_html=True)

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
                              <div class="ev-url">{html.escape(x['source'])}</div>
                              <div class="ev-arrow">↓ REDIRECT</div>
                              <div class="ev-url">{html.escape(x['target'])}</div>
                              <div class="ev-meta">
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
                    st.dataframe(results, use_container_width=True, hide_index=True)

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
                "🌐 ไม่สามารถเชื่อมต่อ Wayback Machine ได้ชั่วคราว\n\n"
                "Wayback Machine อาจกำลังมีผู้ใช้งานจำนวนมาก หรือการเชื่อมต่อขัดข้องชั่วคราว "
                "กรุณารอสักครู่แล้วลองใหม่อีกครั้ง"
            )

            st.markdown('<span class="mk wayback-refresh"></span>', unsafe_allow_html=True)
            if st.button(
                "🔄 Refresh และลองใหม่",
                key="wayback_refresh_btn",
                use_container_width=True,
            ):
                st.session_state["retry_wayback_scan"] = True
                st.rerun()

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
