from typing import Optional, List
from datetime import datetime, timezone
from sqlmodel import Session, select, col
from sqlalchemy import func
from Salva.Repository.Templates import TemplatesRepository

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

class InstancesRepository :

    def __init__(self, session: Session):
        self.session = session

        self.TemplatesRepo = TemplatesRepository(session)

    def create_instance(
        self,
        user_id: int,
        title: str,
        scheduled_start: datetime,
        scheduled_end: datetime,
        origin: TaskOrigin = TaskOrigin.SYSTEM,
        template_id: Optional[int] = None,
        calendar_event_id: Optional[str] = None,
        calendar_name: Optional[str] = None,
        **kwargs,
    ) -> TaskInstance:
        matching_status = MatchingStatus.MATCHED if template_id else MatchingStatus.PENDING

        instance = TaskInstance(
            user_id=user_id,
            title=title,
            normalized_title=normalize_title(title),
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            origin=origin,
            template_id=template_id,
            matching_status=matching_status,
            calendar_event_id=calendar_event_id,
            calendar_name=calendar_name,
            **kwargs,
        )

        self.session.add(instance)
        self.session.commit()
        self.session.refresh(instance)

        if template_id:
            self.TemplatesRepo.increment_template_instance_count(template_id)

        return instance

    def get_instance(self, instance_id: int) -> Optional[TaskInstance]:
        return self.session.get(TaskInstance, instance_id)

    def get_instance_by_calendar_event(self, calendar_event_id: str) -> Optional[TaskInstance]:
        statement = select(TaskInstance).where(
            TaskInstance.calendar_event_id == calendar_event_id
        )
        return self.session.exec(statement).first()

    def get_user_instances(
        self,
        user_id: int,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        status: Optional[TaskStatus] = None,
    ) -> List[TaskInstance]:
        statement = select(TaskInstance).where(TaskInstance.user_id == user_id)

        if start:
            statement = statement.where(TaskInstance.scheduled_start >= start)
        if end:
            statement = statement.where(TaskInstance.scheduled_end <= end)
        if status:
            statement = statement.where(TaskInstance.status == status)

        statement = statement.order_by(TaskInstance.scheduled_start)
        return list(self.session.exec(statement).all())

    def get_user_instances_active(
        self,
        user_id: int,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        status: Optional[TaskStatus] = None,
    ) -> List[TaskInstance]:
        statement = select(TaskInstance).where(TaskInstance.user_id == user_id)

        if start:
            statement = statement.where(TaskInstance.scheduled_start >= start)
        if end:
            statement = statement.where(TaskInstance.scheduled_end <= end)
        if status:
            statement = statement.where(TaskInstance.status == status)
            
        statement = statement.order_by(TaskInstance.scheduled_start)
        return list(self.session.exec(statement).all())

    def get_pending_instances(self, user_id: int) -> List[TaskInstance]:
        """Récupère les instances en attente de matching."""
        statement = (
            select(TaskInstance)
            .where(TaskInstance.user_id == user_id)
            .where(TaskInstance.matching_status == MatchingStatus.PENDING)
        )
        return list(self.session.exec(statement).all())
    
    def get_last_instance_by_template(self, template_id: int) -> Optional[TaskInstance]:
        """Récupère la dernière instance créée pour un template donné."""
        statement = (
            select(TaskInstance)
            .where(TaskInstance.template_id == template_id)
            .where(TaskInstance.status != TaskStatus.CANCELLED)
            .order_by(TaskInstance.scheduled_start.desc())
            .limit(1)
        )
        return self.session.exec(statement).first()

    def get_orphan_instances(self, user_id: int) -> List[TaskInstance]:
        """Récupère les instances orphelines pas encore clusterisées."""
        statement = (
            select(TaskInstance)
            .where(TaskInstance.user_id == user_id)
            .where(TaskInstance.matching_status == MatchingStatus.ORPHAN)
        )
        return list(self.session.exec(statement).all())

    def mark_instance_matched(self, instance_id: int, template_id: int) -> None:
        instance = self.get_instance(instance_id)
        if instance:
            instance.template_id = template_id
            instance.matching_status = MatchingStatus.MATCHED
            instance.updated_at = now_utc()
            self.session.commit()
            self.TemplatesRepo.increment_template_instance_count(template_id)

    def mark_instance_orphan(self, instance_id: int) -> None:
        instance = self.get_instance(instance_id)
        if instance:
            instance.matching_status = MatchingStatus.ORPHAN
            instance.updated_at = now_utc()
            self.session.commit()

    def mark_instance_clustered(self, instance_id: int) -> None:
        instance = self.get_instance(instance_id)
        if instance:
            instance.matching_status = MatchingStatus.CLUSTERED
            instance.updated_at = now_utc()
            self.session.commit()

    def mark_instance_deleted(self, event_uid: str) -> None:
        instance = self.get_instance_by_calendar_event(event_uid)
        if instance:
            instance.status = TaskStatus.CANCELLED
            instance.updated_at = now_utc()
            self.session.commit()

    def complete_instance(self, instance_id: int) -> bool:
        instance = self.get_instance(instance_id)
        if not instance:
            return False
        instance.status = TaskStatus.COMPLETED
        instance.completed_at = now_utc()
        instance.updated_at = now_utc()
        self.session.commit()
        return True

    def cancel_instance(self, instance_id: int) -> bool:
        instance = self.get_instance(instance_id)
        if not instance:
            return False
        instance.status = TaskStatus.CANCELLED
        instance.updated_at = now_utc()
        self.session.commit()
        return True
    
    def find_duplicate(
        self,
        user_id: int,
        title: str,
        scheduled_start: datetime,
    ) -> Optional[TaskInstance]:
        """Vérifie si une instance avec le même titre et horaire existe déjà."""
        statement = (
            select(TaskInstance)
            .where(TaskInstance.user_id == user_id)
            .where(TaskInstance.title == title)
            .where(TaskInstance.scheduled_start == scheduled_start)
            .where(TaskInstance.status != TaskStatus.CANCELLED)
            .limit(1)
        )
        return self.session.exec(statement).first()
    
    def update_instance_by_id(self, id, **kwargs) -> Optional[TaskInstance] :
        instance = self.get_instance(id)

        if not instance:
            raise ValueError(f"Instance with uid : {id} not found")
        
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        instance.updated_at = now_utc()
        self.session.commit()
        self.session.refresh(instance)

        return instance
    
    def update_instance(self, uid : str, **kwargs) -> Optional[TaskInstance] :
        instance = self.get_instance_by_calendar_event(uid)

        if not instance:
            raise ValueError(f"Instance with uid : {uid} not found")
        
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        instance.updated_at = now_utc()
        self.session.commit()
        self.session.refresh(instance)

        return instance
    
    def delete_instance(self, uid : str) -> bool :
        instance = self.get_instance_by_calendar_event(uid)

        if not instance:
            raise ValueError(f"Instance with uid : {uid} not found")
        
        self.session.delete(instance)
        self.session.commit()

        return True

    