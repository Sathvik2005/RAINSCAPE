# RAINSCAPE project status

Updated 2026-11-03.

## Completed milestone

- Retrieved four genuine ECMWF IFS Open Data GRIB2 files from the 2026-11-03 00 UTC cycle, lead steps 3, 6, 9 and 12.
- Inspected each message with ecCodes and recorded hashes, product/parameter, units, cycle, step semantics, grid, bitmap/missing values, statistics and packing-error metadata.
- Implemented metadata-validated precipitation interval processing, source-unit preservation, explicit millimetre conversion, missing propagation and GRIB packing uncertainty treatment.
- Implemented constant-memory regular_ll nearest-cell indexing for the observed 0.25 degree global scan mode, including longitude wrapping and boundary validation.
- Verified six geographic sample points directly against indexed ecCodes source coordinates and values.
- Added deterministic fixture tests, ecCodes-backed sampling checks and separate genuine-file API integration tests.

Evidence and the data-specific scientific decision are in reports/precipitation-processing-20261103.md.

## Current implementation state

Scientific processing and the local FastAPI backend/API contract/cache/reliability layer are implemented and verified against the locally retained genuine files. De-accumulated responses include hashes for both current and baseline source messages. A React/TypeScript dashboard, Leaflet map, location search, interval timeline, chart, typed API client, and responsive states are implemented. Frontend tests pass (14 tests across 5 files), lint passes, and the production build passes. Browser-level visual acceptance, full frontend-backend browser journey, and public deployment remain unverified.

The tested Windows environment requires `ECCODES_DEFINITION_PATH` to point to matching official ecCodes 2.47.0 definitions. The library reports `/MEMFS/definitions` by default, but GRIB decoding fails there in this environment. The API applies an explicit configured path once before its first decode. Local definitions are ignored by Git.

Backend API tests and a local Uvicorn smoke test passed on 2026-11-03. The first genuine metadata request decoded four source messages in about 1.56 s; subsequent cached point and region requests completed in 9–11 ms in this local run (not a load benchmark). Frontend unit/component suite: 14 passed; lint and production build passed on 2026-11-03.

## Workspace and Git

Project root: E:\RAINSCAPE. Local Git repository is initialized on branch main; no local commit or remote is configured. Forecast GRIB files and environment/cache directories are ignored. Public repository https://github.com/Sathvik2005/RAINSCAPE is the destination; project publication is in progress.

## Current limitations

See KNOWN_ISSUES.md. Production output must expose the uncertainty threshold and distinguish values set to zero as below encoded resolution.
