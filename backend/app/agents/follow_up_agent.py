import json
import re
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

from app.models.scam_models import OpportunityReport
from app.services.verification_service import check_student_protection_risks
from app.agents.investigation_agent import (
    _get_genai_client,
    _generate_content_with_failover,
    GeminiQuotaExhaustedError,
)

CASUAL_GREETINGS = {
    "hi", "hello", "hey", "hola", "namaste", "namaskaram", "vanakkam", "yo", "sup",
    "good morning", "good afternoon", "good evening", "gm", "ge", "gn",
}
CASUAL_THANKS = {
    "thanks", "thank you", "thx", "tq", "thank u", "many thanks", "thanks a lot",
    "thank you so much", "dhanyavadalu", "chala thanks", "thnx",
}
CASUAL_ACKS = {
    "ok", "okay", "k", "kk", "got it", "cool", "super", "nice", "awesome", "great",
    "fine", "alright", "all right", "bye", "goodbye", "see you", "see ya", "cya",
    "understood", "sure", "done", "perfect", "clear",
}


class FollowUpResponse(BaseModel):
    message_intent: Literal["CASUAL_CHAT", "STUDENT_QUESTION", "RECRUITER_REPLY"] = Field(
        description="Intent of the message: 'CASUAL_CHAT' for casual greetings/acknowledgments/thank-you, 'STUDENT_QUESTION' if the student is directly asking a question or seeking career/safety guidance, or 'RECRUITER_REPLY' if the student pasted a message or email from a recruiter."
    )
    matched_question: Optional[str] = Field(
        default=None,
        description="Only for RECRUITER_REPLY: identifies which verification question the recruiter reply answers (e.g. 'Q1: Corporate Domain Email Verification', 'Q2: Public Careers Portal Requisition', 'Q3: Zero-Fee Confirmation', or 'Dodged verification questions / General inquiry'). MUST be null for STUDENT_QUESTION and CASUAL_CHAT.",
    )
    verdict: Optional[str] = Field(
        default=None,
        description="Assessment verdict for RECRUITER_REPLY: exactly one of STILL_HIGH_RISK, SUSPICIOUS, or LOOKS_LEGIT. MUST be null for STUDENT_QUESTION and CASUAL_CHAT.",
    )
    analysis: str = Field(
        description="Detailed explanation for the student. For STUDENT_QUESTION: friendly, clear, supportive career/safety advice answering their question. For RECRUITER_REPLY: forensic evaluation of the recruiter's reply. Written in natural Tenglish (Telugu in Latin alphabet) if language is 'te', or English if 'en'."
    )
    suggested_reply: Optional[str] = Field(
        default=None,
        description="For RECRUITER_REPLY: concise professional response to send back to recruiter (or DO NOT REPLY warning if high risk). For STUDENT_QUESTION: optional professional email/message template if helpful, otherwise null. ALWAYS in polite, professional English.",
    )


def _check_casual_chat(clean_message: str, language: str) -> Optional[Dict[str, Any]]:
    """
    Fast-path (<10ms, zero Gemini API calls) for casual greetings, thank-you messages, and acknowledgments.
    """
    normalized = re.sub(r"[^\w\s]", "", clean_message.lower()).strip()
    if not normalized:
        return None

    words = [w for w in normalized.split() if w not in ("sir", "bro", "team", "bot", "there", "scamshield")]
    core = " ".join(words) if words else normalized

    # Check short messages starting with "thank you" or "thanks for" (under 50 chars, no URLs/emails/UPI/money terms)
    is_short_thanks_prefix = False
    if len(clean_message) < 50 and (normalized.startswith("thank you") or normalized.startswith("thanks for") or normalized.startswith("thanks")):
        has_suspicious_patterns = bool(
            re.search(
                r"(?:https?://|www\.|\.[a-z]{2,}/|@[\w\.-]+|upi|gpay|phonepe|paytm|₹|rs\.?|inr|fee|deposit|payment|charge|transfer)",
                clean_message,
                re.I,
            )
        )
        if not has_suspicious_patterns:
            is_short_thanks_prefix = True

    is_greeting = normalized in CASUAL_GREETINGS or core in CASUAL_GREETINGS
    is_thanks_or_ack = (
        normalized in CASUAL_THANKS
        or core in CASUAL_THANKS
        or normalized in CASUAL_ACKS
        or core in CASUAL_ACKS
        or is_short_thanks_prefix
    )

    if is_greeting:
        if language == "te":
            text = "Hello bro! Recruiter nunchi emaina message vachinda? Ikkada paste cheyyandi leda meeku unna doubts adagandi."
        else:
            text = "Hello! How can I help you? Feel free to paste any message from a recruiter or ask any questions about your offer."
        return {
            "message_intent": "CASUAL_CHAT",
            "matched_question": None,
            "verdict": None,
            "analysis": text,
            "suggested_reply": None,
            "has_critical_risk": False,
        }

    if is_thanks_or_ack:
        if language == "te":
            text = "Welcome bro! Inkoka recruiter message vasthe ikkada paste cheyyandi, leda emaina doubt unte adagandi."
        else:
            text = "You're welcome! Feel free to paste any new recruiter message or ask if you have another question."
        return {
            "message_intent": "CASUAL_CHAT",
            "matched_question": None,
            "verdict": None,
            "analysis": text,
            "suggested_reply": None,
            "has_critical_risk": False,
        }

    return None


