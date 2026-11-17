import re
from typing import List, Dict, Any
import tldextract

FREE_EMAIL_PROVIDERS = {
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "proton.me",
    "protonmail.com",
    "yopmail.com",
    "mailinator.com",
}

SUSPICIOUS_TLDS = {
    "xyz",
    "top",
    "click",
    "tk",
    "buzz",
    "info",
    "site",
    "online",
    "live",
}

PII_KEYWORDS = [
    ("aadhaar", "Request for Aadhaar number or identity card"),
    ("pan card", "Request for PAN Card or tax identifier"),
    ("pan number", "Request for PAN number"),
    ("bank account", "Request for personal Bank Account number"),
    ("ifsc", "Request for Bank IFSC Code"),
    ("otp", "High Risk: Request to share One-Time Password (OTP)"),
    ("cvv", "Critical Risk: Request for Credit/Debit Card CVV"),
    ("atm pin", "Critical Risk: Request for ATM PIN or Banking PIN"),
    ("passport", "Request for Passport copy or details"),
]

PAYMENT_KEYWORDS = [
    ("registration fee", "Demand for upfront job/internship registration fee"),
    ("security deposit", "Demand for refundable/non-refundable security deposit"),
    ("training fee", "Demand for training or induction course payment"),
    ("processing fee", "Demand for document verification or processing fee"),
    ("laptop deposit", "Demand for equipment/laptop security deposit"),
    ("upi", "Unprofessional payment channel: Requested UPI transfer"),
    ("gpay", "Unprofessional payment channel: Requested Google Pay payment"),
    ("phonepe", "Unprofessional payment channel: Requested PhonePe payment"),
    ("paytm", "Unprofessional payment channel: Requested Paytm payment"),
]

NEGATION_PHRASES = [
    "zero ",
    "₹0",
    "rs 0",
    "rs. 0",
    "free of charge",
    "not required",
    "will not charge",
    "won't charge",
    "never charge",
    "never charges",
    "does not charge",
    "do not charge",
    "no registration",
    "no security",
    "no training",
    "no processing",
    "no fee",
    "no fees",
    "without any fee",
    "without fee",
    "zero fee",
    "zero fees",
    "never ask",
]


def _is_negated_payment_match(text: str, start_idx: int, end_idx: int) -> bool:
    """
    Checks if a payment keyword match is negated by disclaimer or negation phrases
    within its enclosing sentence, full line, or 80 characters preceding the match.
    """
    # Sentence boundary detection
    last_term = -1
    for punct in (".", "\n", "!", "?", ";", "|"):
        pos = text.rfind(punct, 0, start_idx)
        if pos > last_term:
            last_term = pos
    sentence_start = 0 if last_term == -1 else last_term + 1

    next_term = len(text)
    for punct in (".", "\n", "!", "?", ";", "|"):
        pos = text.find(punct, end_idx)
        if pos != -1 and pos < next_term:
            next_term = pos
    sentence = text[sentence_start:next_term]

    # Preceding context up to 80 characters before match
    window_before = text[max(0, start_idx - 80):start_idx]

    # Full line enclosing the match
    line_start = text.rfind("\n", 0, start_idx)
    line_start = 0 if line_start == -1 else line_start + 1
    line_end = text.find("\n", end_idx)
    line_end = len(text) if line_end == -1 else line_end
    full_line = text[line_start:line_end]

    for phrase in NEGATION_PHRASES:
        if phrase in sentence or phrase in window_before or phrase in full_line:
            return True
    return False

# Regex patterns for Indian identity numbers
AADHAAR_REGEX = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
PAN_REGEX = re.compile(r"\b[A-Za-z]{5}[0-9]{4}[A-Za-z]{1}\b")


def mask_pii(text: str) -> str:
    """
    Redacts 12-digit Aadhaar-like numbers and 10-character Indian PAN patterns
    from text before storage or logging.
    """
    if not text:
        return ""
    masked = AADHAAR_REGEX.sub("[REDACTED_AADHAAR]", text)
    masked = PAN_REGEX.sub("[REDACTED_PAN]", masked)
    return masked


