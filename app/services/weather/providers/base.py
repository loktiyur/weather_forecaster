import asyncio
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

from app.core.language import Language
from app.services.weather.errors import CityNotFoundError, NotACityError, NotSupportedError
from app.services.weather.schemas import CurrentWeather, DailyForecastDay, Location, Units

# The most places /locations/search returns. A region lookup scans the same number of
# candidates, so every place the search shows can be selected again by name + country + region.
MAX_SEARCH_RESULTS = 20

# The provider matches a name only in the search language (and loosely in others): "Київ"
# with language=en finds nothing, "Киев" with language=uk finds a village in Russia, and
# "Germany" with language=ru misses the country. A name without an exact match is therefore
# retried in the other languages written in the same alphabet.
CYRILLIC_LANGUAGES = (Language.UK, Language.RU)
LATIN_LANGUAGES = (Language.EN, Language.CS)
_CYRILLIC = re.compile(r"[\u0400-\u04ff]")


@dataclass(frozen=True)
class SearchResult:
    places: list[Location]
    # Set when the best match for the name is a country ("Germany" → "Germany"): the user
    # typed a country, so no single place stands for it.
    country: str | None = None

    def matches_exactly(self, name: str) -> bool:
        """True when the best match carries exactly this name (ignoring case)."""
        best = self.country or (self.places[0].name if self.places else None)
        return best is not None and best.casefold() == name.strip().casefold()


class GeocodingClient(ABC):
    """Turns a place name into coordinates. One implementation per provider."""

    @abstractmethod
    async def find(
        self, name: str, *, count: int, country_code: str | None, language: Language
    ) -> SearchResult:
        """Up to `count` candidate places, best match first, and the country the name means.

        `places` holds populated places only (cities, towns, villages). Providers also know
        countries, regions, dams, parks, airports, ...: weather "for Germany" would only be
        the weather at the country's centre point, so such entries are never returned.
        Names are in `language` where the provider supports it.
        """

    @abstractmethod
    async def get(self, place_id: int, *, language: Language) -> Location | None:
        """The populated place with this id, named in `language`; None if there is none.

        Raises `NotSupportedError` when the provider cannot look places up by id.
        """

    async def search(
        self,
        name: str,
        *,
        count: int = 5,
        country_code: str | None = None,
        language: Language = Language.EN,
    ) -> list[Location]:
        """Return up to `count` candidate places, best match first. Empty list if none."""
        found = await self._find(name, count=count, country_code=country_code, language=language)
        return found.places

    async def geocode(
        self,
        name: str,
        *,
        country_code: str | None = None,
        region: str | None = None,
        language: Language = Language.EN,
    ) -> Location:
        """Return the best match, or raise `NotACityError` / `CityNotFoundError`.

        `region` (a state, province, ...) picks one of several places with the same name in
        a country: Odessa, Texas vs Odessa, Missouri. It is compared with the region names
        in `language`.
        """
        found = await self._find(
            name,
            count=1 if region is None else MAX_SEARCH_RESULTS,
            country_code=country_code,
            language=language,
        )
        if found.country:
            # Rather than the weather of some town that also answers to "Germany".
            raise NotACityError(name, found.country)
        if region is None:
            results = found.places
        else:
            # The provider also returns fuzzy matches ("Saint Paris" for "Paris"), so the name
            # has to match as well, not only the region.
            results = [
                place
                for place in found.places
                if place.name.casefold() == name.casefold()
                and place.region
                and place.region.casefold() == region.casefold()
            ]
        if not results:
            raise CityNotFoundError(name if region is None else f"{name}, {region}")
        return results[0]

    async def _find(
        self, name: str, *, count: int, country_code: str | None, language: Language
    ) -> SearchResult:
        """`find` in `language`; without an exact match, retried in languages of the same
        alphabet. The first exact match wins (otherwise the first answer stays).

        Places found in another language are looked up again by id, so their names are in
        `language`: typing "Київ" with an English interface shows "Kyiv, Ukraine".
        """
        found = await self.find(name, count=count, country_code=country_code, language=language)
        if found.matches_exactly(name):
            return found
        alphabet = CYRILLIC_LANGUAGES if _CYRILLIC.search(name) else LATIN_LANGUAGES
        for fallback in alphabet:
            if fallback is language:
                continue
            retry = await self.find(name, count=count, country_code=country_code, language=fallback)
            if retry.matches_exactly(name):
                return await self._translate(retry, language)
        return found

    async def _translate(self, found: SearchResult, language: Language) -> SearchResult:
        try:
            places = await asyncio.gather(
                *(self._translated(place, language) for place in found.places)
            )
        except NotSupportedError:
            return found  # no lookup by id: keep the names in the language that found them
        return SearchResult(list(places), country=found.country)

    async def _translated(self, place: Location, language: Language) -> Location:
        if place.id is None:
            return place
        return await self.get(place.id, language=language) or place


class WeatherClient(Protocol):
    """Weather data for coordinates. `OpenMeteoWeatherClient` satisfies it structurally."""

    async def get_current(
        self, latitude: float, longitude: float, *, units: Units = Units.METRIC
    ) -> CurrentWeather: ...

    async def get_daily_forecast(
        self, latitude: float, longitude: float, *, days: int = 7, units: Units = Units.METRIC
    ) -> list[DailyForecastDay]: ...
