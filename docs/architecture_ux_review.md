# Architecture and UX Review

## Overview
Current implementation mixes Streamlit UI composition, session-state bootstrapping, input parsing, prompt orchestration, and retrieval logic inside `app.py`. This monolithic structure makes it hard to reason about user flows, reuse input-handling logic, and introduce compliance-oriented features without risking regressions.

## User flow and input collection
- **Sequencing**: The Build tab walks through brand info, sitemap, golden rules, references, keyword helpers, and controls in a single, long column. Critical context (brand, audience intent) is collected early, but sitemap upload and golden-rule embedding are interleaved with optional helpers, which can overwhelm users and hide required steps for compliant outputs. [Propose] Split the flow into collapsible steps or a wizard that enforces completion of brand → sitemap → rules → SEO → generation in order, with persistent summary cards.
- **Grouping**: Related inputs are scattered (e.g., keyword uploads separated from service keyword generator and document keyword suggestions). Consolidate SEO inputs into a single section with sub-panels: "Keyword sources" (uploads), "Generated ideas" (services/location), and "Applied lists" (final paramount/primary fields).
- **Defaults and clarity**: Several text areas are blank, forcing users to recall what to supply. Add placeholder examples and concise guidance for regulated language (e.g., no outcome guarantees) near UVP, notes, and CTA fields.
- **Progress visibility**: Results column only shows after scrolling back; add a sticky recap panel (brand, location, model, selected rules) to reduce context switching.

## UX friction and clarity
- **Long-form scrolling**: The single-page layout with many expanders requires frequent scrolling; a left-side stepper or tabs per phase would shorten travel. Collapsing advanced options (golden-rule embeddings, lab-only settings) by default would declutter the primary generation path.
- **Validation gaps**: Inputs like location, audience intent, and keywords are not required before enabling generation. Enforce minimal validation and highlight missing regulatory essentials (disclaimers, consent language) to avoid unusable outputs.
- **Preview readability**: Previews and JSON are stacked; offering toggle between "Human-readable" and "JSON" plus copy-to-clipboard would speed QA and collaboration.

## Prompt and data handling
- **Prompt assembly**: Prompt templates are embedded inline in `app.py` and `generation_pipeline.py`, making it hard to ensure consistent compliance language or add shared guardrails. Centralize templates in a dedicated module with explicit sections (compliance, tone, SEO, safety), and feed them via small builder functions.
- **Rule injection**: Golden-rule embeddings are managed directly in the UI code, mixing file parsing, chunking, and persistence with Streamlit widgets. Move rule ingest (upload + parsing + embedding) into a service layer that returns summaries and structured metadata so the UI only renders results.
- **Input normalization**: Keyword parsing, file uploads, and caching are handled inline with session-state manipulation. Extract utilities for `parse_and_merge_keywords`, `normalize_references`, and `validate_project_state` to reduce duplication between Build and Lab flows.

## Modularity and maintainability
- **Separation of concerns**: `app.py` currently handles UI, business rules, and model calls in one file (~1200+ lines). Break into modules: `ui/layout.py` (sections + steppers), `ui/forms.py` (inputs + validation), `services/rules.py` (embedding + storage), `services/keywords.py`, and `services/generation.py` (pipeline calls). Use dataclasses or Pydantic models to pass validated state between layers instead of raw session state.
- **State management**: Session keys are written throughout the UI flow, which risks drift and makes reuse difficult. Introduce a `ProjectState` object that serializes/deserializes from session state and encapsulates defaults and required fields.
- **Testing**: Prompt builders and validators can be unit-tested once separated. Add fixtures for sitemap CSV parsing, keyword parsing, and rule retrieval to prevent regressions when adjusting UX.

## Recommended UX structure (medical/aesthetic focus)
1. **Project setup step**: Brand, industry selection (with medical presets), geography, intent, UVP, compliance reminders; inline validation before proceeding.
2. **Sitemap step**: Upload CSV or paste; display parsed table with editable page types and slug suggestions; warn if required service pages lack keywords.
3. **Content rules step**: Upload/paste golden rules and compliance boilerplate; show retrieved tags and coverage (e.g., consent, risk language); allow selecting retrieval vs full-text application.
4. **SEO step**: Unified keyword workspace with document-derived ideas, service/location generator, manual uploads, and clear “Applied list” outputs.
5. **Generation step**: Model selection summary, preview of per-page context, run button, and queued status for multiple pages.
6. **Review/export step**: Side-by-side preview/JSON toggle, download bundle, and checklist for medical compliance (disclaimers, no cure claims, scope-of-practice language).

Implementing this layered structure will improve clarity for regulated industries, reduce cognitive load, and make the codebase easier to extend and audit.
