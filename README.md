# RAINSCAPE

RAINSCAPE currently serves ECMWF IFS precipitation from locally retained GRIB2
files. Scientific records retain source units and provenance; API amounts are
explicit interval amounts in millimetres, with packing uncertainty reported.

## Local setup

Use Python 3.13 and install the pinned dependencies into the project virtual
environment:

```powershell
$env:TEMP = 'E:\RAINSCAPE\.tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = 'E:\RAINSCAPE\.cache\pip'
New-Item -ItemType Directory -Force $env:TEMP, $env:PIP_CACHE_DIR | Out-Null
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

On Windows, ecCodes 2.47.0's bundled library reports a MEMFS definitions path,
but the packaged definitions are not present in the tested environment. For
local GRIB decoding, install/extract the matching official ecCodes 2.47.0
definitions into a local directory and set `ECCODES_DEFINITION_PATH` to that
directory before starting Python. Keep the definitions and source GRIB data
local; `.ecCodes/` and `data/raw/` are Git-ignored. The API initializes the
ecCodes definition path once, before opening the first GRIB handle. Linux
deployment should use the platform's normal ecCodes package and definitions.

Run the API from the repository root:

```powershell
$env:ECCODES_DEFINITION_PATH = 'E:\RAINSCAPE\.ecCodes\definitions\eccodes-2.47.0-Source\definitions'
$env:RAINSCAPE_DATA_DIR = 'E:\RAINSCAPE\data\raw'
$env:RAINSCAPE_CORS_ORIGINS = 'http://localhost:5173'
.\.venv\Scripts\python.exe -m uvicorn rainscape.api:app --app-dir backend --host 127.0.0.1 --port 8000
```

The first real decode needs genuine files named
`ifs-YYYYMMDDTHH-stepNNN-tp.grib2` in `data/raw/`. Missing source data returns
HTTP 503; the API does not create synthetic forecast values.

## API

- `GET /health` — process and in-process cache status.
- `GET /v1/forecast/metadata?model=ifs&cycle=2026-11-03T00:00:00Z` — source,
  grid and available interval metadata.
- `GET /v1/forecast/point?latitude=12.9716&longitude=77.5946` — interval
  precipitation for the nearest model cell, in mm, with source and baseline
  hashes for de-accumulated intervals.
- `GET /v1/forecast/region?west=77.4&south=12.9&east=77.6&north=13.1&end_step=6`
  — bounded regular latitude/longitude cells; missing values are JSON `null`.

The region endpoint accepts at most 20,000 cells per response. It supports
antimeridian-crossing bounds. Only IFS is enabled; other model identifiers are
rejected. Full API schema is available at `/docs` when the service is running.

## Cache and operations

The cache is process-local, one dataset entry, 10-minute TTL, serialized
single-flight loading, and content-fingerprinted source identity. It is not
shared across workers or instances. Run one worker for the local demo; multiple
workers each decode and retain their own cache. Forecast files are read-only;
the API creates no GRIB temporary files. Configure CORS with the exact frontend
origin. Logs contain request ID, route, status and duration, not query values.

## Tests

```powershell
$env:ECCODES_DEFINITION_PATH = 'E:\RAINSCAPE\.ecCodes\definitions\eccodes-2.47.0-Source\definitions'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:OPENBLAS_NUM_THREADS = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s tests\integration -v
```

Fixture tests are deterministic and do not assert that fixture values are
forecast data. Integration tests are separate and require the genuine local
ECMWF GRIB files; they are not suitable as ordinary network-dependent tests.

