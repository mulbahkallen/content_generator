# generation_pipeline.py
import json
from typing import Any, Dict, List, Optional

from openai import OpenAI

from config import GLOBAL_SYSTEM_PROMPT, MEDICAL_PAGE_SCHEMA, OUTLINE_SCHEMA
from settings import DEFAULT_MODEL_NAME
from examples import get_example_for
from prompt_builder import (
    analyze_homepage_copy,
    build_hybrid_prompt,
    build_query_text,
)
from rule_storage import RuleChunk, RuleStore
from utils import (
    BrandInfo,
    PageDefinition,
    SEOEntry,
    get_page_schema,
    safe_json_loads,
    SchemaValidationError,
    validate_against_schema,
)
from openai_client import call_openai_json


def generate_outline(
    client: OpenAI,
    brand_info: BrandInfo,
    page: PageDefinition,
    seo_entry: Optional[SEOEntry],
    style_profile: str,
    model_name: str = DEFAULT_MODEL_NAME,
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
- Service focus: {page.service_name or 'None provided'}

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

    raw = call_openai_json(client, messages, model_name=model_name)
    outline_json = safe_json_loads(raw)
    validate_against_schema(OUTLINE_SCHEMA, outline_json)
    return outline_json


def generate_draft(
    client: OpenAI,
    brand_info: BrandInfo,
    page: PageDefinition,
    seo_entry: Optional[SEOEntry],
    style_profile: str,
    outline: Dict[str, Any],
    model_name: str = DEFAULT_MODEL_NAME,
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
- Service focus: {page.service_name or 'None provided'}

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

    raw = call_openai_json(client, messages, model_name=model_name)
    draft_json = safe_json_loads(raw)
    validate_against_schema(page_schema, draft_json)
    return draft_json


def refine_draft(
    client: OpenAI,
    brand_info: BrandInfo,
    page: PageDefinition,
    seo_entry: Optional[SEOEntry],
    style_profile: str,
    draft_json: Dict[str, Any],
    model_name: str = DEFAULT_MODEL_NAME,
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
- Service focus: {page.service_name or 'None provided'}

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

    raw = call_openai_json(client, messages, model_name=model_name)
    refined_json = safe_json_loads(raw)
    try:
        validate_against_schema(page_schema, refined_json)
    except SchemaValidationError as exc:
        raise SchemaValidationError(f"Refined draft schema mismatch: {exc}") from exc
    return refined_json


def generate_medical_page(
    client: OpenAI,
    brand_info: BrandInfo,
    page: PageDefinition,
    seo_entry: Optional[SEOEntry],
    style_profile: str,
    topic: str,
    paramount_keywords: List[str],
    primary_keywords: List[str],
    brand_book: str,
    onboarding_notes: str,
    home_page_copy: str,
    static_rules: Dict[str, Any],
    rule_store: Optional[RuleStore],
    audience_intent: str,
    page_goal: str,
    golden_rule_text: str = "",
    golden_rule_mode: str = "retrieval",
    top_rules: int = 12,
    model_name: str = DEFAULT_MODEL_NAME,
) -> Dict[str, Any]:
    """Generate structured medical page copy using golden rule retrieval."""

    primary_kw = seo_entry.primary_keyword if seo_entry else None
    supporting_kws = seo_entry.supporting_keywords if seo_entry else []
    service_focus = getattr(page, "service_name", None)
    target_keywords = list(
        {kw: None for kw in primary_keywords + supporting_kws + ([service_focus] if service_focus else [])}.keys()
    )
    home_page_profile = analyze_homepage_copy(home_page_copy or brand_book)
    tone_hint = home_page_profile.get("tone_indicators", brand_info.voice_tone)
    topic_query = build_query_text(
        brand_info.industry,
        page.page_type,
        brand_info.location,
        audience_intent,
        tone_hint,
        service_focus or "",
    )
    use_full_rules = golden_rule_mode == "full_text" and golden_rule_text.strip()
    dynamic_rules: List[RuleChunk] = []

    page_tags = {
        "home": ["structure", "tone", "cta"],
        "service": ["seo", "structure", "cta"],
        "sub service": ["seo", "structure"],
        "about": ["tone", "structure"],
        "location": ["seo", "structure", "cta"],
    }.get(page.page_type, ["general"])

    if use_full_rules:
        dynamic_rules = [RuleChunk(text=golden_rule_text.strip(), embedding=[], metadata={"tags": ["full_text"]})]
    elif rule_store is not None and rule_store.is_ready:
        dynamic_rules = rule_store.query(client, topic_query, top_k=top_rules, required_tags=page_tags)

    prompt, diagnostics = build_hybrid_prompt(
        static_rules,
        dynamic_rules,
        brand_info={
            "name": brand_info.name,
            "industry": brand_info.industry,
            "location": brand_info.location,
            "voice_tone": brand_info.voice_tone,
            "target_audience": brand_info.target_audience,
            "uvp": brand_info.uvp,
            "notes": brand_info.notes,
        },
        page_info={
            "page_type": page.page_type,
            "page_name": page.page_name,
            "topic": topic or page.page_name,
            "service": service_focus or "None provided",
            "intent": audience_intent,
            "goal": page_goal,
        },
        keywords={
            "paramount": paramount_keywords,
            "primary": primary_keywords,
            "page_primary": [primary_kw] if primary_kw else [],
            "page_supporting": supporting_kws,
        },
        onboarding_notes=onboarding_notes,
        brand_book=brand_book,
        home_page_copy=home_page_copy,
        home_page_profile=home_page_profile,
    )

    schema_block = json.dumps(MEDICAL_PAGE_SCHEMA, indent=2)

    messages = [
        {"role": "system", "content": GLOBAL_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""
{prompt}

Schema to follow:
{schema_block}

Also include a compact diagnostics object capturing used rule tags, keyword coverage, and any structural risks using the key `diagnostics`.
""",
        },
    ]

    raw = call_openai_json(client, messages, model_name=model_name)
    return safe_json_loads(raw)
