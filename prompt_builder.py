"""Prompt construction utilities for hybrid static + RAG rule guidance."""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Sequence, Tuple

from rule_storage import RuleChunk

PAGE_LENGTH_HINTS = {
    "home": "Home pages should read like a full landing page: aim for 1,300–1,700 words across 8–12 sections with full paragraphs, not stubs.",
    "service": "Service pages should land around 1,000–1,300 words with descriptive sections, proof points, FAQs, and a closing CTA.",
    "about": "About pages should run 900–1,200 words with a rich story, team details, values, and credibility.",
    "location": "Location pages should be 1,000–1,300 words covering local details, services, trust signals, and FAQs.",
}


def _format_rule_block(static_rules: Dict[str, Sequence[str]]) -> str:
    if not static_rules:
        return "No static rules available."

    sections = []
    for section, rules in static_rules.items():
        if not rules:
            continue

        seen = set()
        deduped_rules = []
        for rule in rules:
            normalized = rule.strip()
            if not normalized or normalized.lower() in seen:
                continue
            seen.add(normalized.lower())
            deduped_rules.append(normalized)

        if not deduped_rules:
            continue

        joined = "\n".join(f"- {rule}" for rule in deduped_rules)
        sections.append(f"{section.title()}\n{joined}")

    return "\n\n".join(sections)


def _format_dynamic_rules(chunks: Sequence[RuleChunk]) -> str:
    if not chunks:
        return "No dynamic golden rule snippets retrieved; rely on static core rules."

    seen_texts = set()
    unique_chunks: List[RuleChunk] = []
    for chunk in chunks:
        normalized = chunk.text.strip()
        if not normalized or normalized.lower() in seen_texts:
            continue
        seen_texts.add(normalized.lower())
        unique_chunks.append(chunk)

    if not unique_chunks:
        return "No dynamic golden rule snippets retrieved; rely on static core rules."

    lines = []
    for idx, chunk in enumerate(unique_chunks, start=1):
        tags = ", ".join(chunk.metadata.get("tags", []))
        score = chunk.metadata.get("score")
        score_txt = f" (sim={score:.3f})" if isinstance(score, float) else ""
        lines.append(f"[{idx}] (tags: {tags}){score_txt}\n{chunk.text.strip()}")
    return "\n\n".join(lines)


def analyze_homepage_copy(home_page_copy: str) -> Dict[str, str]:
    """Derive a lightweight tone/structure profile from a provided homepage copy."""

    if not home_page_copy.strip():
        return {}
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", home_page_copy) if s.strip()]
    if not sentences:
        return {}

    avg_sentence_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
    short_sentence_ratio = sum(1 for s in sentences if len(s.split()) <= 12) / len(sentences)

    cta_count = len(re.findall(r"call|schedule|book|contact|request|learn more|get started", home_page_copy, re.I))
    headline_like = len([s for s in sentences if len(s.split()) <= 8])

    tone_flags = []
    if re.search(r"we\b|our team|our clinic", home_page_copy, re.I):
        tone_flags.append("collaborative")
    if re.search(r"you\b|your", home_page_copy, re.I):
        tone_flags.append("second-person")
    if re.search(r"expert|board-certified|specialist|clinical", home_page_copy, re.I):
        tone_flags.append("authoritative")
    if re.search(r"calm|gentle|compassion|caring|trust", home_page_copy, re.I):
        tone_flags.append("empathetic")

    return {
        "average_sentence_length": f"{avg_sentence_len:.1f} words",
        "short_sentence_ratio": f"{short_sentence_ratio:.0%} of lines are crisp",
        "cta_density": f"Detected {cta_count} CTA-like phrases",
        "headline_to_body_ratio": f"{headline_like} headline-style snippets vs {len(sentences)} total sentences",
        "tone_indicators": ", ".join(tone_flags) if tone_flags else "neutral",
    }


def build_query_text(
    industry: str,
    page_type: str,
    location: str,
    intent: str,
    tone: str,
    service: str = "",
) -> str:
    parts = [industry, page_type, location, intent, tone, service]
    return " | ".join(p for p in parts if p)


def build_hybrid_prompt(
    static_rules: Dict[str, Sequence[str]],
    dynamic_rules: Sequence[RuleChunk],
    brand_info: Dict[str, str],
    page_info: Dict[str, str],
    keywords: Dict[str, List[str]],
    onboarding_notes: str,
    brand_book: str,
    home_page_copy: str,
    home_page_profile: Dict[str, str],
) -> Tuple[str, str]:
    """Construct the unified prompt string plus diagnostics."""

    static_block = _format_rule_block(static_rules)
    dynamic_block = _format_dynamic_rules(dynamic_rules)
    length_hint = PAGE_LENGTH_HINTS.get(
        page_info.get("page_type", ""),
        "Aim for 1,000–1,300 words with complete sections that would fit a production-ready web page.",
    )
    keyword_block = "\n".join(
        [
            f"Paramount keywords: {', '.join(keywords.get('paramount', [])) or 'None'}",
            f"Primary keywords: {', '.join(keywords.get('primary', [])) or 'None'}",
            f"Page SEO keywords: {', '.join(keywords.get('page_primary', [])) or 'None'}",
            f"Supporting keywords: {', '.join(keywords.get('page_supporting', [])) or 'None'}",
        ]
    )

    home_profile_lines = (
        "\n".join(f"- {k}: {v}" for k, v in home_page_profile.items()) if home_page_profile else "None provided"
    )

    prompt = f"""
You are a medical website copy specialist. Follow the static core rules FIRST, then the retrieved dynamic golden rule snippets, without contradicting either.

STATIC CORE RULES (always apply):
{static_block}

DYNAMIC GOLDEN RULE SNIPPETS (semantic retrieval):
{dynamic_block}

BRAND + CONTEXT:
- Brand: {brand_info.get('name', '')}
- Industry/Niche: {brand_info.get('industry', '')}
- Location: {brand_info.get('location', '')}
- Voice & tone: {brand_info.get('voice_tone', '')}
- Target audience: {brand_info.get('target_audience', '')}
- UVP: {brand_info.get('uvp', '')}
- Notes: {brand_info.get('notes', '')}

PAGE REQUEST:
- Page type: {page_info.get('page_type', '')}
- Page name: {page_info.get('page_name', '')}
- Page topic: {page_info.get('topic', '')}
- Service focus: {page_info.get('service', 'None specified')}
- Audience intent: {page_info.get('intent', '')}
- Goal: {page_info.get('goal', '')}

KEYWORDS & SEO:
{keyword_block}

BRAND BOOK / PERSONA HIGHLIGHTS:
{brand_book or 'None provided'}

ONBOARDING INSIGHTS:
{onboarding_notes or 'None provided'}

HOMEPAGE STYLE PROFILE (mimic structure, tone, CTA pacing when provided):
{home_profile_lines}

HOMEPAGE REFERENCE COPY:
{home_page_copy or 'None'}

OUTPUT INSTRUCTIONS:
- Ensure the target audience stays consistent (do not shift between clinician and patient voices).
- Use paramount and primary keywords naturally; avoid stuffing.
- Respect SEO/AEO guidance, CTA style, and structure cues from the retrieved rules.
- Length guardrail: {length_hint}
- Write concise, empathetic, medically accurate copy.
- Return ONLY the JSON following the provided schema.
"""

    diagnostics = json.dumps(
        {
            "static_rules": list(static_rules.keys()),
            "dynamic_rules": [chunk.metadata for chunk in dynamic_rules],
            "home_page_profile": home_page_profile,
        },
        indent=2,
    )

    return prompt.strip(), diagnostics
