from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Form, File, UploadFile, Request, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.limiter import limiter
from app.models.scam_models import OpportunityReport, ScamEntity, ReportEntityLink
from app.services.scam_connection_service import record_scam_entities
from app.agents.investigation_agent import investigate_opportunity
from app.agents.follow_up_agent import analyze_follow_up

router = APIRouter(prefix="/api", tags=["Investigation & Reports"])

ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/pdf",
}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/investigate")
@limiter.limit("10/minute")
async def investigate_career_opportunity(
    request: Request,
    text: Optional[str] = Form(None),
    opportunity_type: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Submits a job/internship offer for multimodal investigation.
    Validates file upload, executes fraud detection pipeline, persists reports,
    and updates the scam entity network registry.
    """
    if not text and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide at least a text message/description or an uploaded document/image.",
        )

    file_bytes: Optional[bytes] = None
    mime_type: Optional[str] = None

    if file:
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{file.content_type}'. Allowed types: PNG, JPEG, WEBP, PDF.",
            )

        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded file size ({len(file_bytes)} bytes) exceeds the maximum allowed 5MB limit.",
            )
        mime_type = file.content_type

    # Execute Multimodal AI & Deterministic Detection Agent
    investigation_result = investigate_opportunity(
        db=db,
        text=text,
        file_bytes=file_bytes,
        mime_type=mime_type,
        default_opportunity_type=opportunity_type,
    )

    report_data = investigation_result.get("report", {})
    resolved_op_type = report_data.get("opportunity_type") or opportunity_type or "Job"
    resolved_risk_level = report_data.get("risk_level", "LOW")
    resolved_risk_score = report_data.get("risk_score", 0)

    # Persist the investigation report in the database
    new_report = OpportunityReport(
        opportunity_type=resolved_op_type,
        company_name=report_data.get("company_name"),
        risk_level=resolved_risk_level,
        risk_score=resolved_risk_score,
        summary_en=report_data.get("summary_en", ""),
        summary_te=report_data.get("summary_te", ""),
        red_flags=report_data.get("red_flags", []),
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    # Record and correlate flagged scam entities for MEDIUM / HIGH risks
    record_scam_entities(
        db=db,
        report_id=new_report.id,
        risk_level=resolved_risk_level,
        entities=investigation_result.get("entities", {}),
    )

    return {
        "report_id": new_report.id,
        "created_at": new_report.created_at.isoformat() if new_report.created_at else None,
        "report": report_data,
        "scam_connections": investigation_result.get("scam_connections", {}),
        "domain_analysis": investigation_result.get("domain_analysis", {}),
        "student_protection": investigation_result.get("student_protection", {}),
        "extracted_entities": investigation_result.get("entities", {}),
    }


@router.post("/investigate/followup")
@limiter.limit("15/minute")
async def follow_up_investigation(
    request: Request,
    report_id: int = Form(...),
    message: str = Form(""),
    language: str = Form("en"),
    chat_history: str = Form("[]"),
    verification_questions: str = Form("[]"),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Evaluates follow-up inquiries, questions, or pasted recruiter responses/documents for an investigated report.
    Supports optional image/PDF file upload via multipart/form-data.
    Returns structured forensic analysis, updated risk verdict, and suggested response.
    """
    clean_message = (message or "").strip()
    if not clean_message and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a message or attach a document/image to evaluate.",
        )

    report = (
        db.query(OpportunityReport)
        .filter(OpportunityReport.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with id {report_id} not found",
        )

    file_bytes: Optional[bytes] = None
    mime_type: Optional[str] = None

    if file:
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{file.content_type}'. Allowed types: PNG, JPEG, WEBP, PDF.",
            )

        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded file size ({len(file_bytes)} bytes) exceeds the maximum allowed 5MB limit.",
            )
        mime_type = file.content_type

    parsed_history: List[Dict[str, Any]] = []
    if chat_history:
        try:
            parsed_history = json.loads(chat_history)
            if not isinstance(parsed_history, list):
                parsed_history = []
        except Exception:
            parsed_history = []

    parsed_questions: List[str] = []
    if verification_questions:
        try:
            parsed_questions = json.loads(verification_questions)
            if not isinstance(parsed_questions, list):
                parsed_questions = []
        except Exception:
            parsed_questions = []

    result = analyze_follow_up(
        report=report,
        user_message=clean_message,
        language=language or "en",
        verification_questions=parsed_questions,
        chat_history=parsed_history,
        file_bytes=file_bytes,
        mime_type=mime_type,
    )

    return result


