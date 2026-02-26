from typing import Optional, List
from datetime import datetime, date, timezone
from sqlmodel import SQLModel, Field, Relationship, Column, JSON, Index
from sqlalchemy import DateTime, Integer, ForeignKey, func
from pydantic import BaseModel, field_validator
import enum


# ============================================
# ENUMS
# ============================================
class TaskOrigin(str, enum.Enum):
    USER = "user"
    SYSTEM = "system"
    CALENDAR = "calendar"
    DETECTED = "detected"


class TaskStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MatchingStatus(str, enum.Enum):
    PENDING = "pending"
    MATCHED = "matched"
    ORPHAN = "orphan"
    CLUSTERED = "clustered"


class RecurrencePattern(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"
    SMART = "smart"


class TimePreference(str, enum.Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    ANYTIME = "anytime"


class MatchMethod(str, enum.Enum):
    FUZZY = "fuzzy"
    EMBEDDING = "embedding"
    LLM = "llm"


class ClusterStatus(str, enum.Enum):
    ACTIVE = "active"
    PROMOTED = "promoted"
    DISMISSED = "dismissed"


# ============================================
# UTILS
# ============================================
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_title(title: str) -> str:
    """Normalise un titre pour le matching (minuscule, sans stopwords, sans ponctuation)."""
    import re

    text = title.lower().strip()

    stopwords = {
        "le", "la", "les", "un", "une", "des", "du", "de", "d",
        "à", "au", "aux", "faire", "aller", "prendre", "mon", "ma",
        "mes", "son", "sa", "ses", "ce", "cette", "ces", "et", "ou",
    }
    words = text.split()
    words = [w for w in words if w not in stopwords]
    text = " ".join(words)

    text = re.sub(r"[^\w\s]", "", text)

    return text.strip()


# ============================================
# USER PREFERENCES (Pydantic validation)
# ============================================
class UserPreferences(BaseModel):
    """Modèle Pydantic pour valider les préférences utilisateur avant stockage."""

    work_hours_start: str = "9:00"
    work_hours_end: str = "18:30"
    work_days: List[int] = [1, 2, 3, 4, 5]
    max_tasks_per_day: int = 5
    default_task_duration_minutes: int = 60
    buffer_between_tasks_minutes: int = 15
    language: str = "fr"

    @field_validator("work_hours_start", "work_hours_end")
    @classmethod
    def validate_hours(cls, v: str) -> str:
        nb = int(v.split(":")[0])
        if not 0 <= nb <= 23:
            raise ValueError("Les heures doivent être entre 0 et 23")
        return v

    @field_validator("work_days")
    @classmethod
    def validate_work_days(cls, v: List[int]) -> List[int]:
        if not all(1 <= d <= 7 for d in v):
            raise ValueError("Les jours doivent être entre 1 (lundi) et 7 (dimanche)")
        return sorted(set(v))

    @field_validator("max_tasks_per_day")
    @classmethod
    def validate_max_tasks(cls, v: int) -> int:
        if not 1 <= v <= 20:
            raise ValueError("max_tasks_per_day doit être entre 1 et 20")
        return v


# ============================================
# USER
# ============================================
class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)

    # iCloud — le mot de passe devrait être chiffré avant stockage
    icloud_username: Optional[str] = Field(default=None, max_length=255)
    icloud_encrypted_password: Optional[str] = Field(default=None)
    icloud_caldav_url: Optional[str] = Field(default=None)

    timezone: str = Field(default="Europe/Paris", max_length=50)

    # Préférences validées par UserPreferences
    preferences: dict = Field(
        default_factory=lambda: UserPreferences().model_dump(),
        sa_column=Column(JSON),
    )
    preferences_supplements: Optional[str] = Field(default=None, max_length=500)

    created_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    last_active: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )

    # Relations
    templates: List["TaskTemplate"] = Relationship(back_populates="user", cascade_delete=True)
    instances: List["TaskInstance"] = Relationship(back_populates="user", cascade_delete=True)
    clusters: List["OrphanCluster"] = Relationship(back_populates="user", cascade_delete=True)
    patterns: List["LearnedPattern"] = Relationship(back_populates="user", cascade_delete=True)

    def set_preferences(self, data: dict) -> None:
        """Valide et applique les préférences."""
        validated = UserPreferences(**data)
        self.preferences = validated.model_dump()

    def get_preferences(self) -> UserPreferences:
        """Retourne les préférences sous forme de modèle Pydantic."""
        return UserPreferences(**self.preferences)


