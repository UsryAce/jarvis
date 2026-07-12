"""Weather skill for Jarvis."""
import aiohttp
from typing import Any, Dict

from src.skills.registry import Skill
from src.config import config


class WeatherSkill(Skill):
    """Weather information skill."""

    name = "weather"
    description = "Get current weather and forecasts"
    triggers = ["weather", "temperature", "forecast", "rain", "sunny", "cloudy"]

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        """Get weather information."""
        text = context.get("text", "") if context else ""
        location = params.get("location", self._extract_location(text))

        if not location:
            return "Where would you like the weather for? Example: weather in New York"

        api_key = config.get("external_apis.weather")
        if not api_key:
            return "Weather API not configured. Set WEATHER_API_KEY environment variable."

        return await self._get_weather(location, api_key)

    def _extract_location(self, text: str) -> str:
        """Extract location from text."""
        # Simple extraction - look for "in <location>" or "for <location>"
        import re
        match = re.search(r'\b(in|for|at)\s+([A-Za-z\s,]+)', text, re.IGNORECASE)
        if match:
            return match.group(2).strip()
        # Fallback: last word(s)
        words = text.split()
        if len(words) > 1:
            return " ".join(words[-2:])
        return ""

    async def _get_weather(self, location: str, api_key: str) -> str:
        """Get weather from OpenWeatherMap API."""
        # First, get coordinates
        geo_url = "http://api.openweathermap.org/geo/1.0/direct"
        geo_params = {"q": location, "limit": 1, "appid": api_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(geo_url, params=geo_params) as response:
                    geo_data = await response.json()
                    if not geo_data:
                        return f"Could not find location: {location}"

                lat = geo_data[0]["lat"]
                lon = geo_data[0]["lon"]
                city_name = geo_data[0].get("name", location)
                country = geo_data[0].get("country", "")

                # Get current weather
                weather_url = "https://api.openweathermap.org/data/2.5/weather"
                weather_params = {
                    "lat": lat,
                    "lon": lon,
                    "appid": api_key,
                    "units": "metric",
                }

                async with session.get(weather_url, params=weather_params) as response:
                    weather_data = await response.json()

                temp = weather_data["main"]["temp"]
                feels_like = weather_data["main"]["feels_like"]
                humidity = weather_data["main"]["humidity"]
                description = weather_data["weather"][0]["description"].capitalize()
                wind_speed = weather_data["wind"]["speed"]

                return (
                    f"Weather in {city_name}, {country}:\n"
                    f"🌡️ Temperature: {temp:.1f}°C (feels like {feels_like:.1f}°C)\n"
                    f"☁️ Conditions: {description}\n"
                    f"💧 Humidity: {humidity}%\n"
                    f"💨 Wind: {wind_speed} m/s"
                )

        except Exception as e:
            return f"Weather error: {e}"