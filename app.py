# app.py
import json
from typing import List, Dict, Any

import pandas as pd
import streamlit as st

from settings import DEFAULT_MODEL_NAME, MODEL_OPTIONS, STYLE_PROFILE_OPTIONS
from openai_client import call_openai_json, get_openai_client
from utils import (
    BrandInfo,
    PageDefinition,
    SEOEntry,
    build_site_export,
    load_text_from_upload,
    parse_keywords,
    parse_seo_csv,
    parse_sitemap_csv,
    render_page_preview,
    safe_json_loads,
)
from generation_pipeline import generate_medical_page
from prompt_builder import analyze_homepage_copy
from rule_storage import RuleStore, load_core_rules
from golden_rules import embed_rule_chunks, split_into_chunks


st.set_page_config(
    page_title="Agency Website Copy Generator",
    layout="wide",
)

CORE_RULE_PATH = "docs/core_rules.json"
RULE_STORE_PATH = ".cache/golden_rules/index"


def generate_service_keywords(
    client,
    services: List[str],
    location: str,
    audience_intent: str,
    model_name: str,
) -> List[str]:
    """Create location-aware primary keyword ideas from a list of services."""

    prompt = f"""
You are an SEO strategist.
Create location-ready primary keywords that match how people search for providers.

Services to target: {', '.join(services)}
Location: {location or 'Not provided'}
Search intent: {audience_intent}

Rules:
- Favor phrasing that mirrors the pattern "best <service> <location>" while keeping grammar natural (e.g., "best Invisalign dentist Los Angeles").
- Keep each keyword concise (max ~6 words) and avoid duplicates.
- Return 1-2 variants per service if needed for natural phrasing.

Return a JSON object: {{"keywords": ["keyword one", "keyword two"]}}
"""

    messages = [
        {
            "role": "system",
            "content": "Provide concise, search-friendly keywords only. Return valid JSON.",
        },
        {"role": "user", "content": prompt},
    ]

    raw = call_openai_json(client, messages, model_name=model_name)
    parsed = safe_json_loads(raw)
    keywords = parsed.get("keywords", []) if isinstance(parsed, dict) else []
    return [kw for kw in keywords if isinstance(kw, str) and kw.strip()]


def generate_document_keywords(
    client,
    *,
    brand_name: str,
    industry: str,
    location: str,
    audience_intent: str,
    page_goal: str,
    services: List[str],
    supporting_text: str,
    model_name: str,
) -> Dict[str, List[str]]:
    """Derive keyword ideas from uploaded references and the buyer journey."""

    prompt = f"""
You are an SEO keyword strategist helping plan a website build for a healthcare practice.

Brand: {brand_name}
Industry/Niche: {industry}
Primary location: {location or 'Not provided'}
Search intent / buyer journey: {audience_intent}
Primary CTA/goal: {page_goal}
Service offerings: {', '.join(services) or 'Not provided'}

Supporting documents (brand book, onboarding forms, homepage copy):
{supporting_text[:3500]}

Tasks:
1) Suggest 5-10 paramount/umbrella keywords that capture the brand and journey (e.g., "cosmetic dentistry clinic Los Angeles").
2) Suggest 1-3 primary keywords per service that match how users search when ready to choose a provider.
3) Keep phrasing buyer-journey aware (discovery vs booking) and location-aware.

Return JSON with two arrays:
{{
  "paramount_keywords": ["..."],
  "primary_keywords": ["..."]
}}
Only return JSON.
"""

    messages = [
        {
            "role": "system",
            "content": "Return clean JSON keyword recommendations without commentary.",
        },
        {"role": "user", "content": prompt},
    ]

    raw = call_openai_json(client, messages, model_name=model_name)
    parsed = safe_json_loads(raw)
    if not isinstance(parsed, dict):
        return {"paramount_keywords": [], "primary_keywords": []}

    paramount = parsed.get("paramount_keywords", []) or []
    primary = parsed.get("primary_keywords", []) or []
    paramount = [kw for kw in paramount if isinstance(kw, str) and kw.strip()]
    primary = [kw for kw in primary if isinstance(kw, str) and kw.strip()]
    return {"paramount_keywords": paramount, "primary_keywords": primary}

