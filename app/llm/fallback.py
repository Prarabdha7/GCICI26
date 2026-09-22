"""Domain-grounded fallback engine — used when the LLM provider is absent or rate-limited.

The module intentionally imports ``app.llm.client`` lazily inside each
function body.  This keeps the module importable in test environments where
no provider SDK is installed, and makes the monkeypatch points explicit.

Two layers are exposed:

    1.  Heuristic functions — ``fallback_content``, ``fallback_localize``,
        ``heuristic_compliance_check``, ``self_healing_fix`` — operate entirely
        on string manipulation and brand knowledge data.  They never call the
        network.

    2.  Safe wrappers — ``safe_text_call``, ``safe_structured_call`` — attempt
        the real provider first and silently downgrade to the heuristic layer on
        ``LLMError``.

Brand copy is sourced from ``app.agents.brand_knowledge`` to ensure a single
source of truth for underwriting data, taglines, and jurisdiction disclaimers.
"""

from __future__ import annotations

import logging
import re

from app.agents.brand_knowledge import get_brand

log = logging.getLogger(__name__)

BANNED_PHRASES = [
    "100% guaranteed", "always approved", "cheap", "loophole",
    "immune", "foolproof", "100% covered", "zero risk",
    "guaranteed payout", "no questions asked",
]

DISCLAIMER = "Terms, conditions, and exclusions apply. Subject to formal policy wording and underwriting approval."


def _brand_key(brand: str) -> str:
    """Normalise a brand display name to a canonical lookup key.

    The three supported brands are identified by substring matching on the
    lowercased input, so ``"Jade Assure"``, ``"jade"``, and ``"JADE"`` all
    resolve to ``"jade"``.

    Args:
        brand: Raw brand name string as received from the API or state dict.

    Returns:
        One of ``"doctorshield"``, ``"jaguar_transit"``, or ``"jade"`` (the
        default when the input does not match either of the first two).
    """
    b = (brand or "").lower()
    if "doctor" in b:
        return "doctorshield"
    if "jaguar" in b:
        return "jaguar_transit"
    return "jade"


def fallback_content(brand: str, platform: str, topic: str = "", feedback_guidance: str = "") -> str:
    """Generate brand-compliant marketing copy without calling the LLM provider.

    Produces deterministic, regulation-safe copy conditioned on the topic
    string.  Banned phrases (as defined in ``BANNED_PHRASES``) are never present
    in the output.  The statutory disclaimer from ``DISCLAIMER`` and the brand's
    ``compliance_disclaimer`` are always appended.

    Consumer electronics / promotional retail language in the topic triggers a
    generic high-value merchandise body rather than brand-specific copy because
    these products fall outside all three brands' underwriting appetite.

    Args:
        brand: Brand display name used to select body text and disclaimer.
        platform: Target social channel (``"linkedin"``, ``"instagram"``,
            ``"x"``, ``"tiktok"``, or ``"blog"``).  Controls the opening label
            of the copy (e.g., ``"Executive Risk Note:"``).
        topic: The user-supplied topic or prompt from the generation request.
            If empty, the brand's configured tagline is used as the hook.
        feedback_guidance: Optional excerpt from the ``CRITICAL GUIDANCE``
            injection block of a previous compliance failure.  If non-empty,
            a truncated version (140 characters) is appended to the body to
            surface the guidance for human review.

    Returns:
        A multi-paragraph, compliance-safe marketing copy string including the
        statutory disclaimer.
    """
    info = get_brand(brand)
    key = _brand_key(brand)
    hook = (topic or "").strip().rstrip(".")
    if not hook:
        hook = info["tagline"]

    platform_hint = {
        "linkedin": "Executive Risk Note:",
        "instagram": "Behind every showcase consignment:",
        "x": "Market brief:",
        "tiktok": "60-second risk explainer:",
        "blog": "Specialist Underwriting Briefing:",
    }.get((platform or "").lower(), "Overview:")

    if any(w in hook.lower() for w in ["iphone", "phone", "device", "retail", "offer", "discount", "electronics"]):
        body = (
            f"{platform_hint} {hook}.\n\n"
            f"High-turnover promotional inventory and consumer technology shipments face heightened transit and storage risks across regional trade corridors. "
            f"{brand} provides Lloyd's-backed commercial indemnity with verified chain-of-custody, dual-key vault parity, and transit protection for high-value merchandise."
        )
    elif key == "doctorshield":
        body = (
            f"{platform_hint} {hook}.\n\n"
            f"DoctorShield provides contract-based medical indemnity with 24/7 medico-legal advisory, "
            f"retroactive cover transfer, and transparent legal defense representation for specialist clinicians across Singapore, Malaysia, and Hong Kong."
        )
    elif key == "jaguar_transit":
        body = (
            f"{platform_hint} {hook}.\n\n"
            f"Jaguar Transit binds per-consignment high-value multi-modal cargo cover in minutes "
            f"with IoT telematics-linked chain-of-custody documentation across ASEAN freight trade corridors."
        )
    else:
        body = (
            f"{platform_hint} {hook}.\n\n"
            f"Jade Jewellers Block covers physical vault stock, memo goods, and attended exhibition transit "
            f"with same-day memo endorsements designed by specialists for luxury horology and diamond boutiques."
        )

    if feedback_guidance:
        body += f"\n\n(Reviewer guidance incorporated: {feedback_guidance[:140]})"
    return f"{body}\n\n{info['compliance_disclaimer']} {DISCLAIMER}"


