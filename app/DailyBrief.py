from datetime import datetime, timezone, timedelta
from Calendars import Calendars
from Weather import Weather
from Ollama import Ollama

class DailyBrief :
    calendars : Calendars = None
    weather : Weather = None
    ollama : Ollama = None
    response : str = None

    def __init__(self):
        self.calendars = Calendars()
        self.weather = Weather()
        self.ollama = Ollama()

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
    
    def get_daily_brief_LLM(self) :
        self.set_calendar_event()
        self.set_weather_report()
        self.response = self.ollama.query(self.get_information_JSON())


if __name__ == "__main__":
    DB = DailyBrief()
    DB.get_daily_brief_LLM()
    print(DB.response)
