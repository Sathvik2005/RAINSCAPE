# RAINSCAPE scientific processing verification

Checked: 2026-11-03 (Asia/Kolkata). Scope: genuine ECMWF Open Data IFS oper/fc, 00 UTC, 2026-11-03, total precipitation (tp).

## Verified source messages

All four are single-message GRIB2 files, centre=ecmf, class=od, shortName=tp, name=Total precipitation, paramId=228, units=m, surface level 0; stepType=accum, statistical processing 1, step unit code 1 (hours), regular_ll 1440 x 721, 1,038,240 points, scan mode 0, 0.25 degrees, no bitmap and no missing values. Each valid time equals reference time plus endStep.

| Step | Range | Valid time UTC | SHA256 | Packing / bits | packingError (m) | Source min / max / mean (m) |
|---:|:---:|:---|:---|:---|---:|:---|
| 3 | 0–3 | 03:00 | f25ae87507751109964e1e3f7b9a505b48f05e58af8c4879b99a23d3d8b03e83 | grid_ccsds / 12 | 0.0000152587890625 | 0 / 0.112548828125 / 0.0002834059935281853 |
| 6 | 0–6 | 06:00 | f478de9dca09334768a5201f0fa9ba99d945012e5b545ffdcddcbf7e189e88c9 | grid_ccsds / 12 | 0.000030517578125 | 0 / 0.22735595703125 / 0.0005688538994438606 |
| 9 | 0–9 | 09:00 | e5464f2437584c4c0f9baed7cff500bc359994ee79dedd59fe5acf18c92fd933 | grid_ccsds / 12 | 0.00006103515625 | 0 / 0.312255859375 / 0.0008553430725088251 |
| 12 | 0–12 | 12:00 | c37235121f2dced9dc240293f60778952fa357fe3cfbf7e30c4d56b82cd653bb | grid_ccsds / 12 | 0.00006103515625 | 0 / 0.3392333984375 / 0.0011380796863110889 |

The global grid begins at 90N, 180E; last point is 90S, 179.75E; increments are +0.25 degrees eastward and 0.25 degrees toward the south. ecCodes reports wrapped longitudes in [-180, 180); the indexer compares longitude circularly. The downloaded files remain unchanged and are ignored by Git.

## Temporal interpretation

These are cumulative forecast-to-date accumulations, not 3-hour interval fields: every message declares stepType=accum, statistical processing 1, and startStep=0 with increasing endStep (0–3, 0–6, 0–9, 0–12). Therefore the engine uses the first field as 0–3 and differences compatible successive cumulative fields to derive 3–6, 6–9 and 9–12. It validates cycle, valid time, parameter, units, grid, processing version, strict endpoint increase and duplicate absence. Wider cumulative gaps are represented as wider output intervals without imputation. Cross-cycle records, resets, duplicate endpoints, incompatible fields, missing packing-error metadata, or material negative differences raise validation errors. Explicit non-zero-start intervals are passed through directly and overlapping intervals are rejected.

## GRIB packing finding and handling

Naive differencing produced negative grid values: 22,379 for +3 to +6 (minimum -0.000030517578125 m) and 43,560 for +6 to +9 (minimum -0.00006103515625 m); +9 to +12 had none. This matches ECMWF's ecCodes FAQ describing spurious positive and negative de-accumulated values caused by different GRIB packing precision across cumulative steps. The GRIB packingError doubles over these messages. The engine uses the sum of the two source messages' packingError values as the conservative uncertainty bound for each difference. Non-zero differences whose absolute value is within that bound, positive or negative, are treated as indeterminate and set to zero; larger negative differences fail validation. Missing in either input remains missing. This deliberately sacrifices values below the data's encoded resolution; it must not be presented as evidence of exactly zero model precipitation.

After this treatment, the global intervals contain no negative values. Counts of non-zero differences zeroed as indeterminate are:
- 3–6 h: 120,555 cells; bound 0.0000457763671875 m (0.0457763671875 mm).
- 6–9 h: 187,218 cells; bound 0.000091552734375 m (0.091552734375 mm).
- 9–12 h: 168,879 cells; bound 0.0001220703125 m (0.1220703125 mm).

The first 0–3 h field is used directly and is not de-accumulated. Its small decoded amounts remain as encoded.

## Spatial sampling and source comparisons

RegularLLGrid.index() computes row/column from GRIB grid metadata without generating latitude or longitude arrays. The verified scan order is north-to-south rows and eastward columns. It rejects out-of-range latitude, non-finite coordinates, unsupported scan modes, inconsistent bounds and non-global grids. Longitude wraps modulo 360; exact half-cell ties resolve toward increasing flat index.

The live integration test sampled six coordinates (Bengaluru, both antimeridian spellings, north/south bounds, Sydney). For each, it compared the computed cell coordinates and source value against indexed eccodes.codes_get_elements() reads, and compared the 3–6 h result to separately indexed ecCodes values from both source files. All comparisons passed at GRIB precision. Bengaluru (12.9716, 77.5946) resolves to index 444550 at (13.0, 77.5). One sampled derived sequence was 0, 0, 0.0001220703125, 0.000244140625 m, or 0, 0, 0.1220703125, 0.244140625 mm after the explicit display conversion.

No full coordinate arrays are allocated. The prior codes_grib_get_data approach raised MemoryError; the new O(1) metadata index path and bounded point queries are verified. Peak-process memory was not benchmarked.

## Reproduction

From E:\RAINSCAPE run:
$env:OPENBLAS_NUM_THREADS='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s tests\integration -v

Deterministic fixture tests: 11 passed. Live genuine-GRIB integration tests: 2 passed. The test modules are separate so the live suite can skip cleanly when the locally downloaded, Git-ignored source GRIBs are unavailable.

## Scientific references

- ECMWF ecCodes FAQ, [Why are there sometimes small negative precipitation accumulations](https://confluence.ecmwf.int/spaces/UDOC/pages/208501579/Why%2Bare%2Bthere%2Bsometimes%2Bsmall%2Bnegative%2Bprecipitation%2Baccumulations%2B-%2BecCodes%2BGRIB%2BFAQ) — explains changing GRIB packing precision and false positive/negative values after de-accumulation. Its example threshold recommendations are for a specific 10-day ENS analysis; this implementation instead uses the inspected messages' individual packingError bounds.
- ECMWF, [GRIB keys](https://confluence.ecmwf.int/spaces/ECC/pages/188042102/GRIB%2BKeys) — ecCodes exposes message metadata through typed keys.
- ECMWF, [Total precipitation definition](https://confluence.ecmwf.int/spaces/FCST/pages/111155324/How+are+Large+Scale+precipitation+Convective+Precipitation+and+Snowfall+defined+in+the+ECMWF+model) — total precipitation combines convective and large-scale precipitation.
- ECMWF, [Open Data parameter mapping](https://confluence.ecmwf.int/spaces/MTG2US/pages/554148197/Migration+to+GRIB2+-+changes+to+encoding+of+parameters) — confirms Open Data tp, paramId 228, in metres (as observed in these messages).

