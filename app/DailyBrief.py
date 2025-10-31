from datetime import datetime, timezone, timedelta
from Daily.Calendars import Calendars
from Daily.Weather import Weather
from Daily.CDB import DBCCollection
from Daily.Ollama import Ollama

import argparse



class DailyBrief :
    _COLLECTION_NAME = "article"
    _CALENDARS_NAME = "Travail"
    calendars : Calendars = None
    weather : Weather = None
    ollama : Ollama = None
    chroma : DBCCollection = None
    response : str = None

    def __init__(self, opt):
        self._options = opt

        self._COLLECTION_NAME = self._options.collection_name

        self.calendars = Calendars()
        self.weather = Weather()
        self.chroma = DBCCollection(self._COLLECTION_NAME)
        self.ollama = Ollama()

    def set_calendar_event(self) :
        events = self.calendars.get_apple_calendar_events(self._CALENDARS_NAME, datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(days=7))
        self.calendars.set_events(events)

    def set_weather_report(self) :
        self.weather.get_weather_report()

    def set_Articles_Informations(self, question):
        self.chroma.set_article_informations(question)

    def get_information_JSON(self) : 
        return {
            'calendars' : self.calendars.Get_Events_JSON(),
            'weather' : self.weather.Get_Weather_JSON(),
            'articles' : self.chroma.Get_Article_JSON()
        }
    
    def get_daily_brief_LLM(self) :
        self.set_calendar_event()
        self.set_weather_report()

        if getattr(self._options, 'collection_activation', False):
            self.set_Articles_Informations(self._options.question)

        self.ollama.query(self.get_information_JSON())

def main(opt):
    DB = DailyBrief(opt)
    DB.get_daily_brief_LLM()

def get_options():
    """
        Configures a parser. 
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--collection-activation",
        action="store_true",
        help="Activation of collection process",
    )
    parser.add_argument(
        "--question",
        type=str,
        default="",
        help="Question for calculate distance in vectorial database"
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default="",
        help="Name of collection in you'r chroma database"
    )
    return parser.parse_args()

if __name__ == "__main__":
    main(get_options())