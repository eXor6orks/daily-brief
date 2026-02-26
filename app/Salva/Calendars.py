import os
import caldav
from icalendar import Calendar, Todo, Event, Alarm
import uuid
from caldav import DAVClient
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from typing import Optional, List
load_dotenv()

ICLOUD_URL = os.getenv("ICLOUD_URL")
ICLOUD_USERNAME = os.getenv("ICLOUD_USERNAME")
ICLOUD_APP_PASSWORD = os.getenv("ICLOUD_PW")

class EventNew() :
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

        self.principal = self.client.principal()
        self.calendars = self.principal.calendars()

    def get_caldav_client(self):
        return DAVClient(
            url=ICLOUD_URL,
            username=ICLOUD_USERNAME,
            password=ICLOUD_APP_PASSWORD
        )

    def discover_caldav_calendars(self):
        try:
            if self.calendars:
                print("Available calendars:")
                for calendar in self.calendars:
                    print(f"- {calendar.name} (URL: {calendar.url})")
            else:
                print("No calendars found.")
            
            return ICLOUD_URL
    
        except caldav.lib.error.AuthorizationError as e:
            print(f"Authorization failed: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")
        
        return None
    
    def set_events(self, events) :
        for event in events:
            ics_data = event._get_data()
            cal = Calendar.from_ical(ics_data)

            for component in cal.walk():
                if component.name == "VEVENT":
                    self.events.append(EventNew(
                        uid=component.get("UID"),
                        summary=str(component.get("SUMMARY", "Sans titre")),
                        start=component.get("DTSTART").dt,
                        end=component.get("DTEND").dt if component.get("DTEND") else None
                    ))

    def get_apple_calendar_events(self, calendar_name, start_date, end_date):        
        calendar = next((cal for cal in self.calendars if cal.name == calendar_name), None)
        
        if calendar:
            events = calendar.search(start=start_date, end=end_date)
            return events
        else:
            print(f"Calendar '{calendar_name}' not found.")
            return None

    def update_event_in_calendar(self, calendar_name, event_uid, summary, start_time, end_time):
        # TODO
        pass

    def delete_event_from_calendar(self, calendar_name, event_uid, start_date, end_date):
        calendar = next((cal for cal in self.calendars if cal.name == calendar_name), None)
        if not calendar:
            print(f"Calendar '{calendar_name}' not found.")
            return False

        try:
            events = calendar.search(start=start_date, end=end_date)
            for event in events:
                ics_data = event.data if hasattr(event, "data") else event._get_data()
                if event_uid in ics_data:
                    event.delete()
                    print(f"Event {event_uid} supprimé de '{calendar_name}'.")
                    return True
            print(f"Event {event_uid} introuvable dans '{calendar_name}'.")
            return False
        except Exception as e:
            print(f"Erreur suppression event {event_uid}: {e}")
            return False
    
    def Get_Events_JSON(self) :
        return {'events' : [event.get_Event() for event in self.events]}
    
    def check_event_exists(self, calendar_name, event_uid, start_date, end_date):
        calendar = next((cal for cal in self.calendars if cal.name == calendar_name), None)
        if not calendar:
            print(f"Calendar '{calendar_name}' not found.")
            return False
        
        events = calendar.search(start=start_date, end=end_date)
        for event in events:
            ics_data = event.data if hasattr(event, "data") else event._get_data()
            if event_uid in ics_data:
                return True
        return False
        
    def add_complete_todo(
        self,
        summary,
        start_time,
        end_time,
        calendar_name,
        description=None,
        alerts=None,
        location=None,
        url=None,
    ) -> str | bool :
        """TODO complet avec toutes les options"""
        calendar = next((cal for cal in self.calendars if cal.name == calendar_name), None)
        
        if not calendar:
            return False
        
        cal = Calendar()
        cal.add('prodid', '-//DailyBrief//EN')
        cal.add('version', '2.0')
        
        event = Event()
        event.add('summary', summary)
        event.add('dtstart', start_time)
        event.add('dtend', end_time)
        event.add('dtstamp', datetime.now())
        event.add('uid', str(uuid.uuid4()))
        
        # Description avec checklist
        if description:
            event.add('description', description)
        
        # Alertes
        if alerts:
            for minutes in alerts:
                alarm = Alarm()
                alarm.add('action', 'DISPLAY')
                alarm.add('description', summary)
                alarm.add('trigger', timedelta(minutes=-minutes))
                event.add_component(alarm)
        
        # Lieu
        if location:
            event.add('location', location)
        
        # URL
        if url:
            event.add('url', url)
        
        cal.add_component(event)
        
        try:
            calendar.add_event(cal.to_ical().decode('utf-8'))
            print(f"✓ TODO créé : {summary}")
            print(f"  ⏰ Alertes: {len(alerts) if alerts else 0}")
            print(f"  📍 Lieu: {location or 'aucun'}")
            print(f"  🔗 URL: {url or 'aucune'}")
            return event['uid']
        except Exception as e:
            print(f"✗ Erreur: {e}")
            return False