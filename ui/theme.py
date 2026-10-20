"""All RefundRx UI styling. Warm minimalist light theme on top of .streamlit/config.toml.

Streamlit internals are targeted by data-testid only; everything else uses the
rr-* classes emitted by streamlit_app.py.
"""
import streamlit as st

FONTS_URL = (
    "https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600"
    "&family=Geist+Mono:wght@400;500&display=swap"
)

CSS = f"""
@import url('{FONTS_URL}');

:root {{
  --rr-canvas: #F7F6F3;
  --rr-surface: #FFFFFF;
  --rr-text: #2F3437;
  --rr-muted: #787774;
  --rr-border: #EAEAEA;
  --rr-ink: #111111;
  --rr-sans: "Geist", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --rr-mono: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
}}

/* --- Streamlit chrome ------------------------------------------------------ */
[data-testid="stApp"] {{ background: var(--rr-canvas); color: var(--rr-text); font-family: var(--rr-sans); }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stDecoration"] {{ display: none; }}
[data-testid="stMainBlockContainer"] {{ padding-top: 1.75rem; padding-bottom: 2rem; max-width: 1240px; }}
[data-testid="stSidebar"] {{ background: var(--rr-canvas); border-right: 1px solid var(--rr-border); }}
[data-testid="stSidebarUserContent"] {{ padding-top: 1.5rem; }}

/* No shadows, no gradients anywhere. */
[data-testid="stApp"] *, [data-testid="stApp"] *::before, [data-testid="stApp"] *::after {{
  box-shadow: none !important;
  background-image: none;
}}

/* Focus: ink outline, never the default blue. */
[data-testid="stApp"] :focus-visible {{ outline: 1px solid var(--rr-ink) !important; outline-offset: 1px; }}
[data-testid="stTextInputRootElement"]:focus-within,
[data-testid="stDateInputField"]:focus-within,
[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {{ border-color: var(--rr-ink) !important; }}

/* --- Buttons: solid ink, white text --------------------------------------- */
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primaryFormSubmit"] {{
  background: var(--rr-ink); color: #FFFFFF; border: 1px solid var(--rr-ink);
  border-radius: 5px; font-family: var(--rr-sans); font-weight: 500; padding: 0.45rem 1rem;
}}
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-primaryFormSubmit"]:hover {{ background: var(--rr-text); border-color: var(--rr-text); color: #FFFFFF; }}
[data-testid="stBaseButton-primary"]:active,
[data-testid="stBaseButton-primaryFormSubmit"]:active {{ background: var(--rr-ink); color: #FFFFFF; }}

/* --- Toggles and radios take primaryColor (ink) from config.toml ------------ */
[data-testid="stRadio"] label {{ padding: 0.35rem 0; }}

/* --- Containers ------------------------------------------------------------ */
[data-testid="stForm"] {{ border: 1px solid var(--rr-border); border-radius: 6px; background: var(--rr-surface); padding: 1.25rem; }}
[data-testid="stExpander"] details {{ border: 1px solid var(--rr-border); border-radius: 6px; background: transparent; }}
[data-testid="stExpander"] summary {{ font-size: 0.875rem; color: var(--rr-text); }}
[data-testid="stSpinner"] {{ color: var(--rr-muted); font-size: 0.875rem; }}
[data-testid="stWidgetLabel"] p {{ font-size: 0.8125rem; color: var(--rr-muted); }}
[data-testid="stCaptionContainer"] {{ color: var(--rr-muted); }}
/* IDs and dates are mono. Inputs are matched on their stable aria-labels. */
[data-testid="stDateInputField"] input,
input[aria-label="Patient ID (999 test range)"],
input[aria-label="FP57 form reference"] {{ font-family: var(--rr-mono); font-size: 0.8125rem; }}

/* --- App classes ----------------------------------------------------------- */
.rr-mono {{ font-family: var(--rr-mono); font-size: 0.8125rem; letter-spacing: -0.01em; }}
.rr-muted {{ color: var(--rr-muted); }}
.rr-label {{ font-size: 0.75rem; font-weight: 500; color: var(--rr-muted); letter-spacing: 0.02em; margin: 0 0 0.5rem; }}

.rr-header {{ display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid var(--rr-border); padding-bottom: 0.75rem; margin-bottom: 0.9rem; }}
.rr-wordmark {{ font-family: var(--rr-sans); font-weight: 600; font-size: 1.05rem; color: var(--rr-ink); letter-spacing: -0.02em; }}
.rr-nav a {{ color: var(--rr-text); text-decoration: none; font-size: 0.8125rem; margin-left: 1.25rem; }}
.rr-nav a:hover {{ color: var(--rr-ink); text-decoration: underline; text-underline-offset: 3px; }}
.rr-lede {{ font-size: 0.9375rem; line-height: 1.55; color: var(--rr-text); max-width: 52rem; margin: 0 0 0.9rem; }}
.rr-lede span {{ color: var(--rr-muted); }}

.rr-panel {{ border: 1px solid var(--rr-border); border-radius: 6px; background: var(--rr-surface); padding: 1.25rem; }}
.rr-section {{ border-top: 1px solid var(--rr-border); padding-top: 1rem; margin-top: 1rem; }}
.rr-empty {{ border: 1px dashed #DCDBD7; border-radius: 6px; padding: 2.5rem 1.5rem; text-align: center;
  color: var(--rr-muted); font-size: 0.875rem; line-height: 1.6; }}
.rr-empty strong {{ display: block; color: var(--rr-text); font-weight: 500; margin-bottom: 0.25rem; }}

.rr-notice {{ border: 1px solid var(--rr-border); border-left: 2px solid var(--rr-ink); border-radius: 4px;
  background: var(--rr-surface); padding: 0.7rem 0.9rem; font-size: 0.875rem; color: var(--rr-text); margin: 0.25rem 0 0.75rem; }}
.rr-notice b {{ font-weight: 600; margin-right: 0.35rem; }}

.rr-pill {{ display: inline-block; font-family: var(--rr-mono); font-size: 0.75rem; font-weight: 500;
  letter-spacing: 0.04em; padding: 0.2rem 0.55rem; border-radius: 4px; border: 1px solid transparent; }}
.rr-pill-approved {{ background: #EDF3EC; color: #346538; }}
.rr-pill-rejected {{ background: #FDEBEC; color: #9F2F2D; }}
.rr-pill-none {{ background: #FBF3DB; color: #956400; }}
.rr-decision {{ display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }}
.rr-refund {{ font-size: 1.05rem; font-weight: 600; color: var(--rr-ink); margin-left: auto; }}
.rr-reasons {{ margin: 0.6rem 0 0; padding-left: 1.1rem; font-size: 0.875rem; color: var(--rr-text); }}

.rr-plan {{ margin: 0; padding-left: 1.4rem; }}
[data-testid="stHtml"] ol.rr-trace {{ margin: 0 0 0 4px; padding: 0; }}
.rr-plan li {{ padding: 0.12rem 0; }}
.rr-plan li::marker {{ font-family: var(--rr-mono); font-size: 0.75rem; color: var(--rr-muted); }}

.rr-trace {{ list-style: none; margin: 0; padding: 0; border-left: 1px solid var(--rr-border); }}
.rr-step {{ position: relative; padding: 0 0 0.85rem 1.1rem; }}
.rr-step::before {{ content: ""; position: absolute; left: -4px; top: 0.4rem; width: 7px; height: 7px;
  border-radius: 50%; background: var(--rr-canvas); border: 1px solid var(--rr-text); }}
.rr-step-fail::before {{ background: var(--rr-ink); border-color: var(--rr-ink); }}
.rr-step-head {{ display: flex; align-items: baseline; gap: 0.6rem; }}
.rr-step-head .rr-mono {{ color: var(--rr-ink); }}
.rr-result {{ margin-left: auto; font-family: var(--rr-mono); font-size: 0.6875rem; letter-spacing: 0.05em;
  padding: 0.05rem 0.4rem; border-radius: 3px; border: 1px solid var(--rr-border); color: var(--rr-muted); }}
.rr-result-fail {{ border-color: var(--rr-ink); color: var(--rr-ink); font-weight: 500; }}
.rr-step-detail {{ font-size: 0.8125rem; color: var(--rr-muted); margin-top: 0.15rem; line-height: 1.5; }}

.rr-citation {{ font-size: 0.8125rem; line-height: 1.6; color: var(--rr-text); }}
.rr-citation h4 {{ font-family: var(--rr-sans); font-size: 0.875rem; font-weight: 600; margin: 0 0 0.25rem; padding: 0; color: var(--rr-ink); }}
.rr-citation p {{ margin: 0 0 0.4rem; }}

.rr-meta {{ display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap; color: var(--rr-muted); font-size: 0.75rem; }}

.rr-table-wrap {{ overflow-x: auto; border: 1px solid var(--rr-border); border-radius: 6px; background: var(--rr-surface); }}
.rr-table {{ width: 100%; border-collapse: collapse; font-size: 0.8125rem; }}
.rr-table th {{ text-align: left; font-weight: 500; font-size: 0.75rem; color: var(--rr-muted);
  padding: 0.6rem 0.9rem; border-bottom: 1px solid var(--rr-border); white-space: nowrap; }}
.rr-table td {{ padding: 0.55rem 0.9rem; border-bottom: 1px solid var(--rr-border); white-space: nowrap; color: var(--rr-text); }}
.rr-table tr:last-child td {{ border-bottom: none; }}

.rr-verify {{ display: flex; align-items: center; gap: 0.6rem; font-size: 0.875rem; min-height: 2.4rem; }}
.rr-verify b {{ font-weight: 600; color: var(--rr-ink); }}

.rr-footer {{ border-top: 1px solid var(--rr-border); margin-top: 2.5rem; padding-top: 1rem;
  text-align: center; font-size: 0.8125rem; color: var(--rr-muted); }}
.rr-footer b {{ color: var(--rr-text); font-weight: 500; }}

.rr-h2 {{ font-size: 1rem; font-weight: 600; color: var(--rr-ink); margin: 2rem 0 0.25rem; letter-spacing: -0.01em; }}
@media (max-width: 640px) {{
  [data-testid="stMainBlockContainer"] {{ padding-top: 3.5rem; }}
}}

.rr-sub {{ font-size: 0.8125rem; color: var(--rr-muted); margin: 0 0 0.75rem; }}
"""


def apply() -> None:
    """Inject the stylesheet. Call once, right after st.set_page_config."""
    st.html(f"<style>{CSS}</style>")