# ============================================
# TASK TEMPLATE
# ============================================
class TaskTemplate(SQLModel, table=True):
    __tablename__ = "task_templates"
    __table_args__ = (
        Index("idx_templates_user_id", "user_id"),
        Index("idx_templates_normalized", "normalized_title"),
        Index("idx_templates_active", "user_id", "active"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE")

    title: str = Field(max_length=500)
    normalized_title: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = Field(default=None)

    priority: int = Field(default=3, ge=1, le=5)
    estimated_duration: Optional[int] = Field(default=None)  # minutes

    # Récurrence
    recurrence_pattern: Optional[RecurrencePattern] = Field(default=None)
    recurrence_interval: Optional[int] = Field(default=1)
    recurrence_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    # Exemple: {"days_of_week": [1, 3, 5], "time": "10:00"}

    time_preference: Optional[TimePreference] = Field(default=TimePreference.ANYTIME)

    # Tracking
    last_instance_created_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    next_suggested_date: Optional[date] = Field(default=None)
    instance_count: int = Field(default=0)

    # Origine
    origin: TaskOrigin = Field(default=TaskOrigin.USER)
    promoted_from_cluster_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            "promoted_from_cluster_id",
            Integer,
            ForeignKey("orphan_clusters.id", name="fk_template_from_cluster", use_alter=True),
            nullable=True,
        ),
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # Métadonnées
    created_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )
    active: bool = Field(default=True)

    # Relations
    user: User = Relationship(back_populates="templates")
    instances: List["TaskInstance"] = Relationship(back_populates="template")
    match_attempts: List["MatchAttempt"] = Relationship(back_populates="template")

    def compute_normalized_title(self) -> None:
        self.normalized_title = normalize_title(self.title)


# ============================================
# TASK INSTANCE
# ============================================
class TaskInstance(SQLModel, table=True):
    __tablename__ = "task_instances"
    __table_args__ = (
        Index("idx_instances_user_id", "user_id"),
        Index("idx_instances_template_id", "template_id"),
        Index("idx_instances_matching", "user_id", "matching_status"),
        Index("idx_instances_scheduled", "scheduled_start"),
        Index("idx_instances_calendar_event", "calendar_event_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE")
    template_id: Optional[int] = Field(
        default=None, foreign_key="task_templates.id", ondelete="SET NULL"
    )

    title: str = Field(max_length=500)
    normalized_title: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = Field(default=None)

    priority: Optional[int] = Field(default=3, ge=1, le=5)

    # Planification
    scheduled_start: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    scheduled_end: datetime = Field(sa_column=Column(DateTime(timezone=True)))

    # Lieu & URL
    location: Optional[str] = Field(default=None, max_length=500)
    location_lat: Optional[float] = Field(default=None)
    location_lon: Optional[float] = Field(default=None)
    url: Optional[str] = Field(default=None, max_length=1000)

    # Alertes — stockées en JSON, ex: [15, 60] = 15min et 1h avant
    alerts_minutes: Optional[List[int]] = Field(default=None, sa_column=Column(JSON))

    # Calendrier iCloud
    calendar_event_id: Optional[str] = Field(default=None, max_length=255)
    calendar_name: Optional[str] = Field(default=None, max_length=100)

    # Statut
    status: TaskStatus = Field(default=TaskStatus.SCHEDULED)
    completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    # Origine & Matching
    origin: TaskOrigin = Field(default=TaskOrigin.SYSTEM)
    matching_status: MatchingStatus = Field(default=MatchingStatus.PENDING)

    # Métadonnées
    created_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )

    # Relations
    user: User = Relationship(back_populates="instances")
    template: Optional[TaskTemplate] = Relationship(back_populates="instances")
    match_attempts: List["MatchAttempt"] = Relationship(back_populates="instance")
    cluster_links: List["ClusterInstance"] = Relationship(back_populates="instance")

    def compute_normalized_title(self) -> None:
        self.normalized_title = normalize_title(self.title)


