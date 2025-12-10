# utils.py
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple

import pandas as pd
import streamlit as st

from config import PAGE_TYPE_SCHEMAS


@dataclass
class BrandInfo:
    name: str
    industry: str
    location: str
    voice_tone: str
    target_audience: str
    uvp: str
    notes: str


@dataclass
class PageDefinition:
    slug: str
    page_name: str
    page_type: str  # "home", "service", "sub service", "about", "location"


@dataclass
class SEOEntry:
    slug: str
    primary_keyword: Optional[str] = None
    supporting_keywords: List[str] = field(default_factory=list)


SEOMap = Dict[str, SEOEntry]


def parse_seo_csv(uploaded_file) -> Tuple[SEOMap, List[str]]:
    """
    Parse the uploaded SEO CSV into a SEOMap keyed by slug.
    CSV must contain at least: slug, primary_keyword, supporting_keywords.
    Returns (seo_map, warnings).
    """
    seo_map: SEOMap = {}
    warnings: List[str] = []

    if uploaded_file is None:
        return seo_map, warnings

    try:
        df = pd.read_csv(uploaded_file)
    except Exception as exc:
        warnings.append(f"Failed to parse CSV: {exc}")
        return seo_map, warnings

    required_cols = {"slug", "primary_keyword", "supporting_keywords"}
    missing = required_cols - set(df.columns)
    if missing:
        warnings.append(
            f"SEO CSV is missing required columns: {', '.join(sorted(missing))}"
        )
        return seo_map, warnings

    for _, row in df.iterrows():
        slug = str(row.get("slug", "")).strip()
        if not slug:
            continue

        primary = str(row.get("primary_keyword", "")).strip() or None
        supporting_raw = str(row.get("supporting_keywords", "")).strip()
        supporting_list = (
            [s.strip() for s in supporting_raw.split(",") if s.strip()]
            if supporting_raw
            else []
        )

        seo_map[slug] = SEOEntry(
            slug=slug,
            primary_keyword=primary,
            supporting_keywords=supporting_list,
        )

    return seo_map, warnings


