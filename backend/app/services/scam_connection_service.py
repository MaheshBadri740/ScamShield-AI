from datetime import datetime, timezone
from typing import Dict, List, Any
from sqlalchemy.orm import Session

from app.models.scam_models import ScamEntity, ReportEntityLink

TRACKED_ENTITY_TYPES = {"phone", "email", "domain", "upi_id", "telegram"}


def normalize_value(val: str) -> str:
    """Normalize entity value by stripping whitespace and converting to lowercase."""
    return val.strip().lower()


def find_scam_connections(db: Session, entities: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    Looks up normalized entity values in the ScamEntity registry.
    Returns matched entities, total connected report count, and coordinated campaign flag.
    """
    matched_entities: List[Dict[str, Any]] = []

    for entity_type, values in entities.items():
        norm_type = normalize_value(entity_type)
        if norm_type not in TRACKED_ENTITY_TYPES or not values:
            continue

        # Deduplicate and normalize non-empty values
        normalized_values = {
            normalize_value(v) for v in values if isinstance(v, str) and v.strip()
        }
        if not normalized_values:
            continue

        matches = (
            db.query(ScamEntity)
            .filter(
                ScamEntity.entity_type == norm_type,
                ScamEntity.entity_value.in_(normalized_values),
            )
            .all()
        )

        for match in matches:
            matched_entities.append(
                {
                    "entity_type": match.entity_type,
                    "entity_value": match.entity_value,
                    "previous_reports": match.report_count,
                }
            )

    total_connected_reports = sum(item["previous_reports"] for item in matched_entities)
    is_coordinated_campaign = any(item["previous_reports"] >= 2 for item in matched_entities)

    return {
        "matched_entities": matched_entities,
        "total_connected_reports": total_connected_reports,
        "is_coordinated_campaign": is_coordinated_campaign,
    }


def record_scam_entities(
    db: Session,
    report_id: int,
    risk_level: str,
    entities: Dict[str, List[str]],
) -> None:
    """
    Records and upserts scam entities when risk_level is MEDIUM or HIGH.
    Increments report counts, updates timestamps, and establishes ReportEntityLink rows.
    """
    normalized_risk = str(risk_level).strip().upper()
    if normalized_risk not in {"MEDIUM", "HIGH"}:
        return

    now = datetime.now(timezone.utc)
    seen_pairs = set()

    for entity_type, values in entities.items():
        norm_type = normalize_value(entity_type)
        if norm_type not in TRACKED_ENTITY_TYPES or not values:
            continue

        for raw_val in values:
            if not isinstance(raw_val, str) or not raw_val.strip():
                continue
            norm_val = normalize_value(raw_val)
            pair = (norm_type, norm_val)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            # Query existing ScamEntity
            scam_entity = (
                db.query(ScamEntity)
                .filter(
                    ScamEntity.entity_type == norm_type,
                    ScamEntity.entity_value == norm_val,
                )
                .first()
            )

            if scam_entity:
                scam_entity.report_count += 1
                scam_entity.last_seen = now
            else:
                scam_entity = ScamEntity(
                    entity_type=norm_type,
                    entity_value=norm_val,
                    report_count=1,
                    first_seen=now,
                    last_seen=now,
                )
                db.add(scam_entity)
                db.flush()  # Populate scam_entity.id

            # Establish link if not already existing
            existing_link = (
                db.query(ReportEntityLink)
                .filter(
                    ReportEntityLink.report_id == report_id,
                    ReportEntityLink.entity_id == scam_entity.id,
                )
                .first()
            )
            if not existing_link:
                link = ReportEntityLink(report_id=report_id, entity_id=scam_entity.id)
                db.add(link)

    db.commit()
