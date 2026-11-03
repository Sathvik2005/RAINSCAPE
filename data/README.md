# ECMWF sample data provenance

Checked: 2026-11-03. Sample file: `data/raw/ifs-20261103T00-step006-tp.grib2` (311,916 bytes; SHA-256 `F478DE9DCA09334768A5201F0FA9BA99D945012E5B545FFDCDDCBF7E189E88C9`). This raw file is intentionally ignored by Git.

Retrieved from ECMWF Open Data with `ecmwf-opendata` 0.3.35 using `source=ecmwf`, `model=ifs`, `resol=0p25`, `date=20261103`, `time=0`, `stream=oper`, `type=fc`, `levtype=sfc`, `param=tp`, `step=6`. Remote basename reported by the client: `20261103000000-6h-oper-fc.grib2`.

## ecCodes message inspection

One GRIB2 message; the original inspection report records ecCodes API 2.50.0. The current repeatable integration environment uses ecCodes 2.47.0 with matching definitions; it re-reads the genuine messages and verifies the metadata and numerical samples independently.

- `centre=ecmf`, `class=od`, `stream=oper`, `type=fc`, `expver=0001`
- `shortName=tp`, `name=Total precipitation`, `paramId=228`, `units=m`, `typeOfLevel=surface`, `level=0`
- Reference time: `dataDate=20261103`, `dataTime=0` (2026-11-03 00:00 UTC)
- Raw `forecastTime=0`; interval keys are authoritative here: `stepType=accum`, `startStep=0`, `endStep=6`, `stepRange=0-6`, `lengthOfTimeRange=6`, `typeOfStatisticalProcessing=1`
- Valid time: `validityDate=20261103`, `validityTime=600` (2026-11-03 06:00 UTC)
- Grid: `regular_ll`, `Ni=1440`, `Nj=721`, `numberOfPoints=1038240`, increments 0.25 degrees, `scanningMode=0`; first point (90.0°, 180.0°), last point (-90.0°, 179.75°)
- `bitmapPresent=0`; all 1,038,240 decoded values are finite. `missingValue=9999` is the header sentinel and does not occur as a missing-data bitmap in this message.
- Decoded range: 0 to 0.22735595703125 m (equivalent depth). Unit conversion for display: metres × 1000 = millimetres, giving a maximum of 227.35595703125 mm for this six-hour interval.

This is the direct first forecast accumulation from hour 0 to hour 6; no subtraction from another forecast field was used. The GRIB `forecastTime` key reads 0 despite `endStep=6`, so processing must use the interval and validity metadata rather than that key alone. ECMWF documentation identifies ECMWF-encoding `tp`/paramId 228 as metres of water equivalent; its WMO-unit variant is a distinct encoding. ECMWF describes total precipitation as convective plus large-scale precipitation. Attribution required by the retrieval client: ECMWF, CC BY 4.0.

The initial diagnostic attempt to expand all grid points into Python coordinate objects failed with `MemoryError`. The production sampler now uses formula-based regular_ll indexing without expanding global coordinate arrays. Multiple coordinates were checked against direct ecCodes source queries; processing/API details are documented in `reports/precipitation-processing-20261103.md` and `PROJECT_STATUS.md`. The local API uses the genuine ignored source files; deployment and live browser integration remain unverified.
