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

class TemplatesRepository :

    def __init__(self, session: Session):
        self.session = session

    def create_template(
        self,
        user_id: int,
        title: str,
        origin: TaskOrigin = TaskOrigin.USER,
        **kwargs,
    ) -> TaskTemplate:
        template = TaskTemplate(
            user_id=user_id,
            title=title,
            normalized_title=normalize_title(title),
            origin=origin,
            **kwargs,
        )
        self.session.add(template)
        self.session.commit()
        self.session.refresh(template)
        return template

    def get_template(self, template_id: int) -> Optional[TaskTemplate]:
        return self.session.get(TaskTemplate, template_id)

    def get_user_templates(self, user_id: int, active_only: bool = True) -> List[TaskTemplate]:
        statement = select(TaskTemplate).where(TaskTemplate.user_id == user_id)
        if active_only:
            statement = statement.where(TaskTemplate.active == True)
        return list(self.session.exec(statement).all())

    def deactivate_template(self, template_id: int) -> bool:
        template = self.get_template(template_id)
        if not template:
            return False
        template.active = False
        template.updated_at = now_utc()
        self.session.commit()
        return True

    def increment_template_instance_count(self, template_id: int) -> None:
        template = self.get_template(template_id)
        if template:
            template.instance_count += 1
            template.last_instance_created_at = now_utc()
            self.session.commit()

    def update_template(
            self,
            template_id: int,
            title: Optional[str] = None,
            **kwargs,
    ) :
        template = self.get_template(template_id)
        if not template:
            return None

        if title:
            template.title = title
            template.normalized_title = normalize_title(title)

        for key, value in kwargs.items():
            if hasattr(template, key):
                setattr(template, key, value)

        template.updated_at = now_utc()
        self.session.commit()
        self.session.refresh(template)
        return template
    
    def delete_template(self, template_id: int) -> bool:
        template = self.get_template(template_id)
        if not template :
            return None
        self.session.delete(template)
        self.session.commit()
        return True