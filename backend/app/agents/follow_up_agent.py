import json
import re
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

from app.models.scam_models import OpportunityReport
from app.services.verification_service import check_student_protection_risks
from app.agents.investigation_agent import (
    _get_genai_client,
    _generate_content_with_failover,
    _optimize_image_if_needed,
    _is_model_in_cooldown,
    _mark_model_exhausted,
    GeminiQuotaExhaustedError,
    types,
)

CASUAL_GREETINGS = {
    "hi", "hello", "hey", "hola", "namaste", "namaskaram", "vanakkam", "yo", "sup",
    "good morning", "good afternoon", "good evening", "gm", "ge", "gn",
    "bagunnara", "ela unnaru", "namaste bro", "namaskaram bro", "hi bro", "hello bro",
}
CASUAL_THANKS = {
    "thanks", "thank you", "thx", "tq", "thank u", "many thanks", "thanks a lot",
    "thank you so much", "dhanyavadalu", "chala thanks", "chala dhanyavadalu", "thnx",
    "thanks bro", "tq bro",
}
CASUAL_ACKS = {
    "ok", "okay", "k", "kk", "got it", "cool", "super", "nice", "awesome", "great",
    "fine", "alright", "all right", "bye", "goodbye", "see you", "see ya", "cya",
    "understood", "sure", "done", "perfect", "clear",
    "ardham ayindi", "artham ayindi", "ardhamaindi", "arthamaindi", "ardhamayindi", "arthamayindi",
    "sare", "sare bro", "avunu", "avunu bro", "super bro", "cool bro", "nice bro",
    "alage", "alage bro", "pakka", "pakka bro", "done bro",
}

TENGLISH_CASUAL_TRIGGERS = {
    "ardham ayindi", "artham ayindi", "ardhamaindi", "arthamaindi", "ardhamayindi", "arthamayindi",
    "dhanyavadalu", "chala thanks", "chala dhanyavadalu", "sare", "sare bro",
    "avunu", "avunu bro", "super bro", "cool bro", "nice bro", "alage", "alage bro",
    "pakka", "pakka bro", "namaskaram", "namaste bro", "namaskaram bro", "bagunnara",
    "ela unnaru", "tq bro",
}


def _detect_tenglish(text: str) -> bool:
    """
    Detects if the user's message contains Tenglish words, conversational markers,
    or explicit language switch requests (e.g. 'explain in Tenglish', 'telugu lo cheppu').
    """
    if not text:
        return False
    lowered = text.lower()
    tenglish_patterns = [
        # Explicit language requests
        r"\b(tenglish|telugu\s*lo|telugu\s*lo\s*cheppu|tenglish\s*lo|explain\s*in\s*tenglish|telugulo)\b",
        # Common greetings & conversational markers
        r"\b(bro|bhayya|anna|cheppu|cheppandi|enti|entha|eppudu|ekkada|ela|enduku|em|emaina|emi|emiti)\b",
        r"\b(undhi|undi|unnaru|unnanu|ledu|ledhu|kadu|kaadu|avunu|kadha|kada|sare)\b",
        r"\b(dabbulu|dabbu|kattala|kattali|pay\s*cheyala|pay\s*cheyali|adagavu|aduguthunnaru|adagaru)\b",
        r"\b(vachindi|vachinda|vasthe|pampincharu|pampadu|chesaru|cheyandi|cheyyandi|cheyoddu|cheyavaddu)\b",
        r"\b(ardham|artham|ardhamaindi|arthamaindi|ardhamayindi|arthamayindi|ayindi|ayindhi|chala|nijama|nijame|pakka)\b",
        r"\b(meeku|naaku|naku|nenu|memu|manam|vallu|vaallu|ikkada|akkada|chudu|chudandi)\b",
        r"\b(dhanyavadalu|namaskaram|bagunnara|alage|ippudu|taruvatha|idi|idhi)\b",
    ]
    for pattern in tenglish_patterns:
        if re.search(pattern, lowered):
            return True
    return False


