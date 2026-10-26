"""WMO weather interpretation codes, as used by Open-Meteo (`weather_code` variable).

Source: https://open-meteo.com/en/docs (section "WMO Weather interpretation codes").
"""

from app.core.language import Language

# code → (en, uk, cs, ru); the column order follows `_COLUMNS`.
_COLUMNS = (Language.EN, Language.UK, Language.CS, Language.RU)
_DESCRIPTIONS: dict[int, tuple[str, str, str, str]] = {
    0: ("Clear sky", "Ясне небо", "Jasno", "Ясное небо"),
    1: ("Mainly clear", "Переважно ясно", "Převážně jasno", "Преимущественно ясно"),
    2: ("Partly cloudy", "Мінлива хмарність", "Polojasno", "Переменная облачность"),
    3: ("Overcast", "Хмарно", "Zataženo", "Пасмурно"),
    45: ("Fog", "Туман", "Mlha", "Туман"),
    48: ("Depositing rime fog", "Туман з памороззю", "Mlha s námrazou", "Туман с изморозью"),
    51: ("Light drizzle", "Слабка мряка", "Slabé mrholení", "Слабая морось"),
    53: ("Moderate drizzle", "Помірна мряка", "Mírné mrholení", "Умеренная морось"),
    55: ("Dense drizzle", "Сильна мряка", "Silné mrholení", "Сильная морось"),
    56: (
        "Light freezing drizzle",
        "Слабка крижана мряка",
        "Slabé mrznoucí mrholení",
        "Слабая ледяная морось",
    ),
    57: (
        "Dense freezing drizzle",
        "Сильна крижана мряка",
        "Silné mrznoucí mrholení",
        "Сильная ледяная морось",
    ),
    61: ("Slight rain", "Невеликий дощ", "Slabý déšť", "Небольшой дождь"),
    63: ("Moderate rain", "Помірний дощ", "Mírný déšť", "Умеренный дождь"),
    65: ("Heavy rain", "Сильний дощ", "Silný déšť", "Сильный дождь"),
    66: (
        "Light freezing rain",
        "Слабкий крижаний дощ",
        "Slabý mrznoucí déšť",
        "Слабый ледяной дождь",
    ),
    67: (
        "Heavy freezing rain",
        "Сильний крижаний дощ",
        "Silný mrznoucí déšť",
        "Сильный ледяной дождь",
    ),
    71: ("Slight snowfall", "Невеликий сніг", "Slabé sněžení", "Небольшой снег"),
    73: ("Moderate snowfall", "Помірний сніг", "Mírné sněžení", "Умеренный снег"),
    75: ("Heavy snowfall", "Сильний снігопад", "Silné sněžení", "Сильный снегопад"),
    77: ("Snow grains", "Снігова крупа", "Sněhová zrna", "Снежная крупа"),
    80: ("Slight rain showers", "Невелика злива", "Slabé přeháňky", "Небольшой ливень"),
    81: ("Moderate rain showers", "Злива", "Přeháňky", "Ливень"),
    82: ("Violent rain showers", "Сильна злива", "Silné přeháňky", "Сильный ливень"),
    85: (
        "Slight snow showers",
        "Короткочасний сніг",
        "Sněhové přeháňky",
        "Кратковременный снег",
    ),
    86: (
        "Heavy snow showers",
        "Сильний короткочасний сніг",
        "Silné sněhové přeháňky",
        "Сильный кратковременный снег",
    ),
    95: ("Thunderstorm", "Гроза", "Bouřka", "Гроза"),
    96: (
        "Thunderstorm with slight hail",
        "Гроза з невеликим градом",
        "Bouřka se slabým krupobitím",
        "Гроза с небольшим градом",
    ),
    99: (
        "Thunderstorm with heavy hail",
        "Гроза з сильним градом",
        "Bouřka se silným krupobitím",
        "Гроза с сильным градом",
    ),
}
_UNKNOWN = ("Unknown", "Невідомо", "Neznámé", "Неизвестно")

WMO_WEATHER_CODES = tuple(_DESCRIPTIONS)


def describe_weather_code(code: int, language: Language = Language.EN) -> str:
    return _DESCRIPTIONS.get(code, _UNKNOWN)[_COLUMNS.index(language)]
