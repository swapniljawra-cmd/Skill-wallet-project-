"""Multimodal Construction Intelligence Platform.

Runs in demonstration mode without credentials and uses Gemini when a key is
provided in the sidebar. The app intentionally keeps all state in Streamlit
session state so it can be deployed without a database.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from io import BytesIO
from typing import Any, Dict, Optional
from urllib.parse import quote

import streamlit as st
from PIL import Image


APP_NAME = "Multimodal Construction Intelligence Platform"
SEVERITIES = ("Low", "Medium", "High", "Critical")
GEMINI_MODEL = "gemini-1.5-flash"


def configure_page() -> None:
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="🏗️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
        :root { --ink:#102a43; --muted:#627d98; --teal:#0f766e; --gold:#f59e0b; --surface:#f7fafc; }
        html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
        h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; color: var(--ink); }
        .hero { background: linear-gradient(120deg,#102a43 0%,#0f766e 100%); color:white; padding:2.2rem 2.4rem; border-radius:18px; margin-bottom:1.2rem; }
        .hero h1 { color:white; font-size:2.25rem; margin:0 0 .35rem; }
        .hero p { color:#d9f0ee; margin:0; font-size:1.05rem; }
        .eyebrow { color:#fcd34d; text-transform:uppercase; letter-spacing:.13em; font-size:.75rem; font-weight:700; }
        .pill { display:inline-block; border-radius:999px; padding:.28rem .75rem; font-weight:700; font-size:.8rem; }
        .pill.good { background:#dcfce7; color:#166534; } .pill.warn { background:#fef3c7; color:#92400e; }
        .pill.bad { background:#fee2e2; color:#991b1b; } .pill.info { background:#dbeafe; color:#1e40af; }
        .card { background:white; border:1px solid #e5e7eb; border-radius:14px; padding:1rem 1.1rem; box-shadow:0 3px 12px rgba(16,42,67,.05); }
        .muted { color:var(--muted); font-size:.9rem; }
        [data-testid="stMetric"] { background:white; border:1px solid #e5e7eb; padding:1rem; border-radius:12px; }
        .stButton > button { border-radius:9px; font-weight:600; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    if "chat" not in st.session_state:
        st.session_state.chat = [
            {
                "role": "assistant",
                "content": "Hello! I can help with sequencing, concrete quality, PPE controls, and weather protocols. What is happening on site today?",
            }
        ]


def parse_json(text: str) -> Optional[Dict[str, Any]]:
    cleaned = text.strip().replace("```json", "").replace("```", "").strip()
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None


def gemini_request(api_key: str, image: Image.Image, prompt: str) -> Optional[Dict[str, Any]]:
    """Ask Gemini for a JSON response, returning None so callers can use demo mode."""
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            GEMINI_MODEL,
            generation_config={"temperature": 0.1, "response_mime_type": "application/json"},
        )
        response = model.generate_content([prompt, image])
        return parse_json(response.text)
    except Exception as exc:  # provider failures should not take down the dashboard
        st.warning(f"Gemini was unavailable, so demonstration mode was used ({exc.__class__.__name__}).")
        return None


def image_seed(uploaded_file: Any) -> int:
    return int(hashlib.sha256(uploaded_file.getvalue()).hexdigest()[:8], 16)


def demo_safety(seed: int) -> dict[str, Any]:
    score = 72 + seed % 22
    hazards = [
        {"hazard": "Unprotected slab edge", "severity": "High", "remedy": "Install guardrails and toe boards before access resumes."},
        {"hazard": "Material stored near access route", "severity": "Medium", "remedy": "Clear the route and mark a dedicated material laydown zone."},
    ]
    return {
        "safety_score": score,
        "overall_status": "Acceptable with corrective actions",
        "ppe_detection": {
            "helmets": {"status": "Detected", "coverage": "Most workers", "notes": "Verify chin straps at elevated workfaces."},
            "high_visibility_vests": {"status": "Detected", "coverage": "All visible workers", "notes": "Good visibility in the captured area."},
            "steel_toe_boots": {"status": "Not verifiable", "coverage": "Not visible", "notes": "Confirm during toolbox talk."},
            "safety_harnesses": {"status": "Required", "coverage": "Not visible", "notes": "Mandatory at unprotected edges and work at height."},
        },
        "hazards": hazards,
        "standards_note": "Screening aligned to common OSHA PPE controls and IS 456 construction safety considerations; obtain competent-person sign-off.",
    }


def demo_crack(seed: int) -> dict[str, Any]:
    types = ["Hairline", "Settlement", "Thermal Expansion", "Spalling"]
    defect = types[seed % len(types)]
    return {
        "defect_type": defect,
        "estimated_crack_width_mm": round(0.3 + (seed % 15) / 10, 1),
        "severity": "Medium" if defect != "Hairline" else "Low",
        "root_causes": ["Drying shrinkage or thermal movement", "Inadequate curing or restraint", "Local water ingress"],
        "recommended_repairs": ["Map and monitor crack progression", "Seal non-moving cracks with compatible resin", "Use epoxy injection after engineer approval if structural continuity is affected"],
        "urgency": "Schedule engineering inspection within 7 days",
        "disclaimer": "Image screening is indicative only. A licensed structural engineer must inspect load-bearing defects before repair.",
    }


def safety_prompt() -> str:
    return """You are a construction safety auditor. Inspect the image and return ONLY valid JSON with:
{"safety_score":0-100,"overall_status":"string","ppe_detection":{"helmets":{"status":"Detected|Missing|Not verifiable","coverage":"string","notes":"string"},"high_visibility_vests":{},"steel_toe_boots":{},"safety_harnesses":{}},"hazards":[{"hazard":"string","severity":"Low|Medium|High|Critical","remedy":"string"}],"standards_note":"string"}.
Assess visible PPE conservatively under common OSHA controls and Indian IS 456 construction safety considerations. Never claim PPE is present if the image cannot verify it."""


def crack_prompt() -> str:
    return """You are a structural concrete inspection assistant. Return ONLY valid JSON with:
{"defect_type":"Hairline|Settlement|Structural Shear|Thermal Expansion|Spalling","estimated_crack_width_mm":0.0,"severity":"Low|Medium|High|Critical","root_causes":["string"],"recommended_repairs":["string"],"urgency":"string","disclaimer":"string"}.
Use image evidence conservatively, distinguish surface defects from likely structural movement, and state when width cannot be reliably measured."""


def render_safety(result: dict[str, Any]) -> None:
    score = int(result.get("safety_score", 0))
    status = str(result.get("overall_status", "Review required"))
    status_class = "good" if score >= 80 else "warn" if score >= 60 else "bad"
    c1, c2, c3 = st.columns(3)
    c1.metric("Safety score", f"{score}/100")
    c2.metric("Overall status", status)
    c3.markdown(f"**Risk band**<br><span class='pill {status_class}'>{'LOW' if score >= 80 else 'REVIEW' if score >= 60 else 'HIGH RISK'}</span>", unsafe_allow_html=True)
    st.subheader("PPE detection checklist")
    ppe = result.get("ppe_detection", {})
    cols = st.columns(4)
    for col, (label, value) in zip(cols, ppe.items()):
        value = value if isinstance(value, dict) else {"status": str(value)}
        state = str(value.get("status", "Not verifiable"))
        cls = "good" if state.lower() == "detected" else "warn" if "required" in state.lower() or "verif" in state.lower() else "bad"
        col.markdown(f"<div class='card'><b>{label.replace('_', ' ').title()}</b><br><span class='pill {cls}'>{state}</span><p class='muted'>{value.get('notes', '')}</p></div>", unsafe_allow_html=True)
    st.subheader("Identified site hazards")
    for hazard in result.get("hazards", []):
        severity = str(hazard.get("severity", "Medium"))
        cls = "bad" if severity in ("High", "Critical") else "warn" if severity == "Medium" else "good"
        st.markdown(f"**{hazard.get('hazard', 'Unspecified hazard')}** &nbsp; <span class='pill {cls}'>{severity}</span><br><span class='muted'>Corrective remedy: {hazard.get('remedy', 'Obtain competent-person guidance.')}</span>", unsafe_allow_html=True)
    st.caption(result.get("standards_note", "Review with a competent safety professional."))
    st.download_button("Download safety JSON report", json.dumps(result, indent=2), "site-safety-report.json", "application/json")


def render_crack(result: dict[str, Any]) -> None:
    severity = str(result.get("severity", "Medium"))
    cls = "bad" if severity in ("High", "Critical") else "warn" if severity == "Medium" else "good"
    a, b, c = st.columns(3)
    a.metric("Defect classification", result.get("defect_type", "Unclassified"))
    b.metric("Estimated width", f"{result.get('estimated_crack_width_mm', '—')} mm")
    c.markdown(f"**Severity**<br><span class='pill {cls}'>{severity}</span>", unsafe_allow_html=True)
    st.info(f"**Urgency:** {result.get('urgency', 'Engineering review recommended.')}")
    left, right = st.columns(2)
    with left:
        st.subheader("Likely root causes")
        for cause in result.get("root_causes", []):
            st.markdown(f"- {cause}")
    with right:
        st.subheader("Recommended engineering repairs")
        for repair in result.get("recommended_repairs", []):
            st.markdown(f"- {repair}")
    st.warning(result.get("disclaimer", "Have a licensed structural engineer verify the finding before repair."))
    st.download_button("Download crack JSON report", json.dumps(result, indent=2), "crack-diagnostics-report.json", "application/json")


def inspection_tab(api_key: str) -> None:
    st.header("Site Safety & PPE Audit")
    st.caption("Upload a site image for a conservative PPE and hazard screen. Results are decision support, not a substitute for a competent-person inspection.")
    uploaded = st.file_uploader("Construction site photo", type=["jpg", "jpeg", "png"], key="safety_upload")
    if not uploaded:
        st.markdown("<div class='card'><b>What this checks</b><p class='muted'>Hard hats, high-visibility vests, steel-toe boots, harnesses, access hazards, and corrective actions mapped to a structured JSON contract.</p></div>", unsafe_allow_html=True)
        return
    image = Image.open(BytesIO(uploaded.getvalue()))
    st.image(image, caption=uploaded.name, use_container_width=True)
    if st.button("Run PPE & hazard audit", type="primary"):
        with st.spinner("Reviewing image evidence..."):
            result = gemini_request(api_key, image, safety_prompt()) if api_key else None
            render_safety(result or demo_safety(image_seed(uploaded)))


def crack_tab(api_key: str) -> None:
    st.header("Crack Diagnostics & Structural Integrity")
    st.caption("Classify visible concrete or wall defects and prioritize engineering follow-up.")
    uploaded = st.file_uploader("Concrete or wall surface photo", type=["jpg", "jpeg", "png"], key="crack_upload")
    if not uploaded:
        st.markdown("<div class='card'><b>Supported screening</b><p class='muted'>Hairline, settlement, structural shear, thermal expansion, and spalling patterns with indicative width and repair guidance.</p></div>", unsafe_allow_html=True)
        return
    image = Image.open(BytesIO(uploaded.getvalue()))
    st.image(image, caption=uploaded.name, use_container_width=True)
    if st.button("Run crack diagnostics", type="primary"):
        with st.spinner("Assessing defect pattern..."):
            result = gemini_request(api_key, image, crack_prompt()) if api_key else None
            render_crack(result or demo_crack(image_seed(uploaded)))


def format_inr(value: float) -> str:
    if value >= 10_000_000:
        return f"₹{value / 10_000_000:.2f} Cr"
    return f"₹{value / 100_000:.2f} L"


def planning_tab() -> None:
    st.header("Planning & Real Estate Valuation")
    st.caption("A transparent feasibility model for early-stage planning. Replace assumptions with QS and market data before investment decisions.")
    left, right = st.columns([1, 1.4])
    with left:
        structure = st.selectbox("Structure type", ["Residential RCC", "Commercial RCC", "Warehouse / Industrial", "Villa / Premium Residential"])
        sqft = st.number_input("Built-up area (sqft)", min_value=500, max_value=5_000_000, value=25_000, step=500)
        tier = st.selectbox("Location tier", ["Tier 1", "Tier 2", "Tier 3"])
        completion = st.slider("Construction completion", 0, 100, 42, 1)
        rates = {"Residential RCC": 2_800, "Commercial RCC": 3_600, "Warehouse / Industrial": 1_900, "Villa / Premium Residential": 4_500}
        multipliers = {"Tier 1": 1.35, "Tier 2": 1.0, "Tier 3": 0.78}
        rate = rates[structure]
        budget = sqft * rate * multipliers[tier]
        incurred = budget * completion / 100
        market_rate = rate * multipliers[tier] * {"Tier 1": 2.1, "Tier 2": 1.65, "Tier 3": 1.3}[tier]
        valuation = sqft * market_rate
    with right:
        st.subheader("Project economics")
        m1, m2 = st.columns(2)
        m1.metric("Total project budget", format_inr(budget))
        m2.metric("Capital expenditure incurred", format_inr(incurred))
        m3, m4 = st.columns(2)
        m3.metric("Current market asset valuation", format_inr(valuation))
        m4.metric("Estimated value uplift", format_inr(max(0, valuation - incurred)))
        st.progress(completion / 100, text=f"{completion}% construction milestone")
        steel = sqft * 4.2 / 1000
        cement = sqft * 0.42
        st.subheader("Material planning indicators")
        x, y = st.columns(2)
        x.metric("Steel requirement", f"{steel:,.1f} MT")
        y.metric("Cement requirement", f"{cement:,.0f} bags")
        st.caption("Indicative assumptions: steel 4.2 kg/sqft and cement 0.42 bag/sqft. Validate with structural drawings and BOQ.")
    prompt = f"{structure}, {sqft:,} sqft, {tier} Indian city, construction stage {completion}%. Modern sustainable architecture, realistic daylight, site context."
    url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width=1024&height=640&nologo=true"
    st.subheader("Conceptual 3D architectural rendering")
    st.markdown(f"[Open generated concept image ↗]({url})")
    st.caption("Pollinations is an optional concept generator; never use generated imagery as a construction drawing.")


WEATHER_ADVISORIES = {
    "High Wind": ("Suspend crane, hoist, facade, and unsecured elevated work. Tie down materials and inspect temporary works.", "Critical"),
    "Heavy Rain": ("Stop exposed electrical work, isolate standing-water circuits, protect excavations, and postpone concrete placement unless the pour is covered and approved.", "High"),
    "Extreme Heat": ("Schedule strenuous work at cooler hours, provide hydration and shaded rest, monitor heat stress, and extend concrete curing controls.", "High"),
    "Normal": ("Proceed with the approved method statement. Complete toolbox talk, housekeeping, PPE checks, and daily weather log.", "Low"),
}


def assistant_answer(question: str, weather: str) -> str:
    lower = question.lower()
    advisory, _ = WEATHER_ADVISORIES[weather]
    if any(word in lower for word in ("rain", "weather", "wind", "heat")):
        return f"Based on the current **{weather}** condition: {advisory} Record the decision in the daily site log and have the site engineer confirm restart criteria."
    if "concrete" in lower or "curing" in lower:
        return "For concrete work, confirm the approved mix, slump, cube sampling plan, pour sequence, vibration, and curing method. Do not add water on site without mix-design approval."
    if "crane" in lower or "lifting" in lower:
        return "Before lifting, verify the lift plan, SWL, certified accessories, exclusion zone, signal person, wind limit, and pre-use inspection. Stop if any control is missing."
    return "Use the approved method statement and risk assessment as the source of truth. I recommend a toolbox talk, a competent-person walkdown, and documenting any deviation before work starts."


def assistant_tab() -> None:
    st.header("Daily Site Assistant & Weather Advisory")
    weather = st.selectbox("Today's site condition", list(WEATHER_ADVISORIES))
    advisory, level = WEATHER_ADVISORIES[weather]
    st.markdown(f"<div class='card'><span class='pill {'bad' if level == 'Critical' else 'warn' if level == 'High' else 'good'}'>{level} ALERT</span><h3>{weather}</h3><p>{advisory}</p></div>", unsafe_allow_html=True)
    st.subheader("Construction engineering assistant")
    for message in st.session_state.chat:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    question = st.chat_input("Ask about today's controls, sequencing, or site quality...")
    if question:
        st.session_state.chat.append({"role": "user", "content": question})
        answer = assistant_answer(question, weather)
        st.session_state.chat.append({"role": "assistant", "content": answer})
        st.rerun()


def sidebar() -> str:
    with st.sidebar:
        st.markdown("## 🏗️ Skill Wallet")
        st.markdown(f"**{APP_NAME}**")
        st.divider()
        api_key = st.text_input("Google Gemini API key", type="password", value=os.getenv("GEMINI_API_KEY", ""), help="Stored only in the current Streamlit session. Leave blank for deterministic demonstration mode.")
        if api_key:
            st.success("Gemini vision enabled")
        else:
            st.info("Demonstration mode enabled")
        st.divider()
        st.markdown("### Architecture")
        st.caption("Streamlit UI → optional Gemini vision → validated JSON contracts → local session state")
        st.caption("No database • INR-first planning • deployment-ready")
        st.divider()
        st.markdown("### Safety note")
        st.caption("AI outputs are screening aids. A licensed engineer and competent safety professional must approve site decisions.")
    return api_key


def main() -> None:
    configure_page()
    init_state()
    api_key = sidebar()
    st.markdown(f"<div class='hero'><div class='eyebrow'>Skill Wallet Capstone · Platform 01</div><h1>{APP_NAME}</h1><p>Turn site imagery, project inputs, and weather signals into clear construction decisions.</p></div>", unsafe_allow_html=True)
    tabs = st.tabs(["🦺 Safety & PPE", "🧱 Crack Diagnostics", "📊 Planning & Valuation", "🌦️ Daily Assistant"])
    with tabs[0]:
        inspection_tab(api_key)
    with tabs[1]:
        crack_tab(api_key)
    with tabs[2]:
        planning_tab()
    with tabs[3]:
        assistant_tab()


if __name__ == "__main__":
    main()
