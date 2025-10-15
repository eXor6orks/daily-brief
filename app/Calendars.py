import os
import caldav
from icalendar import Calendar
from caldav import DAVClient
import datetime
from dotenv import load_dotenv
load_dotenv()

ICLOUD_URL = os.getenv("ICLOUD_URL")
ICLOUD_USERNAME = os.getenv("ICLOUD_USERNAME")
ICLOUD_APP_PASSWORD = os.getenv("ICLOUD_PW")  # We'll use the base URL

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

class Calendars() :

    events = []

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