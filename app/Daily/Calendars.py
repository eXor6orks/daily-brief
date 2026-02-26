import os
import caldav
from icalendar import Calendar, Todo
from caldav import DAVClient
import datetime
from dotenv import load_dotenv
load_dotenv()

ICLOUD_URL = os.getenv("ICLOUD_URL")
ICLOUD_USERNAME = os.getenv("ICLOUD_USERNAME")
ICLOUD_APP_PASSWORD = os.getenv("ICLOUD_PW")

class Event() :
    def __init__(self, uid, summary, start, end):
        self.uid = uid
        self.summary = summary
        self.start = start
        self.end = end

    def get_Event(self):
        return {
            'uid' : self.uid,
            'summary' : self.summary,
            'start' : self.start,
            'end' : self.end
        }

    def __str__(self):
        return f"Event(uid={self.uid}, summary={self.summary}, start={self.start}, end={self.end})\n"


class Task():
    def __init__(self, uid, summary, status, due=None, completed=None, priority=None, percent_complete=None):
        self.uid = uid
        self.summary = summary
        self.status = status  # NEEDS-ACTION, COMPLETED, IN-PROCESS, CANCELLED
        self.due = due
        self.completed = completed
        self.priority = priority  # 1-9 (1 = highest)
        self.percent_complete = percent_complete

    def get_Task(self):
        return {
            'uid': self.uid,
            'summary': self.summary,
            'status': self.status,
            'due': self.due,
            'completed': self.completed,
            'priority': self.priority,
            'percent_complete': self.percent_complete
        }

    def __str__(self):
        return f"Task(uid={self.uid}, summary={self.summary}, status={self.status}, due={self.due})\n"