def _is_student_question(msg: str) -> bool:
    lowered = msg.lower().strip()
    if lowered.endswith("?"):
        return True
    return bool(
        re.search(
            r"\b(should i|can i|could i|what if|how do|how to|what happens|is it safe|is this safe|why|where|how|what do you think|do you think)\b",
            lowered,
        )
    )


def _match_verification_question(
    user_message: str,
    verification_questions: Optional[List[str]],
) -> Optional[str]:
    if not verification_questions:
        return "General Inquiry / Recruiter Reply"
    msg_lower = (user_message or "").lower()
    for idx, q in enumerate(verification_questions):
        q_lower = q.lower()
        if any(term in msg_lower for term in ("domain", "corporate email", "official email", "company email", "@", "mailbox", "corporate domain")) and any(term in q_lower for term in ("domain", "email")):
            return f"Q{idx + 1}: Corporate Domain Email Verification"
        if any(term in msg_lower for term in ("portal", "requisition", "careers", "job id", "req id", "career page", "website link")) and any(term in q_lower for term in ("portal", "requisition", "careers")):
            return f"Q{idx + 1}: Public Portal Requisition Verification"
        if any(term in msg_lower for term in ("fee", "charge", "deposit", "payment", "free", "zero", "₹0", "cost", "free of charge", "no money")) and any(term in q_lower for term in ("fee", "payment", "deposit", "charge", "cost")):
            return f"Q{idx + 1}: Zero-Fee & Safety Confirmation"
    return "Dodged verification questions / General inquiry"


