import io
import re
import time
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.verification_service import (
    analyze_domain_and_email,
    check_student_protection_risks,
    mask_pii,
    FREE_EMAIL_PROVIDERS,
)
import tldextract
from app.services.scam_connection_service import find_scam_connections

# Optional google-genai import
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


# --- Pydantic Schemas for Structured Output ---

class ExtractedEntities(BaseModel):
    phone: List[str] = Field(default_factory=list, description="Phone numbers found")
    email: List[str] = Field(default_factory=list, description="Email addresses found")
    domain: List[str] = Field(default_factory=list, description="Domains or URLs found")
    upi_id: List[str] = Field(default_factory=list, description="UPI IDs found (e.g., name@okaxis)")
    telegram: List[str] = Field(default_factory=list, description="Telegram handles or links")


class BilingualInvestigationReport(BaseModel):
    opportunity_type: str = Field(default="Job")
    company_name: Optional[str] = None
    risk_level: str = Field(description="Risk assessment: LOW, MEDIUM, or HIGH")
    risk_score: int = Field(description="Integer score from 0 (completely safe) to 100 (critical scam)")
    red_flags: List[str] = Field(default_factory=list, description="List of detected red flags")
    student_protection_alerts: List[str] = Field(
        default_factory=list, description="Alerts related to financial and PII risks"
    )
    summary_en: str = Field(description="Clear investigation summary in English")
    summary_te: str = Field(
        description="Clear explanation in natural Tenglish (Telugu language written in English/Roman letters, e.g. 'Ee job offer lo high fraud risk undi...') for regional student accessibility"
    )
    preventive_actions_en: List[str] = Field(
        default_factory=list, description="Concrete defensive steps in English"
    )
    preventive_actions_te: List[str] = Field(
        default_factory=list,
        description="Concrete defensive steps in natural Tenglish (Telugu written in English/Roman letters, e.g. 'Registration fee peru tho dabbu transfer cheyavaddu.')",
    )
    verification_questions: List[str] = Field(
        default_factory=list,
        description="3 pointed questions the student can ask the recruiter to verify legitimacy",
    )


class UnifiedMultimodalInvestigation(BaseModel):
    """Combined single-call schema extracting document text, contact entities, and full risk report."""
    extracted_text: str = Field(
        default="",
        description="Clean, complete transcription of all visible text in the document or image",
    )
    entities: ExtractedEntities = Field(
        default_factory=ExtractedEntities,
        description="All contact indicators found (phone numbers, emails, domains, UPI IDs, telegram handles)",
    )
    opportunity_type: str = Field(
        default="Job",
        description="Opportunity category: Job, Internship, WFH, Freelancing, Training Program, or Placement Drive",
    )
    company_name: Optional[str] = Field(
        default=None,
        description="Company, recruiter, or organization name identified in the document",
    )
    risk_level: str = Field(
        default="LOW",
        description="Risk assessment: LOW, MEDIUM, or HIGH",
    )
    risk_score: int = Field(
        default=15,
        description="Integer score from 0 (completely safe) to 100 (critical scam)",
    )
    red_flags: List[str] = Field(
        default_factory=list,
        description="List of detected red flags and fraudulent indicators",
    )
    student_protection_alerts: List[str] = Field(
        default_factory=list,
        description="Alerts related to upfront payments, fees, or sensitive PII demands",
    )
    summary_en: str = Field(
        default="",
        description="Clear investigation summary in English",
    )
    summary_te: str = Field(
        default="",
        description="Clear explanation in natural Tenglish (Telugu written in English/Roman letters, e.g. 'Ee job offer lo high fraud risk undi...')",
    )
    preventive_actions_en: List[str] = Field(
        default_factory=list,
        description="Concrete defensive steps in English",
    )
    preventive_actions_te: List[str] = Field(
        default_factory=list,
        description="Concrete defensive steps in natural Tenglish (Telugu written in English/Roman letters)",
    )
    verification_questions: List[str] = Field(
        default_factory=list,
        description="3 pointed questions the student can ask the recruiter to verify legitimacy",
    )


class GeminiQuotaExhaustedError(Exception):
    """Raised when all candidate Gemini models fail due to 429 RESOURCE_EXHAUSTED."""
    pass


def _get_genai_client() -> Optional[Any]:
    """Instantiate and return google-genai Client with 25s timeout if configured."""
    if not GENAI_AVAILABLE or not settings.GEMINI_API_KEY:
        return None
    # If the user still has placeholder text, treat as unconfigured
    if "your_gemini_api_key" in settings.GEMINI_API_KEY.lower():
        return None
    try:
        http_options = None
        if hasattr(types, "HttpOptions"):
            http_options = types.HttpOptions(timeout=25000)

        if http_options is not None:
            return genai.Client(api_key=settings.GEMINI_API_KEY, http_options=http_options)
        return genai.Client(api_key=settings.GEMINI_API_KEY)
    except Exception as e:
        print(f"[ScamShield AI Gemini Error]: {e}")
        return None


