"""Shadbala: six-fold planetary strength in virupas (1/60 rupa).

Implements the B.V. Raman / PVR Narasimha Rao formulation of BPHS ch. 27,
cross-checked against PyJHora's strength.py and the dirah.org/BVRaman
reference formulas. Convention choices that vary across software are
documented inline and echoed in each response's conventions_used block:

- Uccha bala: distance from deep debilitation folded to [0,180] / 3.
- Saptavargaja: D1,D2,D3,D7,D9,D12,D30; moolatrikona (whole-sign) 45 in D1;
  own sign 30; otherwise points by COMPOUND relation (natural + temporary,
  computed from the rasi chart) to each varga sign's lord.
- Dig bala: distance from the Placidus sidereal bhava cusp of the planet's
  powerless house / 3.
- Nathonnatha: solar-midnight interpolation; Paksha/Tribhaga/Hora per Raman;
  Abda/Masa via Raman's epoch tables; Ayana with declination sign reversed
  for Moon/Saturn (BPHS/dirah rule).
- Cheshta: seeghra kendra between modern mean longitudes (JPL Standish
  elements) reduced to [0,180], / 3. Sun and Moon get none.
- Drik: Parasara sphuta drishti piecewise values with special-aspect
  overrides for Mars/Jupiter/Saturn capped to [0,60]; benefic sum minus
  malefic sum over 4.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import swisseph as swe

from core import ephemeris as ep
from core.charts import MAIN_PLANETS, varga_sign, resolve_varga
from core.constants import (
    DEEP_DEBILITATION_DEGREE,
    MOOLATRIKONA_SIGN,
    NAISARGIKA_BALA,
    PLANET_RELATIONS,
    PLANET_DISC_DIAMETERS,
    SHADBALA_REQUIRED_RUPAS,
    SIGN_LORDS,
    HORA_CYCLE,
    normalize_deg,
)

# Standish J2000 mean longitudes (deg) and rates (deg/julian century).
_MEAN_LONG_ELEMENTS = {
    "Sun": (100.46457166 + 180.0, 35999.37244981),
    "Mercury": (252.25032350, 149472.67411175),
    "Venus": (181.97909950, 58517.81538729),
    "Mars": (-4.55343205, 19140.30268499),
    "Jupiter": (34.39644051, 3034.74612775),
    "Saturn": (49.95424423, 1222.49362201),
}

# Saptavargaja points by compound relation code.
_COMPOUND_POINTS = {0: 1.875, 1: 3.75, 2: 7.5, 3: 15.0, 4: 22.5}
_ADHIMITRA, _MITRA, _SAMA, _SATRU, _ADHISATRU = 4, 3, 2, 1, 0

_SAPTAVARGAJA_VARGAS = ["D1", "D2", "D3", "D7", "D9", "D12", "D30"]
_DIG_BALA_POWERLESS_HOUSE = {"Sun": 4, "Moon": 10, "Mars": 4, "Mercury": 7,
                             "Jupiter": 7, "Venus": 10, "Saturn": 1}
_MALE_PLANETS = ("Sun", "Mars", "Jupiter")
_FEMALE_PLANETS = ("Moon", "Venus")
_NEUTRAL_PLANETS = ("Mercury", "Saturn")


def _mean_longitude(name: str, jd_ut: float) -> float:
    t = (jd_ut - 2451545.0) / 36525.0
    base, rate = _MEAN_LONG_ELEMENTS[name]
    return normalize_deg(base + rate * t)


def _reduce_180(angle: float) -> float:
    a = abs(normalize_deg(angle))
    return a if a <= 180.0 else 360.0 - a


def _compound_relations(signs: dict[str, int]) -> dict[str, dict[str, int]]:
    """5-state compound relations (PVR): natural + temporary friendship.

    Returns {planet: {other: code}} where code is one of
    4 adhimitra / 3 mitra / 2 sama / 1 satru / 0 adhisatru.
    """
    temp_friends: dict[str, set] = {}
    temp_enemies: dict[str, set] = {}
    names = list(signs)
    for p in names:
        tf, te = set(), set()
        for q in names:
            if q == p:
                continue
            offset = (signs[q] - signs[p]) % 12  # house of q from p minus one
            if offset in (1, 2, 3, 9, 10, 11):
                tf.add(q)
            else:  # offsets 0,4,5,6,7,8 -> houses 1,5,6,7,8,9
                te.add(q)
        temp_friends[p], temp_enemies[p] = tf, te

    out: dict[str, dict[str, int]] = {}
    for p in names:
        row = {}
        for q in names:
            if q == p:
                continue
            nf = q in PLANET_RELATIONS[p]["friends"]
            nn = q in PLANET_RELATIONS[p]["neutral"]
            ne = q in PLANET_RELATIONS[p]["enemies"]
            tf = q in temp_friends[p]
            if nf and tf:
                row[q] = _ADHIMITRA
            elif (nf and not tf) or (ne and tf):
                row[q] = _SAMA
            elif nn and tf:
                row[q] = _MITRA
            elif nn and not tf:
                row[q] = _SATRU
            else:  # ne and te
                row[q] = _ADHISATRU
        out[p] = row
    return out


def _uccha_bala(longitudes: dict[str, float]) -> dict[str, float]:
    out = {}
    for p in MAIN_PLANETS:
        dist = _reduce_180(longitudes[p] - DEEP_DEBILITATION_DEGREE[p])
        out[p] = round(dist / 3.0, 2)
    return out


def _saptavargaja_bala(longitudes: dict[str, float],
                       compound: dict[str, dict[str, int]]) -> dict[str, float]:
    totals = {p: 0.0 for p in MAIN_PLANETS}
    for code in _SAPTAVARGAJA_VARGAS:
        spec = resolve_varga(code)
        for p in MAIN_PLANETS:
            vsign, _ = varga_sign(spec, longitudes[p])
            lord = SIGN_LORDS[vsign]
            if code == "D1" and vsign == MOOLATRIKONA_SIGN[p]:
                pts = 45.0
            elif lord == p:
                pts = 30.0
            else:
                pts = _COMPOUND_POINTS[compound[p][lord]]
            totals[p] += pts
    return {p: round(v, 2) for p, v in totals.items()}


def _ojayugma_bala(rasi_signs: dict[str, int],
                   navamsha_signs: dict[str, int]) -> dict[str, float]:
    out = {}
    for p in MAIN_PLANETS:
        want_even = p in _FEMALE_PLANETS
        pts = 0.0
        if (rasi_signs[p] % 2 == 1) == want_even:
            pts += 15.0
        if (navamsha_signs[p] % 2 == 1) == want_even:
            pts += 15.0
        out[p] = pts
    return out


def _kendradi_bala(houses_from_lagna: dict[str, int]) -> dict[str, float]:
    out = {}
    for p in MAIN_PLANETS:
        h = houses_from_lagna[p]
        out[p] = 60.0 if h in (1, 4, 7, 10) else 30.0 if h in (2, 5, 8, 11) else 15.0
    return out


def _drekkana_bala(degrees_in_sign: dict[str, float]) -> dict[str, float]:
    out = {}
    for p in MAIN_PLANETS:
        drekkana = min(int(degrees_in_sign[p] // 10.0), 2)
        if p in _MALE_PLANETS:
            got = drekkana == 0
        elif p in _NEUTRAL_PLANETS:
            got = drekkana == 1
        else:
            got = drekkana == 2
        out[p] = 15.0 if got else 0.0
    return out


def _sthana_bala(longitudes, rasi_signs, navamsha_signs, houses,
                 degrees_in_sign, compound) -> tuple[dict, dict]:
    parts = {
        "ucchabala": _uccha_bala(longitudes),
        "saptavargaja_bala": _saptavargaja_bala(longitudes, compound),
        "ojayugma_bala": _ojayugma_bala(rasi_signs, navamsha_signs),
        "kendra_bala": _kendradi_bala(houses),
        "drekkana_bala": _drekkana_bala(degrees_in_sign),
    }
    total = {p: round(sum(parts[k][p] for k in parts), 2) for p in MAIN_PLANETS}
    return total, parts


def _dig_bala(cusps: list[float], longitudes: dict[str, float]) -> dict[str, float]:
    out = {}
    for p in MAIN_PLANETS:
        cusp = cusps[_DIG_BALA_POWERLESS_HOUSE[p] - 1]
        out[p] = round(_reduce_180(cusp - longitudes[p]) / 3.0, 2)
    return out


def _nathonnatha_bala(midnight_hour: float, birth_hour: float) -> dict[str, float]:
    dm = (birth_hour - midnight_hour) % 24.0
    t_diff = min(dm, 24.0 - dm) * 5.0
    out = {}
    for p in MAIN_PLANETS:
        if p == "Mercury":
            out[p] = 60.0
        elif p in ("Sun", "Jupiter", "Venus"):
            out[p] = round(t_diff, 2)
        else:
            out[p] = round(60.0 - t_diff, 2)
    return out


def _functional_benefics_malefics(tithi_index_one_based: int,
                                  longitudes: dict[str, float]):
    benefics = {"Jupiter", "Venus"}
    malefics = {"Sun", "Mars", "Saturn"}
    waxing = tithi_index_one_based <= 15
    merc_sign = int(normalize_deg(longitudes["Mercury"]) // 30)
    co_habiting = [q for q in MAIN_PLANETS
                   if q != "Mercury"
                   and int(normalize_deg(longitudes[q]) // 30) == merc_sign]
    b_count = len([q for q in co_habiting if q in benefics or (q == "Moon" and waxing)])
    m_count = len([q for q in co_habiting if q in malefics or (q == "Moon" and not waxing)])
    if waxing:
        benefics.add("Moon")
    else:
        malefics.add("Moon")
    if b_count > m_count or (b_count == 0 and m_count == 0):
        benefics.add("Mercury")
    elif m_count > b_count:
        malefics.add("Mercury")
    else:
        closest = min(co_habiting,
                      key=lambda q: abs(longitudes[q] - longitudes["Mercury"]),
                      default=None)
        if closest in benefics:
            benefics.add("Mercury")
        else:
            malefics.add("Mercury")
    return benefics, malefics


def _paksha_bala(sun_lon: float, moon_lon: float,
                 benefics: set, malefics: set) -> dict[str, float]:
    pb = _reduce_180(moon_lon - sun_lon) / 3.0
    out = {}
    for p in MAIN_PLANETS:
        if p in benefics:
            v = pb
        else:
            v = 60.0 - pb
        if p == "Moon":
            v *= 2
        out[p] = round(v, 2)
    return out


def _tribhaga_bala(birth_hour: float, sunrise_hour: float,
                   sunset_hour: float) -> dict[str, float]:
    """60 to the lord of the current third of day/night; Jupiter always 60."""
    hrs = (birth_hour - sunrise_hour) % 24.0
    day_len = (sunset_hour - sunrise_hour) % 24.0
    night_len = 24.0 - day_len
    out = {p: 0.0 for p in MAIN_PLANETS}
    out["Jupiter"] = 60.0
    if hrs < day_len / 3:
        out["Mercury"] = 60.0
    elif hrs < 2 * day_len / 3:
        out["Sun"] = 60.0
    elif hrs < day_len:
        out["Saturn"] = 60.0
    elif hrs < day_len + night_len / 3:
        out["Moon"] = 60.0
    elif hrs < day_len + 2 * night_len / 3:
        out["Venus"] = 60.0
    else:
        out["Mars"] = 60.0
    return out


def _days_since_base(year: int, base_year: int, base_days: int) -> int:
    total_years = year - base_year
    leaps = len([y for y in range(base_year + 1, year + 1)
                 if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0])
    return base_days + leaps * 366 + (total_years - leaps) * 365


_ABDA_WEEKDAY_ORDER = ["Mars", "Mercury", "Jupiter", "Venus", "Saturn",
                       "Sun", "Moon"]  # cycle starts Tuesday


def _abdahipathi_bala(jd_local: float, year: int) -> dict[str, float]:
    jan1 = swe.julday(year, 1, 1, 0.0)
    elapsed = int(jd_local - jan1 + 1)
    ahargana = _days_since_base(year - 1, 1951, 174) + elapsed
    idx = (int(ahargana // 360) * 3 + 1) % 7
    return {p: (15.0 if p == _ABDA_WEEKDAY_ORDER[idx] else 0.0)
            for p in MAIN_PLANETS}


def _masadhipathi_bala(jd_local: float, year: int) -> dict[str, float]:
    jan1 = swe.julday(year, 1, 1, 0.0)
    elapsed = int(jd_local - jan1 + 1)
    ahargana = _days_since_base(year - 1, 1951, 174) + elapsed
    idx = (int(ahargana // 30) * 2 + 1) % 7
    return {p: (30.0 if p == _ABDA_WEEKDAY_ORDER[idx] else 0.0)
            for p in MAIN_PLANETS}


def _varadhipathi_bala(jd_local: float, year: int, birth_hour: float,
                       sunrise_hour: float) -> dict[str, float]:
    jan1 = swe.julday(year, 1, 1, 0.0)
    elapsed = int(jd_local - jan1 + 1)
    ahargana = _days_since_base(year - 1, 1827, 244) + elapsed
    if birth_hour < sunrise_hour:
        ahargana -= 1
    idx = int(ahargana) % 7
    return {p: (45.0 if p == _ABDA_WEEKDAY_ORDER[idx] else 0.0)
            for p in MAIN_PLANETS}


def _hora_bala(birth_hour: float, sunrise_hour: float,
               vara_sun_to_sat: int) -> dict[str, float]:
    """Clock-hour horas from sunrise; first hora belongs to the day lord.

    Lords advance through the Chaldean cycle (HORA_CYCLE) hour by hour;
    the cycle is anchored so the running day's lord owns the first hora.
    vara_sun_to_sat: weekday index 0=Sunday..6=Saturday (sunrise-to-sunrise).
    """
    day_lord = ["Sun", "Moon", "Mars", "Mercury", "Jupiter",
                "Venus", "Saturn"][vara_sun_to_sat]
    start = HORA_CYCLE.index(day_lord)
    slot = int((birth_hour - sunrise_hour) % 24.0)
    lord = HORA_CYCLE[(start + slot) % 7]
    return {p: (60.0 if p == lord else 0.0) for p in MAIN_PLANETS}


def _ayana_bala(jd_ut: float, flags: int) -> dict[str, float]:
    sign_by_planet = {"Sun": 1, "Venus": 1, "Mars": 1, "Jupiter": 1,
                      "Mercury": 1, "Moon": -1, "Saturn": -1}
    out = {}
    bodies = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
              "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
              "Venus": swe.VENUS, "Saturn": swe.SATURN}
    for p, body in bodies.items():
        pos, _rf = swe.calc_ut(jd_ut, body, flags | swe.FLG_EQUATORIAL)
        dec = pos[1]
        v = 30.0 + sign_by_planet[p] * dec * 1.25
        out[p] = round(min(60.0, max(0.0, v)) * (2.0 if p == "Sun" else 1.0), 2)
    return out


def _yuddha_bala(longitudes: dict[str, float], partial_totals: dict[str, float]) -> dict[str, float]:
    fighters = ["Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    best = None
    for i, p in enumerate(fighters):
        for q in fighters[i + 1:]:
            sep = _reduce_180(longitudes[p] - longitudes[q])
            if best is None or sep < best[0]:
                best = (sep, p, q)
    _sep, p, q = best
    diff = abs(partial_totals[p] - partial_totals[q])
    dia_diff = abs(PLANET_DISC_DIAMETERS[p] - PLANET_DISC_DIAMETERS[q])
    yb = round(diff / dia_diff, 2)
    winner, loser = (p, q) if partial_totals[p] > partial_totals[q] else (q, p)
    out = {k: 0.0 for k in MAIN_PLANETS}
    out[winner] = yb
    out[loser] = -yb
    return out


def _kaala_bala(jd_ut, jd_local, birth_hour, sr_ss, tithi_idx,
                longitudes, flags, sthana_total, dig_total):
    nath = _nathonnatha_bala(sr_ss["midnight_hour"], birth_hour)
    benefics, malefics = _functional_benefics_malefics(tithi_idx, longitudes)
    paksha = _paksha_bala(longitudes["Sun"], longitudes["Moon"], benefics, malefics)
    tribhaga = _tribhaga_bala(birth_hour, sr_ss["sunrise"], sr_ss["sunset"])
    abda = _abdahipathi_bala(jd_local, sr_ss["year"])
    masa = _masadhipathi_bala(jd_local, sr_ss["year"])
    vaara = _varadhipathi_bala(jd_local, sr_ss["year"], birth_hour,
                               sr_ss["sunrise"])
    hora = _hora_bala(birth_hour, sr_ss["sunrise"], sr_ss["vara_index"])
    ayana = _ayana_bala(jd_ut, flags)

    upto_hora = {
        p: sthana_total[p] + dig_total[p] + nath[p] + paksha[p] +
           tribhaga[p] + abda[p] + masa[p] + vaara[p] + hora[p]
        for p in MAIN_PLANETS
    }
    yuddha = _yuddha_bala(longitudes, upto_hora)

    parts = {
        "nathonnatha_bala": nath,
        "paksha_bala": paksha,
        "tribhaga_bala": tribhaga,
        "abda_bala": abda,
        "masa_bala": masa,
        "vaara_bala": vaara,
        "hora_bala": hora,
        "ayana_bala": ayana,
        "yuddha_bala": yuddha,
    }
    total = {p: round(sum(parts[k][p] for k in parts), 2) for p in MAIN_PLANETS}
    return total, parts, (benefics, malefics)


def _cheshta_bala(jd_ut: float) -> dict[str, float]:
    sun_mean = _mean_longitude("Sun", jd_ut)
    out = {p: 0.0 for p in ("Sun", "Moon")}
    for p in ("Mars", "Mercury", "Jupiter", "Venus", "Saturn"):
        kendra = _reduce_180(sun_mean - _mean_longitude(p, jd_ut))
        out[p] = round(kendra / 3.0, 2)
    return out


def _drishti_value(aspecting: str, angle: float) -> float:
    """Parasara sphuta drishti virupas; special aspects override, cap 60."""
    a = normalize_deg(angle)
    if a < 30.0:
        v = 0.0
    elif a < 60.0:
        v = 0.5 * (a - 30.0)
    elif a < 90.0:
        v = (a - 60.0) + 15.0
    elif a < 120.0:
        v = 0.5 * (120.0 - a) + 30.0
    elif a < 150.0:
        v = 150.0 - a
    elif a < 180.0:
        v = 2.0 * (a - 150.0)
    elif a < 300.0:
        v = 0.5 * (300.0 - a)
    else:
        v = 0.0
    if aspecting == "Saturn":
        if 30.0 <= a < 60.0:
            v = 2.0 * (a - 30.0)
        elif 60.0 <= a < 90.0:
            v = 45.0 + 0.5 * (90.0 - a)
        elif 270.0 <= a < 300.0:
            v = 2.0 * (300.0 - a)
    elif aspecting == "Mars":
        if 90.0 <= a < 120.0:
            v = 45.0 + 0.5 * (a - 90.0)
        elif 120.0 <= a < 150.0:
            v = 2.0 * (150.0 - a)
        elif 210.0 <= a < 240.0:
            v = 270.0 - a
    elif aspecting == "Jupiter":
        if 90.0 <= a < 120.0:
            v = 45.0 + 0.5 * (a - 90.0)
        elif 120.0 <= a < 150.0:
            v = 2.0 * (150.0 - a)
        elif 210.0 <= a < 240.0:
            v = 45.0 + 0.5 * (a - 210.0)
    return min(60.0, max(0.0, v))


def _drik_bala(longitudes: dict[str, float],
               benefics: set, malefics: set) -> dict[str, float]:
    out = {}
    for target in MAIN_PLANETS:
        good = sum(_drishti_value(b,
                                  longitudes[target] - longitudes[b])
                   for b in benefics)
        bad = sum(_drishti_value(m,
                                 longitudes[target] - longitudes[m])
                  for m in malefics)
        out[target] = round((good - bad) / 4.0, 2)
    return out


def build_shadbala(
    naive_local,
    tz_name: str,
    latitude: float,
    longitude: float,
    ayanamsha: str | None = "lahiri",
    node_type: str = "true",
    true_positions: bool = False,
) -> dict:
    jd = ep.to_jd(naive_local, tz_name)
    source = ep.ephemeris_source()
    aya_key, _, aya_label = ep.resolve_ayanamsha(ayanamsha)
    flags = ep._flags(true_positions)
    positions = ep.planet_positions(jd, ayanamsha=aya_key, node_type=node_type,
                                    true_positions=true_positions)
    asc, _mc = ep.ascendant_and_mc(jd, latitude, longitude, ayanamsha=aya_key,
                                   true_positions=true_positions)
    cusps = ep.bhava_cusps(jd, latitude, longitude, ayanamsha=aya_key,
                           true_positions=true_positions)

    local_dt = naive_local
    jd_local = jd + (local_dt.replace(tzinfo=ZoneInfo(tz_name))
                     - ep.jd_to_datetime_utc(jd)).total_seconds() / 86400.0
    birth_hour = local_dt.hour + local_dt.minute / 60.0 + local_dt.second / 3600.0

    riseset = ep.sunrise_sunset(local_dt.date(), tz_name, latitude, longitude)
    prev_set = ep.sunrise_sunset(local_dt.date() - timedelta(days=1), tz_name,
                                 latitude, longitude)["sunset"]

    def _hour_of(iso_or_none, fallback):
        if iso_or_none is None:
            return fallback
        hh = datetime.fromisoformat(iso_or_none)
        return hh.hour + hh.minute / 60.0 + hh.second / 3600.0

    sunrise_hour = _hour_of(riseset["sunrise"], 6.0)
    sunset_hour = _hour_of(riseset["sunset"], 18.0)
    prev_sunset_hour = _hour_of(prev_set, 18.0)
    raw_midnight = 0.5 * (sunrise_hour + prev_sunset_hour)
    midnight_hour = 12.0 - raw_midnight if raw_midnight < 12.0 else raw_midnight - 12.0

    longitudes = {p: positions[p]["longitude"] for p in MAIN_PLANETS}
    rasi_signs = {p: int(normalize_deg(longitudes[p]) // 30) for p in MAIN_PLANETS}
    degrees_in_sign = {p: normalize_deg(longitudes[p]) % 30.0 for p in MAIN_PLANETS}
    d9spec = resolve_varga("D9")
    navamsha_signs = {p: varga_sign(d9spec, longitudes[p])[0] for p in MAIN_PLANETS}
    asc_sign = int(normalize_deg(asc) // 30)
    houses = {p: (rasi_signs[p] - asc_sign) % 12 + 1 for p in MAIN_PLANETS}
    compound = _compound_relations(rasi_signs)

    sthana, sthana_parts = _sthana_bala(longitudes, rasi_signs, navamsha_signs,
                                        houses, degrees_in_sign, compound)
    dig = _dig_bala(cusps, longitudes)

    # Tithi at the moment (for paksha bala's Moon rule).
    sep = (longitudes["Moon"] - longitudes["Sun"]) % 360.0
    tithi_idx = int(sep // 12.0) + 1  # 1..30

    # Weekday index (Sunday=0) of the sunrise-to-sunrise running day.
    vara_index = (local_dt.weekday() + 1) % 7
    if birth_hour < sunrise_hour:
        vara_index = (vara_index - 1) % 7

    sr_ss = {"midnight_hour": midnight_hour, "sunrise": sunrise_hour,
             "sunset": sunset_hour, "year": local_dt.year,
             "vara_index": vara_index}

    kaala, kaala_parts, (benefics, malefics) = _kaala_bala(
        jd, jd_local, birth_hour, sr_ss, tithi_idx, longitudes, flags,
        sthana, dig)
    cheshta = _cheshta_bala(jd)
    naisargika = {p: NAISARGIKA_BALA[p] for p in MAIN_PLANETS}
    drik = _drik_bala(longitudes, benefics, malefics)

    six = {"sthana_bala": sthana, "dig_bala": dig, "kala_bala": kaala,
           "cheshta_bala": cheshta, "naisargika_bala": naisargika,
           "drik_bala": drik}
    totals = {p: round(sum(six[k][p] for k in six), 2) for p in MAIN_PLANETS}
    rupas = {p: round(totals[p] / 60.0, 2) for p in MAIN_PLANETS}
    ratios = {p: round(totals[p] / 60.0 / SHADBALA_REQUIRED_RUPAS[p], 2)
              for p in MAIN_PLANETS}

    return {
        "input": {
            "datetime_local": local_dt.isoformat(),
            "timezone": tz_name,
            "latitude": latitude,
            "longitude": longitude,
        },
        "julian_day_ut": round(jd, 8),
        "ephemeris_source": source,
        "conventions_used": {
            "zodiac": "sidereal",
            "ayanamsha": {"key": aya_key, "name": aya_label,
                          "value_degrees": round(ep.ayanamsha_value(jd, aya_key), 6)},
            "node_type": node_type,
            "position_type": "true" if true_positions else "apparent",
            "shadbala": {
                "school": "B.V. Raman / BPHS ch.27 (PVR formulation)",
                "required_rupas": SHADBALA_REQUIRED_RUPAS,
                "saptavargaja_vargas": _SAPTAVARGAJA_VARGAS,
                "relations_for_saptavargaja": "compound (natural+temporary) "
                                              "from rasi chart",
                "dig_bala_cusps": "sidereal Placidus bhava madhya",
                "horas": "clock hours from sunrise, first hora = day lord",
                "ayana_rule": "30 +/- declination*1.25 (+ for Sun/Mars/"
                              "Jupiter/Venus/Mercury, reversed for Moon/"
                              "Saturn), Sun doubled",
                "cheshta_means": "modern mean longitudes (Standish elements); "
                                 "Sun & Moon carry no cheshta bala",
                "drik_drishti": "sphuta drishti with Mars/Jupiter/Saturn "
                                "special-aspect overrides capped [0,60]; "
                                "(benefic - malefic)/4",
            },
        },
        "functional_benefics": sorted(benefics),
        "functional_malefics": sorted(malefics),
        "six_fold_strength": {
            k: v for k, v in six.items()
        },
        "strength_breakdown": {"sthana": sthana_parts, "kala": kaala_parts},
        "totals_virupas": totals,
        "totals_rupas": rupas,
        "required_vs_actual_ratio": ratios,
    }