def _deterministic_followup_fallback(
    report: OpportunityReport,
    user_message: str,
    language: str,
    protection_risks: Dict[str, Any],
    verification_questions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Deterministic fallback when Gemini API is unconfigured, rate-limited, or unavailable.
    Prioritizes student safety by checking upfront payment demands, sensitive data requests,
    and classifying student questions vs recruiter responses.
    """
    has_critical = protection_risks.get("has_critical_risk", False)
    alerts = protection_risks.get("all_alerts", [])

    # Check if student is asking a direct question
    if not has_critical and _is_student_question(user_message):
        if language == "te":
            analysis = (
                f"Meeru adigina question gurinchi: Ee opportunity baseline risk level '{report.risk_level}'. "
                "Elanti upfront payment, laptop deposit, leda registration fee adigithe asalu chellinchakandi. "
                "Company official public careers portal leda verified corporate domain email nunchi confirmation unte matrame interview attend avvandi."
            )
        else:
            analysis = (
                f"Regarding your inquiry: This opportunity currently carries a '{report.risk_level}' risk profile. "
                "Never pay any upfront registration, laptop deposit, or processing fee. "
                "Ensure all communication is confirmed through the employer's official public careers portal or corporate domain before sharing sensitive information."
            )
        return {
            "message_intent": "STUDENT_QUESTION",
            "matched_question": None,
            "verdict": None,
            "analysis": analysis,
            "suggested_reply": None,
            "has_critical_risk": False,
        }

    matched_q = _match_verification_question(user_message, verification_questions)

    if has_critical:
        verdict = "STILL_HIGH_RISK"
        if language == "te":
            alert_text = f" ({', '.join(alerts)})" if alerts else ""
            analysis = (
                f"Recruiter message lo critical fraud indicators detect ayyayi{alert_text}. "
                "Registration fee, security deposit, laptop deposit leda OTP/Aadhaar adagadam unethical scam tactic. "
                "Ee recruiter ki elanti dabbu transfer cheyavaddu mariyu private documents share cheyavaddu."
            )
        else:
            alert_text = f" ({', '.join(alerts)})" if alerts else ""
            analysis = (
                f"Critical recruitment fraud indicators detected in recruiter's reply{alert_text}. "
                "Demanding upfront fees, security deposits, or personal documents (Aadhaar/PAN/OTP) violates recruitment ethics. "
                "Legitimate employers never demand financial commitments before hiring."
            )
        suggested_reply = (
            "DO NOT REPLY: Block and report this recruiter immediately. Do not transfer funds or disclose private documents."
        )
    elif report.risk_level == "HIGH":
        lowered_msg = (user_message or "").lower()
        has_disclaimer = any(
            phrase in lowered_msg
            for phrase in (
                "never ask", "never charge", "do not ask", "don't ask",
                "do not charge", "don't charge", "no registration", "no fee",
                "zero fee", "not required", "no need"
            )
        )
        if has_disclaimer:
            is_verified_detail = any(
                k in lowered_msg for k in ("official", "portal", "careers", "requisition", "website", "interview", "scheduled")
            )
            verdict = "LOOKS_LEGIT" if is_verified_detail else "SUSPICIOUS"
            if verdict == "LOOKS_LEGIT":
                if language == "te":
                    analysis = (
                        "Recruiter fee leda Aadhaar/OTP adagamu ani clear ga clarify chesaru mariyu official details provide chesaru. "
                        "Ee response legitimate ga kanipisthondi. Standard corporate recruitment process follow avvandi."
                    )
                else:
                    analysis = (
                        "The recruiter explicitly states that they never charge fees or request sensitive PII and provided verifiable official details. The response appears legitimate."
                    )
                suggested_reply = (
                    "Thank you for confirming that no fees or sensitive documents are required. I look forward to proceeding with the formal evaluation process."
                )
            else:
                if language == "te":
                    analysis = (
                        "Recruiter fee teesukomu ani chepparu, kani initial offer high risk lo unde. "
                        "Company official careers portal lo ee requisition ID ni independent ga cross-check chesukondi."
                    )
                else:
                    analysis = (
                        "The recruiter states they do not charge fees or request sensitive data. However, the initial opportunity carried high risk indicators. Independently confirm this opening on the employer's official careers portal."
                    )
                suggested_reply = (
                    "Thank you for confirming that no fees or sensitive documents are required. Could you please provide the official job requisition link on your public careers portal?"
                )
        else:
            verdict = "STILL_HIGH_RISK"
            if language == "te":
                analysis = (
                    "Recruiter previous high-risk issues ni clear ga clarify cheyaledu. "
                    "Inka fraud risk undi. Upfront payments leda confidential documents share cheyavaddu."
                )
            else:
                analysis = (
                    "The recruiter's response failed to resolve previous high-risk fraudulent indicators. "
                    "Proceeding is not advised. Do not disclose confidential information or advance funds."
                )
            suggested_reply = (
                "DO NOT REPLY: Block and report this recruiter immediately. Do not transfer funds or disclose private documents."
            )
    elif report.risk_level == "MEDIUM":
        verdict = "SUSPICIOUS"
        if language == "te":
            analysis = (
                "Recruiter ichina reply lo inka ambiguity undi. Official company domain email leda clear requisition link ivvaledu. "
                "Official website lo ee opportunity ni confirm chesukune varaku munduku velloddu."
            )
        else:
            analysis = (
                "The recruiter's response remains ambiguous. They have not yet provided verifiable company domain credentials or an official public careers requisition ID. Proceed with caution."
            )
        suggested_reply = (
            "Thank you for the update. Could you please send this formal communication from your official company domain email address, along with the job requisition ID listed on your public careers portal?"
        )
    else:
        verdict = "LOOKS_LEGIT"
        if language == "te":
            analysis = (
                "Recruiter reply lo upfront payments leda sensitive data demands kanipinchaledu. "
                "Normal hiring process laage undi. Ayina sare offer letter and interview schedule official portal lo check cheyandi."
            )
        else:
            analysis = (
                "No critical red flags or payment demands were found in the recruiter's message. The response follows normal recruitment conventions. Continue standard verification during interviews."
            )
        suggested_reply = (
            "Thank you for the clarification. I have reviewed the details and look forward to proceeding with the formal evaluation process."
        )

    return {
        "message_intent": "RECRUITER_REPLY",
        "matched_question": matched_q,
        "verdict": verdict,
        "analysis": analysis,
        "suggested_reply": suggested_reply,
        "has_critical_risk": has_critical,
    }


def analyze_follow_up(
    report: OpportunityReport,
    user_message: str,
    language: str = "en",
    verification_questions: Optional[List[str]] = None,
    chat_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Analyzes student follow-ups, questions, or pasted recruiter responses:
    1. Instant casual chat fast-path (<10ms, 0 Gemini calls) for greetings and thank-yous.
    2. Scans user_message with deterministic check_student_protection_risks() for immediate payment/PII threats.
    3. Runs Gemini failover chain with intent classification (STUDENT_QUESTION vs RECRUITER_REPLY).
    4. Matches recruiter response against verification questions and enforces natural Tenglish when language == 'te'.
    5. Falls back to deterministic student protection rules if API is unavailable or exhausted.
    """
    clean_message = (user_message or "").strip()
    clean_lang = "te" if language == "te" else "en"

    # Step 1: Instant Fast-Path for Casual Greetings, Thank-Yous, and Acknowledgments (<10ms)
    casual_chat_res = _check_casual_chat(clean_message, clean_lang)
    if casual_chat_res is not None:
        return casual_chat_res

    # Step 2: Deterministic student protection scan on the new message
    protection_risks = check_student_protection_risks(clean_message)
    has_critical = protection_risks.get("has_critical_risk", False)

    # Format verification questions
    q_lines: List[str] = []
    for idx, q in enumerate(verification_questions or []):
        q_lines.append(f"- Q{idx + 1}: {q}")
    formatted_questions = "\n".join(q_lines) if q_lines else "None specified."

    # Format chat history for context
    history_lines: List[str] = []
    for item in (chat_history or []):
        sender = item.get("role") or item.get("sender") or "User"
        content = item.get("content") or item.get("message") or item.get("text") or ""
        if content:
            history_lines.append(f"- {sender.capitalize()}: {content}")
    formatted_history = "\n".join(history_lines) if history_lines else "None (first follow-up question)."

    # Step 3: Gemini AI Analysis with failover and intent classification
    client = _get_genai_client()
    if client is not None:
        try:
            prompt = (
                "You are ScamShield AI — an authoritative career fraud investigator and supportive career safety advisor protecting students.\n"
                "A student has either asked a question, sought guidance, or pasted a recruiter's response regarding a previously investigated opportunity.\n\n"
                "ORIGINAL OPPORTUNITY CONTEXT:\n"
                f"- Company: {report.company_name or 'Unverified Employer'}\n"
                f"- Category: {report.opportunity_type}\n"
                f"- Baseline Risk Level: {report.risk_level} (Score: {report.risk_score}/100)\n"
                f"- Identified Red Flags: {report.red_flags}\n\n"
                "VERIFICATION QUESTIONS SENT BY STUDENT TO RECRUITER:\n"
                f"{formatted_questions}\n\n"
                "STUDENT PROTECTION SCAN (Current Message):\n"
                f"- Critical Payment/PII Threats: {has_critical}\n"
                f"- Detected Alerts: {protection_risks.get('all_alerts', [])}\n\n"
                f"CONVERSATION HISTORY:\n{formatted_history}\n\n"
                f"NEW MESSAGE TO EVALUATE:\n\"\"\"{clean_message}\"\"\"\n\n"
                "GUIDELINES FOR INTENT CLASSIFICATION AND RESPONSE:\n"
                "1. INTENT 'STUDENT_QUESTION':\n"
                "   - If the student is asking a direct question, seeking advice, or asking what they should do next (e.g. 'Should I share my resume?', 'What happens if they call me?', 'How do I check their CIN number?', 'Is 15000 stipend normal for this role?'):\n"
                "     * Set message_intent = 'STUDENT_QUESTION'.\n"
                "     * Respond warmly, helpfully, and authoritatively like a supportive senior AI safety mentor and career advisor in 'analysis'.\n"
                "     * Set matched_question = null and verdict = null.\n"
                "     * Only include 'suggested_reply' if an email/message template to send to the employer is genuinely helpful for their specific question; otherwise set suggested_reply = null.\n\n"
                "2. INTENT 'RECRUITER_REPLY':\n"
                "   - If the student pasted a recruiter's email, message, WhatsApp chat, or offer clarification:\n"
                "     * Set message_intent = 'RECRUITER_REPLY'.\n"
                "     * Identify which verification question the recruiter is answering (e.g. 'Q1: Corporate Domain Email Verification', 'Q2: Public Careers Portal Requisition', 'Q3: Zero-Fee Confirmation', or 'Dodged verification questions / General inquiry') and set 'matched_question'.\n"
                "     * If recruiter explicitly states they 'never ask for' fees or Aadhaar/OTP and provides verifiable official details (such as official corporate portal link or requisition ID) without demanding payment or sensitive data, evaluate it fairly as LOOKS_LEGIT.\n"
                "     * If recruiter demands any money (registration, security deposit, training fee, laptop deposit, processing fee, UPI transfer) or requests sensitive credentials (Aadhaar, PAN, OTP, Bank details), verdict MUST be 'STILL_HIGH_RISK'.\n"
                "     * If recruiter uses free emails (gmail/yahoo), avoids answering direct questions, or redirects to Telegram/WhatsApp without official verification, verdict should be 'SUSPICIOUS' or 'STILL_HIGH_RISK'.\n"
                "     * If transparent, verifiable corporate credentials with NO fee demands, verdict should be 'LOOKS_LEGIT'.\n"
                "     * 'suggested_reply' MUST be provided in polite, professional English (or DO NOT REPLY warning if STILL_HIGH_RISK).\n\n"
                "3. INTENT 'CASUAL_CHAT':\n"
                "   - If the student sent a casual greeting, acknowledgment, or thank you:\n"
                "     * Set message_intent = 'CASUAL_CHAT', matched_question = null, verdict = null, suggested_reply = null, and a warm friendly message in 'analysis'.\n\n"
                "4. LANGUAGE RULES:\n"
                + (
                    "   - When language is 'te', write 'analysis' in natural, fluent Tenglish (Telugu words written strictly using English/Roman alphabet, e.g. 'Meeru resume share cheyachu, kani OTP leda deposit lanti sensitive details ivvoddu...', DO NOT use Telugu Unicode script characters).\n"
                    if clean_lang == "te"
                    else "   - When language is 'en', write 'analysis' in clear, authoritative, student-friendly English.\n"
                )
                + "   - When 'suggested_reply' is provided, it MUST ALWAYS be written in polite, professional English (never Telugu or Tenglish) so the student can send it directly to the recruiter, OR if verdict is 'STILL_HIGH_RISK', provide a clear English warning directive (e.g., 'DO NOT REPLY: Block and report this recruiter immediately.')."
            )

            response = _generate_content_with_failover(
                client=client,
                contents=[prompt],
                response_schema=FollowUpResponse,
            )

            if response and response.text:
                res_obj = FollowUpResponse.model_validate_json(response.text)
                intent = res_obj.message_intent or "RECRUITER_REPLY"

                if intent in ("STUDENT_QUESTION", "CASUAL_CHAT"):
                    return {
                        "message_intent": intent,
                        "matched_question": None,
                        "verdict": None,
                        "analysis": res_obj.analysis,
                        "suggested_reply": res_obj.suggested_reply,
                        "has_critical_risk": has_critical,
                    }

                # Handling for RECRUITER_REPLY
                resolved_verdict = (res_obj.verdict or "SUSPICIOUS").upper().strip()
                if resolved_verdict not in ("STILL_HIGH_RISK", "SUSPICIOUS", "LOOKS_LEGIT"):
                    resolved_verdict = "STILL_HIGH_RISK" if has_critical else "SUSPICIOUS"

                # Enforce safety guardrail: if payment/PII demand was flagged, force STILL_HIGH_RISK
                if has_critical:
                    resolved_verdict = "STILL_HIGH_RISK"

                return {
                    "message_intent": "RECRUITER_REPLY",
                    "matched_question": res_obj.matched_question or _match_verification_question(clean_message, verification_questions),
                    "verdict": resolved_verdict,
                    "analysis": res_obj.analysis,
                    "suggested_reply": res_obj.suggested_reply,
                    "has_critical_risk": has_critical,
                }
        except GeminiQuotaExhaustedError:
            pass
        except Exception as e:
            print(f"[ScamShield AI Follow-Up Error]: {e}")

    # Step 4: Deterministic Fallback Engine
    return _deterministic_followup_fallback(
        report=report,
        user_message=clean_message,
        language=clean_lang,
        protection_risks=protection_risks,
        verification_questions=verification_questions,
    )
