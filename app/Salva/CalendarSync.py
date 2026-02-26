from typing import Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from icalendar import Calendar
import logging

from sqlmodel import Session
from Salva.models import TaskInstance, TaskOrigin, TaskStatus
from Salva.Repository.Instances import InstancesRepository 
from Salva.Calendars import Calendars

logger = logging.getLogger(__name__)


class CalendarSync:
    """Pont entre la classe Calendars (iCloud) et TaskRepository (DB).

    Responsabilités :
        - Pull  : events iCloud absents en base → instances PENDING
        - Push  : instances DB sans event iCloud → création dans iCloud
        - Sync  : pull + push en un appel
        - Delete: suppression d'un event iCloud lors d'une annulation
    """

    def __init__(self, session: Session, calendars: Calendars):
        self.InstancesRepo = InstancesRepository(session)
        self.cal = calendars

    ICAL_TO_DB_FIELDS = {
        "summary": "title",
        "start": "scheduled_start",
        "end": "scheduled_end",
        "description": "description",
        "location": "location",
        "location_lat": "location_lat",
        "location_lon": "location_lon",
        "url": "url",
        "alerts_minutes": "alerts_minutes",
    }

    # ============================================
    # PULL : iCloud → DB
    # ============================================

    def pull_events(
        self,
        user_id: int,
        calendar_name: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[TaskInstance]:
        """Importe les events iCloud absents en base comme instances PENDING."""

        raw_events = self.cal.get_apple_calendar_events(calendar_name, start_date, end_date)
        if not raw_events:
            logger.info(f"Aucun event dans '{calendar_name}' pour cette période.")
            return []

        created = []
        updated = []

        for raw_event in raw_events:
            parsed = self._parse_ical_event(raw_event)
            if not parsed:
                continue

            uid = parsed["uid"]
            existant = self.InstancesRepo.get_instance_by_calendar_event(uid)
            if existant:
                changes = self._diff(existant, parsed)
                if changes:
                    self.InstancesRepo.update_instance(existant.calendar_event_id, **changes)
                    logger.info(f"Mis à jour : '{parsed['summary']}' → instance #{existant.id}")
                    updated.append(existant)
            else:
                instance = self._create_from_parsed(user_id, calendar_name, parsed)
                logger.info(f"Importé : '{parsed['summary']}' → instance #{instance.id}")
                created.append(instance)

        logger.info(f"{len(created)} events importés depuis '{calendar_name}'.")
        return created
    
    def _create_from_parsed(self, user_id: int, calendar_name: str, parsed: dict) -> TaskInstance:
        """Crée une instance à partir des données iCal parsées."""
        start = parsed["start"]
        end = parsed["end"]
        return self.InstancesRepo.create_instance(
            user_id=user_id,
            title=parsed["summary"],
            scheduled_start=start,
            scheduled_end=end or start + timedelta(hours=1),
            origin=TaskOrigin.CALENDAR,
            calendar_event_id=parsed["uid"],
            calendar_name=calendar_name,
            description=parsed["description"],
            location=parsed["location"],
            location_lat=parsed["location_lat"],
            location_lon=parsed["location_lon"],
            url=parsed["url"],
            alerts_minutes=parsed["alerts_minutes"],
        )
    
    def _diff(self, instance: TaskInstance, parsed: dict) -> dict:
        """Compare une instance DB avec les données iCal parsées.

        Returns:
            dict des champs DB à mettre à jour (vide si rien n'a changé)
        """
        changes = {}

        for ical_key, db_field in self.ICAL_TO_DB_FIELDS.items():
            new_value = parsed.get(ical_key)
            current_value = getattr(instance, db_field, None)

            # Gérer le cas "end" → fallback 1h si None
            if ical_key == "end" and new_value is None:
                new_value = parsed["start"] + timedelta(hours=1)

            if not self._values_equal(current_value, new_value):
                changes[db_field] = new_value

        # Si le titre change, recalculer le normalized_title
        if "title" in changes:
            from models import normalize_title
            changes["normalized_title"] = normalize_title(changes["title"])

        return changes

    @staticmethod
    def _values_equal(current, new) -> bool:
        """Comparaison tolérante entre valeur DB et valeur iCal."""
        if current is None and new is None:
            return True
        if current is None or new is None:
            return False

        # Comparer les datetimes en ignorant les microsecondes
        if isinstance(current, datetime) and isinstance(new, datetime):
            return current.replace(microsecond=0) == new.replace(microsecond=0)

        # Comparer les floats avec tolérance (coordonnées GPS)
        if isinstance(current, float) and isinstance(new, float):
            return abs(current - new) < 1e-6

        # Comparer les listes (alerts)
        if isinstance(current, list) and isinstance(new, list):
            return sorted(current) == sorted(new)

        return current == new

    # ============================================
    # PUSH : DB → iCloud
    # ============================================

    def push_instance(
        self,
        instance : TaskInstance,
    ) -> Optional[TaskInstance]:
        """Planifie une nouvelle tâche : iCloud d'abord, puis DB.

        Returns:
            L'instance créée, ou None si le push iCloud a échoué.
        """

        # exists = self.InstancesRepo.find_duplicate(user_id, title, scheduled_start)
        # if exists:
        #     logger.warning(f"Instance similaire existe déjà (id={exists.id}) pour '{title}' à {scheduled_start}. Push ignoré.")
        #     return None

        # 1. iCloud d'abord
        event_uid = self.cal.add_complete_todo(
            summary=instance.title,
            start_time=instance.scheduled_start,
            end_time=instance.scheduled_end,
            calendar_name=instance.calendar_name,
            description=instance.description,
            alerts=instance.alerts_minutes,
            location=instance.location,
            url=instance.url,
        )

        if not event_uid:
            logger.error(f"Échec push '{instance.title}' vers iCloud. Rien créé en base.")
            return None

        # 2. Succès iCloud → créer en base
        instance = self.InstancesRepo.update_instance_by_id(
            instance.id,
            calendar_event_id = event_uid
        )

        logger.info(f"'{instance.title}' → iCloud (uid={event_uid}) + DB (instance #{instance.id})")
        return instance

    # ============================================
    # DELETE : suppression iCloud
    # ============================================

    def delete_event(self, calendar_name: str, event_uid: str, start_date : datetime, end_date: datetime) -> bool:
        if self.cal.delete_event_from_calendar(calendar_name, event_uid, start_date, end_date) :
            self.InstancesRepo.mark_instance_deleted(event_uid)

    def cancel_and_delete(self, instance_id: int) -> bool:
        """Annule une instance en base ET supprime l'event iCloud correspondant."""

        instance = self.InstancesRepo.get_instance(instance_id)
        if not instance:
            logger.error(f"Instance #{instance_id} introuvable.")
            return False

        # Supprimer côté iCloud si l'event existe
        if instance.calendar_event_id and instance.calendar_name:
            self.delete_event(instance.calendar_name, instance.calendar_event_id)

        # Annuler en base
        self.InstancesRepo.cancel_instance(instance_id)
        logger.info(f"Instance #{instance_id} annulée et supprimée d'iCloud.")
        return True

    # ============================================
    # SYNC BIDIRECTIONNEL
    # ============================================

    def sync(
        self,
        user_id: int,
        calendar_name: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """Synchronisation complète :
            1. Pull les nouveaux events iCloud → instances PENDING
            2. Push les instances système sans event iCloud → iCloud

        Returns:
            {"pulled": [...], "pushed": [...]}
        """

        # 1. Pull
        pulled = self.pull_events(user_id, calendar_name, start_date, end_date)

        self.check_instances_in_icloud(user_id, calendar_name, start_date, end_date)

        # 2. Push — seulement les instances créées par le système, pas encore dans iCloud
        all_instances = self.InstancesRepo.get_user_instances(
            user_id, start=start_date, end=end_date
        )
        to_push = [
            inst for inst in all_instances
            if inst.calendar_event_id is None and inst.origin != TaskOrigin.CALENDAR
        ]

        pushed = []
        for instance in to_push:
            if self.push_instance(
                instance
            ):
                pushed.append(instance)

        logger.info(f"Sync : {len(pulled)} importés, {len(pushed)} poussés.")
        return {"pulled": pulled, "pushed": pushed}
    
    # ============================================
    # CHECK si instances existes encore dans icloud
    # ============================================

    def check_instances_in_icloud(
            self,
            user_id: int,
            calendar_name: str,
            start_date: datetime,
            end_date: datetime,
    ):
        """Vérifie que les instances avec calendar_event_id existent toujours dans iCloud.

        Si un event iCloud a été supprimé manuellement, l'instance correspondante est annulée en base.
        """
        instances = self.InstancesRepo.get_user_instances(
            user_id, start=start_date, end=end_date, status=TaskStatus.SCHEDULED
        )
        for inst in instances:
            if inst.calendar_event_id and inst.calendar_name:
                exists = self.cal.check_event_exists(inst.calendar_name, inst.calendar_event_id, start_date, end_date)
                if not exists:
                    self.InstancesRepo.cancel_instance(inst.id)
                    print(f"Instance #{inst.id} annulée car event iCloud (uid={inst.calendar_event_id}) introuvable.")
                else :
                    print(f"Instance #{inst.id} exist toujours dans iCloud.")

    # ============================================
    # PARSING iCal
    # ============================================

    def _parse_ical_event(self, raw_event) -> Optional[dict]:
        """Extrait les champs utiles d'un event caldav brut.

        Returns:
            dict avec uid, summary, start, end, description, location,
            location_lat, location_lon, url, alerts_minutes
        """
        try:
            ics_data = raw_event.data if hasattr(raw_event, "data") else raw_event._get_data()
            cal = Calendar.from_ical(ics_data)

            for component in cal.walk():
                if component.name == "VEVENT":
                    uid = str(component.get("UID", ""))
                    summary = str(component.get("SUMMARY", "Sans titre"))

                    dtstart = component.get("DTSTART")
                    dtend = component.get("DTEND")

                    start = dtstart.dt if dtstart else None
                    end = dtend.dt if dtend else None

                    if not uid or not start:
                        logger.warning(f"Event ignoré (uid/start manquant) : {summary}")
                        return None

                    # Dates naïves → UTC
                    if hasattr(start, "hour") and start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    if end and hasattr(end, "hour") and end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)

                    # Description
                    description = str(component.get("DESCRIPTION", "")) or None

                    # Location
                    location = str(component.get("LOCATION", "")) or None

                    # Coordonnées GPS depuis X-APPLE-STRUCTURED-LOCATION
                    lat, lon = self._extract_coordinates(component)

                    # URL
                    url_val = component.get("URL")
                    url = str(url_val) if url_val else None

                    # Alertes (VALARM)
                    alerts = self._extract_alerts(component)

                    return {
                        "uid": uid,
                        "summary": summary,
                        "start": start,
                        "end": end,
                        "description": description,
                        "location": location,
                        "location_lat": lat,
                        "location_lon": lon,
                        "url": url,
                        "alerts_minutes": alerts if alerts else None,
                    }

        except Exception as e:
            logger.error(f"Erreur parsing iCal : {e}")

        return None

    def _extract_alerts(self, component) -> List[int]:
        """Extrait les durées d'alerte en minutes depuis les VALARM."""
        alerts = []
        for sub in component.subcomponents:
            if sub.name == "VALARM":
                trigger = sub.get("TRIGGER")
                if trigger and trigger.dt:
                    # trigger.dt est un timedelta négatif (ex: -15min)
                    minutes = abs(int(trigger.dt.total_seconds() / 60))
                    alerts.append(minutes)
        return sorted(set(alerts))

    def _extract_coordinates(self, component) -> Tuple[Optional[float], Optional[float]]:
        """Extrait lat/lon depuis X-APPLE-STRUCTURED-LOCATION ou GEO."""
        # Essayer GEO standard (format: "lat;lon")
        geo = component.get("GEO")
        if geo:
            try:
                return float(geo.latitude), float(geo.longitude)
            except Exception:
                pass

        # Essayer X-APPLE-STRUCTURED-LOCATION (format: geo:lat,lon)
        structured = component.get("X-APPLE-STRUCTURED-LOCATION")
        if structured:
            value = str(structured)
            if "geo:" in value:
                try:
                    coords = value.split("geo:")[1].split(",")
                    return float(coords[0]), float(coords[1])
                except (IndexError, ValueError):
                    pass

        return None, None