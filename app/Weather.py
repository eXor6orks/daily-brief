import ipapi
import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry

class Location :
    def __init__(self, latitude, longitude) :
        self.latitude = latitude
        self.longitude = longitude

    def __str__(self) :
        return f"({self.latitude}, {self.longitude})"
    
    def _get_JSON(self) :
        return {
            'Latitude' : self.latitude,
            'Longitude' : self.longitude
        }

class Position :
    def __init__(self, JSON) :
        self.city = JSON['city']
        self.region = JSON['region']
        self.country = JSON['country_name']
        self.location = Location(JSON['latitude'], JSON['longitude'])

    def _get_JSON(self) :
        return {
            'city' : self.city,
            'region' : self.region,
            'country' : self.country,
            'Location' : self.location._get_JSON()
        }

class Weather :

    df_weather_prediction = None

    def __init__(self) :
        self.position = Position(ipapi.location())

    def get_weather_report(self):
        cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
        retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
        openmeteo = openmeteo_requests.Client(session = retry_session)

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": self.position.location.latitude,
            "longitude": self.position.location.longitude,
            "timezone": "auto",
            "hourly": ["temperature_2m", "relative_humidity_2m"],
        }
        responses = openmeteo.weather_api(url, params=params)

        response = responses[0]

        hourly = response.Hourly()
        hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
        hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy()

        hourly_data = {"date": pd.date_range(
            start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
            end = pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
            freq = pd.Timedelta(seconds = hourly.Interval()),
            inclusive = "left"
        )}

        hourly_data["temperature_2m"] = hourly_temperature_2m
        hourly_data["relative_humidity_2m"] = hourly_relative_humidity_2m

        self.df_weather_prediction = pd.DataFrame(data = hourly_data)

    def Get_Weather_JSON(self) :
        return {
            'Location' : self.position._get_JSON(),
            'Prediction' : self.df_weather_prediction.head(24).to_dict(orient='records') if self.df_weather_prediction is not None else []
        }