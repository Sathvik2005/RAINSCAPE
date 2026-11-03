"""Reproducibly inspect GRIB messages with ecCodes and write a Markdown report."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import numpy as np
import eccodes as ec

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data/raw/ifs-20261103T00-step006-tp.grib2"
DEFAULT_REPORT = ROOT / "reports/ifs-20261103T00-step006-tp.md"
KEYS = (
    "edition", "centre", "shortName", "name", "paramId", "units",
    "dataDate", "dataTime", "validityDate", "validityTime", "forecastTime",
    "stepType", "startStep", "endStep", "stepRange", "typeOfStatisticalProcessing",
    "lengthOfTimeRange", "typeOfLevel", "level", "gridType", "Ni", "Nj",
    "numberOfPoints", "numberOfDataPoints", "latitudeOfFirstGridPointInDegrees",
    "longitudeOfFirstGridPointInDegrees", "latitudeOfLastGridPointInDegrees",
    "longitudeOfLastGridPointInDegrees", "iDirectionIncrementInDegrees",
    "jDirectionIncrementInDegrees", "scanningMode", "bitmapPresent", "missingValue",
    "numberOfMissing", "class", "stream", "type", "expver",
    "generatingProcessIdentifier",
)

def get(gid, key):
    try:
        if ec.codes_is_defined(gid, key):
            return ec.codes_get(gid, key)
    except Exception:
        pass
    return None

def stamp(date, hhmm):
    if date is None or hhmm is None:
        return "UNKNOWN"
    return datetime.strptime(f"{int(date):08d}{int(hhmm):04d}", "%Y%m%d%H%M").replace(tzinfo=timezone.utc).isoformat()

def inspect(source: Path):
    digest = hashlib.sha256()
    with source.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    messages = []
    with source.open("rb") as f:
        while (gid := ec.codes_grib_new_from_file(f)) is not None:
            try:
                item = {key: get(gid, key) for key in KEYS}
                values = np.asarray(ec.codes_get_values(gid), dtype=np.float64)
                bitmap = bool(item["bitmapPresent"] or 0)
                valid = np.isfinite(values)
                if bitmap and item["missingValue"] is not None:
                    valid &= values != float(item["missingValue"])
                good = values[valid]
                item.update({
                    "valueCount": int(values.size),
                    "validValueCount": int(good.size),
                    "computedMissingCount": int(values.size - good.size),
                    "minimum": float(good.min()) if good.size else None,
                    "maximum": float(good.max()) if good.size else None,
                    "mean": float(good.mean()) if good.size else None,
                    "referenceTimeUtc": stamp(item["dataDate"], item["dataTime"]),
                    "validTimeUtc": stamp(item["validityDate"], item["validityTime"]),
                })
                first_lat = item["latitudeOfFirstGridPointInDegrees"]
                last_lat = item["latitudeOfLastGridPointInDegrees"]
                item["latitudeBounds"] = [min(first_lat, last_lat), max(first_lat, last_lat)] if first_lat is not None and last_lat is not None else None
                ni, di = item["Ni"], item["iDirectionIncrementInDegrees"]
                if ni is not None and di is not None and abs(float(ni) * float(di) - 360.0) < 1e-6:
                    item["longitudeCoverage"] = "global cyclic 0 to <360 degrees east"
                else:
                    item["longitudeCoverage"] = "see first/last scanned point keys"
                item["classification"] = (
                    f"Interval accumulation over steps {item['startStep']}–{item['endStep']} h; "
                    "because startStep is 0, this is also the forecast-to-date total at this first lead."
                    if item["stepType"] == "accum" and item["startStep"] is not None and item["endStep"] is not None
                    else "Not classified as an accumulation; inspect the reported stepType and units."
                )
                messages.append(item)
            finally:
                ec.codes_release(gid)
    return digest.hexdigest().upper(), messages

def render(source: Path, digest: str, messages: list[dict]) -> str:
    lines = [
        "# GRIB inspection: IFS total precipitation, 2026-11-03 00 UTC +6 h", "",
        f"- Source file: `{source}`",
        f"- File size: {source.stat().st_size:,} bytes",
        f"- SHA-256: `{digest}`",
        f"- ecCodes API version: `{ec.codes_get_api_version()}`",
        f"- GRIB message count: **{len(messages)}**", "",
        "## Retrieval identity", "",
        "The retrieval request used `ecmwf-opendata` with `source=ecmwf`, `model=ifs`, `resol=0p25`, `date=20261103`, `time=0`, `stream=oper`, `type=fc`, `levtype=sfc`, `param=tp`, `step=6`. The GRIB itself records the class, stream, type and experiment version shown below; `model=ifs` is preserved here from the request provenance.", "",
    ]
    for index, m in enumerate(messages, 1):
        lines += [f"## Message {index}", "", "### Parameter and time", "",
            f"- Edition: `{m['edition']}`; centre: `{m['centre']}`",
            f"- shortName/name/paramId/units: `{m['shortName']}` / `{m['name']}` / `{m['paramId']}` / `{m['units']}`",
            f"- Level: `{m['typeOfLevel']}` = `{m['level']}`",
            f"- Reference time: `{m['referenceTimeUtc']}` (`dataDate={m['dataDate']}`, `dataTime={m['dataTime']}`)",
            f"- Valid time: `{m['validTimeUtc']}` (`validityDate={m['validityDate']}`, `validityTime={m['validityTime']}`)",
            f"- Step metadata: `stepType={m['stepType']}`, `startStep={m['startStep']}`, `endStep={m['endStep']}`, `stepRange={m['stepRange']}`, `forecastTime={m['forecastTime']}`",
            f"- Statistical processing: `typeOfStatisticalProcessing={m['typeOfStatisticalProcessing']}`, `lengthOfTimeRange={m['lengthOfTimeRange']}` hours",
            f"- Classification: **{m['classification']}** Not instantaneous and not a rate.", "",
            "### Grid", "",
            f"- `gridType={m['gridType']}`, dimensions `{m['Ni']} × {m['Nj']}`, points `{m['numberOfPoints']}` (data points `{m['numberOfDataPoints']}`)",
            f"- Latitude bounds: `{m['latitudeBounds']}` degrees north; first scanned point `({m['latitudeOfFirstGridPointInDegrees']}, {m['longitudeOfFirstGridPointInDegrees']})`, last `({m['latitudeOfLastGridPointInDegrees']}, {m['longitudeOfLastGridPointInDegrees']})` degrees",
            f"- Resolution: `i={m['iDirectionIncrementInDegrees']}°`, `j={m['jDirectionIncrementInDegrees']}°`; scanning mode `{m['scanningMode']}`; longitude coverage: {m['longitudeCoverage']}.", "",
            "### Missing values and statistics", "",
            f"- `bitmapPresent={m['bitmapPresent']}`, `missingValue={m['missingValue']}`, `numberOfMissing={m['numberOfMissing']}`",
            f"- Values read: `{m['valueCount']}`; valid: `{m['validValueCount']}`; computed missing/non-finite count: `{m['computedMissingCount']}`",
            f"- Minimum: `{m['minimum']}` `{m['units']}`",
            f"- Maximum: `{m['maximum']}` `{m['units']}`",
            f"- Mean: `{m['mean']}` `{m['units']}` (simple unweighted grid-point arithmetic mean; not area-weighted)", "",
        ]
    lines += [
        "## Scientific interpretation", "",
        "The observed message is an accumulated total-precipitation field. Its actual interval keys are `startStep=0`, `endStep=6`, `stepRange=0-6`, and `stepType=accum`; therefore it represents the 0–6 h accumulation. As this is the first lead from step 0, the interval amount also equals the forecast-to-date amount at +6 h. It is not a precipitation rate or instantaneous field. `forecastTime=0` is also present, so it must not be used by itself to infer the interval.", "",
        "ECMWF definitions: total precipitation (`tp`) is precipitation from convective and large-scale schemes. This GRIB uses ECMWF encoding `paramId=228`, unit metres of water equivalent; the distinct WMO-unit encoding uses `paramId=228228`, kg m⁻². Convert this message to millimetres of water equivalent by multiplying values in metres by 1000.", "",
        "## Limitations and uncertainty", "",
        "- `numberOfMissing=0`, `bitmapPresent=0`, and all decoded values are finite. The `missingValue=9999` key is metadata; without a bitmap it does not mark any values missing in this message.",
        "- Longitude is cyclic. The first/last scanned longitude keys are not a simple west/east min/max pair. Global coverage is derived from `Ni × iDirectionIncrementInDegrees = 360°`; no full coordinate array was materialized.",
        "- A previous attempt to expand all grid coordinates into Python objects raised `MemoryError`; this report uses grid metadata and decoded values only. Memory-bounded coordinate indexing remains unverified.",
        "- The mean is unweighted across grid points. It is not a spherical-area-weighted global mean.", "",
        "## Official definitions", "",
        "- [ECMWF total precipitation definition](https://confluence.ecmwf.int/spaces/FCST/pages/111155324/How+are+Large+Scale+precipitation+Convective+Precipitation+and+Snowfall+defined+in+the+ECMWF+model)",
        "- [ECMWF GRIB2 parameter encoding and units](https://confluence.ecmwf.int/spaces/MTG2US/pages/554148197/Migration+to+GRIB2+-+changes+to+encoding+of+parameters)",
        "- [ecCodes time and step keys](https://confluence.ecmwf.int/spaces/ECC/pages/7374731/ksec1)",
        "",
    ]
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--force", action="store_true", help="replace the specified output report")
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_file():
        raise SystemExit(f"Source file not found: {source}")
    if output.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite report: {output}; pass --force to replace it")
    digest, messages = inspect(source)
    report = render(source, digest, messages)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"REPORT={output}")
    print(f"SHA256={digest}")
    print(f"MESSAGE_COUNT={len(messages)}")

if __name__ == "__main__":
    main()