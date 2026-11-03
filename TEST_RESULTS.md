# Test results

Updated 2026-11-03. Python 3.13 virtual environment: E:\RAINSCAPE\.venv. ecCodes 2.47.0 requires an explicit matching `ECCODES_DEFINITION_PATH` in this Windows environment.

## Deterministic unit tests

Command: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`, with `PYTHONDONTWRITEBYTECODE=1`, `OPENBLAS_NUM_THREADS=1`, and the local ecCodes definitions path.

Result: 18 tests passed; 0 failed. Includes API validation, cache concurrency/expiry/invalidation/eviction/failure recovery, cumulative differencing, explicit intervals, irregular gaps, duplicates, decreases, cycle/valid-time mismatch, missing cells, packing-error uncertainty, unit conversion, grid orientation, wrapping, ties, and bounds. Values in fixture tests are not represented as forecast data.

## Genuine ECMWF integration tests

Command: `.\.venv\Scripts\python.exe -m unittest discover -s tests\integration -v`, with `PYTHONDONTWRITEBYTECODE=1`, `OPENBLAS_NUM_THREADS=1`, and the local ecCodes definitions path.

Result: 5 tests passed; 0 failed. Reads four actual ECMWF IFS GRIB files in `data/raw`, verifies their metadata and directly compares six location index/coordinate/value samples using ecCodes. It also checks derived 3–6 h amounts against separately extracted ecCodes values and verifies that uncertainty treatment removes negative output. Genuine API tests verify metadata and point provenance, bounded regional output/dateline handling, and rejection of oversized payloads. This is live-source evidence; files remain local and Git-ignored.

## Local server smoke test

Started `python -m uvicorn rainscape.api:app --app-dir backend --host 127.0.0.1 --port 8765`. Health, metadata, point and region GET requests all returned HTTP 200. The metadata response exposed four valid intervals and source units `m`; Bengaluru snapped to (13.0, 77.5). For the 2026-11-03 00 UTC cycle, point display amounts were 0, 0, 0.1220703125 and 0.244140625 mm for the 0–3, 3–6, 6–9 and 9–12 h intervals. The +6 h regional response included genuine source SHA256 `f478de9dca09334768a5201f0fa9ba99d945012e5b545ffdcddcbf7e189e88c9`. Server was stopped after smoke checks.

## Frontend tests

Command: `npm test -- --reporter=dot` from `frontend`.

Result: 14 tests passed across 5 files. These use deterministic frontend fixtures and mocked API/geocoder calls; they are not live ECMWF tests. `npm run lint` passed with no warnings. `npm run build` passed: Vite emitted a 426.59 kB JavaScript bundle (131.57 kB gzip) and 24.59 kB CSS (9.08 kB gzip).

## Current gaps

The source sample covers one cycle and only +3/+6/+9/+12. No full-field memory or 100-user concurrency benchmark has been run. The source is locally ingested; the API does not yet retrieve current forecasts dynamically. Browser-level viewport/visual acceptance and deployed full-stack smoke tests remain unverified.