class FollowUpResponse(BaseModel):
    message_intent: Literal["CASUAL_CHAT", "STUDENT_QUESTION", "RECRUITER_REPLY"] = Field(
        description="Intent of the message: 'CASUAL_CHAT' for pure greetings/acknowledgments, 'STUDENT_QUESTION' if the user asks ANY question (identity, math, general knowledge, coding, career/safety advice), or 'RECRUITER_REPLY' strictly if the student pasted or quoted a recruiter message/email/reply."
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
        description="Detailed response for the student. For STUDENT_QUESTION: direct, accurate, friendly answer to their question (math, coding, identity, career guidance, etc.). For RECRUITER_REPLY: forensic evaluation of the recruiter's reply. Written in natural Tenglish (Telugu in Latin alphabet) if language is 'te', or English if 'en'."
    )
    suggested_reply: Optional[str] = Field(
        default=None,
        description="For RECRUITER_REPLY: concise professional response to send back to recruiter (or DO NOT REPLY warning if high risk). For STUDENT_QUESTION: optional professional email/message template if helpful, otherwise null. ALWAYS in polite, professional English.",
    )


def _check_casual_chat(clean_message: str, language: str) -> Optional[Dict[str, Any]]:
    """
    Fast-path (<10ms, zero Gemini API calls) for pure casual greetings, thank-you messages, and acknowledgments.
    Does NOT intercept questions (e.g., 'who are you', 'what is your name', math, coding, etc.).
    """
    # If there is a question mark, let Gemini or fallback answer naturally
    if "?" in clean_message:
        return None

    normalized = re.sub(r"[^\w\s]", "", clean_message.lower()).strip()
    if not normalized:
        return None

    # Don't intercept if message starts with question words
    if re.match(r"^(what|who|why|where|when|how|which|can|could|should|is|are|do|does|tell|explain|calculate)\b", normalized):
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

    is_te_param = str(language or "").strip().lower() in ("te", "tenglish")
    is_te_msg = (
        normalized in TENGLISH_CASUAL_TRIGGERS
        or core in TENGLISH_CASUAL_TRIGGERS
        or _detect_tenglish(clean_message)
    )
    reply_in_te = is_te_param or is_te_msg

    if is_greeting:
        if reply_in_te:
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
        if reply_in_te:
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
    if "?" in lowered:
        return True
    return bool(
        re.search(
            r"\b(should i|can i|could i|what if|how do|how to|what happens|is it safe|is this safe|why|where|how|what do you think|do you think|who are you|what is your name|who made you|what are you|tell me|explain|calculate|solve|write a|help me with|who is|what is)\b",
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
    file_bytes: Optional[bytes] = None,
    mime_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deterministic fallback when Gemini API is unconfigured, rate-limited, or unavailable.
    Prioritizes student safety by checking upfront payment demands, sensitive data requests,
    and classifying student questions vs recruiter responses.
    """
    has_critical = protection_risks.get("has_critical_risk", False)
    alerts = protection_risks.get("all_alerts", [])
    lowered_msg = (user_message or "").lower().strip()
    matched_q = _match_verification_question(user_message, verification_questions)
    is_te = str(language or "").strip().lower() in ("te", "tenglish") or _detect_tenglish(user_message or "")

    # If file was attached but Gemini unavailable
    if file_bytes:
        if is_te:
            analysis = (
                f"Meeru upload chesina document ({mime_type or 'attachment'}) ni record chesamu. "
                f"Ee opportunity baseline risk level '{report.risk_level}'. "
                "Document lo registration fee, laptop deposit, training fee leda Aadhaar/OTP demands unte reject cheyandi. "
                "Company official public portal lo verify chesukondi."
            )
        else:
            analysis = (
                f"An attached document ({mime_type or 'attachment'}) was received. "
                f"This opportunity currently holds a '{report.risk_level}' risk profile. "
                "Inspect the document carefully for upfront payment demands, unofficial email domains, or requests for sensitive PII (Aadhaar/PAN/OTP). "
                "Never advance funds prior to verified in-person or official portal hiring."
            )
        return {
            "message_intent": "RECRUITER_REPLY",
            "matched_question": matched_q,
            "verdict": "STILL_HIGH_RISK" if report.risk_level == "HIGH" else "SUSPICIOUS",
            "analysis": analysis,
            "suggested_reply": "Thank you for the document. Could you please confirm this position on your official company careers portal with a public requisition ID?",
            "has_critical_risk": has_critical,
        }

    # Check if student is asking a direct question (identity, guidance, general)
    if _is_student_question(user_message):
        # Identity / Name Question
        is_identity_q = bool(re.search(r"\b(name|who are you|who made you|what are you|your identity)\b", lowered_msg))
        if is_identity_q:
            if is_te:
                analysis = (
                    "Nenu ScamShield Assistant ni! Vidyarthulanu recruitment fraud mariyu job scams nunchi kapadadaniki, "
                    "mariyu me career doubts clarify cheyadaniki nenu unnanu. Meeku emaina doubts unna leda recruiter message unna ikkada adagandi!"
                )
            else:
                analysis = (
                    "I am ScamShield Assistant, your AI companion and career safety mentor! "
                    "I help protect students against job scams and recruitment fraud, while answering any career or verification questions. "
                    "Feel free to ask me anything or paste a recruiter's message to check."
                )
            return {
                "message_intent": "STUDENT_QUESTION",
                "matched_question": None,
                "verdict": None,
                "analysis": analysis,
                "suggested_reply": None,
                "has_critical_risk": False,
            }

        # Question inquiring about fee demands or sensitive credentials
        if any(k in lowered_msg for k in ("fee", "pay", "deposit", "money", "otp", "aadhaar", "pan", "bank")):
            if is_te:
                analysis = (
                    "Meeru adigina payment/sensitive data question gurinchi: "
                    "Asalu elanti registration fee, laptop deposit, training fee leda OTP/Aadhaar details share cheyavaddu! "
                    "Legitimate companies hiring mundu eppudu dabbulu adagavu. Ee offer lo fraud risk undi, jagrathaga undandi."
                )
            else:
                analysis = (
                    "Regarding your inquiry about payments or sensitive credentials: "
                    "Never pay any advance registration fee, laptop deposit, or processing charge, and never share OTPs or Aadhaar cards. "
                    "Legitimate employers never demand financial commitments before hiring. Proceed with extreme caution."
                )
            return {
                "message_intent": "STUDENT_QUESTION",
                "matched_question": None,
                "verdict": None,
                "analysis": analysis,
                "suggested_reply": None,
                "has_critical_risk": has_critical,
            }

        # General inquiry / Career guidance fallback
        if is_te:
            analysis = (
                f"Meeru adigina question gurinchi: Ee opportunity baseline risk level '{report.risk_level}'. "
                "Elanti upfront payment leda registration fee adigithe asalu chellinchakandi. "
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
        if is_te:
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
                if is_te:
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
                if is_te:
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
            if is_te:
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
        if is_te:
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
        if is_te:
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
    file_bytes: Optional[bytes] = None,
    mime_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyzes student follow-ups, general questions, or pasted recruiter responses/documents:
    1. Instant casual chat fast-path (<10ms, 0 Gemini calls) strictly for greetings, thank-yous, and acknowledgments (only when no file attached).
    2. Scans user_message with deterministic check_student_protection_risks() for immediate payment/PII threats.
    3. Prepares multimodal image/PDF parts if a file is uploaded.
    4. Runs Gemini failover chain with intelligent intent classification (STUDENT_QUESTION vs RECRUITER_REPLY).
       - STUDENT_QUESTION: handles identity, math, coding, general questions, and career/safety advice with verdict=null.
       - RECRUITER_REPLY: performs forensic verification and generates verdict + suggested reply.
    5. Matches recruiter response against verification questions and enforces natural Tenglish when language == 'te'.
    6. Falls back to deterministic student protection rules if API is unavailable or exhausted.
    """
    clean_message = (user_message or "").strip()
    is_te_param = str(language or "").strip().lower() in ("te", "tenglish")
    is_te_msg = _detect_tenglish(clean_message)
    user_wants_tenglish = is_te_param or is_te_msg
    clean_lang = "te" if user_wants_tenglish else "en"

    # Step 1: Instant Fast-Path strictly for Casual Greetings, Thank-Yous, and Acknowledgments (<10ms)
    # ONLY when NO file is attached and message is not a question
    if not file_bytes:
        casual_chat_res = _check_casual_chat(clean_message, clean_lang)
        if casual_chat_res is not None:
            return casual_chat_res

    if not clean_message and file_bytes:
        clean_message = "Please review and evaluate this attached recruiter document or screenshot."

    # Step 2: Deterministic student protection scan on the message
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

    # Step 3: Optimize Image or Prepare PDF Part
    file_part = None
    if file_bytes and mime_type:
        opt_bytes, opt_mime = _optimize_image_if_needed(file_bytes, mime_type)
        if types and hasattr(types, "Part"):
            try:
                file_part = types.Part.from_bytes(data=opt_bytes, mime_type=opt_mime)
            except Exception as e:
                print(f"[ScamShield AI Follow-Up File Part Error]: {e}")

    file_context = ""
    if file_bytes:
        file_context = (
            f"\nATTACHED FILE: An attached document or screenshot ({mime_type}) has been provided by the student. "
            "Carefully inspect all visible text, letters, seals, signatures, payment details, QR codes, or conversation history inside the file.\n"
            "Treat an attached document or screenshot as a recruiter-sent document/reply (intent 'RECRUITER_REPLY') unless the user explicitly asked a general knowledge question about it.\n"
        )

    # Step 4: Gemini AI Analysis with failover and intent classification
    client = _get_genai_client()
    if client is not None:
        try:
            prompt = (
                "You are ScamShield Assistant — an intelligent, versatile AI assistant and authoritative career safety mentor.\n"
                "A student is conversing with you. Below is the background context of an opportunity they previously evaluated:\n\n"
                "BACKGROUND EVALUATION CONTEXT (use this if the student asks about the job/company):\n"
                f"- Company: {report.company_name or 'Unverified Employer'}\n"
                f"- Category: {report.opportunity_type}\n"
                f"- Baseline Risk Level: {report.risk_level} (Score: {report.risk_score}/100)\n"
                f"- Identified Red Flags: {report.red_flags}\n\n"
                "VERIFICATION QUESTIONS SENT BY STUDENT TO RECRUITER:\n"
                f"{formatted_questions}\n\n"
                f"{file_context}"
                "STUDENT PROTECTION SCAN (Current Message):\n"
                f"- Critical Payment/PII Threats: {has_critical}\n"
                f"- Detected Alerts: {protection_risks.get('all_alerts', [])}\n\n"
                f"CONVERSATION HISTORY:\n{formatted_history}\n\n"
                f"NEW MESSAGE TO PROCESS:\n\"\"\"{clean_message}\"\"\"\n\n"
                "INSTRUCTIONS FOR INTENT CLASSIFICATION AND RESPONSE:\n\n"
                "1. INTENT 'STUDENT_QUESTION':\n"
                "   - Choose this when the user is asking ANY question or seeking knowledge, advice, or assistance:\n"
                "     * Identity/About you: 'What is your name?', 'Who are you?', 'Who made you?' -> Introduce yourself as 'ScamShield Assistant', a helpful AI safety & career companion.\n"
                "     * General Knowledge, Math, Coding, Science, History: 'What is 15 * 8?', 'Write Python code for binary search', 'Why is the sky blue?', etc. -> Answer directly, accurately, and smartly as a helpful AI assistant.\n"
                "     * Career & Offer Guidance: 'Should I send my resume?', 'Is 20k stipend good for Bangalore?', 'What happens if I reject?', 'What does this company do?' -> Answer helpfully and supportively, referencing the opportunity context if relevant.\n"
                "   - RULES FOR 'STUDENT_QUESTION':\n"
                "     * Set message_intent = 'STUDENT_QUESTION'.\n"
                "     * Set verdict = null and matched_question = null (DO NOT generate a forensic verdict for student questions!).\n"
                "     * Set suggested_reply = null (only provide a message template if the student explicitly asked for one to send to someone).\n"
                "     * Write your direct, helpful answer in 'analysis'.\n\n"
                "2. INTENT 'RECRUITER_REPLY':\n"
                "   - Choose this when the user attached an image/PDF document, or pasted/quoted an actual message, email, or WhatsApp communication from a recruiter or employer (e.g. 'Dear candidate...', 'Recruiter said: pay 500 for laptop deposit', 'Here is what they sent me: ...'):\n"
                "     * Set message_intent = 'RECRUITER_REPLY'.\n"
                "     * Identify which verification question the recruiter is answering (e.g. 'Q1: Corporate Domain Email Verification', 'Q2: Public Careers Portal Requisition', 'Q3: Zero-Fee Confirmation', or 'Dodged verification questions / General inquiry') and set 'matched_question'.\n"
                "     * Evaluate the recruiter's message or attached document:\n"
                "       - If recruiter explicitly states they 'never ask for' fees or Aadhaar/OTP and provides verifiable official details, evaluate fairly as LOOKS_LEGIT.\n"
                "       - If recruiter demands money (registration, security deposit, training fee, laptop deposit, processing fee, UPI transfer) or requests sensitive credentials (Aadhaar, PAN, OTP, Bank details), verdict MUST be 'STILL_HIGH_RISK'.\n"
                "       - If recruiter uses free emails (gmail/yahoo), avoids answering direct questions, or redirects to Telegram/WhatsApp without official verification, verdict should be 'SUSPICIOUS' or 'STILL_HIGH_RISK'.\n"
                "       - If transparent, verifiable corporate credentials with NO fee demands, verdict should be 'LOOKS_LEGIT'.\n"
                "     * Provide a clear forensic explanation in 'analysis'.\n"
                "     * 'suggested_reply' MUST be provided in polite, professional English (or DO NOT REPLY warning if STILL_HIGH_RISK).\n\n"
                "3. INTENT 'CASUAL_CHAT':\n"
                "   - If the user sent a casual greeting, acknowledgment, or thank you without a question (e.g. 'hi', 'thanks', 'cool'):\n"
                "     * Set message_intent = 'CASUAL_CHAT', matched_question = null, verdict = null, suggested_reply = null, and a warm friendly message in 'analysis'.\n\n"
                "4. DYNAMIC LANGUAGE MATCHING RULES (AUTOMATIC MIRRORING):\n"
                "   - AUTOMATICALLY MIRROR THE USER'S INPUT LANGUAGE for the 'analysis' field:\n"
                "     * If the user writes in Tenglish (Telugu written in Roman/English alphabet, e.g., 'Ee offer safe aa bro?', 'Dabbulu kattala?', 'Artham ayindi', 'Naku email vachindi'), OR explicitly requests Telugu/Tenglish (e.g., 'explain in Tenglish', 'telugu lo cheppu', 'Tenglish lo cheppandi'):\n"
                "       -> Write 'analysis' STRICTLY in natural, fluent Tenglish (Telugu words written in Latin/English alphabet, e.g. 'Ee message pakka scam bro. TCS lanti companies eppudu Rs 2000 registration fee adagavu. Asalu dabbu pay cheyyakandi!'). DO NOT use Telugu Unicode script characters.\n"
                "     * If the user writes in standard English:\n"
                "       -> Write 'analysis' in clear, friendly, intelligent English.\n"
                "     * If the user writes in a mix or requests explanation in a specific language, always follow the user's latest message language preference.\n"
                "   - RECRUITER SUGGESTED REPLY RULE:\n"
                "     * 'suggested_reply' (when provided for RECRUITER_REPLY) MUST ALWAYS be written in polite, professional English (never Telugu or Tenglish) so the student can copy and send it directly to the recruiter, OR if verdict is 'STILL_HIGH_RISK', provide a clear English warning directive (e.g., 'DO NOT REPLY: Block and report this recruiter immediately.')."
            )

            if user_wants_tenglish:
                prompt += (
                    "\n\nCRITICAL LANGUAGE DIRECTIVE: The user's query is in Tenglish/Telugu or they requested Tenglish. "
                    "Write the 'analysis' field strictly in natural Tenglish (Telugu language written in English/Roman letters, "
                    "e.g., 'Ee message pakka scam bro. TCS lanti companies eppudu Rs 2000 registration fee or Aadhaar/PAN details adagavu. Asalu dabbu pay cheyyakandi!'). "
                    "NEVER write 'analysis' in pure English when replying to a Tenglish query. Keep 'suggested_reply' in polite, professional English."
                )

            contents: List[Any] = []
            if file_part is not None:
                contents.append(file_part)
            contents.append(prompt)

            response = _generate_content_with_failover(
                client=client,
                contents=contents,
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

    # Step 5: Deterministic Fallback Engine
    return _deterministic_followup_fallback(
        report=report,
        user_message=clean_message,
        language=clean_lang,
        protection_risks=protection_risks,
        verification_questions=verification_questions,
        file_bytes=file_bytes,
        mime_type=mime_type,
    )