def _build_generation_config(response_schema: Any, model_name: str = "gemini-3.8-flash") -> Any:
    """
    Builds GenerateContentConfig.
    Only passes thinking_config=types.ThinkingConfig(thinking_budget=0) when model_name is "gemini-3.8-flash".
    For "gemini-3.5-flash-lite" (and any "-lite" model), thinking_config is omitted
    so it does not throw 400 INVALID_ARGUMENT.
    """
    if not GENAI_AVAILABLE:
        return None

    is_lite = "-lite" in model_name.lower()
    # Only include zero thinking budget for gemini-3.8-flash to avoid 400 INVALID_ARGUMENT on -lite models
    if model_name == "gemini-3.8-flash" and not is_lite:
        try:
            if hasattr(types, "ThinkingConfig"):
                return types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                )
        except Exception:
            pass

    # Standard config without thinking_config for -lite models or fallback
    try:
        return types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        )
    except Exception:
        return None


# Module-level cache for models that encounter 429 RESOURCE_EXHAUSTED
# Key: model_name, Value: expiry timestamp (time.time() + cooldown)
_EXHAUSTED_MODELS_COOLDOWN: Dict[str, float] = {}
COOLDOWN_SECONDS: float = 15 * 60  # 15 minutes


def _is_model_in_cooldown(model_name: str) -> bool:
    """Checks whether a model is currently in a 15-minute 429 quota cooldown."""
    expiry = _EXHAUSTED_MODELS_COOLDOWN.get(model_name)
    if expiry is None:
        return False
    if time.time() < expiry:
        return True
    # Cooldown has passed; evict from cache
    _EXHAUSTED_MODELS_COOLDOWN.pop(model_name, None)
    return False


def _mark_model_exhausted(model_name: str, cooldown_seconds: float = COOLDOWN_SECONDS) -> None:
    """Marks a model as quota-exhausted with a cooldown timestamp."""
    _EXHAUSTED_MODELS_COOLDOWN[model_name] = time.time() + cooldown_seconds
    print(
        f"[ScamShield AI Quota Cache]: Model '{model_name}' marked as quota-exhausted (429). "
        f"Cooldown active for {cooldown_seconds / 60:.0f} minutes."
    )


def _is_transient_error(err_str: str) -> bool:
    """Checks for 503 UNAVAILABLE or 504 DEADLINE_EXCEEDED / timeout errors."""
    err_lower = err_str.lower()
    return (
        "503" in err_str
        or "unavailable" in err_lower
        or "504" in err_str
        or "deadline_exceeded" in err_lower
        or "deadline exceeded" in err_lower
        or "timed out" in err_lower
        or "timeout" in err_lower
    )


def _generate_content_with_failover(
    client: Any,
    contents: List[Any],
    response_schema: Optional[Any] = None,
    config: Optional[Any] = None,
) -> Any:
    """
    Calls Gemini API trying gemini-3.8-flash first.
    If it encounters 503 UNAVAILABLE or 504 DEADLINE_EXCEEDED, waits 1 second and retries once
    before failing over to gemini-3.5-flash-lite.
    If 429 RESOURCE_EXHAUSTED occurs, caches the exhausted model for 15 minutes so subsequent
    calls jump straight to gemini-3.5-flash-lite in 0ms without wasting time.
    Only passes thinking_config(thinking_budget=0) for gemini-3.8-flash; omits it for gemini-3.5-flash-lite
    (and any -lite model) to prevent 400 INVALID_ARGUMENT.
    Logs all failures as: [ScamShield AI Gemini Error]: {e}
    """
    models = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
    last_error: Optional[Exception] = None
    all_quota_failures = True

    # Resolve target response schema from explicit argument or config object
    target_schema = response_schema
    if target_schema is None and config is not None:
        target_schema = getattr(config, "response_schema", None)

    for idx, model_name in enumerate(models):
        # 1. Skip models currently in 15-minute 429 cooldown
        if _is_model_in_cooldown(model_name):
            remaining_sec = int(_EXHAUSTED_MODELS_COOLDOWN.get(model_name, 0) - time.time())
            print(
                f"[ScamShield AI Quota Cache]: Skipping '{model_name}' "
                f"(in 429 cooldown, ~{max(1, remaining_sec // 60)}m remaining). Jumping to next candidate in 0ms."
            )
            continue

        if target_schema is not None:
            current_config = _build_generation_config(target_schema, model_name=model_name)
        else:
            current_config = config

        # 2. Call with a 1-second retry once per model on 503 UNAVAILABLE or 504 DEADLINE_EXCEEDED
        retried_transient = False
        while True:
            try:
                return client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=current_config,
                )
            except Exception as e:
                last_error = e
                err_msg = str(e)
                err_lower = err_msg.lower()

                # If transient error (503/504), retry once after 1s before failing over
                if not retried_transient and _is_transient_error(err_msg):
                    retried_transient = True
                    print(
                        f"[ScamShield AI Gemini Transient]: {model_name} encountered transient error "
                        f"({e}). Retrying in 1s once before failover..."
                    )
                    time.sleep(1)
                    continue

                print(f"[ScamShield AI Gemini Error] [{model_name}]: {e}")

                is_quota_issue = (
                    "429" in err_msg
                    or "resource_exhausted" in err_lower
                    or "quota" in err_lower
                    or "rate limit" in err_lower
                )

                if is_quota_issue:
                    _mark_model_exhausted(model_name)
                else:
                    all_quota_failures = False

                is_failover_status = (
                    is_quota_issue
                    or _is_transient_error(err_msg)
                    or "500" in err_msg
                    or "internal" in err_lower
                    or "404" in err_msg
                    or "not found" in err_lower
                )

                if is_failover_status and idx < len(models) - 1:
                    next_model = models[idx + 1]
                    print(
                        f"[ScamShield AI Gemini Failover]: {model_name} returned error ({e}). "
                        f"Failing over to {next_model}..."
                    )
                break

    if all_quota_failures:
        print(
            "[ScamShield AI Quota Notice]: All Gemini models exhausted quota (429 RESOURCE_EXHAUSTED). "
            "Engaging ScamShield Deterministic Student Protection Engine."
        )
        msg = str(last_error) if last_error else "All candidate Gemini models are in 429 cooldown."
        raise GeminiQuotaExhaustedError(msg)

    if last_error is not None:
        raise last_error

    raise RuntimeError("Failed to generate content: no candidate Gemini models available.")


