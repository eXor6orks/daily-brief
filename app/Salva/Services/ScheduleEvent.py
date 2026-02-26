from Salva.Repository.Instances import InstancesRepository
from Salva.Repository.Templates import TemplatesRepository
from sqlmodel import Session
from Salva.models import (
    TaskTemplate,
    RecurrencePattern,
    TaskOrigin,
    TaskStatus,
    )

from datetime import date, datetime, timedelta, timezone, time
from typing import Optional, List

jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

class ScheduleEvent :

    def __init__(self, session : Session):
        self.session = session
        self.InsRep = InstancesRepository(session)
        self.TemRep = TemplatesRepository(session)

    def calcul_new_week(self) :
        today = datetime.now().weekday()
        date_now = datetime.now()
        if jours[today] == "Dimanche" :
            Templates = self.TemRep.get_user_templates(1)
            for template in Templates :
                prefs = template.recurrence_data
                if template.recurrence_pattern == RecurrencePattern.DAILY :
                    print(f"Template {template.title} : Toutes la semaine à {prefs['time']}")
                elif template.recurrence_pattern == RecurrencePattern.WEEKLY :
                    if len(prefs["days"]) == 1 :
                        self._create_instance(template, date_now + timedelta(days=prefs["days"][0]))
                    else :
                        for jour in prefs["days"] :
                            self._create_instance(template, date_now + timedelta(days=jour))
                elif template.recurrence_pattern == RecurrencePattern.BIWEEKLY :
                    if self._should_schedule_biweekly(template.id) :
                        if prefs :
                            self._create_instance(template, date_now + timedelta(days=prefs["days"][0]))
                elif template.recurrence_pattern == RecurrencePattern.MONTHLY :
                    if self._should_schedule_monthly(template.id) :
                        if prefs :
                            self._create_instance(template, date_now + timedelta(days=prefs["days"][0]))
            return
        else :
            print(f"Aujourd'hui nous sommes {jours[today]}, je n'ai créer l'emploie du temps que le Dimanche.")
            print(f"De nouvelle amélioration arriverons prochainement.")

    def _should_schedule_biweekly(self, template_id: int) -> bool:
        """Vérifie si la tâche biweekly doit être planifiée cette semaine.
        
        Règle : si la dernière instance est dans la semaine passée, on skip.
        """
        last = self.InsRep.get_last_instance_by_template(template_id)
        if not last:
            return True

        last_date = last.scheduled_start.date() if hasattr(last.scheduled_start, 'date') else last.scheduled_start
        today = date.today()
        days_since = (today - last_date).days

        # Si fait il y a moins de 7 jours → skip
        return days_since >= 7  

    
    def _should_schedule_monthly(self, template_id: int) -> bool:
        """Vérifie si la tâche monthly doit être planifiée cette semaine.
        
        Règle : si la dernière instance date de moins de 3 semaines, on skip.
        """
        last = self.InsRep.get_last_instance_by_template(template_id)
        if not last:
            return True

        last_date = last.scheduled_start.date() if hasattr(last.scheduled_start, 'date') else last.scheduled_start
        today = date.today()
        days_since = (today - last_date).days

        # Si fait il y a moins de 21 jours → skip
        return days_since >= 21              
        
    def _create_instance(
                self,
                template: TaskTemplate,
                day: date
            ) :
        prefs = template.recurrence_data
        pref_time = self._parse_time(prefs['time'])
        start = datetime.combine(day, pref_time, tzinfo=timezone.utc)
        end = start + timedelta(minutes=template.estimated_duration or 60)

        print(f"{template.title} : {start}")

        existing = self.InsRep.find_duplicate(template.user_id, template.title, start)

        if existing :
            return None

        instance = self.InsRep.create_instance(
            user_id=template.user_id,
            title=template.title,
            scheduled_start=start,
            scheduled_end=end,
            origin=TaskOrigin.SYSTEM,
            template_id=template.id,
            description=template.description,
            priority=template.priority,
            calendar_name="Travail",
            status=TaskStatus.SCHEDULED
        )

        # Mettre à jour le template
        self.TemRep.update_template(
            template.id,
            last_instance_created_at=datetime.now(timezone.utc),
            next_suggested_date=day,
        )
    
    @staticmethod
    def _parse_time(time_str: Optional[str]) -> time:
        """Parse '10:00' en objet time. Défaut 09:00."""
        if not time_str:
            return time(9, 0)
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))