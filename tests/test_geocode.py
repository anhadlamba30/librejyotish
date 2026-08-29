"""Gazetteer geocoding tests: deterministic offline resolution."""

import pytest

from core import geocode

APPROX = {
    "nashik": (19.99727, 73.79096, "Asia/Kolkata"),
    "delhi": (28.65195, 77.23149, "Asia/Kolkata"),
    "paris": (48.85341, 2.3488, "Europe/Paris"),
}


def test_exact_name_unambiguous():
    r = geocode.geocode("Nashik, India")
    assert r["resolved"] and not r["ambiguous"]
    assert r["matched_tier"] == "exact_name"
    top = r["candidates"][0]
    assert top["name"] == "Nashik"
    assert top["country_code"] == "IN"
    assert top["timezone"] == "Asia/Kolkata"
    assert top["latitude"] == pytest.approx(19.99727, abs=1e-4)
    assert top["longitude"] == pytest.approx(73.79096, abs=1e-4)
    assert r["query"]["place"] == "Nashik"


def test_country_code_hint_and_case_insensitive():
    r = geocode.geocode("nashik, in", limit=1)
    assert r["resolved"] and not r["ambiguous"]
    assert r["candidates"][0]["name"] == "Nashik"


def test_region_abbreviation_collision_flagged():
    # 'MH' is a real ISO country code (Marshall Islands); no Nashik there, so
    # the filter is dropped and the result is flagged ambiguous for confirmation.
    r = geocode.geocode("Nashik, MH, India")
    assert r["resolved"]
    assert r["ambiguous"]
    assert r["candidates"][0]["name"] == "Nashik"


def test_alias_resolves_but_flagged():
    r = geocode.geocode("Bombay")
    assert r["resolved"]
    assert r["matched_tier"] == "exact_alias"
    assert r["ambiguous"]  # alternate names are not canonical place names
    assert r["candidates"][0]["name"] == "Mumbai"


def test_no_match():
    r = geocode.geocode("Qwertzuiopville, XZ")
    assert not r["resolved"]
    assert r["candidates"] == []


def test_place_filter_and_limit():
    r = geocode.geocode("New York", country="US", limit=2)
    assert r["resolved"]
    assert all(c["country_code"] == "US" for c in r["candidates"])
    assert len(r["candidates"]) <= 2


def test_invalid_inputs():
    with pytest.raises(ValueError):
        geocode.geocode("")
    with pytest.raises(ValueError):
        geocode.geocode("Paris", limit=99)