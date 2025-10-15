from datetime import datetime, timezone, timedelta
from Calendars import Calendars
from Weather import Weather

class DailyBrief :
    calendars : Calendars = None
    weather : Weather = None

    def __init__(self):
        self.calendars = Calendars()
        self.weather = Weather()

    def set_calendar_event(self) :
        events = self.calendars.get_apple_calendar_events("Travail", datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(days=7))
        self.calendars.set_events(events)

    def set_weather_report(self) :
        self.weather.get_weather_report()

    def get_information_JSON(self) : 
        return {
            'calendars' : self.calendars.Get_Events_JSON(),
            'weather' : self.weather.Get_Weather_JSON()
        }

                
DB = DailyBrief()
DB.set_calendar_event()
DB.set_weather_report()
print(DB.get_information_JSON())