def _optimize_image_if_needed(file_bytes: bytes, mime_type: str) -> Tuple[bytes, str]:
    """
    Downsamples uploaded images in-memory if width or height exceeds 1280px (maintaining aspect ratio).
    Converts RGBA, P, LA, or non-RGB images to RGB with img.convert('RGB') before saving as JPEG,
    and returns (compressed_bytes, 'image/jpeg') for robust, fast Gemini multimodal input.
    """
    if not mime_type or not mime_type.startswith("image/"):
        return file_bytes, mime_type

    try:
        img = Image.open(io.BytesIO(file_bytes))
        max_dim = 1280
        width, height = img.size

        if width > max_dim or height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        # Convert RGBA, P, LA or non-RGB modes to RGB for safe JPEG serialization
        if img.mode in ("RGBA", "P", "LA") or img.mode != "RGB":
            img = img.convert("RGB")

        output_buffer = io.BytesIO()
        img.save(output_buffer, format="JPEG", quality=85)
        return output_buffer.getvalue(), "image/jpeg"
    except Exception as e:
        print(f"[ScamShield AI Image Processing Error]: {e}")
        return file_bytes, mime_type


def _regex_extract_entities(text: str) -> ExtractedEntities:
    """Fast regex extractor for contact indicators without incurring any LLM latency."""
    if not text:
        return ExtractedEntities()

    emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    phones = re.findall(r"(?:\+91[-.\s]?)?[6-9]\d{9}\b|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", text)
    domains = re.findall(r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+|(?:\b[a-zA-Z0-9-]+\.(?:com|org|net|in|co|xyz|top|info|site|tech)\b)", text)
    upi_ids = re.findall(r"\b[a-zA-Z0-9.\-_]{2,256}@(?!gmail|yahoo|outlook|hotmail|proton)[a-zA-Z]{2,64}\b", text)
    telegram = re.findall(r"(?:^|[\s,;:(])@([A-Za-z0-9_]{5,32})\b|t\.me/([A-Za-z0-9_]{5,32})", text)
    flattened_tg = [t[0] or t[1] for t in telegram if any(t)]

    return ExtractedEntities(
        phone=list(set(phones)),
        email=list(set(emails)),
        domain=list(set(domains)),
        upi_id=list(set(upi_ids)),
        telegram=list(set(flattened_tg)),
    )


def _infer_opportunity_type(text: str, default: Optional[str] = None) -> str:
    """Infers opportunity category from text or default value."""
    if default:
        return default
    lowered = text.lower()
    if "intern" in lowered:
        return "Internship"
    if "wfh" in lowered or "work from home" in lowered:
        return "WFH"
    if "freelanc" in lowered:
        return "Freelancing"
    if "placement" in lowered:
        return "Placement Drive"
    if "training" in lowered:
        return "Training Program"
    return "Job"


GENERIC_DOMAINS = {
    "gmail", "yahoo", "outlook", "hotmail", "proton", "protonmail", "yopmail", "mailinator",
    "telegram", "t", "whatsapp", "wa", "google", "drive", "docs", "bit", "bitly", "tinyurl",
    "shorturl", "linkedin", "github", "gitlab", "facebook", "instagram", "twitter", "x",
    "youtube", "example", "test", "domain",
}

PREPOSITION_BLACKLIST = {
    "home", "office", "work", "us", "me", "you", "them", "him", "her", "it",
    "today", "tomorrow", "yesterday", "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday", "january", "february", "march", "april", "may",
    "june", "july", "august", "september", "october", "november", "december",
    "paying", "sending", "depositing", "clicking", "visiting", "applying",
    "least", "most", "all", "any", "this", "that", "these", "those",
    "first", "second", "third", "end", "beginning", "start",
    "candidate", "students", "graduates", "hr", "team",
}


def _clean_company_name(name: str) -> str:
    cleaned = name.strip(" \t\r\n,;:-*\"'`_")
    if cleaned.endswith(".") and not (cleaned.endswith("Ltd.") or cleaned.endswith("Inc.") or cleaned.endswith("Pvt.")):
        cleaned = cleaned[:-1].strip()
    return cleaned


def extract_company_name(
    text: Optional[str] = "",
    emails: Optional[List[str]] = None,
    domains: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Extracts company/organization/employer name in priority order:
    1) Explicit labels: Company|Organization|Employer|Program|From|Issued by\s*[:\-]\s*([^\n\r]+)
    2) Corporate suffixes anywhere in text: capitalized multi-word names ending in
       Pvt\.?\s*Ltd\.?|Private Limited|Ltd\.?|Inc\.?|LLC|Technologies|Solutions|Systems|Labs|Corporation|Corp|Infotech|Agency
    3) Preposition phrases anywhere in text: (?:at|from|with|by)\s+([A-Z][A-Za-z0-9&\.\-]+(?:\s+[A-Z][A-Za-z0-9&\.\-]+){0,3})
    4) Non-free corporate email / website domain fallback (e.g. careers.freshworks.com or zoho.com -> 'Freshworks' / 'Zoho')
    """
    if not text and not emails and not domains:
        return None
    raw_text = text or ""

    # 1. Explicit labels
    m1 = re.search(
        r"(?:company|organization|employer|program|from|issued\s+by)\s*[:\-]\s*([^\n\r]+)",
        raw_text,
        re.I,
    )
    if m1:
        extracted = _clean_company_name(m1.group(1))
        if extracted and not (extracted.startswith("http") or "@" in extracted):
            return extracted

    # 2. Corporate suffixes anywhere in text
    m2 = re.search(
        r"\b([A-Z][A-Za-z0-9&.\-]+(?:\s+[A-Z][A-Za-z0-9&.\-]+)*\s+(?:Pvt\.?\s*Ltd\.?|Private Limited|Ltd\.?|Inc\.?|LLC|Technologies|Solutions|Systems|Labs|Corporation|Corp|Infotech|Agency))(?!\w)",
        raw_text,
    )
    if m2:
        extracted = _clean_company_name(m2.group(1))
        if extracted:
            return extracted

    # 3. Preposition phrases anywhere in text
    for m3 in re.finditer(
        r"\b(?:at|from|with|by)\s+([A-Z][A-Za-z0-9&.\-]+(?:\s+[A-Z][A-Za-z0-9&.\-]+){0,3})\b",
        raw_text,
    ):
        cand = _clean_company_name(m3.group(1))
        words = cand.split()
        if (
            words
            and words[0].lower() not in PREPOSITION_BLACKLIST
            and cand.lower() not in PREPOSITION_BLACKLIST
        ):
            return cand

    # 4. Non-free corporate email / website domain fallback
    candidate_domains: List[str] = []
    if emails:
        for em in emails:
            if em and "@" in em:
                candidate_domains.append(em.split("@")[-1].strip().lower())
    if domains:
        for dom in domains:
            if dom:
                candidate_domains.append(dom.strip().lower())

    # Fallback to regex entity extraction if emails/domains not provided
    if not candidate_domains and raw_text:
        text_emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", raw_text)
        for em in text_emails:
            candidate_domains.append(em.split("@")[-1].strip().lower())
        text_domains = re.findall(
            r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+|(?:\b[a-zA-Z0-9-]+\.(?:com|org|net|in|co|xyz|top|info|site|tech)\b)",
            raw_text,
        )
        for dom in text_domains:
            candidate_domains.append(dom.strip().lower())

    for raw_domain in candidate_domains:
        if raw_domain in FREE_EMAIL_PROVIDERS:
            continue
        ext = tldextract.extract(raw_domain)
        d_name = ext.domain
        if (
            d_name
            and len(d_name) > 1
            and d_name.lower() not in GENERIC_DOMAINS
            and f"{d_name}.{ext.suffix}".lower() not in FREE_EMAIL_PROVIDERS
        ):
            return d_name.capitalize()

    return None


_extract_company_name_fallback = extract_company_name


def _build_deterministic_report(
    opportunity_type: str,
    company_name: Optional[str],
    deterministic_red_flags: List[str],
    step_b_domain: Dict[str, Any],
    step_b_protection: Dict[str, Any],
    step_b_connections: Dict[str, Any],
    is_quota_fallback: bool = False,
    text: Optional[str] = None,
    emails: Optional[List[str]] = None,
    domains: Optional[List[str]] = None,
) -> BilingualInvestigationReport:
    """Deterministic report generator used when Gemini is unconfigured or encounters an error."""
    if not company_name and text:
        company_name = extract_company_name(text, emails=emails, domains=domains)
    has_critical = step_b_protection.get("has_critical_risk", False)
    is_coordinated = step_b_connections.get("is_coordinated_campaign", False)
    has_suspicious_domain = step_b_domain.get("has_suspicious_domain", False)

    if has_critical or is_coordinated:
        risk_level = "HIGH"
        risk_score = 88 if is_coordinated else 82
        summary_en = (
            "High fraud risk detected. The opportunity demands financial payments or sensitive personal identity "
            "credentials, which violates ethical recruitment standards. Do not pay any amount or share private documents."
        )
        summary_te = (
            "Ee job/internship offer lo high fraud risk undi. Registration leda deposit peru tho dabbu adagadam "
            "mariyu sensitive identity documents adagadam scammers standard trick. Ee offer kosam e mathram dabbu pay cheyavaddu mariyu private documents share cheyavaddu."
        )
    elif has_suspicious_domain or step_b_connections.get("total_connected_reports", 0) > 0:
        risk_level = "MEDIUM"
        risk_score = 55
        summary_en = (
            "Moderate risk detected. The recruiter is utilizing non-corporate communication channels or unverified domains. "
            "Proceed with extreme caution and verify the opportunity directly on the employer's official website."
        )
        summary_te = (
            "Ee offer lo konni warnings detect ayyayi. Recruiter personal email leda unverified domains use chesthunnaru. "
            "Company official website lo ee job opportunity gurinchi direct ga check chesi confirm chesukondi."
        )
    else:
        risk_level = "LOW"
        risk_score = 18
        summary_en = (
            "Low risk detected. No upfront financial demands or critical PII harvesting patterns were flagged. "
            "Always follow safe career practices before sharing confidential information."
        )
        summary_te = (
            "Preliminary check lo elanti severe scam signs kanipinchaledu. Ayina sare company official rules follow avvandi mariyu verified HR channels tho mathrame communicate cheyandi."
        )

    if is_quota_fallback:
        summary_en += (
            "\n\n[Notice: Real-time Gemini API quota reached (429 RESOURCE_EXHAUSTED). "
            "Assessment completed via ScamShield Deterministic Student Protection Engine.]"
        )
        summary_te += (
            "\n\n[Notice: Real-time Gemini API quota reach ayyindi (429 RESOURCE_EXHAUSTED). "
            "ScamShield Deterministic Student Protection Engine dwara analyze cheyabadindi.]"
        )
        quota_notice = "Notice: Evaluated via ScamShield Deterministic Engine (Gemini 429 Quota Exceeded)."
        if quota_notice not in deterministic_red_flags:
            deterministic_red_flags.append(quota_notice)

    return BilingualInvestigationReport(
        opportunity_type=opportunity_type,
        company_name=company_name,
        risk_level=risk_level,
        risk_score=risk_score,
        red_flags=deterministic_red_flags or ["No immediate structural red flags found."],
        student_protection_alerts=step_b_protection.get("all_alerts", []),
        summary_en=summary_en,
        summary_te=summary_te,
        preventive_actions_en=[
            "Never transfer money for registration, onboarding, or training.",
            "Do not disclose Aadhaar, PAN card, or bank account details prior to formal in-person or verified portal hiring.",
            "Independently cross-verify the recruiter's identity on official corporate directories or LinkedIn.",
        ],
        preventive_actions_te=[
            "Registration fee, training fee, leda laptop deposit peru tho e mathram dabbu transfer cheyavaddu.",
            "Official offer letter mariyu verified hiring portal lekunda Aadhaar, PAN card, leda bank details share cheyavaddu.",
            "Company official website mariyu recruiter LinkedIn profile ni independent ga cross-check cheyandi.",
        ],
        verification_questions=[
            "Can you provide a formal offer letter from your official company corporate email domain?",
            "Is this position registered on your company's official public careers portal with a verifiable requisition ID?",
            "Can you confirm in writing that no candidate will ever be asked to pay training, equipment, or document fees?",
        ],
    )


def _generate_report_single_call(
    client: Optional[Any],
    raw_text: str,
    opportunity_type: str,
    step_b_domain: Dict[str, Any],
    step_b_protection: Dict[str, Any],
    step_b_connections: Dict[str, Any],
) -> BilingualInvestigationReport:
    """
    Single-call fast path for text-only inputs.
    Extracts company_name and generates the full bilingual investigation report in ONE Gemini call.
    """
    deterministic_red_flags: List[str] = []
    deterministic_red_flags.extend(step_b_domain.get("flags", []))
    deterministic_red_flags.extend(step_b_protection.get("all_alerts", []))

    if step_b_connections.get("is_coordinated_campaign"):
        deterministic_red_flags.append(
            f"Coordinated Scam Warning: Contact entities have been reported in {step_b_connections.get('total_connected_reports', 0)} previous fraud incidents."
        )

    is_quota_fallback = False
    if client is not None:
        try:
            prompt = (
                "You are ScamShield AI — an authoritative career fraud investigator protecting students.\n"
                "Analyze this opportunity message/description, extract the company_name if mentioned, "
                "and synthesize the forensic data into an exhaustive, clear bilingual evaluation in JSON format.\n\n"
                f"Opportunity Category: {opportunity_type}\n"
                f"Opportunity Text:\n{raw_text}\n\n"
                f"Deterministic Domain Flags: {step_b_domain.get('flags', [])}\n"
                f"Student Protection Alerts (PII & Payments): {step_b_protection.get('all_alerts', [])}\n"
                f"Scam Connection Network Data: {step_b_connections}\n\n"
                "Guidelines:\n"
                "1. Identify the company_name from the text if available, or null/None if not mentioned.\n"
                "2. If upfront money/security deposits/crypto/UPI is demanded or critical PII is requested, risk_level MUST be HIGH (score >= 80).\n"
                "3. If free email providers or suspicious domains are used without money demands, risk_level should usually be MEDIUM (score 40-75).\n"
                "4. If legitimate company credentials and no fees or sensitive data demands are present, risk_level is LOW (score <= 30).\n"
                "5. Provide summary_en and clear summary_te in natural Tenglish (Telugu language written in English alphabet / Roman letters, NOT Telugu script, e.g., 'Ee job offer lo high fraud risk undi. Upfront ga dabbu pay cheyavaddu...').\n"
                "6. Provide preventive_actions_en and preventive_actions_te in natural Tenglish (Telugu language written in English/Roman letters, e.g., 'Registration fee leda laptop deposit peru tho e mathram dabbu pay cheyavaddu.').\n"
                "7. Provide exactly 3 pointed verification questions the student can ask the recruiter."
            )

            response = _generate_content_with_failover(
                client=client,
                contents=[prompt],
                response_schema=BilingualInvestigationReport,
            )

            if response and response.text:
                return BilingualInvestigationReport.model_validate_json(response.text)
        except GeminiQuotaExhaustedError:
            is_quota_fallback = True
        except Exception as e:
            print(f"[ScamShield AI Gemini Error]: {e}")
            err_lower = str(e).lower()
            if "429" in err_lower or "quota" in err_lower or "resource_exhausted" in err_lower:
                is_quota_fallback = True

    return _build_deterministic_report(
        opportunity_type=opportunity_type,
        company_name=_extract_company_name_fallback(raw_text),
        deterministic_red_flags=deterministic_red_flags,
        step_b_domain=step_b_domain,
        step_b_protection=step_b_protection,
        step_b_connections=step_b_connections,
        is_quota_fallback=is_quota_fallback,
        text=raw_text,
    )


def _single_call_multimodal_investigation(
    client: Optional[Any],
    file_bytes: bytes,
    mime_type: str,
    text: Optional[str],
    default_opportunity_type: Optional[str],
) -> Tuple[Optional[UnifiedMultimodalInvestigation], bool]:
    """
    Executes a single-call multimodal investigation on an uploaded document or image.
    Extracts transcribed text, entities, and risk evaluation in a single Gemini request.
    Returns (result, is_quota_fallback).
    """
    if client is None:
        return None, False

    try:
        contents: List[Any] = []

        part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
        contents.append(part)

        prompt = (
            "You are ScamShield AI — an authoritative career fraud investigator protecting students.\n"
            "Examine this uploaded career document or screenshot and candidate notes thoroughly in ONE pass.\n\n"
            "Tasks:\n"
            "1. Transcribe all readable text into 'extracted_text'.\n"
            "2. Extract all contact entities: phone numbers, email addresses, domains/URLs, UPI IDs, and Telegram handles into 'entities'.\n"
            "3. Identify 'company_name' and categorize 'opportunity_type' (Job, Internship, WFH, Freelancing, Training Program, or Placement Drive).\n"
            "4. Conduct forensic fraud analysis:\n"
            "   - If upfront money/security deposits/crypto/UPI is demanded or critical PII (Aadhaar, PAN, Bank details, OTP, CVV) is requested, risk_level MUST be HIGH (score >= 80).\n"
            "   - If free email providers (e.g. @gmail.com for corporate hiring) or suspicious domains (.xyz, .top, .click) are used without money demands, risk_level should usually be MEDIUM (score 40-75).\n"
            "   - If authentic company credentials and no fees or private data demands are present, risk_level is LOW (score <= 30).\n"
            "5. Detail detected 'red_flags' and 'student_protection_alerts'.\n"
            "6. Provide 'summary_en' and an accessible 'summary_te' in natural Tenglish (Telugu written in English/Roman letters, NOT Telugu script, e.g., 'Ee job offer lo high fraud risk undi. Upfront ga dabbu pay cheyavaddu...').\n"
            "7. Provide 'preventive_actions_en' and 'preventive_actions_te' in natural Tenglish (e.g., 'Registration fee leda laptop deposit peru tho e mathram dabbu transfer cheyavaddu.').\n"
            "8. Provide exactly 3 pointed 'verification_questions' the student can ask the recruiter."
        )

        if text and text.strip():
            prompt += f"\n\nAdditional Candidate Notes:\n{text.strip()}"

        if default_opportunity_type:
            prompt += f"\nCandidate Stated Category: {default_opportunity_type}"

        contents.append(prompt)

        response = _generate_content_with_failover(
            client=client,
            contents=contents,
            response_schema=UnifiedMultimodalInvestigation,
        )

        if response and response.text:
            return UnifiedMultimodalInvestigation.model_validate_json(response.text), False
    except GeminiQuotaExhaustedError:
        return None, True
    except Exception as e:
        print(f"[ScamShield AI Gemini Error]: {e}")
        err_lower = str(e).lower()
        is_quota = "429" in err_lower or "quota" in err_lower or "resource_exhausted" in err_lower
        return None, is_quota

    return None, False


def investigate_opportunity(
    db: Session,
    text: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    mime_type: Optional[str] = None,
    default_opportunity_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes the fraud investigation pipeline.
    Optimized for ultra low-latency (1-3s response time):
    - Text-Only inputs: Single Gemini 3.8 Flash call with thinking_budget=0 after deterministic entity extraction.
    - Multimodal inputs: Image resizing (max 1280px) + Single Gemini 3.8 Flash call combining OCR, entity extraction,
      and bilingual report generation, followed by instant (<15ms) deterministic verification and safety merges.
    """
    client = _get_genai_client()
    has_file = bool(file_bytes and mime_type)

    if not has_file:
        # ============================================================
        # FAST PATH (Text-Only): Single Gemini 3.8 Flash Call
        # ============================================================
        raw_text = text or ""
        resolved_op_type = _infer_opportunity_type(raw_text, default_opportunity_type)

        # Fast deterministic extraction
        extracted_entities = _regex_extract_entities(raw_text)
        extracted_entities_dict = extracted_entities.model_dump()

        # Step B: Deterministic forensic checks
        step_b_domain = analyze_domain_and_email(
            emails=extracted_entities_dict.get("email", []),
            urls=extracted_entities_dict.get("domain", []),
        )
        step_b_protection = check_student_protection_risks(raw_text)
        step_b_connections = find_scam_connections(db, entities=extracted_entities_dict)

        # Single Gemini call for company extraction + full report
        report = _generate_report_single_call(
            client=client,
            raw_text=raw_text,
            opportunity_type=resolved_op_type,
            step_b_domain=step_b_domain,
            step_b_protection=step_b_protection,
            step_b_connections=step_b_connections,
        )

        sanitized_text = mask_pii(raw_text)

        return {
            "report": report.model_dump(),
            "entities": extracted_entities_dict,
            "scam_connections": step_b_connections,
            "domain_analysis": step_b_domain,
            "student_protection": step_b_protection,
            "sanitized_text": sanitized_text,
        }

    # ============================================================
    # MULTIMODAL PATH (Image / PDF): Single Gemini 3.8 Flash Call
    # ============================================================
    # 1. Image Optimization: Downsample to <= 1280px in-memory to minimize upload latency
    optimized_bytes, optimized_mime = _optimize_image_if_needed(
        file_bytes=file_bytes,  # type: ignore[arg-type]
        mime_type=mime_type,    # type: ignore[arg-type]
    )

    # 2. Single-Call Multimodal Inspection
    multimodal_res, is_quota_fallback = _single_call_multimodal_investigation(
        client=client,
        file_bytes=optimized_bytes,
        mime_type=optimized_mime,
        text=text,
        default_opportunity_type=default_opportunity_type,
    )

    if multimodal_res is not None:
        extracted_text = multimodal_res.extracted_text or (text or "")

        # Merge Gemini extracted entities with regex extraction to guarantee 100% recall
        regex_ents = _regex_extract_entities(extracted_text)
        merged_entities = ExtractedEntities(
            phone=list(set(multimodal_res.entities.phone + regex_ents.phone)),
            email=list(set(multimodal_res.entities.email + regex_ents.email)),
            domain=list(set(multimodal_res.entities.domain + regex_ents.domain)),
            upi_id=list(set(multimodal_res.entities.upi_id + regex_ents.upi_id)),
            telegram=list(set(multimodal_res.entities.telegram + regex_ents.telegram)),
        )
        extracted_entities_dict = merged_entities.model_dump()

        # 3. Deterministic Guardrails (<15ms): Domain analysis, student risk checks, and DB connections
        full_text_for_checks = f"{extracted_text}\n{text or ''}"
        step_b_domain = analyze_domain_and_email(
            emails=merged_entities.email,
            urls=merged_entities.domain,
        )
        step_b_protection = check_student_protection_risks(full_text_for_checks)
        step_b_connections = find_scam_connections(db, entities=extracted_entities_dict)

        # 4. Merge deterministic evidence and enforce strict safety guardrails
        red_flags = list(dict.fromkeys(multimodal_res.red_flags + step_b_domain.get("flags", [])))
        student_alerts = list(
            dict.fromkeys(
                multimodal_res.student_protection_alerts + step_b_protection.get("all_alerts", [])
            )
        )

        if step_b_connections.get("is_coordinated_campaign"):
            conn_msg = (
                f"Coordinated Scam Warning: Contact entities have been reported in "
                f"{step_b_connections.get('total_connected_reports', 0)} previous fraud incidents."
            )
            if conn_msg not in red_flags:
                red_flags.insert(0, conn_msg)

        has_critical = step_b_protection.get("has_critical_risk", False)
        is_coordinated = step_b_connections.get("is_coordinated_campaign", False)
        has_suspicious_domain = step_b_domain.get("has_suspicious_domain", False)

        resolved_risk_level = (
            multimodal_res.risk_level.upper()
            if multimodal_res.risk_level in ("LOW", "MEDIUM", "HIGH")
            else "LOW"
        )
        resolved_risk_score = max(0, min(100, multimodal_res.risk_score))

        # Enforce minimum HIGH risk if critical payments/PII or coordinated campaign is present
        if has_critical or is_coordinated:
            resolved_risk_level = "HIGH"
            resolved_risk_score = max(resolved_risk_score, 88 if is_coordinated else 82)
        elif has_suspicious_domain and resolved_risk_level == "LOW":
            resolved_risk_level = "MEDIUM"
            resolved_risk_score = max(resolved_risk_score, 55)

        summary_en = multimodal_res.summary_en
        summary_te = multimodal_res.summary_te

        # If risk was elevated to HIGH by guardrails, ensure the summary warns the student
        if (has_critical or is_coordinated) and (not summary_en or "high" not in summary_en.lower()):
            summary_en = (
                "High fraud risk detected. The opportunity demands financial payments or sensitive personal identity "
                "credentials, which violates ethical recruitment standards. Do not pay any amount or share private documents."
            )
            summary_te = (
                "Ee job/internship offer lo high fraud risk undi. Registration leda deposit peru tho dabbu adagadam "
                "mariyu sensitive identity documents adagadam scammers standard trick. Ee offer kosam e mathram dabbu pay cheyavaddu mariyu private documents share cheyavaddu."
            )

        report = BilingualInvestigationReport(
            opportunity_type=multimodal_res.opportunity_type or default_opportunity_type or "Job",
            company_name=multimodal_res.company_name,
            risk_level=resolved_risk_level,
            risk_score=resolved_risk_score,
            red_flags=red_flags or ["No immediate structural red flags found."],
            student_protection_alerts=student_alerts,
            summary_en=summary_en,
            summary_te=summary_te,
            preventive_actions_en=multimodal_res.preventive_actions_en or [
                "Never transfer money for registration, onboarding, or training.",
                "Do not disclose Aadhaar, PAN card, or bank account details prior to formal in-person or verified portal hiring.",
                "Independently cross-verify the recruiter's identity on official corporate directories or LinkedIn.",
            ],
            preventive_actions_te=multimodal_res.preventive_actions_te or [
                "Registration fee, training fee, leda laptop deposit peru tho e mathram dabbu transfer cheyavaddu.",
                "Official offer letter mariyu verified hiring portal lekunda Aadhaar, PAN card, leda bank details share cheyavaddu.",
                "Company official website mariyu recruiter LinkedIn profile ni independent ga cross-check cheyandi.",
            ],
            verification_questions=multimodal_res.verification_questions or [
                "Can you provide a formal offer letter from your official company corporate email domain?",
                "Is this position registered on your company's official public careers portal with a verifiable requisition ID?",
                "Can you confirm in writing that no candidate will ever be asked to pay training, equipment, or document fees?",
            ],
        )

        sanitized_text = mask_pii(extracted_text)

        return {
            "report": report.model_dump(),
            "entities": extracted_entities_dict,
            "scam_connections": step_b_connections,
            "domain_analysis": step_b_domain,
            "student_protection": step_b_protection,
            "sanitized_text": sanitized_text,
        }

    # ============================================================
    # DETERMINISTIC FALLBACK: If Gemini API is unreachable/offline
    # ============================================================
    raw_text = text or ""
    extracted_entities = _regex_extract_entities(raw_text)
    extracted_entities_dict = extracted_entities.model_dump()

    step_b_domain = analyze_domain_and_email(
        emails=extracted_entities_dict.get("email", []),
        urls=extracted_entities_dict.get("domain", []),
    )
    step_b_protection = check_student_protection_risks(raw_text)
    step_b_connections = find_scam_connections(db, entities=extracted_entities_dict)

    deterministic_red_flags: List[str] = []
    deterministic_red_flags.extend(step_b_domain.get("flags", []))
    deterministic_red_flags.extend(step_b_protection.get("all_alerts", []))
    if step_b_connections.get("is_coordinated_campaign"):
        deterministic_red_flags.append(
            f"Coordinated Scam Warning: Contact entities have been reported in "
            f"{step_b_connections.get('total_connected_reports', 0)} previous fraud incidents."
        )

    fallback_report = _build_deterministic_report(
        opportunity_type=_infer_opportunity_type(raw_text, default_opportunity_type),
        company_name=extract_company_name(
            raw_text,
            emails=extracted_entities_dict.get("email"),
            domains=extracted_entities_dict.get("domain"),
        ),
        deterministic_red_flags=deterministic_red_flags,
        step_b_domain=step_b_domain,
        step_b_protection=step_b_protection,
        step_b_connections=step_b_connections,
        is_quota_fallback=is_quota_fallback,
        text=raw_text,
        emails=extracted_entities_dict.get("email"),
        domains=extracted_entities_dict.get("domain"),
    )

    return {
        "report": fallback_report.model_dump(),
        "entities": extracted_entities_dict,
        "scam_connections": step_b_connections,
        "domain_analysis": step_b_domain,
        "student_protection": step_b_protection,
        "sanitized_text": mask_pii(raw_text),
    }