def parse_sitemap_csv(
    uploaded_file, allowed_page_types: List[str]
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Parse the uploaded sitemap CSV into a DataFrame with columns:
        slug, page_name, page_type

    - Ensures required columns exist.
    - Normalizes whitespace.
    - Normalizes page_type to lower case and collapses underscores to spaces.
    - Warns if page_type is not in allowed_page_types.
    - Returns (df, warnings).
    """
    warnings: List[str] = []

    if uploaded_file is None:
        return pd.DataFrame(columns=["slug", "page_name", "page_type"]), warnings

    try:
        df = pd.read_csv(uploaded_file)
    except Exception as exc:
        warnings.append(f"Failed to parse sitemap CSV: {exc}")
        return pd.DataFrame(columns=["slug", "page_name", "page_type"]), warnings

    required_cols = {"slug", "page_name", "page_type"}
    missing = required_cols - set(df.columns)
    if missing:
        warnings.append(
            f"Sitemap CSV is missing required columns: {', '.join(sorted(missing))}"
        )
        return pd.DataFrame(columns=["slug", "page_name", "page_type"]), warnings

    # Normalize and trim
    df["slug"] = df["slug"].astype(str).str.strip()
    df["page_name"] = df["page_name"].astype(str).str.strip()

    # normalize page_type: lower, replace '_' with ' ', collapse multiple spaces
    def normalize_pt(pt: Any) -> str:
        s = str(pt).strip().lower().replace("_", " ")
        # collapse multiple spaces
        parts = [p for p in s.split(" ") if p]
        return " ".join(parts)

    df["page_type"] = df["page_type"].apply(normalize_pt)

    # Filter out rows without slug or page_name
    original_count = len(df)
    df = df[(df["slug"] != "") & (df["page_name"] != "")]
    removed = original_count - len(df)
    if removed > 0:
        warnings.append(f"Removed {removed} row(s) with empty slug or page_name.")

    # Warn for invalid page types
    invalid_types = sorted(
        {pt for pt in df["page_type"].unique() if pt not in allowed_page_types}
    )
    if invalid_types:
        warnings.append(
            "Found unsupported page_type values in sitemap CSV: "
            + ", ".join(invalid_types)
            + f". Allowed: {', '.join(allowed_page_types)}."
        )

    # Keep all rows; UI will let you adjust invalid types via selectbox
    return df, warnings


def get_page_schema(page_type: str) -> Dict[str, Any]:
    """
    Retrieve the schema dict for the given page type.
    Raises KeyError if not found.
    """
    if page_type not in PAGE_TYPE_SCHEMAS:
        raise KeyError(f"Unsupported page type: {page_type}")
    return PAGE_TYPE_SCHEMAS[page_type]


def safe_json_loads(raw: str) -> Any:
    """
    Safely parse JSON string. If parsing fails, try to extract the first
    top-level JSON object from the string by trimming outside text.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise


def build_site_export(pages_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a combined export structure for all pages.
    pages_results is a list of dicts like:
        {
            "page": PageDefinition,
            "outline": dict or None,
            "draft": dict or None,
            "final": dict or None,
            "seo": SEOEntry or None,
        }
    """
    site = {"pages": {}}

    for entry in pages_results:
        page: PageDefinition = entry["page"]
        final_json = entry.get("final")
        seo: Optional[SEOEntry] = entry.get("seo")

        site["pages"][page.slug] = {
            "page_name": page.page_name,
            "page_type": page.page_type,
            "seo": {
                "primary_keyword": seo.primary_keyword if seo else None,
                "supporting_keywords": seo.supporting_keywords if seo else [],
            },
            "final_copy": final_json,
        }

    return site


def render_page_preview(page_type: str, page_json: Dict[str, Any]) -> None:
    """
    Render a human-readable preview of the structured JSON.
    """
    if not page_json:
        st.info("No final JSON available for this page.")
        return

    hero = page_json.get("hero", {})
    if hero:
        headline = hero.get("headline") or hero.get("eyebrow") or "Hero"
        st.subheader(headline)
        subheadline = hero.get("subheadline")
        if subheadline:
            st.write(subheadline)
        if hero.get("primary_cta_label"):
            st.markdown(
                f"**Primary CTA:** {hero.get('primary_cta_label')} → {hero.get('primary_cta_url', '#')}"
            )
        if hero.get("secondary_cta_label"):
            st.markdown(
                f"**Secondary CTA:** {hero.get('secondary_cta_label')} → {hero.get('secondary_cta_url', '#')}"
            )

    # Home-style layout
    if page_type == "home":
        for section in page_json.get("sections", []):
            st.markdown(f"### {section.get('title', section.get('id', 'Section'))}")
            if "intro" in section and isinstance(section["intro"], str):
                st.write(section["intro"])

            if section.get("items"):
                for item in section["items"]:
                    label = item.get("label") or item.get("question") or item.get(
                        "name"
                    )
                    if label:
                        st.markdown(f"- **{label}**")
                    desc = (
                        item.get("description")
                        or item.get("answer")
                        or item.get("quote")
                    )
                    if desc:
                        st.write(f"  {desc}")

            if section.get("steps"):
                for step in section["steps"]:
                    step_title = step.get("title", "Step")
                    st.markdown(f"- **{step_title}**")
                    if step.get("description"):
                        st.write(f"  {step['description']}")

            if section.get("bullets"):
                for bullet in section["bullets"]:
                    st.markdown(f"- {bullet}")

    # Service & sub service share the same visual pattern
    elif page_type in ("service", "sub service"):
        for key in [
            "problem_section",
            "solution_section",
            "benefits_section",
            "process_section",
            "faq_section",
            "final_cta_section",
        ]:
            sec = page_json.get(key)
            if not sec:
                continue
            title = sec.get("title", key.replace("_", " ").title())
            st.markdown(f"### {title}")

            intro = sec.get("intro") or sec.get("body")
            if intro:
                st.write(intro)

            if sec.get("bullets"):
                for bullet in sec["bullets"]:
                    st.markdown(f"- {bullet}")

            if sec.get("steps"):
                for step in sec["steps"]:
                    st.markdown(f"- **{step.get('title', 'Step')}**")
                    if step.get("description"):
                        st.write(f"  {step['description']}")

            if sec.get("items"):
                for item in sec["items"]:
                    label = item.get("label") or item.get("question")
                    if label:
                        st.markdown(f"- **{label}**")
                    if item.get("description") or item.get("answer"):
                        st.write(
                            f"  {item.get('description') or item.get('answer')}"
                        )

    elif page_type == "about":
        for key in [
            "brand_story",
            "team_section",
            "values_section",
            "credibility_section",
            "final_cta_section",
        ]:
            sec = page_json.get(key)
            if not sec:
                continue
            title = sec.get("title", key.replace("_", " ").title())
            st.markdown(f"### {title}")

            body = sec.get("body") or sec.get("intro")
            if body:
                st.write(body)

            if key == "team_section" and sec.get("members"):
                for member in sec["members"]:
                    st.markdown(
                        f"- **{member.get('name', '')}**, {member.get('role', '')}"
                    )
                    if member.get("bio"):
                        st.write(f"  {member['bio']}")

            if key == "values_section" and sec.get("values"):
                for val in sec["values"]:
                    st.markdown(f"- **{val.get('label', '')}**")
                    if val.get("description"):
                        st.write(f"  {val['description']}")

            if key == "credibility_section" and sec.get("items"):
                for item in sec["items"]:
                    st.markdown(f"- **{item.get('label', '')}**")
                    if item.get("description"):
                        st.write(f"  {item['description']}")

    elif page_type == "location":
        for key in [
            "local_intro",
            "services_summary",
            "neighborhood_specific_details",
            "trust_signals",
            "local_faqs",
            "final_cta_section",
        ]:
            sec = page_json.get(key)
            if not sec:
                continue
            title = sec.get("title", key.replace("_", " ").title())
            st.markdown(f"### {title}")

            body = sec.get("body") or sec.get("intro")
            if body:
                st.write(body)

            if sec.get("services"):
                for svc in sec["services"]:
                    st.markdown(f"- **{svc.get('label', '')}**")
                    if svc.get("description"):
                        st.write(f"  {svc['description']}")

            if sec.get("bullets"):
                for bullet in sec["bullets"]:
                    st.markdown(f"- {bullet}")

            if sec.get("items"):
                for item in sec["items"]:
                    label = item.get("label") or item.get("question")
                    if label:
                        st.markdown(f"- **{label}**")
                    if item.get("description") or item.get("answer"):
                        st.write(
                            f"  {item.get('description') or item.get('answer')}"
                        )