# Subtle UI theming for a friendlier workspace
st.markdown(
    """
    <style>
        .app-gradient-bg {
            background: radial-gradient(circle at 15% 20%, rgba(99, 102, 241, 0.24), transparent 35%),
                        radial-gradient(circle at 85% 10%, rgba(34, 211, 238, 0.18), transparent 30%),
                        linear-gradient(120deg, #0b1224 0%, #0e1429 45%, #070a15 100%);
            padding: 1.35rem 1.6rem;
            border-radius: 20px;
            color: #e5e7eb;
            box-shadow: 0 12px 40px rgba(0,0,0,0.35);
            border: 1px solid rgba(255,255,255,0.05);
        }
        .section-card {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            padding: 1rem 1.25rem;
            border-radius: 18px;
            margin-bottom: 1rem;
            box-shadow: 0 16px 40px rgba(0,0,0,0.18);
        }
        .stButton button {
            border-radius: 12px !important;
            padding: 0.65rem 1.15rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.01em;
            background: linear-gradient(90deg, #6366f1, #22d3ee);
            color: #0b1224;
            border: none;
        }
        .stTabs [role="tab"] {
            padding: 0.75rem 1.15rem !important;
            border-radius: 14px 14px 0 0 !important;
            font-weight: 600;
        }
        .stTextInput > div > div > input, .stTextArea textarea {
            border-radius: 12px !important;
            border: 1px solid rgba(255,255,255,0.15) !important;
            background: rgba(255,255,255,0.02) !important;
        }
        .metric-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 10px;
            border-radius: 999px;
            background: rgba(99,102,241,0.12);
            color: #c7d2fe;
            border: 1px solid rgba(99,102,241,0.3);
            font-size: 0.9rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

IMAGING_AND_DIAGNOSTIC_OPTIONS = [
    "Imaging & Diagnostic Services",
    "Medical Imaging Center",
    "Diagnostic Radiology",
    "MRI Center",
    "CT Scan Center",
    "PET Scan Center",
    "X-Ray Services",
    "Ultrasound Center",
    "Breast Imaging / Mammography",
    "DEXA Bone Density Testing",
    "Mobile Imaging Services",
    "Interventional Radiology (IR)",
    "Cardiac Imaging",
    "Nuclear Medicine",
]

INDUSTRY_OPTIONS: List[str] = [
    "General Medicine",
    "Internal Medicine",
    "Family Medicine",
    "Concierge Medicine",
    "Urgent Care",
    "Telemedicine",
    "Primary Care",
    "Plastic Surgery",
    "Cosmetic Surgery",
    "Aesthetic Medicine",
    "Medical Spa (MedSpa)",
    "Botox & Fillers",
    "Facial Rejuvenation",
    "Anti-Aging Medicine",
    "Cosmetic Dermatology",
    "Laser & Skin Treatments",
    "Body Contouring",
    "General Dentistry",
    "Cosmetic Dentistry",
    "Pediatric Dentistry",
    "Orthodontics",
    "Periodontics",
    "Endodontics",
    "Prosthodontics",
    "Oral Surgery",
    "Dental Implants",
    "TMJ & Bite Correction",
    "General Surgery",
    "Bariatric Surgery",
    "Colorectal Surgery",
    "Orthopedic Surgery",
    "Spine Surgery",
    "Vascular Surgery",
    "Cardiothoracic Surgery",
    "ENT Surgery",
    "Reconstructive Surgery",
    "Obstetrics & Gynecology (OB-GYN)",
    "Fertility / Reproductive Medicine",
    "Women’s Health Clinics",
    "Men’s Health Clinics",
    "Hormone Replacement Therapy (HRT)",
    "Testosterone Therapy",
    "Pelvic Floor Therapy",
    "Sexual Wellness",
    "Regenerative Medicine",
    "Functional Medicine",
    "Integrative Medicine",
    "Holistic Medicine",
    "Stem Cell Therapy",
    "PRP (Platelet-Rich Plasma)",
    "IV Therapy",
    "NAD+ Therapy",
    "Biohacking Clinics",
    "Peptide Therapy",
    "Pain Management",
    "Interventional Pain",
    "Neurology",
    "Neurosurgery",
    "Spine Center",
    "Migraine Clinic",
    "Headache Specialist",
    "Movement Disorders",
    "Gastroenterology (GI)",
    "Colorectal Health",
    "Digestive Health Clinics",
    "Weight Loss Clinics",
    "Medical Weight Management",
    "Bariatric Medicine",
    "Psychiatry",
    "Psychology",
    "Therapy & Counseling",
    "ADHD Clinics",
    "Depression & Anxiety Centers",
    "Ketamine Clinics",
    "TMS Therapy",
    "Cardiology",
    "Vascular Medicine",
    "Vein Clinics",
    "Varicose Vein Treatment",
    "General Dermatology",
    "Cosmetic Dermatology",
    "MOHS Surgery",
    "Skin Cancer Clinics",
    "Acne & Rosacea Clinics",
    "Hair Restoration",
    "Ophthalmology",
    "Optometry",
    "LASIK & Refractive Surgery",
    "Otolaryngology (ENT)",
    "Audiology",
    "Hearing Aid Centers",
    "Sinus & Allergy Clinics",
    "Pediatrics",
    "Pediatric Dentistry",
    "Pediatric Neurology",
    "Pediatric ENT",
    "Adolescent Behavioral Health",
    "Urology",
    "Erectile Dysfunction Clinics",
    "Nephrology",
    "Endocrinology",
    "Diabetes Management",
    "Pulmonology",
    "Sleep Medicine",
    "CPAP Alternatives",
    "Sleep Apnea Clinics",
    "Physical Therapy",
    "Occupational Therapy",
    "Sports Medicine",
    "Chiropractic",
    "Physical Rehabilitation",
    "Athletic Performance Centers",
    "Post-Surgical Rehab",
    "Allergy & Immunology",
    "Rheumatology",
    "Infectious Disease",
    "Travel Medicine",
    "Genetic Counseling",
    "Wound Care Centers",
    "Concierge Pediatrics",
    "Concierge OB-GYN",
    "Suboxone / MAT Clinics",
    "Aesthetics + Wellness Hybrids",
    *IMAGING_AND_DIAGNOSTIC_OPTIONS,
]
CUSTOM_INDUSTRY_OPTION = "Other / Custom"


with st.sidebar:
    st.subheader("Quick start")
    st.markdown(
        "1. Add brand and sitemap inputs on **Build site copy**.\n"
        "2. Upload SEO keywords to tighten targeting.\n"
        "3. Click **Generate Site Copy** and preview each page."
    )
    st.divider()
    st.markdown(
        "Need a fast spot-check? Jump to **Content QA lab** to run a single page "
        "without configuring the entire sitemap."
    )


def init_session_state():
    if "results" not in st.session_state:
        st.session_state["results"] = []
    if "uploaded_examples" not in st.session_state:
        st.session_state["uploaded_examples"] = {}
    if "lab_result" not in st.session_state:
        st.session_state["lab_result"] = None
    if "rule_store" not in st.session_state:
        st.session_state["rule_store"] = RuleStore()
    if "golden_rule_text" not in st.session_state:
        st.session_state["golden_rule_text"] = ""
    if "static_rules" not in st.session_state:
        st.session_state["static_rules"] = load_core_rules(CORE_RULE_PATH)
    if "rule_store_loaded" not in st.session_state:
        st.session_state["rule_store_loaded"] = False
    if "golden_rule_mode" not in st.session_state:
        st.session_state["golden_rule_mode"] = "retrieval"
    if "golden_rule_top_n" not in st.session_state:
        st.session_state["golden_rule_top_n"] = 12
    if "model_name" not in st.session_state:
        st.session_state["model_name"] = DEFAULT_MODEL_NAME
    if "brand_book_text" not in st.session_state:
        st.session_state["brand_book_text"] = ""
    if "onboarding_text" not in st.session_state:
        st.session_state["onboarding_text"] = ""
    if "home_page_text" not in st.session_state:
        st.session_state["home_page_text"] = ""
    if "lab_doc_keyword_suggestions" not in st.session_state:
        st.session_state["lab_doc_keyword_suggestions"] = {}
    if "lab_generated_service_keywords" not in st.session_state:
        st.session_state["lab_generated_service_keywords"] = []
    if "lab_services_raw" not in st.session_state:
        st.session_state["lab_services_raw"] = ""

def main():
    init_session_state()

    if not st.session_state.get("rule_store_loaded"):
        st.session_state["rule_store"] = RuleStore.load(RULE_STORE_PATH)
        st.session_state["rule_store_loaded"] = True

    st.markdown(
        """
        <div class="app-gradient-bg">
            <h1 style="margin-bottom:0.4rem;">Website Copy Generation</h1>
            <p style="margin:0; opacity:0.85;">Internal agency tool to go from sitemap to polished page copy.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.subheader("Model & runtime settings")
        current_model = st.session_state.get("model_name", DEFAULT_MODEL_NAME)
        default_index = (
            MODEL_OPTIONS.index(current_model)
            if current_model in MODEL_OPTIONS
            else MODEL_OPTIONS.index(DEFAULT_MODEL_NAME)
        )
        selected_model = st.selectbox(
            "OpenAI model",
            options=MODEL_OPTIONS,
            index=default_index,
            key="model_name_select",
            help="Choose which GPT model to run for generation steps.",
        )
        st.session_state["model_name"] = selected_model

    # Initialize OpenAI client
    try:
        client = get_openai_client()
        api_ok = True
    except Exception as exc:
        api_ok = False
        st.error(str(exc))
        st.stop()

    build_tab, lab_tab = st.tabs(["Build site copy", "Content QA lab"])

    # ----------------------------------------
    # TAB 1 – SITE COPY BUILDER
    # ----------------------------------------
    with build_tab:
        col_left, col_right = st.columns([1, 1.2])

        with col_left:
            st.header("1. Brand & Project Info")

            brand_name = st.text_input(
                "Brand / Business Name", value="", key="brand_name"
            )
            industry_option_list = INDUSTRY_OPTIONS + [CUSTOM_INDUSTRY_OPTION]
            saved_industry = st.session_state.get("industry", INDUSTRY_OPTIONS[0])
            default_industry_choice = (
                saved_industry
                if saved_industry in industry_option_list
                else CUSTOM_INDUSTRY_OPTION
            )
            industry_choice = st.selectbox(
                "Industry / Niche",
                options=industry_option_list,
                index=industry_option_list.index(default_industry_choice),
                key="industry_choice",
                help="Search or pick the closest match; choose Other to type a custom niche.",
            )
            industry_custom = st.text_input(
                "Custom industry / niche",
                value=(
                    saved_industry
                    if default_industry_choice == CUSTOM_INDUSTRY_OPTION
                    else st.session_state.get("industry_custom", "")
                ),
                key="industry_custom",
                disabled=industry_choice != CUSTOM_INDUSTRY_OPTION,
            )
            industry = (
                industry_custom.strip()
                if industry_choice == CUSTOM_INDUSTRY_OPTION
                else industry_choice
            )
            st.session_state["industry"] = industry
            location = st.text_input(
                "Primary Location (city, state/region)", value="", key="location"
            )
            voice_tone = st.text_area(
                "Brand voice & tone",
                value="Approachable, expert, no fluff, benefit-driven.",
                key="voice_tone",
            )
            target_audience = st.text_area(
                "Target audience description",
                value="",
                key="target_audience",
            )
            audience_intent = st.selectbox(
                "Audience intent",
                options=[
                    "Informational",
                    "Transactional",
                    "Book an appointment",
                    "Compare providers",
                    "Patient education",
                ],
                key="audience_intent",
            )
            uvp = st.text_area(
                "Unique Value Proposition / Differentiators",
                value="",
                key="uvp",
            )
            notes = st.text_area(
                "Existing site URL(s) or notes (optional)",
                value="",
                key="notes",
            )
            page_goal = st.text_input(
                "Primary page goal / CTA style",
                value="Encourage visitors to book an appointment",
                key="page_goal",
            )

            st.header("2. Sitemap / Pages")

            allowed_page_types = ["home", "service", "sub service", "about", "location"]

            st.caption(
                "Upload a sitemap CSV with columns: `slug`, `page_name`, `page_type` "
                "(page_type must be one of: home, service, sub service, about, location). "
                "You can edit rows after import."
            )

            sitemap_file = st.file_uploader(
                "Upload Sitemap CSV",
                type=["csv"],
                key="sitemap_uploader",
            )

            sitemap_warnings = []
            if sitemap_file is not None:
                pages_df, sitemap_warnings = parse_sitemap_csv(
                    sitemap_file, allowed_page_types
                )
            else:
                # Fallback default sitemap
                pages_df = pd.DataFrame(
                    [
                        {"slug": "home", "page_name": "Home", "page_type": "home"},
                        {
                            "slug": "services/sample-service",
                            "page_name": "Sample Service",
                            "page_type": "service",
                        },
                    ]
                )

            if sitemap_warnings:
                for w in sitemap_warnings:
                    st.warning(w)

            pages_df = st.data_editor(
                pages_df,
                num_rows="dynamic",
                column_config={
                    "slug": st.column_config.TextColumn("Slug", required=True),
                    "page_name": st.column_config.TextColumn("Page Name", required=True),
                    "page_type": st.column_config.SelectboxColumn(
                        "Page Type",
                        options=allowed_page_types,
                        required=True,
                    ),
                },
                key="pages_editor",
            )

            st.header("3. SEO Keyword Map (CSV)")

            seo_file = st.file_uploader(
                "Upload SEO CSV (slug, primary_keyword, supporting_keywords)",
                type=["csv"],
            )
            seo_map, seo_warnings = parse_seo_csv(seo_file)

            if seo_warnings:
                for w in seo_warnings:
                    st.warning(w)

            if not seo_file:
                st.warning(
                    "No SEO CSV uploaded. The tool will still run, but SEO targeting per page will be limited."
                )

            st.header("4. Style Profile")

            style_profile = st.selectbox(
                "Style profile",
                options=STYLE_PROFILE_OPTIONS,
                index=0,
                key="style_profile",
            )

            st.caption(
                "Optional: Upload example JSON mapping page_type -> example payload to override the defaults."
            )
            example_upload = st.file_uploader(
                "Upload example JSON", type=["json"], key="example_uploader"
            )
            if example_upload is not None:
                try:
                    uploaded_data = json.load(example_upload)
                    if not isinstance(uploaded_data, dict):
                        raise ValueError("Uploaded file must be a JSON object mapping page_type to example.")
                    st.session_state["uploaded_examples"] = uploaded_data
                    st.success(
                        "Example JSON loaded. It will override built-in examples for matching page types."
                    )
                    st.caption(
                        "Loaded examples for page types: "
                        + ", ".join(sorted(uploaded_data.keys()))
                    )
                except Exception as exc:
                    st.error(f"Failed to load example JSON: {exc}")

            st.header("5. Golden Rules & Assets")
            st.caption("Hybrid static + retrieval: core rules load automatically; embed the Golden Rule Framework for semantic lookups.")

            with st.expander("View static core rules", expanded=False):
                st.json(st.session_state.get("static_rules", {}))

            golden_rule_mode = st.radio(
                "Dynamic rule application",
                options=["retrieval", "full_text"],
                format_func=lambda opt: (
                    "Retrieve top relevant chunks"
                    if opt == "retrieval"
                    else "Inject the full rule set (no chunking)"
                ),
                index=0 if st.session_state.get("golden_rule_mode") == "retrieval" else 1,
                key="golden_rule_mode_radio",
                help="Use chunked retrieval for concise prompts or inject the full text when you need every rule applied.",
            )
            st.session_state["golden_rule_mode"] = golden_rule_mode

            if golden_rule_mode == "retrieval":
                top_n = st.slider(
                    "How many rule chunks to inject",
                    min_value=3,
                    max_value=24,
                    value=st.session_state.get("golden_rule_top_n", 8),
                    step=1,
                    help="Controls how many embedded rule chunks are pulled into each prompt.",
                )
                st.session_state["golden_rule_top_n"] = top_n
            else:
                st.info(
                    "Full rule set will be sent as one block. Ensure it fits the selected model's context window."
                )

            golden_rule_file = st.file_uploader(
                "Golden Rule Framework document (TXT, DOCX, or PDF)",
                type=["txt", "docx", "pdf"],
                key="golden_rule_upload",
            )
            golden_rule_text = st.text_area(
                "Paste or edit the framework", value=st.session_state.get("golden_rule_text", ""), height=200
            )

            if st.button("Embed & save Golden Rule Framework", use_container_width=True):
                combined_rule_text = golden_rule_text + "\n" + load_text_from_upload(golden_rule_file)
                combined_rule_text = combined_rule_text.strip()
                if not combined_rule_text:
                    st.error("Please provide golden rule content to embed.")
                else:
                    try:
                        store = st.session_state.get("rule_store") or RuleStore()
                        store.build(client, combined_rule_text)
                        store.save(RULE_STORE_PATH)
                        st.session_state["rule_store"] = store
                        st.session_state["golden_rule_text"] = combined_rule_text
                        st.success(
                            f"Embedded {len(store.chunks)} rule chunk(s) with tags; saved for reuse across sessions."
                        )
                        with st.expander("Chunk preview", expanded=False):
                            for idx, chunk in enumerate(store.chunks[:6]):
                                st.markdown(f"**Chunk {idx+1}** — tags: {', '.join(chunk.metadata.get('tags', []))}")
                                st.caption(chunk.text[:400] + ("..." if len(chunk.text) > 400 else ""))
                    except Exception as exc:
                        st.error(f"Failed to embed golden rules: {exc}")

            st.caption("Upload brand and onboarding references (plain text, DOCX, or PDF)")
            brand_col, onboard_col = st.columns(2)
            with brand_col:
                brand_book_upload = st.file_uploader(
                    "Brand book copy", type=["txt", "docx", "pdf"], key="brand_book_uploader"
                )
                brand_book_text = st.text_area(
                    "Brand book text (optional)",
                    value=st.session_state.get("brand_book_text", ""),
                    height=140,
                    key="brand_book_text_input",
                )
            with onboard_col:
                onboarding_upload = st.file_uploader(
                    "Client onboarding form", type=["txt", "docx", "pdf"], key="onboarding_uploader"
                )
                onboarding_text = st.text_area(
                    "Onboarding notes (optional)",
                    value=st.session_state.get("onboarding_text", ""),
                    height=140,
                    key="onboarding_text_input",
                )

            home_page_upload = st.file_uploader(
                "Reference home page copy", type=["txt", "docx", "pdf"], key="home_page_uploader"
            )
            home_page_text = st.text_area(
                "Home page reference (optional)",
                value=st.session_state.get("home_page_text", ""),
                height=140,
                key="home_page_text_input",
            )

            if brand_book_upload:
                uploaded_brand = load_text_from_upload(brand_book_upload)
                if uploaded_brand:
                    brand_book_text = (brand_book_text + "\n" + uploaded_brand).strip()
                    st.session_state["brand_book_text"] = brand_book_text
            else:
                st.session_state["brand_book_text"] = brand_book_text

            if onboarding_upload:
                uploaded_onboarding = load_text_from_upload(onboarding_upload)
                if uploaded_onboarding:
                    onboarding_text = (onboarding_text + "\n" + uploaded_onboarding).strip()
                    st.session_state["onboarding_text"] = onboarding_text
            else:
                st.session_state["onboarding_text"] = onboarding_text

            if home_page_upload:
                uploaded_home_page = load_text_from_upload(home_page_upload)
                if uploaded_home_page:
                    home_page_text = (home_page_text + "\n" + uploaded_home_page).strip()
                    st.session_state["home_page_text"] = home_page_text
            else:
                st.session_state["home_page_text"] = home_page_text

            supporting_doc_text = "\n\n".join(
                [t for t in [brand_book_text, onboarding_text, home_page_text] if t.strip()]
            ).strip()
            service_offerings = [
                str(row.get("page_name", "")).strip()
                for _, row in pages_df.iterrows()
                if str(row.get("page_type", "")).strip() in {"service", "sub service"}
            ]

            keyword_doc_col1, keyword_doc_col2 = st.columns([1, 1])
            with keyword_doc_col1:
                doc_kw_help = st.button(
                    "Generate keywords from uploaded documents", use_container_width=True
                )
            with keyword_doc_col2:
                apply_doc_primary = st.button(
                    "Use document keywords as primary list", use_container_width=True
                )

            if doc_kw_help:
                if not supporting_doc_text:
                    st.warning("Upload or paste supporting documents to extract keywords first.")
                else:
                    with st.spinner("Mining documents for paramount and service keywords..."):
                        try:
                            doc_keywords = generate_document_keywords(
                                client,
                                brand_name=brand_name,
                                industry=industry,
                                location=location,
                                audience_intent=audience_intent,
                                page_goal=page_goal,
                                services=service_offerings,
                                supporting_text=supporting_doc_text,
                                model_name=st.session_state.get("model_name", DEFAULT_MODEL_NAME),
                            )
                            st.session_state["doc_keyword_suggestions"] = doc_keywords
                            st.success("Keyword ideas generated from supporting docs.")
                        except Exception as exc:
                            st.error(f"Failed to generate document keywords: {exc}")

            doc_suggestions = st.session_state.get("doc_keyword_suggestions", {})
            if doc_suggestions:
                with st.expander("Document-derived keyword ideas", expanded=False):
                    paramount = doc_suggestions.get("paramount_keywords", [])
                    primary = doc_suggestions.get("primary_keywords", [])
                    if paramount:
                        st.markdown("**Paramount ideas:** " + ", ".join(paramount))
                    if primary:
                        st.markdown("**Primary ideas:** " + ", ".join(primary))
                    if not paramount and not primary:
                        st.caption("No keyword suggestions available yet.")

            if apply_doc_primary and st.session_state.get("doc_keyword_suggestions"):
                primary_list = st.session_state["doc_keyword_suggestions"].get(
                    "primary_keywords", []
                )
                st.session_state["primary_kw_raw"] = "\n".join(primary_list)
                st.session_state["paramount_kw_raw"] = "\n".join(
                    st.session_state["doc_keyword_suggestions"].get("paramount_keywords", [])
                )
                st.success("Applied document keyword recommendations to the inputs.")

            with st.expander("Homepage tone snapshot", expanded=False):
                profile = analyze_homepage_copy(home_page_text)
                if profile:
                    cols = st.columns(len(profile))
                    for idx, (k, v) in enumerate(profile.items()):
                        cols[idx].markdown(f"<div class='metric-badge'><strong>{k}</strong>: {v}</div>", unsafe_allow_html=True)
                else:
                    st.caption("No homepage reference provided yet. Upload copy to mirror tone and CTA pacing.")

            st.header("6. Keyword Inputs")
            paramount_kw_file = st.file_uploader(
                "Upload paramount keyword list (TXT/CSV)", type=["txt", "csv"], key="paramount_kw_file"
            )
            paramount_kw_raw = st.text_area(
                "Paramount keyword list (comma or newline separated)",
                value=st.session_state.get("paramount_kw_raw", ""),
                key="paramount_kw_raw",
            )
            if paramount_kw_file:
                st.session_state["paramount_kw_raw"] = (
                    st.session_state.get("paramount_kw_raw", "")
                    + "\n"
                    + load_text_from_upload(paramount_kw_file)
                ).strip()
            paramount_kw_raw = st.session_state.get("paramount_kw_raw", "")

            primary_kw_file = st.file_uploader(
                "Upload primary keyword list (TXT/CSV)", type=["txt", "csv"], key="primary_kw_file"
            )
            primary_kw_raw = st.text_area(
                "Primary keyword list (comma or newline separated)",
                value=st.session_state.get("primary_kw_raw", ""),
                key="primary_kw_raw",
            )
            if primary_kw_file:
                st.session_state["primary_kw_raw"] = (
                    st.session_state.get("primary_kw_raw", "")
                    + "\n"
                    + load_text_from_upload(primary_kw_file)
                ).strip()
            primary_kw_raw = st.session_state.get("primary_kw_raw", "")

            st.subheader("Service-based keyword helper")
            services_raw = st.text_area(
                "List of services (one per line or comma separated)",
                value=st.session_state.get("services_raw", ""),
                key="services_raw",
                help="Provide services to generate location-ready primary keyword ideas.",
            )
            keyword_action_cols = st.columns([1, 1])
            with keyword_action_cols[0]:
                generate_kw_button = st.button(
                    "Generate location-based keywords", use_container_width=True
                )
            with keyword_action_cols[1]:
                apply_primary_button = st.button(
                    "Make generated list the primary keywords", use_container_width=True
                )

            if generate_kw_button:
                service_list = parse_keywords(services_raw)
                if not service_list:
                    st.warning("Provide at least one service to generate keywords.")
                elif not location:
                    st.warning("Add a primary location to shape the keyword phrasing.")
                else:
                    with st.spinner("Creating location-aware primary keywords..."):
                        try:
                            generated_keywords = generate_service_keywords(
                                client,
                                services=service_list,
                                location=location,
                                audience_intent=audience_intent,
                                model_name=st.session_state.get(
                                    "model_name", DEFAULT_MODEL_NAME
                                ),
                            )
                            st.session_state["generated_service_keywords"] = generated_keywords
                            st.success("Created keyword ideas using your service list and location.")
                        except Exception as exc:
                            st.error(f"Failed to generate service keywords: {exc}")

            generated_service_keywords = st.session_state.get(
                "generated_service_keywords", []
            )
            if generated_service_keywords:
                st.caption(
                    "Generated keywords follow the 'best + service + location' search pattern."
                )
                st.write("\n".join(f"• {kw}" for kw in generated_service_keywords))

            if apply_primary_button and generated_service_keywords:
                st.session_state["primary_kw_raw"] = "\n".join(generated_service_keywords)
                primary_kw_raw = st.session_state["primary_kw_raw"]
                st.success("Primary keyword list updated from generated suggestions.")

            st.header("7. Controls")
            page_topic = st.text_input(
                "Page topic / subject (e.g., facelift, concierge medicine)", value=""
            )

            show_intermediate = st.checkbox(
                "Show intermediate steps (outline / draft / refinement)", value=True
            )

            generate_button = st.button(
                "Generate Site Copy", type="primary", use_container_width=True
            )

        # ----------------------------------------
        # RIGHT COLUMN – RESULTS
        # ----------------------------------------
        with col_right:
            st.header("Results")
            cols_actions = st.columns([0.4, 0.6])
            with cols_actions[0]:
                if st.button("Clear results", use_container_width=True):
                    st.session_state["results"] = []
                    st.success("Results cleared. Ready for a fresh run.")

        if generate_button and api_ok:
            if not brand_name or not industry:
                st.error("Please fill in at least Brand / Business Name and Industry / Niche.")
            else:
                brand_info = BrandInfo(
                    name=brand_name.strip(),
                    industry=industry.strip(),
                    location=location.strip(),
                    voice_tone=voice_tone.strip(),
                    target_audience=target_audience.strip(),
                    uvp=uvp.strip(),
                    notes=notes.strip(),
                )

                paramount_keywords = parse_keywords(paramount_kw_raw)
                primary_keywords = parse_keywords(primary_kw_raw)
                st.session_state["paramount_kw_cache"] = paramount_keywords
                st.session_state["primary_kw_cache"] = primary_keywords
                rule_store: RuleStore = st.session_state.get("rule_store")
                brand_book_text = st.session_state.get("brand_book_text", "")
                onboarding_text = st.session_state.get("onboarding_text", "")
                home_page_text = st.session_state.get("home_page_text", "")

                if golden_rule_mode == "retrieval" and (rule_store is None or not rule_store.is_ready):
                    st.warning(
                        "No embedded golden rules detected. Add and embed them to guide medical copy."
                    )

                page_definitions: List[PageDefinition] = []
                unsupported_types = set()

                for _, row in pages_df.iterrows():
                    slug = str(row.get("slug", "")).strip()
                    page_name = str(row.get("page_name", "")).strip()
                    page_type = str(row.get("page_type", "")).strip()

                    if not slug or not page_name or not page_type:
                        continue

                    if page_type not in allowed_page_types:
                        unsupported_types.add(page_type)
                        continue

                    page_definitions.append(
                        PageDefinition(
                            slug=slug, page_name=page_name, page_type=page_type
                        )
                    )

                if unsupported_types:
                    st.warning(
                        "The following page_type values are unsupported and were skipped: "
                        + ", ".join(sorted(unsupported_types))
                    )

                if not page_definitions:
                    st.error("Please define at least one valid page in the sitemap.")
                else:
                    st.session_state["results"] = []
                    progress = st.progress(0.0)
                    for idx, page in enumerate(page_definitions):
                        st.markdown(f"#### Generating: {page.page_name} (`{page.slug}`)")
                        with st.spinner(
                            f"Generating outline, draft, and refinement for {page.page_name}..."
                        ):
                            seo_entry = seo_map.get(page.slug)

                            outline = None
                            draft = None
                            final_json = None

                            try:
                                final_json = generate_medical_page(
                                    client,
                                    brand_info,
                                    page,
                                    seo_entry,
                                    style_profile,
                                    topic=page_topic,
                                    paramount_keywords=paramount_keywords,
                                    primary_keywords=primary_keywords,
                                    brand_book=brand_book_text,
                                    onboarding_notes=onboarding_text,
                                    home_page_copy=home_page_text,
                                    static_rules=st.session_state.get("static_rules", {}),
                                    rule_store=rule_store,
                                    audience_intent=audience_intent,
                                    page_goal=page_goal,
                                    golden_rule_text=st.session_state.get(
                                        "golden_rule_text", ""
                                    ),
                                    golden_rule_mode=st.session_state.get(
                                        "golden_rule_mode", "retrieval"
                                    ),
                                    top_rules=st.session_state.get("golden_rule_top_n", 12),
                                    model_name=st.session_state.get(
                                        "model_name", DEFAULT_MODEL_NAME
                                    ),
                                )
                            except Exception as exc:
                                st.error(
                                    f"Error generating page for {page.page_name} ({page.slug}): {exc}"
                                )

                            st.session_state["results"].append(
                                {
                                    "page": page,
                                    "seo": seo_entry,
                                    "outline": outline,
                                    "draft": draft,
                                    "final": final_json,
                                }
                            )

                        progress.progress((idx + 1) / len(page_definitions))
                    progress.empty()

        with col_right:
            # Display results
            results: List[Dict[str, Any]] = st.session_state.get("results", [])

            if results:
                for entry in results:
                    page: PageDefinition = entry["page"]
                    seo_entry = entry.get("seo")
                    outline = entry.get("outline")
                    draft = entry.get("draft")
                    final_json = entry.get("final")

                    label = f"{page.page_name} ({page.slug})"
                    with st.expander(label, expanded=False):
                        if seo_entry:
                            st.markdown(
                                f"**SEO Primary Keyword:** {seo_entry.primary_keyword or 'None'}"
                            )
                            if seo_entry.supporting_keywords:
                                st.markdown(
                                    f"**Supporting Keywords:** {', '.join(seo_entry.supporting_keywords)}"
                                )

                        if show_intermediate:
                            st.markdown("##### Outline (JSON)")
                            if outline is not None:
                                st.json(outline)
                            else:
                                st.info("No outline available (error in generation).")

                            st.markdown("##### Draft (JSON)")
                            if draft is not None:
                                st.json(draft)
                            else:
                                st.info("No draft available (error in generation).")

                        st.markdown("##### Final Refined JSON")
                        if final_json is not None:
                            st.json(final_json)
                        else:
                            st.info("No final JSON available (error in generation).")

                        st.markdown("##### Human-readable Preview")
                        if final_json is not None:
                            render_page_preview(page.page_type, final_json)

                        if final_json is not None:
                            st.download_button(
                                label="Download page JSON",
                                data=json.dumps(final_json, indent=2).encode("utf-8"),
                                file_name=f"{page.slug.replace('/', '_')}.json",
                                mime="application/json",
                                use_container_width=True,
                            )

                st.markdown("---")
                st.caption(
                    f"{len(results)} page(s) generated. Download individually or as a full bundle."
                )
                st.subheader("Download All Final Page JSONs")

                site_export = build_site_export(results)
                site_export_json = json.dumps(site_export, indent=2)
                st.download_button(
                    label="Download site_copy.json",
                    data=site_export_json.encode("utf-8"),
                    file_name="site_copy.json",
                    mime="application/json",
                )
            else:
                st.info("No results yet. Configure inputs and click 'Generate Site Copy'.")

    # ----------------------------------------
    # TAB 2 – CONTENT QA LAB
    # ----------------------------------------
    with lab_tab:
        st.header("Content generator testing")
        st.caption(
            "Use the lab to spot-check a single page without running the full project."
        )

        st.subheader("Golden rules for the lab")
        lab_rule_col1, lab_rule_col2 = st.columns([1, 1.2])
        with lab_rule_col1:
            lab_golden_rule_upload = st.file_uploader(
                "Golden rule set (TXT, DOCX, or PDF)",
                type=["txt", "docx", "pdf"],
                key="lab_golden_rule_upload",
            )
        with lab_rule_col2:
            lab_golden_rule_text = st.text_area(
                "Paste golden rules (optional)",
                value=st.session_state.get("golden_rule_text", ""),
                height=180,
                key="lab_golden_rule_text",
            )

        current_rule_mode = st.session_state.get("golden_rule_mode", "retrieval")
        if current_rule_mode == "retrieval":
            st.caption(
                f"Using retrieval mode with top {st.session_state.get('golden_rule_top_n', 12)} chunks per prompt."
            )
        else:
            st.caption("Full rule set mode is active; the entire text will be injected.")

        if st.button("Embed golden rules for lab", use_container_width=True):
            combined_rule_text = (lab_golden_rule_text or "") + "\n" + load_text_from_upload(
                lab_golden_rule_upload
            )
            combined_rule_text = combined_rule_text.strip()
            if not combined_rule_text:
                st.error("Please provide golden rule content to embed.")
            else:
                try:
                    if current_rule_mode == "full_text":
                        embedded = embed_rule_chunks(client, [combined_rule_text])
                        st.success("Stored full golden rule set for the lab.")
                    else:
                        embedded = embed_rule_chunks(
                            client, split_into_chunks(combined_rule_text)
                        )
                        st.success(
                            f"Embedded {len(embedded)} golden rule chunk(s) for the lab."
                        )
                    st.session_state["golden_rule_chunks"] = embedded
                    st.session_state["golden_rule_text"] = combined_rule_text
                except Exception as exc:
                    st.error(f"Failed to embed golden rules: {exc}")

        st.subheader("Reference assets for this test")
        asset_col1, asset_col2 = st.columns(2)
        with asset_col1:
            lab_brand_book_upload = st.file_uploader(
                "Brand book (TXT, DOCX, or PDF)",
                type=["txt", "docx", "pdf"],
                key="lab_brand_book_upload",
            )
            lab_brand_book_text = st.text_area(
                "Brand book text (optional)",
                value=st.session_state.get("brand_book_text", ""),
                height=140,
                key="lab_brand_book_text",
            )
        with asset_col2:
            lab_onboarding_upload = st.file_uploader(
                "Client onboarding form (TXT, DOCX, or PDF)",
                type=["txt", "docx", "pdf"],
                key="lab_onboarding_upload",
            )
            lab_onboarding_text = st.text_area(
                "Onboarding notes (optional)",
                value=st.session_state.get("onboarding_text", ""),
                height=140,
                key="lab_onboarding_text",
            )

        lab_home_page_upload = st.file_uploader(
            "Reference home page (TXT, DOCX, or PDF)",
            type=["txt", "docx", "pdf"],
            key="lab_home_page_upload",
        )
        lab_home_page_text = st.text_area(
            "Home page reference (optional)",
            value=st.session_state.get("home_page_text", ""),
            height=140,
            key="lab_home_page_text",
        )

        if lab_brand_book_upload:
            uploaded_brand = load_text_from_upload(lab_brand_book_upload)
            if uploaded_brand:
                lab_brand_book_text = (lab_brand_book_text + "\n" + uploaded_brand).strip()
                st.session_state["brand_book_text"] = lab_brand_book_text
        if lab_onboarding_upload:
            uploaded_onboarding = load_text_from_upload(lab_onboarding_upload)
            if uploaded_onboarding:
                lab_onboarding_text = (lab_onboarding_text + "\n" + uploaded_onboarding).strip()
                st.session_state["onboarding_text"] = lab_onboarding_text
        if lab_home_page_upload:
            uploaded_home_page = load_text_from_upload(lab_home_page_upload)
            if uploaded_home_page:
                lab_home_page_text = (lab_home_page_text + "\n" + uploaded_home_page).strip()
                st.session_state["home_page_text"] = lab_home_page_text

        lab_supporting_doc_text = "\n\n".join(
            [
                t
                for t in [lab_brand_book_text, lab_onboarding_text, lab_home_page_text]
                if t.strip()
            ]
        ).strip()

        st.subheader("QA lab keyword helpers")
        st.caption(
            "Optionally mine your references and services to prefill lab keyword inputs."
        )

        helper_doc_col1, helper_doc_col2 = st.columns(2)
        with helper_doc_col1:
            lab_doc_kw_help = st.button(
                "Generate lab keywords from documents", use_container_width=True
            )
        with helper_doc_col2:
            lab_apply_doc_kw = st.button(
                "Apply doc keywords to lab inputs", use_container_width=True
            )

        if lab_doc_kw_help:
            if not lab_supporting_doc_text:
                st.warning("Upload or paste supporting documents to extract keywords first.")
            else:
                with st.spinner("Mining documents for QA lab keywords..."):
                    try:
                        lab_doc_keywords = generate_document_keywords(
                            client,
                            brand_name=st.session_state.get("brand_name", "Sample Brand"),
                            industry=st.session_state.get("industry", "Consulting"),
                            location=(
                                st.session_state.get("lab_location")
                                or st.session_state.get("location", "")
                            ),
                            audience_intent=st.session_state.get(
                                "lab_intent",
                                st.session_state.get("audience_intent", "Informational"),
                            ),
                            page_goal=st.session_state.get(
                                "lab_goal", st.session_state.get("page_goal", "")
                            ),
                            services=parse_keywords(
                                st.session_state.get("lab_services_raw")
                                or st.session_state.get("services_raw", "")
                            ),
                            supporting_text=lab_supporting_doc_text,
                            model_name=st.session_state.get("model_name", DEFAULT_MODEL_NAME),
                        )
                        st.session_state["lab_doc_keyword_suggestions"] = lab_doc_keywords
                        st.success("Keyword ideas generated for the QA lab inputs.")
                    except Exception as exc:
                        st.error(f"Failed to generate document keywords: {exc}")

        lab_doc_suggestions = st.session_state.get("lab_doc_keyword_suggestions", {})
        if lab_doc_suggestions:
            with st.expander("Document-derived lab keyword ideas", expanded=False):
                paramount = lab_doc_suggestions.get("paramount_keywords", [])
                primary = lab_doc_suggestions.get("primary_keywords", [])
                if paramount:
                    st.markdown("**Paramount ideas:** " + ", ".join(paramount))
                if primary:
                    st.markdown("**Primary ideas:** " + ", ".join(primary))
                if not paramount and not primary:
                    st.caption("No keyword suggestions available yet.")

        if lab_apply_doc_kw and lab_doc_suggestions:
            st.session_state["lab_primary_keywords"] = "\n".join(
                lab_doc_suggestions.get("primary_keywords", [])
            )
            st.session_state["lab_paramount_keywords"] = "\n".join(
                lab_doc_suggestions.get("paramount_keywords", [])
            )
            st.success("Applied document keyword recommendations to the QA lab inputs.")

        st.subheader("Service keyword helper (lab)")
        lab_services_raw = st.text_area(
            "List of services (one per line or comma separated)",
            value=st.session_state.get("lab_services_raw", st.session_state.get("services_raw", "")),
            key="lab_services_raw",
            help="Provide services to generate location-ready primary keyword ideas for the lab run.",
        )
        lab_service_cols = st.columns(2)
        with lab_service_cols[0]:
            lab_generate_services = st.button(
                "Generate lab service keywords", use_container_width=True
            )
        with lab_service_cols[1]:
            lab_apply_service_kw = st.button(
                "Use generated keywords for lab", use_container_width=True
            )

        if lab_generate_services:
            service_list = parse_keywords(lab_services_raw)
            lab_location_input = st.session_state.get(
                "lab_location", st.session_state.get("location", "")
            )
            if not service_list:
                st.warning("Provide at least one service to generate keywords.")
            elif not lab_location_input:
                st.warning("Add a primary location to shape the keyword phrasing.")
            else:
                with st.spinner("Creating lab primary keyword ideas..."):
                    try:
                        generated_keywords = generate_service_keywords(
                            client,
                            services=service_list,
                            location=lab_location_input,
                            audience_intent=st.session_state.get(
                                "lab_intent",
                                st.session_state.get("audience_intent", "Informational"),
                            ),
                            model_name=st.session_state.get("model_name", DEFAULT_MODEL_NAME),
                        )
                        st.session_state["lab_generated_service_keywords"] = generated_keywords
                        st.success("Created keyword ideas using your service list and location.")
                    except Exception as exc:
                        st.error(f"Failed to generate service keywords: {exc}")

        lab_generated_service_keywords = st.session_state.get(
            "lab_generated_service_keywords", []
        )
        if lab_generated_service_keywords:
            st.caption(
                "Generated keywords follow the 'best + service + location' search pattern."
            )
            st.write("\n".join(f"• {kw}" for kw in lab_generated_service_keywords))

        if lab_apply_service_kw and lab_generated_service_keywords:
            st.session_state["lab_primary_keywords"] = "\n".join(
                lab_generated_service_keywords
            )
            st.success("Primary keyword list updated from generated lab suggestions.")

        with st.form("qa_lab_form"):
            use_builder_defaults = st.checkbox(
                "Prefill with Build tab brand info when available", value=True
            )

            default_brand = st.session_state.get("brand_name", "Sample Brand")
            default_industry = st.session_state.get("industry", "Consulting")
            default_voice = st.session_state.get(
                "voice_tone", "Confident, concise, and helpful."
            )
            default_uvp = st.session_state.get("uvp", "")
            default_location = st.session_state.get("location", "Remote")
            default_target = st.session_state.get(
                "target_audience", "B2B buyers evaluating service partners."
            )
            default_style = st.session_state.get("style_profile", STYLE_PROFILE_OPTIONS[0])

            lab_col1, lab_col2 = st.columns(2)

            with lab_col1:
                lab_brand = st.text_input(
                    "Brand / Business Name",
                    value=default_brand if use_builder_defaults else "Sample Brand",
                    key="lab_brand",
                )
                lab_industry_base = (
                    default_industry
                    if use_builder_defaults
                    else st.session_state.get("lab_industry", INDUSTRY_OPTIONS[0])
                )
                lab_industry_options = INDUSTRY_OPTIONS + [CUSTOM_INDUSTRY_OPTION]
                lab_industry_default_choice = (
                    lab_industry_base
                    if lab_industry_base in lab_industry_options
                    else CUSTOM_INDUSTRY_OPTION
                )
                lab_industry_choice = st.selectbox(
                    "Industry / Niche",
                    options=lab_industry_options,
                    index=lab_industry_options.index(lab_industry_default_choice),
                    key="lab_industry_choice",
                    help="Search and select an industry; choose Other for a custom entry.",
                )
                lab_industry_custom = st.text_input(
                    "Custom industry / niche",
                    value=(
                        lab_industry_base
                        if lab_industry_default_choice == CUSTOM_INDUSTRY_OPTION
                        else st.session_state.get("lab_industry_custom", "")
                    ),
                    key="lab_industry_custom",
                    disabled=lab_industry_choice != CUSTOM_INDUSTRY_OPTION,
                )
                lab_industry = (
                    lab_industry_custom.strip()
                    if lab_industry_choice == CUSTOM_INDUSTRY_OPTION
                    else lab_industry_choice
                )
                st.session_state["lab_industry"] = lab_industry
                lab_voice = st.text_area(
                    "Voice & tone",
                    value=default_voice
                    if use_builder_defaults
                    else "Confident, concise, and helpful.",
                    key="lab_voice",
                )
                lab_uvp = st.text_area(
                    "Unique value proposition",
                    value=default_uvp if use_builder_defaults else "",
                    key="lab_uvp",
                )

            with lab_col2:
                lab_page_name = st.text_input(
                    "Page name", value="Service Overview", key="lab_page_name"
                )
                lab_slug = st.text_input("Slug", value="services/test", key="lab_slug")
                lab_page_type = st.selectbox(
                    "Page type",
                    options=["home", "service", "about", "location"],
                    key="lab_page_type",
                )
                lab_location = st.text_input(
                    "Primary location",
                    value=default_location if use_builder_defaults else "Remote",
                    key="lab_location",
                )

            lab_target = st.text_area(
                "Target audience",
                value=default_target
                if use_builder_defaults
                else "B2B buyers evaluating service partners.",
                key="lab_target",
            )
            lab_intent = st.selectbox(
                "Audience intent",
                options=["Informational", "Transactional", "Book an appointment", "Compare providers"],
                key="lab_intent",
                index=0,
            )
            lab_goal = st.text_input(
                "CTA focus", value="Schedule a consultation", key="lab_goal"
            )
            lab_supporting_keywords = st.text_input(
                "Supporting keywords (comma separated)",
                value="service partner, trusted consultants",
                key="lab_supporting_keywords",
            )
            lab_primary_keyword = st.text_input(
                "Primary keyword", value="consulting services", key="lab_primary_keyword"
            )
            lab_paramount_keywords = st.text_area(
                "Paramount keywords (comma/newline separated)",
                value=st.session_state.get(
                    "lab_paramount_keywords",
                    ", ".join(st.session_state.get("paramount_kw_cache", [])),
                ),
                key="lab_paramount_keywords",
            )
            lab_primary_keywords = st.text_area(
                "Primary keywords (comma/newline separated)",
                value=st.session_state.get(
                    "lab_primary_keywords",
                    ", ".join(st.session_state.get("primary_kw_cache", [])),
                ),
                key="lab_primary_keywords",
            )
            lab_topic = st.text_input(
                "Page topic / subject", value="Medical service focus", key="lab_topic"
            )
            lab_style_profile = st.selectbox(
                "Style profile for test run",
                options=STYLE_PROFILE_OPTIONS,
                key="lab_style",
                index=STYLE_PROFILE_OPTIONS.index(default_style)
                if use_builder_defaults and default_style in STYLE_PROFILE_OPTIONS
                else 0,
            )
            lab_show_intermediate = st.checkbox(
                "Show intermediate steps", value=False, key="lab_show_intermediate"
            )

            lab_submit = st.form_submit_button(
                "Run quick generation", type="primary", use_container_width=True
            )

        if lab_submit and api_ok:
            lab_paramount_list = parse_keywords(lab_paramount_keywords)
            lab_primary_list = parse_keywords(lab_primary_keywords)
            rule_store: RuleStore = st.session_state.get("rule_store")
            brand_book_text = st.session_state.get("brand_book_text", "")
            onboarding_text = st.session_state.get("onboarding_text", "")
            home_page_text = st.session_state.get("home_page_text", "")

            lab_brand_info = BrandInfo(
                name=lab_brand.strip(),
                industry=lab_industry.strip(),
                location=lab_location.strip(),
                voice_tone=lab_voice.strip(),
                target_audience=lab_target.strip(),
                uvp=lab_uvp.strip(),
                notes="",
            )
            lab_page = PageDefinition(
                slug=lab_slug.strip() or "test-page",
                page_name=lab_page_name.strip() or "Quick Test Page",
                page_type=lab_page_type,
            )
            supporting_list = [
                s.strip() for s in lab_supporting_keywords.split(",") if s.strip()
            ]

            lab_seo = SEOEntry(
                slug=lab_page.slug,
                primary_keyword=lab_primary_keyword.strip() or None,
                supporting_keywords=supporting_list,
            )

            try:
                lab_final = generate_medical_page(
                    client,
                    lab_brand_info,
                    lab_page,
                    lab_seo,
                    lab_style_profile,
                    topic=lab_topic,
                    paramount_keywords=lab_paramount_list,
                    primary_keywords=lab_primary_list,
                    brand_book=brand_book_text,
                    onboarding_notes=onboarding_text,
                    home_page_copy=home_page_text,
                    static_rules=st.session_state.get("static_rules", {}),
                    rule_store=rule_store,
                    audience_intent=lab_intent,
                    page_goal=lab_goal,
                    golden_rule_text=st.session_state.get("golden_rule_text", ""),
                    golden_rule_mode=st.session_state.get(
                        "golden_rule_mode", "retrieval"
                    ),
                    top_rules=st.session_state.get("golden_rule_top_n", 12),
                    model_name=st.session_state.get("model_name", DEFAULT_MODEL_NAME),
                )
                st.session_state["lab_result"] = {
                    "outline": None,
                    "draft": None,
                    "final": lab_final,
                    "page": lab_page,
                }
            except Exception as exc:
                st.error(f"Quick generation failed: {exc}")
                st.session_state["lab_result"] = None

        lab_result = st.session_state.get("lab_result")
        if lab_result:
            st.subheader("Test output")

            if lab_show_intermediate:
                st.markdown("##### Outline (JSON)")
                st.json(lab_result.get("outline"))
                st.markdown("##### Draft (JSON)")
                st.json(lab_result.get("draft"))

            st.markdown("##### Final Refined JSON")
            st.json(lab_result.get("final"))

            st.markdown("##### Quick preview")
            render_page_preview(lab_result["page"].page_type, lab_result.get("final", {}))

        elif api_ok:
            st.info("Run a quick generation to preview outputs without configuring the full site.")


if __name__ == "__main__":
    main()
