from abc import ABC, abstractmethod

from app.core.exceptions import CityNotFoundError
from app.schemas.location import Location


class GeocodingClient(ABC):
    """Turns a place name into coordinates. One implementation per provider."""

    @abstractmethod
    async def search(
        self, name: str, *, count: int = 5, country_code: str | None = None
    ) -> list[Location]:
        """Return up to `count` candidate places, best match first. Empty list if none."""

    async def geocode(self, name: str, *, country_code: str | None = None) -> Location:
        """Return the best match or raise `CityNotFoundError`."""
        results = await self.search(name, count=1, country_code=country_code)
        if not results:
            raise CityNotFoundError(name)
        return results[0]
