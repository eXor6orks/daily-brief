from typing import Optional, List
from datetime import datetime, timezone
from sqlmodel import Session, select, col
from sqlalchemy import func

from Salva.Repository.Templates import TemplatesRepository
from Salva.Repository.Instances import InstancesRepository

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

class OrphanRepository :

    def __init__(self, session: Session):
        self.session = session

        self.instanceRepo = InstancesRepository(session)
        self.templateRepo = TemplatesRepository(session)

    def create_cluster(
        self,
        user_id: int,
        cluster_label: str,
        representative_title: str,
        instance_ids: List[int],
        confidence: float = 0.5,
    ) -> OrphanCluster:
        cluster = OrphanCluster(
            user_id=user_id,
            cluster_label=cluster_label,
            representative_title=representative_title,
            confidence=confidence,
        )
        self.session.add(cluster)
        self.session.commit()
        self.session.refresh(cluster)

        # Lier les instances au cluster
        for iid in instance_ids:
            link = ClusterInstance(
                cluster_id=cluster.id,
                instance_id=iid,
                similarity_score=confidence,
            )
            self.session.add(link)
            self.instanceRepo.mark_instance_clustered(iid)

        self.session.commit()
        self.session.refresh(cluster)
        return cluster

    def add_instance_to_cluster(
        self,
        cluster_id: int,
        instance_id: int,
        similarity_score: float,
    ) -> None:
        link = ClusterInstance(
            cluster_id=cluster_id,
            instance_id=instance_id,
            similarity_score=similarity_score,
        )
        self.session.add(link)
        self.instanceRepo.mark_instance_clustered(instance_id)
        self.session.commit()

    def get_active_clusters(self, user_id: int) -> List[OrphanCluster]:
        statement = (
            select(OrphanCluster)
            .where(OrphanCluster.user_id == user_id)
            .where(OrphanCluster.status == ClusterStatus.ACTIVE)
        )
        return list(self.session.exec(statement).all())

    def promote_cluster_to_template(
        self,
        cluster_id: int,
        **template_kwargs,
    ) -> Optional[TaskTemplate]:
        """Promeut un cluster en template et relie toutes ses instances."""
        cluster = self.session.get(OrphanCluster, cluster_id)
        if not cluster:
            return None

        # Créer le template
        template = self.templateRepo.create_template(
            user_id=cluster.user_id,
            title=cluster.representative_title,
            origin=TaskOrigin.DETECTED,
            confidence=cluster.confidence,
            **template_kwargs,
        )

        # Mettre à jour le cluster
        cluster.status = ClusterStatus.PROMOTED
        cluster.promoted_to_template_id = template.id
        cluster.promoted_at = now_utc()
        cluster.updated_at = now_utc()

        # Rattacher les instances orphelines au nouveau template
        statement = select(ClusterInstance).where(ClusterInstance.cluster_id == cluster_id)
        links = list(self.session.exec(statement).all())

        for link in links:
            self.instanceRepo.mark_instance_matched(link.instance_id, template.id)

        self.session.commit()
        self.session.refresh(template)
        return template