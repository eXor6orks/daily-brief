from typing import Optional, List
from datetime import datetime, timezone
from sqlmodel import Session, select, col
from sqlalchemy import func

from Salva.models import (
    TaskTemplate,
    TaskInstance,
    MatchAttempt,
    ClusterInstance,
    OrphanCluster,
    TaskOrigin,
    TaskStatus,
    MatchingStatus,
    MatchMethod,
    ClusterStatus,
    normalize_title,
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)

class MatchRepository :

    def __init__(self, session: Session):
        self.session = session

    def record_match_attempt(
        self,
        instance_id: int,
        template_id: int,
        score: float,
        method: MatchMethod = MatchMethod.FUZZY,
        accepted: bool = False,
        details: Optional[dict] = None,
    ) -> MatchAttempt:
        attempt = MatchAttempt(
            instance_id=instance_id,
            template_id=template_id,
            score=score,
            method=method,
            accepted=accepted,
            details=details,
        )
        self.session.add(attempt)
        self.session.commit()
        self.session.refresh(attempt)
        return attempt

    def get_match_attempts_for_instance(self, instance_id: int) -> List[MatchAttempt]:
        statement = (
            select(MatchAttempt)
            .where(MatchAttempt.instance_id == instance_id)
            .order_by(MatchAttempt.score.desc())
        )
        return list(self.session.exec(statement).all())