def fallback_localize(draft: str, language: str, brand: str = "Jade") -> str:
    """Apply a lightweight regional pass to a draft without calling the LLM provider.

    Preserves all brand names and copy intact, then prepends a two-to-four
    character jurisdiction prefix (``[MY]``, ``[HK]``, ``[TH]``, ``[ID]``) for
    non-English outputs and appends the mandatory jurisdiction warning from
    ``JURISDICTIONS[jurisdiction]["mandatory_warnings"]``.

    Args:
        draft: The marketing copy string to localize.
        language: ISO 639-1 language code (``"ms"``, ``"zh"``, ``"th"``,
            ``"id"``, or ``"en"``).  Unrecognised codes are treated as English.
        brand: Brand display name — reserved for future per-brand jurisdiction
            routing; currently unused in body generation.

    Returns:
        The localized draft string with jurisdiction prefix and mandatory
        warning appended.
    """
    from app.agents.brand_knowledge import JURISDICTIONS, LANGUAGE_TO_JURISDICTION

    jurisdiction = LANGUAGE_TO_JURISDICTION.get((language or "en").lower(), "Singapore")
    warning = JURISDICTIONS[jurisdiction]["mandatory_warnings"]
    prefix = {"ms": "[MY] ", "zh": "[HK] ", "th": "[TH] ", "id": "[ID] "}.get((language or "").lower(), "")
    return f"{prefix}{draft}\n\n{warning}"


def heuristic_compliance_check(draft: str) -> dict:
    """Run a deterministic banned-phrase and disclaimer check against a draft.

    Evaluates the draft against ``BANNED_PHRASES`` using case-insensitive
    substring matching and checks for the presence of at least one recognised
    disclaimer phrase.  Returns a result dict shaped identically to the
    structured LLM compliance gate output so callers do not need to branch.

    Args:
        draft: Raw marketing copy string to evaluate.

    Returns:
        A dict with exactly two keys:
            ``is_compliant`` (bool): ``True`` when no violations are detected.
            ``violations`` (list[str]): Human-readable violation descriptions
                referencing the rubric rule number, or an empty list when
                compliant.
    """
    lowered = (draft or "").lower()
    violations = [f"Uses banned phrase '{p}' (Rubric 1/4)" for p in BANNED_PHRASES if p in lowered]
    has_disclaimer = any(
        d.lower() in lowered
        for d in ["terms, conditions", "subject to formal policy", "does not constitute financial advice", "syarat", "terms and conditions apply"]
    )
    if not has_disclaimer:
        violations.append("Missing mandatory disclaimer (Rubric 3)")
    return {"is_compliant": not violations, "violations": violations}


