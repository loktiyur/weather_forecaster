import asyncio
import pandas as pd
from geopy import geocoders
import httpx
import os
from dotenv import load_dotenv

##Username for the GeoNames(Should be probably later moved to the config file)
load_dotenv()
geo_name = os.environ["GEONAMES_USERNAME"]

##Connetcting and getting the coordinates of the city
async def get_place_coordinates(city_name:str, geo_name:str):
    try:
        gn = geocoders.GeoNames(username= geo_name)
        location = await asyncio.to_thread(gn.geocode,city_name)
        if location is None:
            print("Error: Unable to geocode the city name. Please check the city name or GeoNames username.")
            raise ValueError("Geocoding failed")

    except Exception as e:
            raise RuntimeError(f"Error during geocoding: {e}")
    return location.latitude, location.longitude

async def get_forecast(city_name:str, geo_name:str):

    ##Getting the coordinates of the place
    try:
        latitude, longitude = await get_place_coordinates(city_name, geo_name)
        if latitude is None or longitude is None:
            raise ValueError("Invalid coordinates received from geocoding.")
    except Exception as e:
        raise RuntimeError(f"Getting coordinates failed: {e}")

    ##Setting up important parameters
    ##hourly_forecast_variables = ["wind_speed_10m", "temperature_2m", "relative_humidity_2m"]  not used in the current implementation
    timezone = "auto"
    params = {
        'latitude': latitude,
        'longitude': longitude,
        ##'hourly': hourly_forecast_variables,  not used for now
        'daily': ["temperature_2m_max", "temperature_2m_min",'relative_humidity_2m_mean', "sunrise", "sunset"],
        'timezone': timezone
    }

    ##Connecting to the Open-Meteo API and getting the forecast data
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
        response.raise_for_status()  # Raise an error for bad responses

    ##Converting the response to JSON making it a datafarame and returning it
    data = response.json()
    daily_forecast = data.get("daily")

    if daily_forecast is None:
        raise ValueError("Error: Unable to get the forecast data. Please check the API response")

    daily_forecast_df = pd.DataFrame(daily_forecast)

    return daily_forecast_df
