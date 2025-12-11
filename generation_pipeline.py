# generation_pipeline.py
import json
from typing import Dict, Any, Optional

from openai import OpenAI

from config import GLOBAL_SYSTEM_PROMPT, OUTLINE_SCHEMA
from examples import get_example_for
from utils import BrandInfo, PageDefinition, SEOEntry, get_page_schema, safe_json_loads
from openai_client import call_openai_json


def generate_outline(
    client: OpenAI,
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

SEO targets:
- Primary keyword: {primary_kw or "NONE"}
- Supporting keywords: {", ".join(supporting_kws) if supporting_kws else "NONE"}

Style profile: {style_profile}

Task:
- Produce a lean, logically ordered outline that mirrors the page schema.
- Keep each section purposeful and concise; do NOT write full copy.
- Include target_word_count estimates that keep the page skimmable.

Expected JSON shape for the outline:
{json.dumps(OUTLINE_SCHEMA, indent=2)}

Return ONLY a JSON object matching the outline schema.
""",
        },
    ]

    raw = call_openai_json(client, messages)
    return safe_json_loads(raw)


def generate_draft(
    client: OpenAI,
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
    example = get_example_for(style_profile, page.page_type)
    example_block = (
        f"\nReference example (structure/tone only; do NOT copy wording):\n{json.dumps(example, indent=2)}"
        if example
        else ""
    )

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

SEO targets:
- Primary keyword: {primary_kw or "NONE"}
- Supporting keywords: {", ".join(supporting_kws) if supporting_kws else "NONE"}

Style profile: {style_profile}

Outline (follow this structure and intent):
{json.dumps(outline, indent=2)}
{example_block}

Expected JSON schema for the final draft:
{json.dumps(page_schema, indent=2)}

Task:
- Expand the outline into complete, production-ready copy with concise paragraphs and strong headings.
- Populate EVERY field of the schema with appropriate text or arrays.
- Use the primary keyword 2–4 times naturally; weave supporting keywords only where they fit.
- Do not add or remove fields from the schema.
- Return ONLY a single JSON object matching the schema.
""",
        },
    ]

    raw = call_openai_json(client, messages)
    return safe_json_loads(raw)


def refine_draft(
    client: OpenAI,
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

    example = get_example_for(style_profile, page.page_type)
    example_block = (
        f"\nReference example for tone/structure (do not copy wording):\n{json.dumps(example, indent=2)}"
        if example
        else ""
    )

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
{example_block}

Task:
- Keep the SAME JSON structure (identical fields and nesting).
- Ensure the primary keyword appears naturally 2–4 times across the page.
- Weave in supporting keywords only where they add clarity.
- Remove repetition and generic filler; tighten language and headings.
- Preserve intent while improving specificity, flow, and polish.

Return ONLY the refined JSON object with the SAME structure.
""",
        },
    ]

    raw = call_openai_json(client, messages)
    return safe_json_loads(raw)
