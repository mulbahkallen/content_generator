# generation_pipeline.py
import json
from typing import Dict, Any, Optional

from config import GLOBAL_SYSTEM_PROMPT, OUTLINE_SCHEMA
from utils import BrandInfo, PageDefinition, SEOEntry, get_page_schema, safe_json_loads
from openai_client import call_openai_json


def generate_outline(
    client,
    brand_info: BrandInfo,
    page: PageDefinition,
    seo_entry: Optional[SEOEntry],
    style_profile: str,
) -> Dict[str, Any]:
    """
    Generate a structured outline for the given page.
    Returns a dict matching OUTLINE_SCHEMA.
    """
    primary_kw = seo_entry.primary_keyword if seo_entry else None
    supporting_kws = seo_entry.supporting_keywords if seo_entry else []

    messages = [
        {"role": "system", "content": GLOBAL_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""
You are generating ONLY a structured outline for a single website page.

Brand info:
- Name: {brand_info.name}
- Industry: {brand_info.industry}
- Primary location: {brand_info.location}
- Voice & tone: {brand_info.voice_tone}
- Target audience: {brand_info.target_audience}
- Unique value proposition: {brand_info.uvp}

Page info:
- Slug: {page.slug}
- Page name: {page.page_name}
- Page type: {page.page_type}

SEO:
- Primary keyword: {primary_kw or "NONE"}
- Supporting keywords: {", ".join(supporting_kws) if supporting_kws else "NONE"}

Style profile: {style_profile}

Task:
- Create an outline for this page as JSON following this schema:
{json.dumps(OUTLINE_SCHEMA, indent=2)}

Guidelines:
- Map sections to the eventual page schema for page type "{page.page_type}".
- Choose descriptive section titles that reflect the content.
- Include a short description for each section.
- Set reasonable target_word_count values.

Return ONLY a JSON object matching the OUTLINE_SCHEMA.
""",
        },
    ]

    raw = call_openai_json(client, messages)
    return safe_json_loads(raw)


def generate_draft(
    client,
    brand_info: BrandInfo,
    page: PageDefinition,
    seo_entry: Optional[SEOEntry],
    style_profile: str,
    outline: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate the first full draft of the page's copy as structured JSON
    matching the page-type schema.
    """
    primary_kw = seo_entry.primary_keyword if seo_entry else None
    supporting_kws = seo_entry.supporting_keywords if seo_entry else []

    page_schema = get_page_schema(page.page_type)

    messages = [
        {"role": "system", "content": GLOBAL_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""
You are generating the FIRST FULL DRAFT of website copy for a single page.

Brand info:
- Name: {brand_info.name}
- Industry: {brand_info.industry}
- Primary location: {brand_info.location}
- Voice & tone: {brand_info.voice_tone}
- Target audience: {brand_info.target_audience}
- Unique value proposition: {brand_info.uvp}

Page info:
- Slug: {page.slug}
- Page name: {page.page_name}
- Page type: {page.page_type}

SEO:
- Primary keyword: {primary_kw or "NONE"}
- Supporting keywords: {", ".join(supporting_kws) if supporting_kws else "NONE"}

Style profile: {style_profile}

Outline (follow this closely when writing the copy):
{json.dumps(outline, indent=2)}

Expected JSON schema for the final draft:
{json.dumps(page_schema, indent=2)}

Task:
- Expand the outline into complete, production-ready copy.
- Populate EVERY field of the schema with appropriate text or arrays.
- Use the primary and supporting keywords naturally in the content.
- Do not add or remove fields from the schema.
- Return ONLY a single JSON object matching the schema.
""",
        },
    ]

    raw = call_openai_json(client, messages)
    return safe_json_loads(raw)


def refine_draft(
    client,
    brand_info: BrandInfo,
    page: PageDefinition,
    seo_entry: Optional[SEOEntry],
    style_profile: str,
    draft_json: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Refine the draft JSON for SEO and copy quality while preserving structure.
    """
    primary_kw = seo_entry.primary_keyword if seo_entry else None
    supporting_kws = seo_entry.supporting_keywords if seo_entry else []

    messages = [
        {"role": "system", "content": GLOBAL_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""
You are refining a draft of website copy for improved SEO, clarity, and quality.

Brand info:
- Name: {brand_info.name}
- Industry: {brand_info.industry}
- Primary location: {brand_info.location}
- Voice & tone: {brand_info.voice_tone}
- Target audience: {brand_info.target_audience}
- Unique value proposition: {brand_info.uvp}

Page info:
- Slug: {page.slug}
- Page name: {page.page_name}
- Page type: {page.page_type}

SEO requirements:
- Primary keyword: {primary_kw or "NONE"}
- Supporting keywords: {", ".join(supporting_kws) if supporting_kws else "NONE"}

Style profile: {style_profile}

Existing draft JSON:
{json.dumps(draft_json, indent=2)}

Task:
- Keep the SAME JSON structure (same fields and nesting).
- Ensure the primary keyword appears naturally 2–4 times in the overall page.
- Weave in supporting keywords where they genuinely fit.
- Remove obvious repetition and generic filler.
- Tighten language to be concise, specific, and benefit-focused.
- Preserve the intent and structure of the draft while improving it.

Return ONLY the refined JSON object with the SAME structure.
""",
        },
    ]

    raw = call_openai_json(client, messages)
    return safe_json_loads(raw)