# ============================================
# MATCH ATTEMPT — trace chaque tentative de matching
# ============================================
class MatchAttempt(SQLModel, table=True):
    __tablename__ = "match_attempts"
    __table_args__ = (
        Index("idx_match_instance", "instance_id"),
        Index("idx_match_template", "template_id"),
        Index("idx_match_accepted", "accepted"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    instance_id: int = Field(foreign_key="task_instances.id", ondelete="CASCADE")
    template_id: int = Field(foreign_key="task_templates.id", ondelete="CASCADE")

    score: float = Field(ge=0.0, le=1.0)
    method: MatchMethod = Field(default=MatchMethod.FUZZY)
    accepted: bool = Field(default=False)

    # Détails optionnels pour debug / apprentissage
    details: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    # Exemple: {"fuzzy_ratio": 0.87, "token_sort_ratio": 0.92}

    created_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    # Relations
    instance: TaskInstance = Relationship(back_populates="match_attempts")
    template: TaskTemplate = Relationship(back_populates="match_attempts")


# ============================================
# CLUSTER INSTANCE — table de liaison cluster ↔ instance
# ============================================
class ClusterInstance(SQLModel, table=True):
    __tablename__ = "cluster_instances"
    __table_args__ = (
        Index("idx_ci_cluster", "cluster_id"),
        Index("idx_ci_instance", "instance_id"),
    )

    cluster_id: int = Field(
        foreign_key="orphan_clusters.id", primary_key=True, ondelete="CASCADE"
    )
    instance_id: int = Field(
        foreign_key="task_instances.id", primary_key=True, ondelete="CASCADE"
    )
    similarity_score: float = Field(ge=0.0, le=1.0)
    added_at: datetime = Field(default_factory=now_utc)

    # Relations
    cluster: "OrphanCluster" = Relationship(back_populates="instance_links")
    instance: TaskInstance = Relationship(back_populates="cluster_links")


# ============================================
# ORPHAN CLUSTER
# ============================================
class OrphanCluster(SQLModel, table=True):
    __tablename__ = "orphan_clusters"
    __table_args__ = (
        Index("idx_clusters_user_id", "user_id"),
        Index("idx_clusters_status", "status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE")

    cluster_label: str = Field(max_length=500)  # "courses", "coiffeur"
    representative_title: str = Field(max_length=500)  # "Faire les courses"

    # Pattern détecté
    detected_frequency_days: Optional[float] = Field(default=None)
    detected_pattern: Optional[str] = Field(default=None, max_length=50)

    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # Lifecycle du cluster
    status: ClusterStatus = Field(default=ClusterStatus.ACTIVE)
    promoted_to_template_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            "promoted_to_template_id",
            Integer,
            ForeignKey("task_templates.id", name="fk_cluster_to_template", use_alter=True),
            nullable=True,
        ),
    )
    promoted_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    created_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )

    # Relations
    user: User = Relationship(back_populates="clusters")
    instance_links: List[ClusterInstance] = Relationship(back_populates="cluster")

    @property
    def instance_count(self) -> int:
        return len(self.instance_links)


# ============================================
# LEARNED PATTERN
# ============================================
class LearnedPattern(SQLModel, table=True):
    __tablename__ = "learned_patterns"
    __table_args__ = (
        Index("idx_patterns_user_category", "user_id", "category"),
        Index("idx_patterns_type", "pattern_type"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE")

    pattern_type: str = Field(max_length=100)
    # 'completion_time', 'preferred_day', 'duration', 'frequency'

    category: Optional[str] = Field(default=None, max_length=100)

    pattern_data: dict = Field(sa_column=Column(JSON))
    # Exemples:
    # {"preferred_hour": 10, "completion_rate": 0.85}
    # {"avg_frequency_days": 5, "std_deviation": 1.2}

    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    observations_count: int = Field(default=1)

    last_updated: datetime = Field(
        default_factory=now_utc,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )

    # Relations
    user: User = Relationship(back_populates="patterns")