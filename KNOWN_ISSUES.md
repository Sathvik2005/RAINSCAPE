# Known issues and limitations

- The implementation supports only ECMWF total precipitation tp/paramId 228, step units code 1 (hours), accumulated GRIB fields with statistical processing 1, and units m or kg m-2.
- It supports only complete global regular_ll grids with ecCodes scan mode 0. Other scan modes/projections are rejected. No bilinear interpolation is implemented; point results are nearest model grid cells.
- De-accumulation uses per-message GRIB packingError. Values indistinguishable from zero within the sum of the two encoding-error bounds are set to zero and counted. This can suppress real light precipitation below the encoded resolution; the interval/API must expose this uncertainty and count. The 0–3h first accumulation is not differenced and retains source values.
- Only one forecast cycle has been inspected. The engine rejects cross-cycle series; callers must partition requests by model cycle.
- Irregular gaps are represented with the actual wider interval; no temporal interpolation or missing-step synthesis occurs.
- Local file modification time is used as a retrieval-time proxy; it is not an authoritative ECMWF publication/retrieval timestamp.
- ecCodes full coordinate-array expansion previously failed with MemoryError. Formula-based indexing and indexed source queries are verified, but peak memory and 100-user performance are not yet benchmarked.
- Source GRIB samples live under the Git-ignored data/raw; tests requiring them skip when absent. Fixture tests remain independent.
- Windows ecCodes 2.47.0 in this environment reports `/MEMFS/definitions` but cannot decode until an explicit matching official definitions directory is configured. The local extracted definitions are Git-ignored; setup requires the official 2.47.0 source package. This was worked around and both genuine GRIB/API tests and the local server smoke test passed. Deployment must verify its native ecCodes package and definitions independently.
- The API serves the one locally retained IFS cycle only. It does not yet refresh upstream data, persist normalized outputs, or share its process-local cache across workers/instances.
- Frontend unit/component tests pass, but browser-level viewport and visual acceptance, full deployed end-to-end journey, and public hosting remain unverified. Frontend tests mock API/geocoder calls and do not establish live ECMWF behavior.
