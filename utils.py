import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st
from docx import Document
from PyPDF2 import PdfReader

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


class SchemaValidationError(ValueError):
    """Raised when generated JSON does not match the expected schema."""


def validate_against_schema(schema: Any, payload: Any, path: str = "$") -> None:
    """
    Validate that ``payload`` mirrors the structure of ``schema``.

    The check is intentionally lightweight and focuses on presence and nesting of
    keys/collections rather than strict typing. Raises SchemaValidationError on
    mismatch to surface actionable feedback to callers before rendering.
    """

    def _validate(expected: Any, value: Any, current_path: str) -> None:
        if isinstance(expected, dict):
            if not isinstance(value, dict):
                raise SchemaValidationError(
                    f"Expected object at {current_path}, got {type(value).__name__}"
                )
            for key, sub_schema in expected.items():
                if key not in value:
                    raise SchemaValidationError(
                        f"Missing key '{key}' at {current_path}"
                    )
                _validate(sub_schema, value[key], f"{current_path}.{key}")
            return

        if isinstance(expected, list):
            if not isinstance(value, list):
                raise SchemaValidationError(
                    f"Expected list at {current_path}, got {type(value).__name__}"
                )
            if expected:
                exemplar = expected[0]
                for idx, item in enumerate(value):
                    _validate(exemplar, item, f"{current_path}[{idx}]")
            return

        # Primitive exemplar: just ensure presence and non-null value
        if value is None or (isinstance(value, str) and not value.strip()):
            raise SchemaValidationError(
                f"Expected non-empty value at {current_path}, got '{value}'"
            )

    _validate(schema, payload, path)


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
    """Render a human-readable preview of the structured JSON."""
    if not page_json:
        st.info("No final JSON available for this page.")
        return

    if "sections" in page_json and "hero" in page_json and "meta" in page_json:
        st.markdown(f"**Page type:** {page_json.get('page_type', page_type)}")
        hero_block = page_json.get("hero", {})
        hero_headline = hero_block.get("headline") or hero_block.get("eyebrow")
        if hero_headline:
            st.subheader(hero_headline)
        if hero_block.get("subheadline"):
            st.write(hero_block["subheadline"])
        if hero_block.get("primary_cta"):
            st.markdown(f"**CTA:** {hero_block['primary_cta']}")

        for section in page_json.get("sections", []):
            heading = section.get("heading") or section.get("id", "Section")
            st.markdown(f"### {heading}")
            if section.get("body"):
                st.write(section["body"])
            if section.get("target_word_count"):
                st.caption(f"Target words: {section['target_word_count']}")
        return

    st.info("Preview unavailable: JSON does not match expected schema.")




def load_text_from_upload(uploaded_file) -> str:
    """Load text content from an uploaded TXT, DOCX, or PDF file."""
    if uploaded_file is None:
        return ""

    name = (uploaded_file.name or "").lower()

    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    if name.endswith(".txt"):
        return uploaded_file.read().decode("utf-8", errors="ignore")

    if name.endswith(".docx"):
        document = Document(uploaded_file)
        return "\n".join(p.text for p in document.paragraphs)

    if name.endswith(".pdf"):
        try:
            pdf_reader = PdfReader(uploaded_file)
            pages_text = [page.extract_text() or "" for page in pdf_reader.pages]
            return "\n".join(pages_text).strip()
        except Exception:
            return ""

    return ""


def parse_keywords(raw: str) -> List[str]:
    """Parse comma or newline-separated keywords into a clean list."""
    if not raw:
        return []
    parts = [
        piece.strip()
        for line in raw.splitlines()
        for piece in line.split(",")
        if piece.strip()
    ]
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for kw in parts:
        if kw.lower() in seen:
            continue
        seen.add(kw.lower())
        deduped.append(kw)
    return deduped