def analyze_domain_and_email(emails: List[str], urls: List[str]) -> Dict[str, Any]:
    """
    Analyzes domains extracted from emails and URLs using tldextract.
    Flags free email providers used for hiring, suspicious TLDs, and hyphenated lookalike domains.
    """
    free_provider_warnings: List[str] = []
    suspicious_tld_warnings: List[str] = []
    hyphenated_domain_warnings: List[str] = []
    flags: List[str] = []

    # 1. Analyze emails
    for email in emails:
        if not email or "@" not in email:
            continue
        domain_part = email.split("@")[-1].strip().lower()
        if domain_part in FREE_EMAIL_PROVIDERS:
            warning = f"Recruiter contacting from public email service ({domain_part}) instead of verified corporate domain."
            free_provider_warnings.append(warning)
            flags.append(warning)

        extracted = tldextract.extract(domain_part)
        suffix = extracted.suffix.lower()
        if suffix in SUSPICIOUS_TLDS:
            warning = f"Email domain has high-risk / low-cost TLD (.{suffix}) frequently used in phishing scams."
            suspicious_tld_warnings.append(warning)
            flags.append(warning)

        if "-" in extracted.domain:
            warning = f"Email domain '{extracted.domain}.{suffix}' uses hyphens often characteristic of brand spoofing."
            hyphenated_domain_warnings.append(warning)
            flags.append(warning)

    # 2. Analyze URLs
    for url in urls:
        if not url:
            continue
        extracted = tldextract.extract(url)
        if not extracted.domain:
            continue

        full_domain = f"{extracted.domain}.{extracted.suffix}".lower()
        suffix = extracted.suffix.lower()

        if suffix in SUSPICIOUS_TLDS:
            warning = f"URL domain '{full_domain}' uses high-risk TLD (.{suffix})."
            suspicious_tld_warnings.append(warning)
            flags.append(warning)

        if "-" in extracted.domain:
            warning = f"URL domain '{full_domain}' contains hyphens indicative of typosquatting or brand impersonation."
            hyphenated_domain_warnings.append(warning)
            flags.append(warning)

    has_suspicious_domain = bool(
        free_provider_warnings or suspicious_tld_warnings or hyphenated_domain_warnings
    )

    return {
        "free_provider_warnings": list(set(free_provider_warnings)),
        "suspicious_tld_warnings": list(set(suspicious_tld_warnings)),
        "hyphenated_domain_warnings": list(set(hyphenated_domain_warnings)),
        "flags": list(dict.fromkeys(flags)),  # Deduplicated preserving order
        "has_suspicious_domain": has_suspicious_domain,
    }


def check_student_protection_risks(text: str) -> Dict[str, Any]:
    """
    Detects requests for sensitive PII and upfront payment/deposit demands.
    Returns alerts and critical risk status.
    """
    if not text:
        return {
            "pii_alerts": [],
            "payment_alerts": [],
            "has_critical_risk": False,
            "all_alerts": [],
        }

    lowered_text = text.lower()
    pii_alerts: List[str] = []
    payment_alerts: List[str] = []

    for keyword, description in PII_KEYWORDS:
        if keyword in lowered_text:
            pii_alerts.append(f"{description} ('{keyword}' mentioned)")

    for keyword, description in PAYMENT_KEYWORDS:
        # Check all occurrences of keyword; only flag if at least one occurrence is not negated
        start = 0
        has_unnegated = False
        while True:
            idx = lowered_text.find(keyword, start)
            if idx == -1:
                break
            end = idx + len(keyword)
            if not _is_negated_payment_match(lowered_text, idx, end):
                has_unnegated = True
                break
            start = end

        if has_unnegated:
            payment_alerts.append(f"{description} ('{keyword}' mentioned)")

    has_critical_risk = bool(pii_alerts or payment_alerts)

    return {
        "pii_alerts": pii_alerts,
        "payment_alerts": payment_alerts,
        "has_critical_risk": has_critical_risk,
        "all_alerts": pii_alerts + payment_alerts,
    }
