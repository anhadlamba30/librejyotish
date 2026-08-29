# Gazetteer data (`cities.csv`)

Bundled offline dataset powering the `geocode_location` tool. Sourced and
reduced from **GeoNames** `cities1000` (all cities worldwide with population
>= 1,000).

## Contents

- Filter: populated places (feature class `P`) with population >= 20,000.
- ~27.5k rows; columns `name`, `asciiname`, `alternatenames`, `latitude`,
  `longitude`, `country_code`, `admin1_code`, `population`, `timezone` (IANA).
- Deterministic lookup and population ranking live in `core/geocode.py`.

## Attribution

GeoNames data is licensed under the Creative Commons Attribution 4.0
License. Copyright: GeoNames (https://www.geonames.org) and contributors.

If you redistribute this dataset, attribute GeoNames and link to
https://www.geonames.org.

## Regenerating

```bash
conda run -n openjyotish python scripts/build_gazetteer.py
```

Pass `--zip path/to/cities1000.zip` to reuse a local copy instead of a fresh
network download. The downloadable source dataset is
`https://download.geonames.org/export/dump/cities1000.zip`
(cc-by: https://www.geonames.org/export/).

## Why commit it?

The project is local-first (no network at query time, see
`openjyotish-spec.md`). Committing the reduced CSV keeps `geocode_location`
fully offline in restricted MCP deployments; the ignored `data/ephe/*`
files are the only large binaries fetched at setup time.