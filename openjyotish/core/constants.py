"""Shared Vedic astrology constants used across all computation modules.

All longitudes are sidereal (nirayana) unless a function name/docstring says
otherwise. Sign index convention throughout this project: 0 = Aries .. 11 =
Pisces.
"""

SIGNS = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]

SIGN_LORDS = [
    "Mars",      # Aries
    "Venus",     # Taurus
    "Mercury",   # Gemini
    "Moon",      # Cancer
    "Sun",       # Leo
    "Mercury",   # Virgo
    "Venus",     # Libra
    "Mars",      # Scorpio
    "Jupiter",   # Sagittarius
    "Saturn",    # Capricorn
    "Saturn",    # Aquarius
    "Jupiter",   # Pisces
]

# Element per sign, repeating every three signs starting at Aries.
SIGN_ELEMENTS = ["fire", "earth", "air", "water"] * 3

NAKSHATRAS = [
    "Ashwini",
    "Bharani",
    "Krittika",
    "Rohini",
    "Mrigashira",
    "Ardra",
    "Punarvasu",
    "Pushya",
    "Ashlesha",
    "Magha",
    "Purva Phalguni",
    "Uttara Phalguni",
    "Hasta",
    "Chitra",
    "Swati",
    "Vishakha",
    "Anuradha",
    "Jyeshtha",
    "Mula",
    "Purva Ashadha",
    "Uttara Ashadha",
    "Shravana",
    "Dhanishta",
    "Shatabhisha",
    "Purva Bhadrapada",
    "Uttara Bhadrapada",
    "Revati",
]

# Lords repeat every nine nakshatras, starting with Ashwini -> Ketu.
NAKSHATRA_LORD_CYCLE = [
    "Ketu",
    "Venus",
    "Sun",
    "Moon",
    "Mars",
    "Rahu",
    "Jupiter",
    "Saturn",
    "Mercury",
]

# Vimshottari dasha period lengths in years (sum = 120).
VIMSHOTTARI_YEARS = {
    "Ketu": 7,
    "Venus": 20,
    "Sun": 6,
    "Moon": 10,
    "Mars": 7,
    "Rahu": 18,
    "Jupiter": 16,
    "Saturn": 19,
    "Mercury": 17,
}

# Vimshottari sequence starts here (Ketu first) and cycles through this order.
VIMSHOTTARI_SEQUENCE = list(VIMSHOTTARI_YEARS.keys())

VARAS = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]

TITHIS = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi",
]
PAKSHAS = ["Shukla", "Krishna"]
END_TITHIS = ["Purnima", "Amavasya"]

YOGAS = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana",
    "Atiganda", "Sukarman", "Dhriti", "Shoola", "Ganda",
    "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
    "Siddhi", "Vyatipata", "Variyan", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma",
    "Indra", "Vaidhriti",
]

MOVABLE_KARANAS = [
    "Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti",
]
FIXED_KARANAS = ["Kimstughna", "Shakuni", "Chatushpada", "Naga"]

# Combustion orbs (degrees from Sun) per planet. Mercury/Venus have separate
# retrograde orbs. Classical Surya Siddhanta / BPHS values.
COMBUSTION_ORBS = {
    "Moon": 12.0,
    "Mars": 17.0,
    "Mercury": 14.0,
    "Jupiter": 11.0,
    "Venus": 10.0,
    "Saturn": 15.0,
}
COMBUSTION_ORBS_RETRO = {
    "Mercury": 12.0,
    "Venus": 8.0,
}

# Exaltation degree (absolute ecliptic longitude, 0 = Aries 0).
EXALTATION_DEGREE = {
    "Sun": 10.0,        # 10 deg Aries
    "Moon": 33.0,       # 3 deg Taurus
    "Mars": 298.0,      # 28 deg Capricorn
    "Mercury": 165.0,   # 15 deg Virgo
    "Jupiter": 95.0,    # 5 deg Cancer
    "Venus": 357.0,     # 27 deg Pisces
    "Saturn": 200.0,    # 20 deg Libra
    "Rahu": 80.0,       # 20 deg Gemini (school-dependent; informational only)
    "Ketu": 260.0,      # 20 deg Sagittarius
}

# Moolatrikona range: (start longitude inclusive, end longitude exclusive).
MOOLATRIKONA_RANGE = {
    "Sun": (120.0, 140.0),   # Leo 0-20
    "Moon": (30.0, 60.0),    # Taurus 3-30
    "Mars": (0.0, 12.0),     # Aries 0-12
    "Mercury": (165.0, 170.0),  # Virgo 15-20
    "Jupiter": (240.0, 250.0),  # Sagittarius 0-10
    "Venus": (180.0, 195.0),    # Libra 0-15
    "Saturn": (300.0, 320.0),   # Aquarius 0-20
}

