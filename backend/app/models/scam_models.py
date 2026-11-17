from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def utc_now() -> datetime:
    """Return current UTC timestamp with timezone awareness."""
    return datetime.now(timezone.utc)


class OpportunityReport(Base):
    """Stores detailed assessment reports for investigated opportunities."""
    __tablename__ = "opportunity_reports"

    id = Column(Integer, primary_key=True, index=True)
    # Opportunity categories: Job, Internship, WFH, Freelancing, Training, Placement Drive
    opportunity_type = Column(String(50), nullable=False)
    company_name = Column(String(255), nullable=True)
    # Risk assessments: LOW, MEDIUM, HIGH
    risk_level = Column(String(20), nullable=False)
    # Score 0 (safe) to 100 (critical scam)
    risk_score = Column(Integer, nullable=False)
    summary_en = Column(Text, nullable=False)
    summary_te = Column(Text, nullable=False)
    # List of detected scam indicators and warning points
    red_flags = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    entity_links = relationship("ReportEntityLink", back_populates="report", cascade="all, delete-orphan")


class ScamEntity(Base):
    """Stores unique identifiable indicators linked to fraudulent activities."""
    __tablename__ = "scam_entities"

    id = Column(Integer, primary_key=True, index=True)
    # Entity types: phone, email, domain, upi_id, telegram
    entity_type = Column(String(50), nullable=False)
    entity_value = Column(String(255), nullable=False, index=True)
    report_count = Column(Integer, default=1, nullable=False)
    first_seen = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    report_links = relationship("ReportEntityLink", back_populates="entity", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_value", name="uq_entity_type_value"),
    )


class ReportEntityLink(Base):
    """Association table linking OpportunityReports with identified ScamEntities."""
    __tablename__ = "report_entity_links"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("opportunity_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id = Column(Integer, ForeignKey("scam_entities.id", ondelete="CASCADE"), nullable=False, index=True)

    report = relationship("OpportunityReport", back_populates="entity_links")
    entity = relationship("ScamEntity", back_populates="report_links")

    __table_args__ = (
        UniqueConstraint("report_id", "entity_id", name="uq_report_entity_link"),
    )
