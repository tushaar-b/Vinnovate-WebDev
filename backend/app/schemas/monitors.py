import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.models.models import SensitivityEnum, MonitorStatusEnum, CheckRunStateEnum, RuleTypeEnum
from app.config import settings


class MonitorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Monitor label")
    url: str = Field(..., description="Target webpage URL")
    interval_minutes: int = Field(default=60, description="Check frequency in minutes")
    sensitivity: SensitivityEnum = Field(default=SensitivityEnum.MEDIUM)

    @field_validator("name")
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Monitor name cannot be empty or blank.")
        return stripped

    @field_validator("interval_minutes")
    def validate_interval(cls, v: int) -> int:
        min_allowed = 1 if settings.TEST_MODE else 15
        if v < min_allowed or v > 1440:
            raise ValueError(f"Interval minutes must be between {min_allowed} and 1440.")
        return v


class MonitorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    interval_minutes: Optional[int] = None
    sensitivity: Optional[SensitivityEnum] = None
    enabled: Optional[bool] = None

    @field_validator("interval_minutes")
    def validate_interval(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            min_allowed = 1 if settings.TEST_MODE else 15
            if v < min_allowed or v > 1440:
                raise ValueError(f"Interval minutes must be between {min_allowed} and 1440.")
        return v


class MonitorRuleInput(BaseModel):
    rule_type: RuleTypeEnum
    css_selector: str
    label: Optional[str] = None


class MonitorRulesUpdateRequest(BaseModel):
    rules: List[MonitorRuleInput]


class MonitorRuleSchema(BaseModel):
    id: uuid.UUID
    monitor_id: uuid.UUID
    rule_type: RuleTypeEnum
    css_selector: str
    label: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PickerElement(BaseModel):
    selector: str
    label: str
    x: float
    y: float
    width: float
    height: float


class PickerResponse(BaseModel):
    screenshot_url: str
    width: int
    height: int
    elements: List[PickerElement]



class MonitorSummary(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    interval_minutes: int
    sensitivity: SensitivityEnum
    enabled: bool
    status: MonitorStatusEnum
    last_checked_at: Optional[datetime] = None
    last_changed_at: Optional[datetime] = None
    next_check_at: datetime
    last_error: Optional[str] = None
    versions_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MonitorListResponse(BaseModel):
    items: List[MonitorSummary]
    total: int


class MonitorDetail(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    canonical_url: str
    interval_minutes: int
    sensitivity: SensitivityEnum
    enabled: bool
    status: MonitorStatusEnum
    last_checked_at: Optional[datetime] = None
    last_changed_at: Optional[datetime] = None
    next_check_at: datetime
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    versions_count: int = 0
    rules: List[MonitorRuleSchema] = []

    model_config = ConfigDict(from_attributes=True)


class CheckRunResponse(BaseModel):
    id: uuid.UUID
    monitor_id: uuid.UUID
    state: CheckRunStateEnum
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    http_status: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    version_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)


class CheckRunListResponse(BaseModel):
    items: List[CheckRunResponse]


class CheckEnqueueResponse(BaseModel):
    check_run_id: uuid.UUID
    job_id: str
    state: str = "queued"


class VersionSummary(BaseModel):
    id: uuid.UUID
    monitor_id: uuid.UUID
    sequence_number: int
    captured_at: datetime
    content_hash: str
    screenshot_url: str
    short_preview: str

    model_config = ConfigDict(from_attributes=True)


class VersionDetails(BaseModel):
    id: uuid.UUID
    monitor_id: uuid.UUID
    sequence_number: int
    captured_at: datetime
    content_hash: str
    screenshot_url: str
    short_preview: str
    normalized_text: str

    model_config = ConfigDict(from_attributes=True)


class VersionListResponse(BaseModel):
    items: List[VersionSummary]


class TextDiffItem(BaseModel):
    kind: str  # "equal", "add", "remove"
    text: str


class VersionComparisonResponse(BaseModel):
    old_version: VersionDetails
    new_version: VersionDetails
    text_diff: List[TextDiffItem]
    image_old_url: str
    image_new_url: str
    image_diff_url: Optional[str] = None
    change_ratio: float = 0.0

