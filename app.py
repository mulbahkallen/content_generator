# app.py
import json
from typing import List, Dict, Any

import pandas as pd
import streamlit as st

from config import STYLE_PROFILE_OPTIONS
from openai_client import get_openai_client
from utils import (
    BrandInfo,
    PageDefinition,
    parse_seo_csv,
    build_site_export,
    render_page_preview,
)
from generation_pipeline import generate_outline, generate_draft, refine_draft


st.set_page_config(
    page_title="Agency Website Copy Generator",
    layout="wide",
)


def init_session_state():
    if "results" not in st.session_state:
        st.session_state["results"] = []


def main():
    init_session_state()

    st.title("Website Copy Generation – Internal Agency Tool")

    try:
        client = get_openai_client()
        api_ok = True
    except Exception as exc:
        api_ok = False
        st.error(str(exc))
        st.stop()

    col_left, col_right = st.columns([1, 1.2])

    # -------------------------
    # LEFT COLUMN – INPUTS
    # -------------------------
    with col_left:
        st.header("1. Brand & Project Info")

        brand_name = st.text_input("Brand / Business Name", value="")
        industry = st.text_input("Industry / Niche", value="")
        location = st.text_input("Primary Location (city, state/region)", value="")
        voice_tone = st.text_area(
            "Brand voice & tone",
            value="Approachable, expert, no fluff, benefit-driven.",
        )
        target_audience = st.text_area(
            "Target audience description",
            value="",
        )
        uvp = st.text_area(
            "Unique Value Proposition / Differentiators",
            value="",
        )
        notes = st.text_area(
            "Existing site URL(s) or notes (optional)",
            value="",
        )

        st.header("2. Sitemap / Pages")

        allowed_page_types = ["home", "service", "about", "location"]
        default_pages_df = pd.DataFrame(
            [
                {"slug": "home", "page_name": "Home", "page_type": "home"},
                {
                    "slug": "services/sample-service",
                    "page_name": "Sample Service",
                    "page_type": "service",
                },
            ]
        )

        pages_df = st.data_editor(
            default_pages_df,
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
        )

        st.header("5. Controls")

        show_intermediate = st.checkbox(
            "Show intermediate steps (outline / draft / refinement)", value=True
        )

        generate_button = st.button("Generate Site Copy", type="primary", use_container_width=True)

    # -------------------------
    # RIGHT COLUMN – RESULTS
    # -------------------------
    with col_right:
        st.header("Results")

        if generate_button and api_ok:
            # Basic validation
            if not brand_name or not industry:
                st.error("Please fill in at least Brand / Business Name and Industry / Niche.")
            else:
                # Build BrandInfo
                brand_info = BrandInfo(
                    name=brand_name.strip(),
                    industry=industry.strip(),
                    location=location.strip(),
                    voice_tone=voice_tone.strip(),
                    target_audience=target_audience.strip(),
                    uvp=uvp.strip(),
                    notes=notes.strip(),
                )

                # Build page definitions
                page_definitions: List[PageDefinition] = []
                for _, row in pages_df.iterrows():
                    slug = str(row.get("slug", "")).strip()
                    page_name = str(row.get("page_name", "")).strip()
                    page_type = str(row.get("page_type", "")).strip()

                    if not slug or not page_name or not page_type:
                        continue

                    page_definitions.append(
                        PageDefinition(slug=slug, page_name=page_name, page_type=page_type)
                    )

                if not page_definitions:
                    st.error("Please define at least one page in the sitemap table.")
                else:
                    st.session_state["results"] = []
                    for page in page_definitions:
                        st.markdown(f"#### Generating: {page.page_name} (`{page.slug}`)")
                        with st.spinner(f"Generating outline, draft, and refinement for {page.page_name}..."):
                            seo_entry = seo_map.get(page.slug)

                            # Outline
                            try:
                                outline = generate_outline(client, brand_info, page, seo_entry, style_profile)
                            except Exception as exc:
                                st.error(
                                    f"Error generating outline for {page.page_name} ({page.slug}): {exc}"
                                )
                                outline = None

                            # Draft
                            draft = None
                            if outline is not None:
                                try:
                                    draft = generate_draft(
                                        client,
                                        brand_info,
                                        page,
                                        seo_entry,
                                        style_profile,
                                        outline,
                                    )
                                except Exception as exc:
                                    st.error(
                                        f"Error generating draft for {page.page_name} ({page.slug}): {exc}"
                                    )
                                    draft = None

                            # Refinement
                            final_json = None
                            if draft is not None:
                                try:
                                    final_json = refine_draft(
                                        client,
                                        brand_info,
                                        page,
                                        seo_entry,
                                        style_profile,
                                        draft,
                                    )
                                except Exception as exc:
                                    st.error(
                                        f"Error refining draft for {page.page_name} ({page.slug}): {exc}"
                                    )
                                    final_json = draft  # fall back to unrefined draft

                            st.session_state["results"].append(
                                {
                                    "page": page,
                                    "seo": seo_entry,
                                    "outline": outline,
                                    "draft": draft,
                                    "final": final_json,
                                }
                            )

        # Display results from session_state
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

            # Download section
            st.markdown("---")
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


if __name__ == "__main__":
    main()
