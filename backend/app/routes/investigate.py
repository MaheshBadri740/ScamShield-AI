from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Form, File, UploadFile, Request, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.limiter import limiter
from app.models.scam_models import OpportunityReport, ScamEntity, ReportEntityLink
from app.services.scam_connection_service import record_scam_entities
from app.agents.investigation_agent import investigate_opportunity

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
