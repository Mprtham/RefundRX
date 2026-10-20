"""All RefundRx UI styling. Warm minimalist light theme on top of .streamlit/config.toml.

Streamlit internals are targeted by data-testid only; everything else uses the
rr-* classes emitted by streamlit_app.py. Classes added at runtime by ui/motion.html
(rr-motion on <html>, rr-reveal / rr-in, rr-row-new, rr-tilting, #rr-progress) are
styled here too, so all CSS lives in this one file.
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
  --rr-border-strong: #B9B6AE;
  --rr-tint: rgba(31, 35, 38, 0.045);
  --rr-ink: #111111;
  --rr-lift-shadow: 0 8px 30px rgba(31, 35, 38, 0.06);
  --rr-sans: "Geist", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --rr-ease: cubic-bezier(.16, 1, .3, 1);
  --rr-mono: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
}}

/* --- Streamlit chrome ------------------------------------------------------ */
[data-testid="stApp"] {{ background: var(--rr-canvas); color: var(--rr-text); font-family: var(--rr-sans); }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stDecoration"] {{ display: none; }}
[data-testid="stMainBlockContainer"] {{ padding-top: 1.75rem; padding-bottom: 2rem; max-width: 1240px; }}
[data-testid="stSidebar"] {{ background: var(--rr-canvas); border-right: 1px solid var(--rr-border); }}
[data-testid="stSidebarUserContent"] {{ padding-top: 1.5rem; }}
/* The zero-height motion loader (ui/motion.html) takes no room in the layout. */
[data-testid="stElementContainer"]:has(> iframe[srcdoc*="rr-motion-loader"]) {{ display: none; }}

/* No shadows, no gradients anywhere (the hover lift below is the one exception). */
[data-testid="stApp"] *, [data-testid="stApp"] *::before, [data-testid="stApp"] *::after {{
  box-shadow: none !important;
  background-image: none;
}}

/* Focus: ink, never the default blue. Text-like fields get a 2px ring on the wrapper. */
[data-testid="stApp"] :focus-visible {{ outline: 1px solid var(--rr-ink) !important; outline-offset: 1px; }}
[data-testid="stTextInputRootElement"],
[data-testid="stDateInputField"],
[data-testid="stSelectbox"] [role="group"] {{
  cursor: pointer; transition: border-color 0.25s var(--rr-ease), outline-color 0.25s var(--rr-ease);
  outline: 2px solid transparent; outline-offset: 1px;
}}
[data-testid="stTextInputRootElement"] {{ cursor: text; }}
[data-testid="stTextInputRootElement"]:hover,
[data-testid="stDateInputField"]:hover,
[data-testid="stSelectbox"] [role="group"]:hover {{ border-color: var(--rr-border-strong) !important; }}
[data-testid="stTextInputRootElement"]:focus-within,
[data-testid="stDateInputField"]:focus-within,
[data-testid="stSelectbox"] [role="group"]:focus-within {{ border-color: var(--rr-ink) !important; outline-color: var(--rr-ink); }}
[data-testid="stTextInputRootElement"] input:focus-visible,
[data-testid="stDateInputField"] :focus-visible,
[data-testid="stSelectbox"] input:focus-visible {{ outline: none !important; }}

/* --- Buttons: solid ink, white text --------------------------------------- */
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-primaryFormSubmit"] {{
  background: var(--rr-ink); color: #FFFFFF; border: 1px solid var(--rr-ink); cursor: pointer;
  border-radius: 5px; font-family: var(--rr-sans); font-weight: 500; padding: 0.45rem 1rem;
  transition: background-color 0.2s var(--rr-ease), border-color 0.2s var(--rr-ease), transform 0.2s var(--rr-ease);
}}
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-primaryFormSubmit"]:hover {{ background: #000000; border-color: #000000; color: #FFFFFF; transform: translateY(-2px); }}
[data-testid="stBaseButton-primary"]:active,
[data-testid="stBaseButton-primaryFormSubmit"]:active {{ background: #000000; color: #FFFFFF; transform: translateY(0) scale(0.98); }}

/* --- Scenario presets: tint slides in, label nudges right, ink bar on the selected row --- */
[data-testid="stRadioOption"] {{ position: relative; cursor: pointer; padding: 0.4rem 0.6rem; margin-left: -0.6rem;
  border-radius: 4px; overflow: hidden; }}
[data-testid="stRadioOption"] > * {{ position: relative; z-index: 1; }}
[data-testid="stRadioOption"]::before {{ content: ""; position: absolute; inset: 0; z-index: 0; background: var(--rr-tint);
  transform: scaleX(0); transform-origin: left; transition: transform 0.3s var(--rr-ease); }}
[data-testid="stRadioOption"]:hover::before {{ transform: scaleX(1); }}
[data-testid="stRadioOption"] [data-testid="stMarkdownContainer"] {{ transition: transform 0.25s var(--rr-ease); }}
[data-testid="stRadioOption"]:hover [data-testid="stMarkdownContainer"] {{ transform: translateX(4px); }}
[data-testid="stRadioOption"]::after {{ content: ""; position: absolute; left: 0; top: 18%; bottom: 18%; width: 2px;
  background: var(--rr-ink); transform: scaleY(0); transition: transform 0.3s var(--rr-ease); }}
[data-testid="stRadioOption"][data-selected="true"]::after {{ transform: scaleY(1); }}

/* --- Toggles: smooth knob and track ------------------------------------------- */
[data-testid="stCheckbox"] label {{ cursor: pointer; }}
[data-testid="stCheckbox"] label > div:first-of-type {{ transition: background-color 0.3s var(--rr-ease); }}
[data-testid="stCheckbox"] label > div:first-of-type > div {{ transition: transform 0.3s var(--rr-ease); }}
[data-testid="stTooltipIcon"], [data-testid="stSelectbox"] button {{ cursor: pointer; }}

/* --- Containers ------------------------------------------------------------ */
[data-testid="stForm"] {{ border: 1px solid var(--rr-border); border-radius: 6px; background: var(--rr-surface); padding: 1.25rem; }}
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

.rr-linkbar {{ display: flex; justify-content: flex-end;
  padding: 0.25rem 0 0.75rem; margin-bottom: 0.5rem; }}
.rr-anchor {{ scroll-margin-top: 1.5rem; }}
.rr-wordmark {{ font-family: var(--rr-sans); font-weight: 600; font-size: 1.05rem; color: var(--rr-ink); letter-spacing: -0.02em; }}
.rr-nav a {{ position: relative; color: var(--rr-text); text-decoration: none; font-size: 0.8125rem; margin-left: 1.25rem;
  cursor: pointer; transition: color 0.2s var(--rr-ease); }}
.rr-nav a::after {{ content: ""; position: absolute; left: 0; right: 0; bottom: -3px; height: 1px; background: var(--rr-ink);
  transform: scaleX(0); transform-origin: left; transition: transform 0.3s var(--rr-ease); }}
.rr-nav a:hover {{ color: var(--rr-ink); }}
.rr-nav a:hover::after, .rr-nav a:focus-visible::after {{ transform: scaleX(1); }}

.rr-panel {{ border: 1px solid var(--rr-border); border-radius: 6px; background: var(--rr-surface); padding: 1.25rem; }}
.rr-section {{ border-top: 1px solid var(--rr-border); padding-top: 1rem; margin-top: 1rem; }}
.rr-empty {{ border: 1px dashed #DCDBD7; border-radius: 6px; padding: 2.5rem 1.5rem; text-align: center;
  color: var(--rr-muted); font-size: 0.875rem; line-height: 1.6; }}
.rr-empty strong {{ display: block; color: var(--rr-text); font-weight: 500; margin-bottom: 0.25rem; }}

.rr-notice {{ border: 1px solid var(--rr-border); border-left: 2px solid var(--rr-ink); border-radius: 4px;
  background: var(--rr-surface); padding: 0.7rem 0.9rem; font-size: 0.875rem; color: var(--rr-text); margin: 0.25rem 0 0.75rem; }}
.rr-notice b {{ font-weight: 600; margin-right: 0.35rem; }}

.rr-pill {{ display: inline-block; font-family: var(--rr-mono); font-size: 0.75rem; font-weight: 500;
  letter-spacing: 0.04em; padding: 0.2rem 0.55rem; border-radius: 4px; border: 1px solid transparent;
  transition: border-color 0.2s var(--rr-ease), transform 0.2s var(--rr-ease); }}
.rr-pill:hover {{ border-color: currentColor; }}
.rr-pill-approved {{ background: #EDF3EC; color: #346538; }}
.rr-pill-rejected {{ background: #FDEBEC; color: #9F2F2D; }}
.rr-pill-none {{ background: #FBF3DB; color: #956400; }}
.rr-decision {{ display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }}
.rr-refund {{ font-size: 1.05rem; font-weight: 600; color: var(--rr-ink); margin-left: auto; font-variant-numeric: tabular-nums; }}
.rr-reasons {{ margin: 0.6rem 0 0; padding-left: 1.1rem; font-size: 0.875rem; color: var(--rr-text); }}

.rr-plan {{ margin: 0; padding-left: 1.4rem; }}
[data-testid="stHtml"] ol.rr-trace {{ margin: 0 0 0 4px; padding: 0; }}
.rr-plan li {{ padding: 0.12rem 0; }}
.rr-plan li::marker {{ font-family: var(--rr-mono); font-size: 0.75rem; color: var(--rr-muted); }}

/* Trace timeline: the rail is a pseudo-element so it can draw down. */
.rr-trace {{ position: relative; list-style: none; margin: 0; padding: 0; }}
.rr-trace::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 1px; background: var(--rr-border);
  transform-origin: top; }}
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

/* Audit table: row tint, first-cell marker, sticky header once it outgrows its box. */
.rr-table-wrap {{ overflow: auto; max-height: 32rem; border: 1px solid var(--rr-border); border-radius: 6px; background: var(--rr-surface); }}
.rr-table {{ width: 100%; border-collapse: collapse; font-size: 0.8125rem; }}
.rr-table th {{ position: sticky; top: 0; z-index: 2; background: var(--rr-surface); text-align: left; font-weight: 500;
  font-size: 0.75rem; color: var(--rr-muted); padding: 0.6rem 0.9rem; border-bottom: 1px solid var(--rr-border); white-space: nowrap; }}
.rr-table td {{ padding: 0.55rem 0.9rem; border-bottom: 1px solid var(--rr-border); white-space: nowrap; color: var(--rr-text);
  transition: background-color 0.2s var(--rr-ease), color 0.2s var(--rr-ease); }}
.rr-table tr:last-child td {{ border-bottom: none; }}
.rr-table tbody tr:hover td {{ background: var(--rr-tint); }}
.rr-table td:first-child {{ position: relative; }}
.rr-table td:first-child::before {{ content: ""; position: absolute; left: 0; top: 22%; bottom: 22%; width: 2px;
  background: var(--rr-ink); transform: scaleY(0); transition: transform 0.25s var(--rr-ease); }}
.rr-table tbody tr:hover td:first-child {{ color: var(--rr-ink); }}
.rr-table tbody tr:hover td:first-child::before {{ transform: scaleY(1); }}

.rr-verify {{ display: flex; align-items: center; gap: 0.6rem; font-size: 0.875rem; min-height: 2.4rem; }}
.rr-verify b {{ font-weight: 600; color: var(--rr-ink); }}

.rr-footer {{ position: relative; margin-top: 2.5rem; padding-top: 1rem;
  text-align: center; font-size: 0.8125rem; color: var(--rr-muted); }}
.rr-footer b {{ color: var(--rr-text); font-weight: 500; }}
.rr-footer p {{ margin: 0.35rem 0 0; font-size: 0.75rem; }}

.rr-h2 {{ font-size: 1rem; font-weight: 600; color: var(--rr-ink); margin: 2rem 0 0.25rem; letter-spacing: -0.01em; }}
.rr-sub {{ font-size: 0.8125rem; color: var(--rr-muted); margin: 0 0 0.75rem; }}
@media (max-width: 640px) {{
  [data-testid="stMainBlockContainer"] {{ padding-top: 3.5rem; }}
}}

/* --- Story sections (copy shared with site/index.html) ----------------------- */
.rr-story {{ margin: 0 0 1.5rem; }}
.rr-story-row {{ position: relative; display: grid; grid-template-columns: 200px minmax(0, 1fr); gap: 2.5rem; padding: 2rem 0; }}
/* Hairline dividers are pseudo-elements so they can draw in from the left. */
.rr-story-row::before, .rr-footer::before {{ content: ""; position: absolute; left: 0; right: 0; top: 0; height: 1px;
  background: var(--rr-border); transform-origin: left; }}
.rr-story-bridge {{ margin: 2.5rem 0 0.5rem; }}
.rr-story-bridge .rr-story-row {{ padding-bottom: 0; }}
.rr-eyebrow {{ font-family: var(--rr-mono); font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--rr-muted); padding-top: 0.4rem; }}
.rr-prose h2 {{ font-family: var(--rr-sans); font-size: 1.5rem; font-weight: 600; line-height: 1.2; letter-spacing: -0.02em;
  color: var(--rr-ink); margin: 0 0 0.9rem; padding: 0; max-width: 28ch; }}
.rr-prose p {{ max-width: 62ch; margin: 0 0 0.8rem; line-height: 1.65; color: var(--rr-text); }}
.rr-n {{ font-family: var(--rr-mono); font-size: 0.8125rem; color: var(--rr-muted); }}
.rr-fineprint {{ font-size: 0.8125rem; color: var(--rr-muted); margin: 0.25rem 0 0; }}

/* "What it does": three cards with a lift, a drawn top line and a cursor tilt (tilt set by motion.html). */
.rr-steps {{ list-style: none; margin: 0.75rem 0 0; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem; perspective: 900px; }}
.rr-step-card {{ position: relative; margin: 0; padding: 1.15rem 1.15rem 1.25rem; background: var(--rr-surface);
  border: 1px solid var(--rr-border); border-radius: 8px; transform-style: preserve-3d;
  transition: transform 0.35s var(--rr-ease), border-color 0.25s var(--rr-ease); }}
.rr-step-card.rr-tilting {{ transition: transform 0.12s linear, border-color 0.25s var(--rr-ease); }}
.rr-step-card::before {{ content: ""; position: absolute; left: -1px; right: -1px; top: -1px; height: 2px; background: var(--rr-ink);
  border-radius: 8px 8px 0 0; transform: scaleX(0); transform-origin: left; transition: transform 0.4s var(--rr-ease); }}
.rr-step-card:hover {{ transform: translateY(-6px); border-color: var(--rr-border-strong); }}
.rr-step-card:hover::before {{ transform: scaleX(1); }}
.rr-step-card h3 {{ font-family: var(--rr-sans); font-size: 1rem; font-weight: 600; color: var(--rr-ink); margin: 0.6rem 0 0.35rem; padding: 0; }}
.rr-step-card p {{ margin: 0; font-size: 0.875rem; line-height: 1.6; }}
@media (max-width: 900px) {{
  .rr-steps {{ grid-template-columns: minmax(0, 1fr); }}
}}
@media (max-width: 820px) {{
  .rr-story-row {{ grid-template-columns: minmax(0, 1fr); gap: 0.6rem; padding: 1.5rem 0; }}
}}

/* --- Depth: flat at rest; on hover a soft shadow fades in (opacity only) with a small lift --- */
[data-testid="stForm"], .rr-panel {{ position: relative; transition: transform 0.3s var(--rr-ease); }}
[data-testid="stForm"]:hover, .rr-panel:hover {{ transform: translateY(-2px); }}
[data-testid="stApp"] [data-testid="stForm"]::after,
[data-testid="stApp"] .rr-panel::after,
[data-testid="stApp"] .rr-steps .rr-step-card::after {{
  content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none; z-index: -1;
  box-shadow: var(--rr-lift-shadow) !important; opacity: 0; transition: opacity 0.3s var(--rr-ease);
}}
[data-testid="stApp"] [data-testid="stForm"]:hover::after,
[data-testid="stApp"] .rr-panel:hover::after,
[data-testid="stApp"] .rr-steps .rr-step-card:hover::after {{ opacity: 1; }}

/* --- Scroll reveal (classes added by motion.html; nothing is hidden unless it loaded) --- */
.rr-reveal {{ transition: opacity 0.7s var(--rr-ease) var(--rr-delay, 0ms), transform 0.7s var(--rr-ease) var(--rr-delay, 0ms); }}
.rr-motion .rr-reveal:not(.rr-in) {{ opacity: 0; transform: translateY(20px); }}
.rr-reveal::before {{ transition: transform 0.9s var(--rr-ease) var(--rr-delay, 0ms); }}
.rr-motion .rr-story-row.rr-reveal:not(.rr-in)::before,
.rr-motion .rr-footer.rr-reveal:not(.rr-in)::before {{ transform: scaleX(0); }}
/* Eyebrow first, then heading, then body. */
.rr-reveal .rr-eyebrow, .rr-reveal .rr-prose > * {{ transition: opacity 0.6s var(--rr-ease); }}
.rr-reveal .rr-eyebrow {{ transition-delay: calc(var(--rr-delay, 0ms) + 0ms); }}
.rr-reveal .rr-prose > h2 {{ transition-delay: calc(var(--rr-delay, 0ms) + 120ms); }}
.rr-reveal .rr-prose > p, .rr-reveal .rr-prose > ol {{ transition-delay: calc(var(--rr-delay, 0ms) + 200ms); }}
.rr-motion .rr-reveal:not(.rr-in) .rr-eyebrow,
.rr-motion .rr-reveal:not(.rr-in) .rr-prose > * {{ opacity: 0; }}

/* --- Result panel: pill pops, plan and trace stage in, rail draws down, citation last --- */
@keyframes rr-pop {{ from {{ opacity: 0; transform: scale(0.8); }} to {{ opacity: 1; transform: scale(1); }} }}
@keyframes rr-in-up {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes rr-in-left {{ from {{ opacity: 0; transform: translateX(-10px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes rr-draw-down {{ from {{ transform: scaleY(0); }} to {{ transform: scaleY(1); }} }}
@keyframes rr-fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
.rr-panel .rr-decision .rr-pill {{ animation: rr-pop 0.35s var(--rr-ease) 0.1s both; }}
.rr-panel .rr-plan li, .rr-panel .rr-step {{ animation: rr-in-up 0.4s var(--rr-ease) both; }}
.rr-panel .rr-plan li:nth-child(1) {{ animation-delay: 0.20s; }}
.rr-panel .rr-plan li:nth-child(2) {{ animation-delay: 0.26s; }}
.rr-panel .rr-plan li:nth-child(3) {{ animation-delay: 0.32s; }}
.rr-panel .rr-plan li:nth-child(4) {{ animation-delay: 0.38s; }}
.rr-panel .rr-plan li:nth-child(5) {{ animation-delay: 0.44s; }}
.rr-panel .rr-plan li:nth-child(6) {{ animation-delay: 0.50s; }}
.rr-panel .rr-plan li:nth-child(n+7) {{ animation-delay: 0.56s; }}
.rr-panel .rr-trace::before {{ animation: rr-draw-down 0.62s var(--rr-ease) 0.56s both; }}
.rr-panel .rr-step:nth-child(1) {{ animation-delay: 0.56s; }}
.rr-panel .rr-step:nth-child(2) {{ animation-delay: 0.62s; }}
.rr-panel .rr-step:nth-child(3) {{ animation-delay: 0.68s; }}
.rr-panel .rr-step:nth-child(4) {{ animation-delay: 0.74s; }}
.rr-panel .rr-step:nth-child(5) {{ animation-delay: 0.80s; }}
.rr-panel .rr-step:nth-child(6) {{ animation-delay: 0.86s; }}
.rr-panel .rr-step:nth-child(n+7) {{ animation-delay: 0.92s; }}
.rr-panel .rr-citation {{ animation: rr-fade 0.5s var(--rr-ease) 1.05s both; }}
.rr-table tr.rr-row-new {{ animation: rr-in-left 0.45s var(--rr-ease) both; }}

/* --- Reading progress hairline (element created by motion.html) --------------- */
#rr-progress {{ position: fixed; top: 0; left: 0; right: 0; height: 2px; background: var(--rr-text); z-index: 1000000;
  transform: scaleX(0); transform-origin: left; pointer-events: none; will-change: transform; }}

@media (prefers-reduced-motion: reduce) {{
  [data-testid="stApp"] *, [data-testid="stApp"] *::before, [data-testid="stApp"] *::after {{
    animation: none !important; transition: none !important;
  }}
  .rr-step-card:hover, [data-testid="stForm"]:hover, .rr-panel:hover,
  [data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover,
  [data-testid="stRadioOption"]:hover [data-testid="stMarkdownContainer"] {{ transform: none; }}
}}
"""


def apply() -> None:
    """Inject the stylesheet. Call once, right after st.set_page_config."""
    st.html(f"<style>{CSS}</style>")
