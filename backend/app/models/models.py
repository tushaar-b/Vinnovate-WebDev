import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    Enum as SAEnum,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class SensitivityEnum(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MonitorStatusEnum(str, enum.Enum):
    PENDING = "pending"
    OK = "ok"
    CHANGED = "changed"
    ERROR = "error"
    BLOCKED = "blocked"


class RuleTypeEnum(str, enum.Enum):
    WATCH = "watch"
    IGNORE = "ignore"


class CheckRunStateEnum(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    UNCHANGED = "unchanged"
    CHANGED = "changed"
    BASELINE = "baseline"
    ERROR = "error"
    BLOCKED = "blocked"


class ChannelTypeEnum(str, enum.Enum):
    DISCORD = "discord"
    TELEGRAM = "telegram"


class OutboxStateEnum(str, enum.Enum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


class Monitor(Base):
    __tablename__ = "monitors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    url = Column(Text, nullable=False)
    canonical_url = Column(Text, nullable=False)
    interval_minutes = Column(Integer, nullable=False)
    sensitivity = Column(
        SAEnum(SensitivityEnum, name="sensitivity_enum"),
        nullable=False,
        default=SensitivityEnum.MEDIUM,
    )
    enabled = Column(Boolean, nullable=False, default=True)
    status = Column(
        SAEnum(MonitorStatusEnum, name="monitor_status_enum"),
        nullable=False,
        default=MonitorStatusEnum.PENDING,
    )
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_changed_at = Column(DateTime(timezone=True), nullable=True)
    next_check_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_error = Column(Text, nullable=True)
    rebaseline_needed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Relationships
    rules = relationship("MonitorRule", back_populates="monitor", cascade="all, delete-orphan")
    check_runs = relationship("CheckRun", back_populates="monitor", cascade="all, delete-orphan")
    versions = relationship("Version", back_populates="monitor", cascade="all, delete-orphan")
    channels = relationship("NotificationChannel", back_populates="monitor", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_monitors_enabled_next_check_at", "enabled", "next_check_at"),
        Index("ix_monitors_canonical_url", "canonical_url"),
    )


class MonitorRule(Base):
    __tablename__ = "monitor_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monitor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("monitors.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_type = Column(
        SAEnum(RuleTypeEnum, name="rule_type_enum"),
        nullable=False,
    )
    css_selector = Column(Text, nullable=False)
    label = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    monitor = relationship("Monitor", back_populates="rules")

    __table_args__ = (
        Index("ix_monitor_rules_monitor_id_rule_type", "monitor_id", "rule_type"),
    )


class CheckRun(Base):
    __tablename__ = "check_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monitor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("monitors.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id = Column(String(100), unique=True, nullable=False)
    state = Column(
        SAEnum(CheckRunStateEnum, name="check_run_state_enum"),
        nullable=False,
        default=CheckRunStateEnum.QUEUED,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    http_status = Column(Integer, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    attempt = Column(Integer, nullable=False, default=0)

    monitor = relationship("Monitor", back_populates="check_runs")
    version = relationship("Version", back_populates="check_run", uselist=False)

    __table_args__ = (
        Index("ix_check_runs_monitor_id_started_at", "monitor_id", started_at.desc()),
    )


class Version(Base):
    __tablename__ = "versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monitor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("monitors.id", ondelete="CASCADE"),
        nullable=False,
    )
    check_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("check_runs.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    sequence_number = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False)
    normalized_text = Column(Text, nullable=False)
    screenshot_path = Column(Text, nullable=False)
    captured_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    stable_alert_count = Column(Integer, nullable=False, default=0)

    monitor = relationship("Monitor", back_populates="versions")
    check_run = relationship("CheckRun", back_populates="version")

    __table_args__ = (
        UniqueConstraint("monitor_id", "sequence_number", name="uq_versions_monitor_sequence"),
        Index("ix_versions_monitor_id_captured_at", "monitor_id", captured_at.desc()),
    )


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monitor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("monitors.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel_type = Column(
        SAEnum(ChannelTypeEnum, name="channel_type_enum"),
        nullable=False,
    )
    configuration_json = Column(JSON, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    monitor = relationship("Monitor", back_populates="channels")


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monitor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("monitors.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    state = Column(
        SAEnum(OutboxStateEnum, name="outbox_state_enum"),
        nullable=False,
        default=OutboxStateEnum.PENDING,
    )
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("monitor_id", "version_id", "channel_id", name="uq_outbox_monitor_version_channel"),
        Index("ix_notification_outbox_state_created_at", "state", "created_at"),
    )
