"""Metadata-driven precipitation semantics and bounded regular_ll sampling.

Values remain in source units. Conversion to millimetres is explicit at the
presentation boundary via to_millimetres.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import floor, isfinite
import os
from pathlib import Path
from threading import Lock
from typing import Literal, Sequence

import numpy as np

_ECCODES_DEFINITION_PATH: str | None = None
_ECCODES_INIT_LOCK = Lock()


class ScientificDataError(ValueError):
    """Source metadata or values cannot be interpreted safely."""


class GridError(ScientificDataError):
    """The grid or requested coordinate is unsupported or invalid."""


class SequenceError(ScientificDataError):
    """Accumulation records are duplicate, incompatible, or non-monotonic."""


@dataclass(frozen=True)
class RegularLLGrid:
    ni: int
    nj: int
    first_latitude: float
    first_longitude: float
    last_latitude: float
    last_longitude: float
    i_increment: float
    j_increment: float
    scanning_mode: int
    grid_type: str = "regular_ll"

    def __post_init__(self) -> None:
        if self.grid_type != "regular_ll":
            raise GridError(f"unsupported gridType: {self.grid_type}")
        if self.ni <= 0 or self.nj <= 0 or self.i_increment <= 0 or self.j_increment <= 0:
            raise GridError("grid dimensions and increments must be positive")
        if self.scanning_mode != 0:
            raise GridError(f"unsupported scanningMode: {self.scanning_mode}")
        expected_last_lat = self.first_latitude - (self.nj - 1) * self.j_increment
        if abs(expected_last_lat - self.last_latitude) > 1e-6:
            raise GridError("latitude bounds disagree with dimensions/increment")
        if abs(self.ni * self.i_increment - 360.0) > max(1e-6, self.i_increment * 1e-5):
            raise GridError("only complete global regular_ll longitude grids are supported")

    @property
    def size(self) -> int:
        return self.ni * self.nj

    def index(self, latitude: float, longitude: float) -> int:
        """Nearest cell, north-to-south rows and eastward columns, no coord arrays.

        Longitude is cyclic. Half-cell ties resolve toward the increasing
        row/column index. Coordinates outside grid latitude bounds are rejected.
        """
        if not isfinite(latitude) or not isfinite(longitude):
            raise GridError("latitude and longitude must be finite")
        south, north = sorted((self.first_latitude, self.last_latitude))
        if latitude < south or latitude > north:
            raise GridError(f"latitude {latitude} is outside grid bounds [{south}, {north}]")
        row = floor((self.first_latitude - latitude) / self.j_increment + 0.5)
        if not 0 <= row < self.nj:
            raise GridError("latitude maps outside grid dimensions")
        first_lon = self.first_longitude % 360.0
        lon = longitude % 360.0
        col = floor(((lon - first_lon) % 360.0) / self.i_increment + 0.5) % self.ni
        return row * self.ni + col

    def coordinate_at(self, flat_index: int) -> tuple[float, float]:
        if not 0 <= flat_index < self.size:
            raise GridError("flat index outside grid")
        row, col = divmod(flat_index, self.ni)
        lat = self.first_latitude - row * self.j_increment
        lon = ((self.first_longitude + col * self.i_increment + 180.0) % 360.0) - 180.0
        return lat, lon


@dataclass(frozen=True)
class PrecipitationField:
    source_path: str
    source_sha256: str
    model: str
    product: str
    cycle: datetime
    retrieved_at: datetime | None
    step_units_code: int
    parameter_short_name: str
    parameter_name: str
    parameter_id: int
    units: str
    step_type: str
    statistical_processing: int | None
    start_step_hours: float
    end_step_hours: float
    valid_time: datetime
    grid: RegularLLGrid
    values: Sequence[float]
    bitmap_present: bool
    missing_value: float | None
    missing_count: int | None
    packing_error: float | None
    processing_version: str = "precipitation-v1"

    @property
    def accumulation_kind(self) -> Literal["cumulative", "interval"]:
        if self.parameter_short_name != "tp" or self.parameter_id != 228:
            raise ScientificDataError("only ECMWF total precipitation tp/228 is currently supported")
        if self.units not in {"m", "kg m**-2", "kg m-2"}:
            raise ScientificDataError(f"unsupported total-precipitation units: {self.units!r}")
        if self.step_type != "accum" or self.statistical_processing != 1:
            raise ScientificDataError("only GRIB accumulation with statistical processing=1 is supported")
        if self.start_step_hours < 0 or self.end_step_hours <= self.start_step_hours:
            raise ScientificDataError("invalid accumulation range")
        return "cumulative" if self.start_step_hours == 0 else "interval"


@dataclass(frozen=True)
class PrecipitationInterval:
    source_field: PrecipitationField
    interval_start_hours: float
    interval_end_hours: float
    values: np.ndarray
    baseline_source_path: str | None = None
    baseline_source_sha256: str | None = None
    below_encoding_resolution: np.ndarray | None = None
    encoding_uncertainty: float = 0.0
    values_zeroed_as_indeterminate: int = 0

    @property
    def units(self) -> str:
        return self.source_field.units

    @property
    def valid_time(self) -> datetime:
        return self.source_field.valid_time


def _same_identity(a: PrecipitationField, b: PrecipitationField) -> bool:
    attrs = ("model", "product", "cycle", "parameter_short_name", "parameter_id",
             "units", "step_type", "statistical_processing", "grid", "processing_version")
    return all(getattr(a, k) == getattr(b, k) for k in attrs)


def _as_float64(field: PrecipitationField) -> np.ndarray:
    values = np.asarray(field.values, dtype=np.float64)
    if values.ndim != 1 or values.size != field.grid.size:
        raise ScientificDataError("decoded values do not match grid dimensions")
    if field.bitmap_present and field.missing_value is not None:
        values = values.copy()
        values[values == field.missing_value] = np.nan
    return values


def derive_precipitation_intervals(
    fields: Sequence[PrecipitationField]
) -> list[PrecipitationInterval]:
    """Interpret declared intervals or difference a validated cumulative series.

    Irregular non-overlapping ranges are preserved. Cumulative records must
    begin at step zero and increase strictly within an identical source series.
    Gaps become wider explicit intervals; no precipitation is imputed.
    """
    if not fields:
        return []
    ordered = sorted(fields, key=lambda f: f.valid_time)
    first = ordered[0]
    kind = first.accumulation_kind
    for field in ordered:
        field.accumulation_kind
        if not _same_identity(first, field):
            raise SequenceError("cannot combine different model/product/cycle/parameter/unit/grid/version")
        if field.valid_time != field.cycle + timedelta(hours=field.end_step_hours):
            raise SequenceError("valid time does not equal cycle plus accumulation end step")
        if field.accumulation_kind != kind:
            raise SequenceError("cannot mix cumulative and interval accumulation semantics")
    if len({f.end_step_hours for f in ordered}) != len(ordered):
        raise SequenceError("duplicate accumulation endpoint")

    result: list[PrecipitationInterval] = []
    previous = None
    previous_values = None
    for field in ordered:
        current = _as_float64(field)
        if kind == "interval":
            if previous is not None and field.start_step_hours < previous.end_step_hours:
                raise SequenceError("overlapping or reset interval accumulation")
            result.append(PrecipitationInterval(field, field.start_step_hours, field.end_step_hours, current))
        else:
            if field.start_step_hours != 0:
                raise SequenceError("cumulative sequence contains a non-zero startStep")
            if previous is None:
                result.append(PrecipitationInterval(field, 0.0, field.end_step_hours, current))
            else:
                if field.end_step_hours <= previous.end_step_hours:
                    raise SequenceError("cumulative endpoint reset or non-monotonic sequence")
                delta = current - previous_values
                both_valid = np.isfinite(current) & np.isfinite(previous_values)
                if field.packing_error is None or previous.packing_error is None:
                    raise SequenceError("cumulative differencing requires packingError for both source messages")
                uncertainty = float(field.packing_error + previous.packing_error)
                if not isfinite(uncertainty) or uncertainty < 0:
                    raise SequenceError("invalid GRIB packingError metadata")
                if bool(np.any(both_valid & (delta < -uncertainty))):
                    raise SequenceError("cumulative precipitation decreased beyond combined GRIB packing error")
                indeterminate = both_valid & (delta != 0) & (np.abs(delta) <= uncertainty)
                zeroed_count = int(np.count_nonzero(indeterminate))
                delta[indeterminate] = 0.0
                delta[~both_valid] = np.nan
                result.append(PrecipitationInterval(
                    field, previous.end_step_hours, field.end_step_hours,
                    delta, baseline_source_path=previous.source_path,
                    baseline_source_sha256=previous.source_sha256,
                    below_encoding_resolution=indeterminate,
                    encoding_uncertainty=uncertainty,
                    values_zeroed_as_indeterminate=zeroed_count,
                ))
        previous, previous_values = field, current
    return result


def value_at(interval: PrecipitationInterval, flat_index: int) -> float | None:
    if not 0 <= flat_index < interval.values.size:
        raise GridError("flat index outside value array")
    value = float(interval.values[flat_index])
    if not isfinite(value):
        return None
    source = interval.source_field
    if source.bitmap_present and source.missing_value is not None and value == source.missing_value:
        return None
    return value


def is_below_encoding_resolution(interval: PrecipitationInterval, flat_index: int) -> bool:
    """Return whether this grid cell was zeroed within the packing bound."""
    if not 0 <= flat_index < interval.values.size:
        raise GridError("flat index outside value array")
    mask = interval.below_encoding_resolution
    return bool(mask is not None and mask[flat_index])


def to_millimetres(value: float | None, units: str) -> float | None:
    """Convert an amount for display; source values and metadata stay unchanged."""
    if value is None:
        return None
    if units == "m":
        return value * 1000.0
    if units in {"kg m**-2", "kg m-2"}:
        return value
    raise ScientificDataError(f"unsupported precipitation amount units: {units!r}")


def load_grib_field(path: str | Path, *, model: str = "ifs", product: str = "oper-fc") -> PrecipitationField:
    """Load one GRIB message's metadata and values through ecCodes."""
    import hashlib
    import eccodes

    # Some Windows wheels expose a MEMFS definitions path without the actual
    # definitions payload. A project-local (or operator-configured) path must
    # be applied through the ecCodes API before the first handle is created.
    global _ECCODES_DEFINITION_PATH
    configured_definitions = os.environ.get("ECCODES_DEFINITION_PATH")
    if configured_definitions:
        if not Path(configured_definitions).is_dir():
            raise ScientificDataError("ECCODES_DEFINITION_PATH is not a readable directory")
        with _ECCODES_INIT_LOCK:
            if _ECCODES_DEFINITION_PATH is None:
                eccodes.codes_set_definitions_path(configured_definitions)
                _ECCODES_DEFINITION_PATH = configured_definitions
            elif _ECCODES_DEFINITION_PATH != configured_definitions:
                raise ScientificDataError("ECCODES_DEFINITION_PATH cannot change after ecCodes initialization")

    file_path = Path(path)
    digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
    with file_path.open("rb") as stream:
        gid = eccodes.codes_grib_new_from_file(stream)
        if gid is None:
            raise ScientificDataError("file contains no GRIB message")
        try:
            extra = eccodes.codes_grib_new_from_file(stream)
            if extra is not None:
                eccodes.codes_release(extra)
                raise ScientificDataError("expected exactly one GRIB message per source file")
            get = lambda key: eccodes.codes_get(gid, key)
            cycle = datetime.strptime(f"{get('dataDate'):08d}{get('dataTime'):04d}", "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
            valid_time = datetime.strptime(
                f"{get('validityDate'):08d}{get('validityTime'):04d}", "%Y%m%d%H%M"
            ).replace(tzinfo=timezone.utc)
            step_units_code = int(get("stepUnits"))
            if step_units_code != 1:
                raise ScientificDataError(f"unsupported GRIB stepUnits code: {step_units_code}; expected hours (1)")
            grid = RegularLLGrid(
                ni=int(get("Ni")), nj=int(get("Nj")),
                first_latitude=float(get("latitudeOfFirstGridPointInDegrees")),
                first_longitude=float(get("longitudeOfFirstGridPointInDegrees")),
                last_latitude=float(get("latitudeOfLastGridPointInDegrees")),
                last_longitude=float(get("longitudeOfLastGridPointInDegrees")),
                i_increment=float(get("iDirectionIncrementInDegrees")),
                j_increment=float(get("jDirectionIncrementInDegrees")),
                scanning_mode=int(get("scanningMode")), grid_type=str(get("gridType")),
            )
            try:
                stat = int(get("typeOfStatisticalProcessing"))
            except Exception:
                stat = None
            try:
                missing = float(get("missingValue"))
            except Exception:
                missing = None
            try:
                packing_error = float(get("packingError"))
            except Exception:
                packing_error = None
            is_defined = eccodes.codes_is_defined(gid, "numberOfMissing")
            return PrecipitationField(
                source_path=str(file_path), source_sha256=digest, model=model, product=product,
                cycle=cycle, retrieved_at=datetime.fromtimestamp(file_path.stat().st_mtime, timezone.utc),
                step_units_code=int(get("stepUnits")), parameter_short_name=str(get("shortName")),
                parameter_name=str(get("name")), parameter_id=int(get("paramId")),
                units=str(get("units")), step_type=str(get("stepType")),
                statistical_processing=stat, start_step_hours=float(get("startStep")),
                end_step_hours=float(get("endStep")), valid_time=valid_time, grid=grid,
                values=eccodes.codes_get_values(gid),
                bitmap_present=bool(int(get("bitmapPresent"))),
                missing_value=missing,
                missing_count=int(get("numberOfMissing")) if is_defined else None,
                packing_error=packing_error,
            )
        finally:
            eccodes.codes_release(gid)










