"""The template methods of `GeocodingClient`: the alphabet fallback and the translation by id."""

from dataclasses import dataclass, field

import pytest

from app.core.language import Language
from app.services.weather.errors import CityNotFoundError, NotACityError, NotSupportedError
from app.services.weather.providers.base import GeocodingClient, SearchResult
from app.services.weather.schemas import Location

KYIV_UK = Location(id=703448, name="Київ", country="Україна", latitude=50.45, longitude=30.52)
KYIV_EN = KYIV_UK.model_copy(update={"name": "Kyiv", "country": "Ukraine"})
KYIV_CS = KYIV_UK.model_copy(update={"name": "Kyjev", "country": "Ukrajina"})
KYIV_RU = KYIV_UK.model_copy(update={"name": "Киев", "country": "Украина"})


@dataclass
class FakeProvider(GeocodingClient):
    """Finds places only in the languages it was given; looks them up by (id, language)."""

    by_language: dict[Language, SearchResult]
    by_id: dict[tuple[int, Language], Location] = field(default_factory=dict)
    supports_id: bool = True
    searched: list[Language] = field(default_factory=list)

    async def find(
        self, name: str, *, count: int, country_code: str | None, language: Language
    ) -> SearchResult:
        self.searched.append(language)
        return self.by_language.get(language, SearchResult([]))

    async def get(self, place_id: int, *, language: Language) -> Location | None:
        if not self.supports_id:
            raise NotSupportedError("Fake", "ids")
        return self.by_id.get((place_id, language))


async def test_exact_match_is_not_retried() -> None:
    provider = FakeProvider({Language.EN: SearchResult([KYIV_EN])})

    assert await provider.search("kyiv ") == [KYIV_EN]
    assert provider.searched == [Language.EN]


async def test_latin_name_is_retried_in_the_other_latin_language() -> None:
    provider = FakeProvider({})

    assert await provider.search("Qwerty") == []
    assert provider.searched == [Language.EN, Language.CS]


async def test_latin_name_with_czech_interface_is_found_in_english() -> None:
    # "Prague" in Czech finds "Praha" (not exact); English has the exact name.
    praha = KYIV_EN.model_copy(update={"id": 3067696, "name": "Praha"})
    prague = praha.model_copy(update={"name": "Prague"})
    provider = FakeProvider(
        {Language.CS: SearchResult([praha]), Language.EN: SearchResult([prague])},
        by_id={(3067696, Language.CS): praha},
    )

    assert await provider.search("Prague", language=Language.CS) == [praha]
    assert provider.searched == [Language.CS, Language.EN]


async def test_country_hidden_in_the_interface_language_is_found() -> None:
    # "Germany" with language=ru: the country is called "Германия" there, so the best
    # Russian match is a town; in English it is the country.
    town = KYIV_RU.model_copy(update={"name": "Camp Dennison"})
    provider = FakeProvider(
        {
            Language.RU: SearchResult([town]),
            Language.EN: SearchResult([town], country="Germany"),
        }
    )

    with pytest.raises(NotACityError, match="'Germany' is a country"):
        await provider.geocode("Germany", language=Language.RU)


async def test_loose_match_is_replaced_by_an_exact_one() -> None:
    # "Киев" with language=uk finds a village in Russia; Russian has the exact name.
    village = KYIV_UK.model_copy(update={"id": 827619, "name": "Kiev"})
    provider = FakeProvider(
        {Language.UK: SearchResult([village]), Language.RU: SearchResult([KYIV_RU])},
        by_id={(703448, Language.UK): KYIV_UK},
    )

    assert await provider.geocode("Киев", language=Language.UK) == KYIV_UK


async def test_without_any_exact_match_the_first_answer_stays() -> None:
    odesa = KYIV_EN.model_copy(update={"name": "Odesa"})
    provider = FakeProvider({Language.EN: SearchResult([odesa])})

    assert await provider.search("Odessa") == [odesa]
    assert provider.searched == [Language.EN, Language.CS]


async def test_cyrillic_name_is_found_in_ukrainian_and_named_in_english() -> None:
    provider = FakeProvider(
        {Language.UK: SearchResult([KYIV_UK])}, by_id={(703448, Language.EN): KYIV_EN}
    )

    assert await provider.geocode("Київ") == KYIV_EN
    assert provider.searched == [Language.EN, Language.UK]


async def test_russian_name_with_ukrainian_interface_is_retried_in_russian() -> None:
    provider = FakeProvider(
        {Language.RU: SearchResult([KYIV_RU])}, by_id={(703448, Language.UK): KYIV_UK}
    )

    assert await provider.search("Киев", language=Language.UK) == [KYIV_UK]
    # Ukrainian was the interface language, so it is not searched twice.
    assert provider.searched == [Language.UK, Language.RU]


async def test_cyrillic_name_found_directly_is_not_retried() -> None:
    provider = FakeProvider({Language.UK: SearchResult([KYIV_UK])})

    assert await provider.search("Київ", language=Language.UK) == [KYIV_UK]
    assert provider.searched == [Language.UK]


async def test_names_stay_as_found_without_lookup_by_id() -> None:
    provider = FakeProvider({Language.UK: SearchResult([KYIV_UK])}, supports_id=False)

    assert await provider.search("Київ", language=Language.CS) == [KYIV_UK]


async def test_places_without_id_or_translation_stay_as_found() -> None:
    no_id = KYIV_UK.model_copy(update={"id": None})
    provider = FakeProvider({Language.UK: SearchResult([no_id, KYIV_UK])})

    assert await provider.search("Київ") == [no_id, KYIV_UK]


async def test_cyrillic_name_found_nowhere() -> None:
    provider = FakeProvider({})

    with pytest.raises(CityNotFoundError):
        await provider.geocode("Абвгд", language=Language.CS)
    assert provider.searched == [Language.CS, Language.UK, Language.RU]


async def test_country_found_by_the_fallback_is_still_not_a_city() -> None:
    provider = FakeProvider({Language.UK: SearchResult([], country="Німеччина")})

    with pytest.raises(NotACityError, match="Німеччина"):
        await provider.geocode("Німеччина")


async def test_translation_is_used_for_every_language() -> None:
    by_id = {(703448, Language.CS): KYIV_CS}
    provider = FakeProvider({Language.UK: SearchResult([KYIV_UK])}, by_id=by_id)

    assert await provider.search("Київ", language=Language.CS) == [KYIV_CS]