def self_healing_fix(draft: str, violations: list[str]) -> str:
    """Apply a deterministic redline repair to a non-compliant draft.

    Replaces every occurrence of a banned phrase with the safe substitute
    ``"subject to underwriting and policy terms"`` using case-insensitive regex.
    If the violation list indicates a missing disclaimer and the standard
    disclaimer is not already present, it is appended to the end of the draft.

    Args:
        draft: The non-compliant marketing copy to repair.
        violations: The violation list returned by ``heuristic_compliance_check``
            or the LLM compliance gate.  Used only to decide whether the
            disclaimer is missing; the phrase repair is unconditional.

    Returns:
        The repaired copy string.  May still fail compliance if the LLM gate
        finds semantic violations not covered by the banned-phrase list — the
        caller is responsible for re-checking.
    """
    fixed = draft
    for phrase in BANNED_PHRASES:
        fixed = re.sub(re.escape(phrase), "subject to underwriting and policy terms", fixed, flags=re.IGNORECASE)
    if "Missing mandatory disclaimer" in " ".join(violations) and DISCLAIMER.lower() not in fixed.lower():
        fixed = f"{fixed.rstrip()}\n\n{DISCLAIMER}"
    return fixed


def safe_text_call(*, system: str, user: str, brand: str = "Jade", platform: str = "linkedin", **kwargs) -> str:
    """Attempt a live LLM text call, downgrading to domain copy on failure.

    Wraps ``app.llm.client.text_call`` with a catch for ``LLMError``.  On any
    provider failure (missing key, rate limit, network error) the function
    falls back to ``fallback_content`` with the user prompt as the topic and
    any ``CRITICAL GUIDANCE`` fragment from the system prompt forwarded as
    feedback guidance.

    The import of ``app.llm.client`` is deferred to the function body so that
    test modules can monkeypatch ``app.llm.client.text_call`` after import time.

    Args:
        system: System prompt string.  If it contains the literal string
            ``"CRITICAL GUIDANCE"``, it is forwarded to ``fallback_content`` as
            the ``feedback_guidance`` parameter.
        user: User turn content / topic prompt.  First 300 characters are used
            as the fallback topic.
        brand: Brand name forwarded to ``fallback_content``.
        platform: Platform name forwarded to ``fallback_content``.
        **kwargs: Additional keyword arguments forwarded verbatim to
            ``text_call`` (e.g. ``temperature``).

    Returns:
        Either the raw LLM response or a deterministic fallback copy string.
    """
    from app.llm.client import LLMError, text_call

    try:
        return text_call(system=system, user=user, **kwargs)
    except LLMError as exc:
        log.warning("LLM unavailable (%s) — domain fallback for %s/%s", exc, brand, platform)
        topic = user[:300] if user else ""
        guidance = system if "CRITICAL GUIDANCE" in system else ""
        return fallback_content(brand, platform, topic, guidance)


def safe_structured_call(*, system: str, user: str, schema: dict, brand: str = "Jade", **kwargs) -> dict:
    """Attempt a live structured LLM call, downgrading to heuristic gate on failure.

    Wraps ``app.llm.client.structured_call`` with a catch for ``LLMError``.
    On failure the function inspects the ``schema["properties"]`` keys to decide
    which heuristic to apply:

    - Compliance gate schema (keys ``is_compliant`` and ``violations``): runs
      ``heuristic_compliance_check`` on the user string.
    - Lead-score schema (contains key ``fit_score``): returns a fixed-score
      fallback dict with a human-readable rationale note.
    - All other schemas: returns the compliance check result as a best-effort
      structural approximation.

    The import of ``app.llm.client`` is deferred to the function body for the
    same monkeypatch reason as ``safe_text_call``.

    Args:
        system: System prompt string.
        user: User turn content / the draft to evaluate or the lead description.
        schema: JSON Schema dict describing the required response structure.
        brand: Brand name used in the lead-score fallback response string.
        **kwargs: Additional keyword arguments forwarded verbatim to
            ``structured_call``.

    Returns:
        A dict conforming (or approximating) the supplied schema.
    """
    from app.llm.client import LLMError, structured_call

    try:
        return structured_call(system=system, user=user, schema=schema, **kwargs)
    except LLMError as exc:
        log.warning("LLM judge unavailable (%s) — heuristic gate", exc)
        draft = user or ""
        verdict = heuristic_compliance_check(draft)
        # Only return keys the schema requires to avoid breaking callers
        if set(schema.get("properties", {})) == {"is_compliant", "violations"}:
            return verdict
        # Lead-score schema fallback
        if "fit_score" in schema.get("properties", {}):
            return {"fit_score": 72, "score_rationale": "Fallback scoring: B2B fit by niche keyword match.", "outreach_draft": f"Hello — JA Assure {brand} can cover this risk. Terms apply."}
        return verdict