# Natural friendship relations (Naisargika Maitri): friend/neutral/enemy sets.
PLANET_RELATIONS = {
    "Sun":     {"friends": ["Moon", "Mars", "Jupiter"], "neutral": ["Mercury"], "enemies": ["Venus", "Saturn"]},
    "Moon":    {"friends": ["Sun", "Mercury"], "neutral": ["Mars", "Jupiter", "Venus", "Saturn"], "enemies": []},
    "Mars":    {"friends": ["Sun", "Moon", "Jupiter"], "neutral": ["Venus", "Saturn"], "enemies": ["Mercury"]},
    "Mercury": {"friends": ["Sun", "Venus"], "neutral": ["Mars", "Jupiter", "Saturn"], "enemies": ["Moon"]},
    "Jupiter": {"friends": ["Sun", "Moon", "Mars"], "neutral": ["Saturn"], "enemies": ["Mercury", "Venus"]},
    "Venus":   {"friends": ["Mercury", "Saturn"], "neutral": ["Mars", "Jupiter"], "enemies": ["Sun", "Moon"]},
    "Saturn":  {"friends": ["Mercury", "Venus"], "neutral": ["Jupiter"], "enemies": ["Sun", "Moon", "Mars"]},
}

# Naisargika bala (natural strength) in virupas, BPHS values scaled to 60 max.
NAISARGIKA_BALA = {
    "Sun": 60.0,
    "Moon": 51.43,
    "Venus": 42.86,
    "Jupiter": 34.29,
    "Mercury": 25.71,
    "Mars": 17.14,
    "Saturn": 8.57,
}

# Dig bala strongest bhava (whole-sign house from lagna, 1-indexed):
DIGBALA_STRONGEST_HOUSE = {
    "Sun": 10, "Mars": 10,
    "Jupiter": 1, "Mercury": 1,
    "Moon": 4, "Venus": 4,
    "Saturn": 7,
}

# Deep debilitation (absolute sidereal longitude) = exaltation + 180.
DEEP_DEBILITATION_DEGREE = {
    "Sun": 190.0,       # 10 deg Libra
    "Moon": 213.0,      # 3 deg Scorpio
    "Mars": 118.0,      # 28 deg Cancer
    "Mercury": 345.0,   # 15 deg Pisces
    "Jupiter": 275.0,   # 5 deg Capricorn
    "Venus": 177.0,     # 27 deg Virgo
    "Saturn": 20.0,     # 20 deg Aries
}

# Moolatrikona sign per planet (whole-sign convention used by Saptavargaja
# bala; the degree-specific ranges above govern dignity display instead).
MOOLATRIKONA_SIGN = {
    "Sun": 4,       # Leo
    "Moon": 1,      # Taurus
    "Mars": 0,      # Aries
    "Mercury": 5,   # Virgo
    "Jupiter": 8,   # Sagittarius
    "Venus": 6,     # Libra
    "Saturn": 10,   # Aquarius
}

# Minimum required Shadbala in rupas (B.V. Raman / BPHS convention).
SHADBALA_REQUIRED_RUPAS = {
    "Sun": 5.0, "Moon": 6.0, "Mars": 5.0, "Mercury": 7.0,
    "Jupiter": 6.5, "Venus": 5.5, "Saturn": 5.0,
}

# Apparent disc diameters used by Yuddha bala (PVR/JHora values; only ratios
# within a warring pair matter).
PLANET_DISC_DIAMETERS = {
    "Sun": None, "Moon": None,
    "Mars": 9.4, "Mercury": 6.6, "Jupiter": 190.4,
    "Venus": 16.6, "Saturn": 158.0,
}

# Hora lords repeat through this cycle starting with the day's vara lord.
HORA_CYCLE = ["Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter", "Mars"]


def normalize_deg(lon: float) -> float:
    """Normalize an angle to [0, 360)."""
    return lon % 360.0


def sign_index(lon: float) -> int:
    """Sidereal sign index 0..11 for a sidereal longitude."""
    return int(normalize_deg(lon) // 30)


def nakshatra_index(lon: float) -> int:
    """Nakshatra index 0..26 for a sidereal longitude."""
    return int(normalize_deg(lon) // (360.0 / 27.0))