@router.get("/reports")
def get_recent_reports(
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Retrieves the latest 20 OpportunityReport records."""
    reports = (
        db.query(OpportunityReport)
        .order_by(OpportunityReport.created_at.desc())
        .limit(20)
        .all()
    )

    return [
        {
            "id": r.id,
            "opportunity_type": r.opportunity_type,
            "company_name": r.company_name,
            "risk_level": r.risk_level,
            "risk_score": r.risk_score,
            "summary_en": r.summary_en,
            "summary_te": r.summary_te,
            "red_flags": r.red_flags,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]


@router.get("/reports/{report_id}")
def get_single_report(
    report_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Retrieves full investigation report details by ID matching InvestigationResponse.
    Reconstructs scam_connections, student_protection, and domain_analysis from stored data and linked entities.
    """
    report = (
        db.query(OpportunityReport)
        .filter(OpportunityReport.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with id {report_id} not found",
        )

    # Fetch linked scam entities via ReportEntityLink
    links = (
        db.query(ReportEntityLink)
        .filter(ReportEntityLink.report_id == report_id)
        .all()
    )
    matched_entities = []
    extracted_entities: Dict[str, List[str]] = {
        "phone": [],
        "email": [],
        "domain": [],
        "upi_id": [],
        "telegram": [],
    }
    total_connected = 0
    for link in links:
        entity = link.entity
        if entity:
            matched_entities.append({
                "entity_type": entity.entity_type,
                "entity_value": entity.entity_value,
                "previous_reports": entity.report_count,
            })
            if entity.entity_type in extracted_entities:
                extracted_entities[entity.entity_type].append(entity.entity_value)
            if entity.report_count > total_connected:
                total_connected = entity.report_count

    is_coordinated = total_connected >= 2
    scam_connections = {
        "matched_entities": matched_entities,
        "total_connected_reports": total_connected,
        "is_coordinated_campaign": is_coordinated,
    }

    red_flags = report.red_flags or []
    student_protection_alerts = [
        f for f in red_flags
        if any(k in f.lower() for k in ("fee", "deposit", "payment", "upi", "aadhaar", "pan", "otp", "bank", "pii", "money", "rupees", "rs", "₹"))
    ]
    has_critical_risk = report.risk_level == "HIGH" and bool(student_protection_alerts)

    student_protection = {
        "pii_alerts": [a for a in student_protection_alerts if any(k in a.lower() for k in ("aadhaar", "pan", "otp", "bank", "pii"))],
        "payment_alerts": [a for a in student_protection_alerts if any(k in a.lower() for k in ("fee", "deposit", "payment", "upi", "money", "rupees", "rs", "₹"))],
        "has_critical_risk": has_critical_risk,
        "all_alerts": student_protection_alerts,
    }

    domain_flags = [
        f for f in red_flags
        if any(k in f.lower() for k in ("domain", "email provider", "tld", "hyphen", "@gmail", "@yahoo", "@outlook"))
    ]
    domain_analysis = {
        "free_provider_warnings": [f for f in domain_flags if "free" in f.lower() or "provider" in f.lower()],
        "suspicious_tld_warnings": [f for f in domain_flags if "tld" in f.lower()],
        "hyphenated_domain_warnings": [f for f in domain_flags if "hyphen" in f.lower()],
        "flags": domain_flags,
        "has_suspicious_domain": bool(domain_flags),
    }

    report_data = {
        "opportunity_type": report.opportunity_type,
        "company_name": report.company_name,
        "risk_level": report.risk_level,
        "risk_score": report.risk_score,
        "red_flags": red_flags,
        "student_protection_alerts": student_protection_alerts,
        "summary_en": report.summary_en,
        "summary_te": report.summary_te,
        "preventive_actions_en": [
            "Never transfer money for registration, onboarding, training, or equipment.",
            "Do not disclose Aadhaar, PAN card, or bank account details prior to formal in-person or verified portal hiring.",
            "Independently cross-verify the recruiter's identity on official corporate directories or LinkedIn.",
        ],
        "preventive_actions_te": [
            "Registration fee, training fee, leda laptop deposit peru tho e mathram dabbu transfer cheyavaddu.",
            "Official offer letter mariyu verified hiring portal lekunda Aadhaar, PAN card, leda bank details share cheyavaddu.",
            "Company official website mariyu recruiter LinkedIn profile ni independent ga cross-check cheyandi.",
        ],
        "verification_questions": [
            "Can you provide a formal offer letter from your official company corporate email domain?",
            "Is this position registered on your company's official public careers portal with a verifiable requisition ID?",
            "Can you confirm in writing that no candidate will ever be asked to pay training, equipment, or document fees?",
        ],
    }

    return {
        "report_id": report.id,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "report": report_data,
        "scam_connections": scam_connections,
        "domain_analysis": domain_analysis,
        "student_protection": student_protection,
        "extracted_entities": extracted_entities,
    }


@router.delete("/reports")
def clear_all_reports(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Clears all stored reports, entity links, and tracked scam entities."""
    db.query(ReportEntityLink).delete()
    db.query(ScamEntity).delete()
    db.query(OpportunityReport).delete()
    db.commit()
    return {"status": "cleared"}


@router.delete("/reports/{report_id}")
def delete_single_report(
    report_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Deletes a single OpportunityReport by ID.
    Decrements report_count on linked ScamEntity records and deletes orphaned entities.
    """
    report = (
        db.query(OpportunityReport)
        .filter(OpportunityReport.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with id {report_id} not found",
        )

    # Find linked scam entities before deleting the report
    links = (
        db.query(ReportEntityLink)
        .filter(ReportEntityLink.report_id == report_id)
        .all()
    )
    entity_ids = [link.entity_id for link in links]

    # Delete the report (cascade removes ReportEntityLink rows)
    db.delete(report)
    db.flush()

    # Decrement report count on linked entities and delete any with report_count <= 0
    for entity_id in set(entity_ids):
        scam_entity = (
            db.query(ScamEntity)
            .filter(ScamEntity.id == entity_id)
            .first()
        )
        if scam_entity:
            scam_entity.report_count -= 1
            if scam_entity.report_count <= 0:
                db.delete(scam_entity)

    db.commit()
    return {"status": "deleted", "report_id": report_id}


@router.get("/stats")
def get_platform_stats(
    db: Session = Depends(get_db),
) -> Dict[str, int]:
    """
    Returns platform-wide security statistics:
    - total_investigations: Total evaluated opportunities
    - safe_count: Verified low-risk opportunities
    - high_risk_count: Confirmed high-risk scams detected
    - coordinated_campaigns_count: Entities appearing in >= 2 distinct fraud reports
    """
    total_investigations = db.query(OpportunityReport).count()
    safe_count = (
        db.query(OpportunityReport)
        .filter(OpportunityReport.risk_level == "LOW")
        .count()
    )
    high_risk_count = (
        db.query(OpportunityReport)
        .filter(OpportunityReport.risk_level == "HIGH")
        .count()
    )
    coordinated_campaigns_count = (
        db.query(ScamEntity)
        .filter(ScamEntity.report_count >= 2)
        .count()
    )

    return {
        "total_investigations": total_investigations,
        "safe_count": safe_count,
        "high_risk_count": high_risk_count,
        "coordinated_campaigns_count": coordinated_campaigns_count,
    }
