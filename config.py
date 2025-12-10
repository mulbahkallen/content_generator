# config.py
import json
from typing import Dict, Any

MODEL_NAME = "gpt-4.1-mini"  # easy to change in one place

STYLE_PROFILE_OPTIONS = [
    "Default agency style",
    "Conversational expert",
    "Concise and direct",
]

GLOBAL_SYSTEM_PROMPT = """
You are a senior web copywriter and SEO specialist at a high-end digital agency.

Your goals:
- Produce production-ready website copy for business and professional services brands.
- Follow the brand voice, project context, page type, and SEO keyword requirements exactly.
- Write clearly, specifically, and benefit-focused for the defined target audience.

Quality rules:
- Use the primary keyword naturally 2–4 times per page, without keyword stuffing.
- Use supporting keywords where they fit logically and add value.
- Follow the provided JSON schema strictly. Do not add or remove top-level fields.
- Prefer short paragraphs, strong subheadings, and skimmable sections.
- Avoid generic fluff, clichés, and empty jargon.
- Be specific about benefits, outcomes, and differentiators.
- Assume content will be used as-is on a live website.

Output format:
- You MUST return a single valid JSON object.
- The JSON MUST conform exactly to the schema provided in the prompt (correct field names and nesting).
- Do not include any explanations, markdown, or commentary outside the JSON.
"""

OUTLINE_SCHEMA = {
    "outline": [
        {
            "section_id": "string - e.g., 'hero', 'services_overview'",
            "title": "string - section heading",
            "description": "string - what this section should cover",
            "target_word_count": 150,
        }
    ]
}

HOME_PAGE_SCHEMA = {
    "page_type": "home",
    "hero": {
        "eyebrow": "string - short positioning phrase above the headline",
        "headline": "string - main benefit-driven headline",
        "subheadline": "string - one to two sentences expanding on the main promise",
        "primary_cta_label": "string - e.g., 'Request a Consultation'",
        "primary_cta_url": "string - URL path or placeholder",
        "secondary_cta_label": "string - optional",
        "secondary_cta_url": "string - optional",
    },
    "sections": [
        {
            "id": "services_overview",
            "title": "string - section heading",
            "intro": "string - short intro paragraph",
            "items": [
                {
                    "label": "string - service name",
                    "description": "string - 1–2 sentence description",
                }
            ],
        },
        {
            "id": "why_choose_us",
            "title": "string",
            "intro": "string",
            "bullets": [
                "string - specific, benefit-driven reason",
            ],
        },
        {
            "id": "process",
            "title": "string",
            "steps": [
                {
                    "step_number": "integer",
                    "title": "string",
                    "description": "string",
                }
            ],
        },
        {
            "id": "testimonials",
            "title": "string",
            "items": [
                {
                    "quote": "string",
                    "name": "string",
                    "detail": "string - role or location",
                }
            ],
        },
        {
            "id": "faqs",
            "title": "string",
            "items": [
                {
                    "question": "string",
                    "answer": "string",
                }
            ],
        },
        {
            "id": "final_cta",
            "title": "string",
            "body": "string",
            "primary_cta_label": "string",
            "primary_cta_url": "string",
        },
    ],
}

SERVICE_PAGE_SCHEMA = {
    "page_type": "service",
    "hero": {
        "eyebrow": "string",
        "headline": "string",
        "subheadline": "string",
        "primary_cta_label": "string",
        "primary_cta_url": "string",
    },
    "problem_section": {
        "title": "string",
        "intro": "string",
        "bullets": [
            "string - pain point",
        ],
    },
    "solution_section": {
        "title": "string",
        "intro": "string",
        "bullets": [
            "string - how the service solves the problem",
        ],
    },
    "benefits_section": {
        "title": "string",
        "intro": "string",
        "bullets": [
            "string - tangible benefit",
        ],
    },
    "process_section": {
        "title": "string",
        "steps": [
            {
                "step_number": "integer",
                "title": "string",
                "description": "string",
            }
        ],
    },
    "faq_section": {
        "title": "string",
        "items": [
            {
                "question": "string",
                "answer": "string",
            }
        ],
    },
    "final_cta_section": {
        "title": "string",
        "body": "string",
        "primary_cta_label": "string",
        "primary_cta_url": "string",
    },
}

# For now, sub service pages use the same shape as service pages
SUB_SERVICE_PAGE_SCHEMA = {
    **SERVICE_PAGE_SCHEMA,
    "page_type": "sub service",
}

ABOUT_PAGE_SCHEMA = {
    "page_type": "about",
    "hero": {
        "headline": "string",
        "subheadline": "string",
    },
    "brand_story": {
        "title": "string",
        "body": "string - 2–4 paragraphs as a single string",
    },
    "team_section": {
        "title": "string",
        "intro": "string",
        "members": [
            {
                "name": "string",
                "role": "string",
                "bio": "string",
            }
        ],
    },
    "values_section": {
        "title": "string",
        "values": [
            {
                "label": "string",
                "description": "string",
            }
        ],
    },
    "credibility_section": {
        "title": "string",
        "items": [
            {
                "label": "string - e.g., award, certification",
                "description": "string",
            }
        ],
    },
    "final_cta_section": {
        "title": "string",
        "body": "string",
        "primary_cta_label": "string",
        "primary_cta_url": "string",
    },
}

LOCATION_PAGE_SCHEMA = {
    "page_type": "location",
    "hero": {
        "headline": "string",
        "subheadline": "string",
        "primary_cta_label": "string",
        "primary_cta_url": "string",
    },
    "local_intro": {
        "title": "string",
        "body": "string - intro with location details",
    },
    "services_summary": {
        "title": "string",
        "intro": "string",
        "services": [
            {
                "label": "string",
                "description": "string",
            }
        ],
    },
    "neighborhood_specific_details": {
        "title": "string",
        "body": "string",
        "bullets": [
            "string - local-specific note",
        ],
    },
    "trust_signals": {
        "title": "string",
        "items": [
            {
                "label": "string - e.g., years in area, local partnerships",
                "description": "string",
            }
        ],
    },
    "local_faqs": {
        "title": "string",
        "items": [
            {
                "question": "string",
                "answer": "string",
            }
        ],
    },
    "final_cta_section": {
        "title": "string",
        "body": "string",
        "primary_cta_label": "string",
        "primary_cta_url": "string",
    },
}

PAGE_TYPE_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "home": HOME_PAGE_SCHEMA,
    "service": SERVICE_PAGE_SCHEMA,
    "sub service": SUB_SERVICE_PAGE_SCHEMA,
    "about": ABOUT_PAGE_SCHEMA,
    "location": LOCATION_PAGE_SCHEMA,
}