"""
    Class to manage Icloud calendars.

    You can take event from Icloud calendars but you can too
    add and update events.

    This code is inspired from : 
"""
class Calendars() :

    events = []

    tasks = []

    def __init__(self):
        self.client = self.get_caldav_client()

    def get_caldav_client(self):
        return DAVClient(
            url=ICLOUD_URL,
            username=ICLOUD_USERNAME,
            password=ICLOUD_APP_PASSWORD
        )

    def discover_caldav_calendars(self):
        try:
            principal = self.client.principal()
            print(f"Principal URL: {principal.url}")
            
            calendars = principal.calendars()
            
            if calendars:
                print("Available calendars:")
                for calendar in calendars:
                    print(f"- {calendar.name} (URL: {calendar.url})")
            else:
                print("No calendars found.")
            
            return ICLOUD_URL
    
        except caldav.lib.error.AuthorizationError as e:
            print(f"Authorization failed: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")
        
        return None

    def get_apple_calendar_events(self, calendar_name, start_date, end_date):
        principal = self.client.principal()
        calendars = principal.calendars()
        
        calendar = next((cal for cal in calendars if cal.name == calendar_name), None)
        
        if calendar:
            events = calendar.search(start=start_date, end=end_date)
            return events
        else:
            print(f"Calendar '{calendar_name}' not found.")
            return None

    def set_events(self, events) :
        for event in events:
            ics_data = event._get_data()
            cal = Calendar.from_ical(ics_data)

            for component in cal.walk():
                if component.name == "VEVENT":
                    self.events.append(Event(
                        uid=component.get("UID"),
                        summary=str(component.get("SUMMARY", "Sans titre")),
                        start=component.get("DTSTART").dt,
                        end=component.get("DTEND").dt if component.get("DTEND") else None
                    ))

    def add_event_to_calendar(self, calendar_name, summary, start_time, end_time):
        principal = self.client.principal()
        calendars = principal.calendars()
        
        calendar = next((cal for cal in calendars if cal.name == calendar_name), None)
        
        if calendar:
            event = calendar.save_event(
                dtstart=start_time,
                dtend=end_time,
                summary=summary
            )
            return True
        else:
            print(f"Calendar '{calendar_name}' not found.")
            return False

    def update_event_in_calendar(self, calendar_name, event_uid, summary, start_time, end_time):
        principal = self.client.principal()
        calendars = principal.calendars()
        
        calendar = next((cal for cal in calendars if cal.name == calendar_name), None)
        
        if calendar:
            event = calendar.event(event_uid)
            event.load()
            event.instance.vevent.summary.value = summary
            event.instance.vevent.dtstart.value = start_time
            event.instance.vevent.dtend.value = end_time
            event.save()
            return True
        else:
            print(f"Calendar '{calendar_name}' not found.")
            return False

    def delete_event_from_calendar(self, calendar_name, event_uid):
        principal = self.client.principal()
        calendars = principal.calendars()
        
        calendar = next((cal for cal in calendars if cal.name == calendar_name), None)
        
        if calendar:
            event = calendar.event(event_uid)
            event.delete()
            return True
        else:
            print(f"Calendar '{calendar_name}' not found.")
            return False

    def list_calendars(self):
        principal = self.client.principal()
        calendars = principal.calendars()
        
        return [{'name': cal.name, 'url': cal.url} for cal in calendars]
    
    def Get_Events_JSON(self) :
        return {'events' : [event.get_Event() for event in self.events]}
    
    def get_todos_from_calendar(self, calendar_name, start_date=None, end_date=None):
        """Récupère les TODO d'un calendrier"""
        principal = self.client.principal()
        calendars = principal.calendars()
        
        calendar = next((cal for cal in calendars if cal.name == calendar_name), None)
        
        if calendar:
            # CalDAV permet de chercher les VTODO
            todos = calendar.search(
                start=start_date,
                end=end_date,
                comp_filter='VTODO'  # Important : filtre pour les TODO
            )
            return todos
        else:
            print(f"Calendar '{calendar_name}' not found.")
            return None

    def set_tasks(self, todos):
        """Parse les TODO et les ajoute à la liste des tâches"""
        for todo in todos:
            ics_data = todo._get_data()
            cal = Calendar.from_ical(ics_data)

            for component in cal.walk():
                if component.name == "VTODO":
                    self.tasks.append(Task(
                        uid=component.get("UID"),
                        summary=str(component.get("SUMMARY", "Sans titre")),
                        status=str(component.get("STATUS", "NEEDS-ACTION")),
                        due=component.get("DUE").dt if component.get("DUE") else None,
                        completed=component.get("COMPLETED").dt if component.get("COMPLETED") else None,
                        priority=component.get("PRIORITY"),
                        percent_complete=component.get("PERCENT-COMPLETE")
                    ))

    def add_todo_to_calendar(self, calendar_name, summary, due_date=None, priority=5, description=None):
        """Ajoute une nouvelle tâche TODO"""
        principal = self.client.principal()
        calendars = principal.calendars()
        
        calendar = next((cal for cal in calendars if cal.name == calendar_name), None)
        
        if calendar:
            # Créer un objet VTODO
            cal = Calendar()
            todo = Todo()
            
            todo.add('summary', summary)
            todo.add('uid', f"{datetime.datetime.now().timestamp()}@myapp")
            todo.add('dtstamp', datetime.datetime.now())
            todo.add('status', 'NEEDS-ACTION')
            
            if due_date:
                todo.add('due', due_date)
            
            if priority:
                todo.add('priority', priority)
            
            if description:
                todo.add('description', description)
            
            cal.add_component(todo)
            
            # Sauvegarder dans le calendrier
            calendar.save_todo(cal.to_ical())
            return True
        else:
            print(f"Calendar '{calendar_name}' not found.")
            return False

    def complete_todo(self, calendar_name, todo_uid):
        """Marque un TODO comme complété"""
        principal = self.client.principal()
        calendars = principal.calendars()
        
        calendar = next((cal for cal in calendars if cal.name == calendar_name), None)
        
        if calendar:
            todo = calendar.todo_by_uid(todo_uid)
            todo.load()
            
            # Mettre à jour le statut
            todo.instance.vtodo.status.value = 'COMPLETED'
            todo.instance.vtodo.completed.value = datetime.datetime.now()
            todo.instance.vtodo.percent_complete.value = 100
            
            todo.save()
            return True
        else:
            print(f"Calendar '{calendar_name}' not found.")
            return False

    def update_todo(self, calendar_name, todo_uid, summary=None, due_date=None, status=None, priority=None):
        """Met à jour un TODO existant"""
        principal = self.client.principal()
        calendars = principal.calendars()
        
        calendar = next((cal for cal in calendars if cal.name == calendar_name), None)
        
        if calendar:
            todo = calendar.todo_by_uid(todo_uid)
            todo.load()
            
            if summary:
                todo.instance.vtodo.summary.value = summary
            if due_date:
                todo.instance.vtodo.due.value = due_date
            if status:
                todo.instance.vtodo.status.value = status
            if priority:
                todo.instance.vtodo.priority.value = priority
            
            todo.save()
            return True
        else:
            print(f"Calendar '{calendar_name}' not found.")
            return False

    def Get_Tasks_JSON(self):
        """Retourne les tâches en JSON"""
        return {'tasks': [task.get_Task() for task in self.tasks]}