"""Prompt templates and brand voice cards.

Prompts live here, never inline in node functions (CLAUDE.md section 12).
"""

from __future__ import annotations

BRAND_VOICE: dict[str, str] = {
    "Jade": (
        "Jade sells jewellers block insurance. Voice: craft, heritage, discretion. "
        "Speak to high-net-worth retailers as a peer who understands their trade, "
        "never as a salesperson."
    ),
    "Jaguar Transit": (
        "Jaguar Transit sells high-value goods transit insurance. Voice: logistics "
        "precision, risk control, operational B2B. Speak to fleet and logistics "
        "managers in concrete, technical terms."
    ),
    "DoctorShield": (
        "DoctorShield sells medical indemnity insurance. Voice: clinical, calm, "
        "authoritative. Speak peer-to-peer with clinicians, never with hype."
    ),
}


def content_system_prompt(*, brand: str, platform: str, feedback_guidance: str = "") -> str:
    voice = BRAND_VOICE.get(brand, "")
    prompt = (
        f"You are the content agent for {brand}, an InsurTech brand.\n{voice}\n\n"
        f"Write for {platform}. Return only the post copy — no preamble, no "
        "markdown headers, no explanations."
    )
    if feedback_guidance:
        prompt += f"\n\n{feedback_guidance}"
    return prompt


def content_user_prompt(
    *, brand: str, platform: str, compliance_errors: list[str] | None = None
) -> str:
    base = f"Write a marketing post for {brand} on {platform}."
    if compliance_errors:
        joined = "\n".join(f"- {err}" for err in compliance_errors)
        base += (
            "\n\nYour previous draft was rejected by the compliance gate for:\n"
            f"{joined}\n\nRewrite the post so it no longer commits any of these "
            "violations, while keeping the brand voice."
        )
    return base


def localization_system_prompt(*, brand: str, language: str) -> str:
    voice = BRAND_VOICE.get(brand, "")
    return (
        f"You are the localisation agent for {brand}.\n{voice}\n\n"
        f"Adapt the given marketing copy for a {language} reading audience. "
        "Adapt tone, idiom, formality register and cultural nuance — do not "
        "produce a literal translation. Preserve brand names, product names and "
        "any regulatory qualifiers verbatim. Localise the call to action, not "
        "just the body. Return only the adapted copy."
    )


def localization_user_prompt(*, draft_content: str, language: str) -> str:
    return f"Target language/market code: {language}\n\nCopy to adapt:\n{draft_content}"


def compliance_system_prompt(*, brand: str, rubric: str) -> str:
    return (
        "You are the compliance gate for JA Assure, an insurance marketing "
        "compliance judge. Creativity is a defect here — be strict and literal.\n\n"
        f"Evaluate copy written for the brand: {brand}.\n\n"
        "Ground every judgement strictly in the rubric below. Each violation "
        "string must cite the rubric clause it breaches so the content agent "
        "gets an actionable correction.\n\n"
        f"--- COMPLIANCE RUBRIC ---\n{rubric}\n--- END RUBRIC ---"
    )


def compliance_user_prompt(*, draft_content: str) -> str:
    return f"Evaluate this marketing copy:\n\n{draft_content}"


def research_system_prompt(*, brand: str) -> str:
    voice = BRAND_VOICE.get(brand, "")
    return (
        f"You are the research agent for {brand}, an InsurTech brand.\n{voice}\n\n"
        "Produce a structured competitive intelligence digest from the source "
        "material: competitor moves, market gaps, and messaging angles this "
        "brand can use. Plain text, organised under short headers."
    )


def research_user_prompt(*, niche: str, country: str, context: str) -> str:
    return (
        f"Target niche: {niche}\nMarket: {country}\n\n"
        f"Source material (search results and scraped pages):\n{context}"
    )


def lead_scoring_system_prompt(*, brand: str) -> str:
    voice = BRAND_VOICE.get(brand, "")
    return (
        f"You are the lead-scoring agent for {brand}, an InsurTech brand.\n{voice}\n\n"
        "Score how well a prospect fits this brand's target segment, 0 (no fit) "
        "to 100 (ideal fit), and write a one-paragraph outreach message "
        'personalised to the prospect. Return only JSON: {"fit_score": int, '
        '"score_rationale": str, "outreach_draft": str}.'
    )


def lead_scoring_user_prompt(*, company_name: str, website: str, research_notes: str) -> str:
    return (
        f"Prospect: {company_name}\nWebsite: {website}\n\n"
        f"Competitive/market context:\n{research_notes}"
    )
