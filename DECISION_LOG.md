# RAINSCAPE decision log

## 2026-11-03 — Interpret observed IFS tp as cumulative

All four genuine IFS GRIB2 messages declare tp / paramId 228, units m, stepType=accum, statistical processing 1, startStep=0, and end steps 3, 6, 9, 12. Treating them as separate 3-hour intervals would be incorrect. Use the first range directly and difference only increasing cumulative fields from the same cycle and identical parameter/grid/product identity. Preserve the derived interval boundaries and baseline source hash/path. Never difference across cycles.

## 2026-11-03 — Respect message packing uncertainty during de-accumulation

The source messages use CCSDS packing with ecCodes packingError increasing from 0.0000152587890625 m (+3h) to 0.00006103515625 m (+9h). Naive subtraction produced small negative values and potentially false positive drizzle. Based on the ECMWF ecCodes FAQ's explanation of packing artifacts, use the sum of the per-message error bounds for each difference. Set positive or negative differences within that uncertainty to zero and count them; reject larger negatives. Retain the uncertainty in the processed record. Do not label these indeterminate small amounts as observed zero rainfall. See reports/precipitation-processing-20261103.md.

## 2026-11-03 — Convert units only at display boundary

Retain GRIB values in source units through validation and interval arithmetic. Convert metres to millimetres only through to_millimetres; expose source units, interval boundaries and encoding uncertainty with API outputs. kg m-2 water equivalent is supported as a 1:1 mm amount conversion; unsupported units fail.

## 2026-11-03 — Use formula-based regular_ll sampling

Do not materialize global latitude/longitude arrays. For verified scan mode 0, calculate nearest flat index from Ni/Nj, first point, increments and scan orientation; use modulo longitude for the global 360-degree grid. Reject unsupported scan modes and grid layouts rather than guessing. Direct ecCodes point queries are covered by live integration tests.

## 2026-11-03 — Serve a bounded local IFS vertical slice

The first API serves only the verified local IFS cycle and rejects other models rather than imply availability. Point responses use nearest-grid-cell interval amounts in mm and include source provenance/uncertainty; bounded region responses are JSON with null for missing values. The cache holds one dataset per process for 10 minutes, single-flight serializes fills, and cache identity includes source file hashes/stats plus model, product, cycle, parameter and processing version. It is process-local; multiple workers/instances do not share it. No forecast files are rewritten and no processing temporary files are created.

## 2026-11-03 — Configure ecCodes definitions explicitly on Windows

The tested Windows wheel reported `/MEMFS/definitions`, and opening genuine GRIB failed because `boot.def` was unavailable there. An official matching ecCodes 2.47.0 definitions tree from the ECMWF source archive was extracted under ignored `.ecCodes/`; `codes_set_definitions_path` must be called before creating a GRIB handle. The backend now applies `ECCODES_DEFINITION_PATH` once under a lock and rejects a missing directory or changing it after initialization. Deployment must validate native definitions on its own platform.
