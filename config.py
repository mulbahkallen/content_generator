HOME_PAGE_SCHEMA = {
    "page_type": "home",
    "hero": {
        "eyebrow": "string - short positioning phrase above the headline",
        "headline": "string - main benefit-driven headline",
        "subheadline": "string - one to two sentences expanding on the main promise",
        "primary_cta_label": "string - e.g., 'Request a Consultation'",
        "primary_cta_url": "string - URL path or placeholder",
        "secondary_cta_label": "string - optional",
        "secondary_cta_url": "string - optional"
    },
    "sections": [
        {
            "id": "services_overview",
            "title": "string - section heading",
            "intro": "string - short intro paragraph",
            "items": [
                {
                    "label": "string - service name",
                    "description": "string - 1–2 sentence description"
                }
            ]
        },
        {
            "id": "why_choose_us",
            "title": "string",
            "intro": "string",
            "bullets": [
                "string - specific, benefit-driven reason"
            ]
        },
        {
            "id": "process",
            "title": "string",
            "steps": [
                {
                    "step_number": "integer",
                    "title": "string",
                    "description": "string"
                }
            ]
        },
        {
            "id": "testimonials",
            "title": "string",
            "items": [
                {
                    "quote": "string",
                    "name": "string",
                    "detail": "string - role or location"
                }
            ]
        },
        {
            "id": "faqs",
            "title": "string",
            "items": [
                {
                    "question": "string",
                    "answer": "string"
                }
            ]
        },
        {
            "id": "final_cta",
            "title": "string",
            "body": "string",
            "primary_cta_label": "string",
            "primary_cta_url": "string"
        }
    ]
}
