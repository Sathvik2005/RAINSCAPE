from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import anyio
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .cache import BoundedTTLCache
from .precipitation import (
    PrecipitationField, PrecipitationInterval, ScientificDataError,
    derive_precipitation_intervals, load_grib_field, to_millimetres, value_at,
    is_below_encoding_resolution,
)

class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for name in ("request_id", "route", "status_code", "duration_ms", "model"):
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


LOGGER = logging.getLogger("rainscape.api")
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False
PROCESSING_VERSION = "precipitation-v1"
MAX_SOURCE_MESSAGES = 4
MAX_GRID_POINTS = 1_100_000
MAX_REGION_CELLS = 20_000
DEFAULT_CYCLE = datetime(2026, 11, 3, tzinfo=timezone.utc)


class SourceMetadata(BaseModel):
    model: str
    product: str
    cycle: datetime
    source_sha256: str
    baseline_source_sha256: str | None
    retrieved_at: datetime | None
    parameter_short_name: str
    parameter_name: str
    parameter_id: int
    source_units: str
    step_type: str
    statistical_processing: int | None
    accumulation_start_hour: float
    accumulation_end_hour: float
    interval_start_hour: float
    interval_end_hour: float
    valid_time: datetime
    grid_type: str
    ni: int
    nj: int
    number_of_points: int
    scanning_mode: int
    bitmap_present: bool
    missing_count: int | None
    packing_error_source_units: float | None
    processing_version: str


class ForecastStep(BaseModel):
    interval_start_hour: float
    interval_end_hour: float
    valid_time: datetime
    amount_mm: float | None
    below_encoding_resolution: bool
    unit: Literal["mm"]
    encoding_uncertainty_mm: float
    values_zeroed_as_indeterminate: int
    source: SourceMetadata


class PointForecastResponse(BaseModel):
    model: str
    selected_location: dict[str, float]
    grid_cell: dict[str, float]
    sampling: Literal["nearest_grid_cell"]
    interval_semantics: Literal["interval_amount"]
    steps: list[ForecastStep]


class GridCell(BaseModel):
    latitude: float
    longitude: float
    amount_mm: float | None
    below_encoding_resolution: bool


class RegionForecastResponse(BaseModel):
    model: str
    interval_start_hour: float
    interval_end_hour: float
    valid_time: datetime
    unit: Literal["mm"]
    source_units: str
    encoding_uncertainty_mm: float
    values_zeroed_as_indeterminate: int
    grid_type: str
    grid_resolution_degrees: dict[str, float]
    missing_value_semantics: Literal["null"]
    cells: list[GridCell]
    source: SourceMetadata


class AvailableStep(BaseModel):
    interval_start_hour: float
    interval_end_hour: float
    valid_time: datetime


class ForecastMetadataResponse(BaseModel):
    model: str
    product: str
    cycle: datetime
    parameter: str
    source_units: str
    display_units: Literal["mm"]
    grid_type: str
    ni: int
    nj: int
    number_of_points: int
    grid_resolution_degrees: dict[str, float]
    steps: list[AvailableStep]


@dataclass(frozen=True)
class ForecastDataset:
    fields: tuple[PrecipitationField, ...]
    intervals: tuple[PrecipitationInterval, ...]


class ForecastService:
    def __init__(self, data_dir: Path, cache: BoundedTTLCache[ForecastDataset]):
        self.data_dir = data_dir
        self.cache = cache

    @staticmethod
    def _cycle(cycle: datetime) -> datetime:
        if cycle.tzinfo is None:
            cycle = cycle.replace(tzinfo=timezone.utc)
        return cycle.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)

    def _paths_and_key(self, model: str, cycle: datetime) -> tuple[list[Path], tuple]:
        if model != "ifs":
            raise HTTPException(status_code=422, detail={"code": "unsupported_model"})
        cycle = self._cycle(cycle)
        stamp = cycle.strftime("%Y%m%dT%H")
        paths = sorted(self.data_dir.glob(f"ifs-{stamp}-step*-tp.grib2"))
        if not paths:
            raise HTTPException(status_code=503, detail={"code": "forecast_unavailable"})
        if len(paths) > MAX_SOURCE_MESSAGES:
            raise HTTPException(status_code=503, detail={"code": "source_series_exceeds_bound"})
        fingerprint = []
        for path in paths:
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            stat = path.stat()
            fingerprint.append((path.name, stat.st_size, stat.st_mtime_ns, digest))
        key = (
            model, "oper-fc", cycle.isoformat(), "tp", 228,
            PROCESSING_VERSION, tuple(fingerprint),
        )
        return paths, key

    def dataset(self, model: str, cycle: datetime) -> ForecastDataset:
        cycle = self._cycle(cycle)
        paths, key = self._paths_and_key(model, cycle)

        def load() -> ForecastDataset:
            fields = tuple(load_grib_field(path, model=model, product="oper-fc") for path in paths)
            if any(field.cycle != cycle for field in fields):
                raise ScientificDataError("source messages do not match requested cycle")
            if any(field.parameter_id != 228 or field.parameter_short_name != "tp" for field in fields):
                raise ScientificDataError("source series contains an unexpected parameter")
            if any(field.grid.size > MAX_GRID_POINTS for field in fields):
                raise ScientificDataError("source grid exceeds the configured point bound")
            intervals = tuple(derive_precipitation_intervals(fields))
            return ForecastDataset(fields, intervals)

        return self.cache.get_or_load(key, load)


def source_metadata(interval: PrecipitationInterval) -> SourceMetadata:
    field = interval.source_field
    return SourceMetadata(
        model=field.model, product=field.product, cycle=field.cycle,
        source_sha256=field.source_sha256,
        baseline_source_sha256=interval.baseline_source_sha256,
        retrieved_at=field.retrieved_at,
        parameter_short_name=field.parameter_short_name, parameter_name=field.parameter_name,
        parameter_id=field.parameter_id, source_units=field.units, step_type=field.step_type,
        statistical_processing=field.statistical_processing,
        accumulation_start_hour=field.start_step_hours, accumulation_end_hour=field.end_step_hours,
        interval_start_hour=interval.interval_start_hours, interval_end_hour=interval.interval_end_hours,
        valid_time=field.valid_time, grid_type=field.grid.grid_type, ni=field.grid.ni, nj=field.grid.nj,
        number_of_points=field.grid.size, scanning_mode=field.grid.scanning_mode,
        bitmap_present=field.bitmap_present, missing_count=field.missing_count,
        packing_error_source_units=field.packing_error, processing_version=field.processing_version,
    )


def _mm_uncertainty(interval: PrecipitationInterval) -> float:
    return to_millimetres(interval.encoding_uncertainty, interval.units) or 0.0


def create_app(data_dir: Path | None = None, *, cache: BoundedTTLCache[ForecastDataset] | None = None) -> FastAPI:
    project_root = Path(__file__).resolve().parents[2]
    resolved_data_dir = data_dir or Path(os.getenv("RAINSCAPE_DATA_DIR", project_root / "data" / "raw"))
    forecast_cache = cache or BoundedTTLCache[ForecastDataset](max_entries=1, ttl_seconds=600)
    service = ForecastService(resolved_data_dir, forecast_cache)
    app = FastAPI(
        title="RAINSCAPE Forecast API",
        version="0.1.0",
        description="IFS precipitation forecast values with source metadata and accumulation uncertainty.",
    )
    app.state.forecast_service = service
    app.state.forecast_cache = forecast_cache

    origins = [x.strip() for x in os.getenv(
        "RAINSCAPE_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if x.strip()]
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_credentials=False,
        allow_methods=["GET"], allow_headers=["Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            LOGGER.exception("request_failed", extra={"request_id": request_id, "route": request.url.path})
            raise
        elapsed = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        LOGGER.info("request_completed", extra={
            "request_id": request_id, "route": request.url.path,
            "status_code": response.status_code, "duration_ms": round(elapsed, 2),
        })
        return response

    @app.get("/health")
    async def health():
        info = forecast_cache.info()
        return {"status": "ok", "forecast_cache_entries": info.entries}

    @app.get("/v1/forecast/metadata", response_model=ForecastMetadataResponse)
    async def metadata(
        model: Literal["ifs"] = "ifs",
        cycle: datetime = DEFAULT_CYCLE,
    ):
        try:
            dataset = await anyio.to_thread.run_sync(service.dataset, model, cycle)
        except HTTPException:
            raise
        except Exception as exc:
            LOGGER.exception("forecast_load_failed", extra={"model": model})
            raise HTTPException(status_code=503, detail={"code": "forecast_unavailable"}) from exc
        first = dataset.fields[0]
        return ForecastMetadataResponse(
            model=first.model, product=first.product, cycle=first.cycle,
            parameter=first.parameter_short_name, source_units=first.units, display_units="mm",
            grid_type=first.grid.grid_type, ni=first.grid.ni, nj=first.grid.nj,
            number_of_points=first.grid.size,
            grid_resolution_degrees={"longitude": first.grid.i_increment, "latitude": first.grid.j_increment},
            steps=[AvailableStep(
                interval_start_hour=item.interval_start_hours,
                interval_end_hour=item.interval_end_hours, valid_time=item.valid_time,
            ) for item in dataset.intervals],
        )

    @app.get("/v1/forecast/point", response_model=PointForecastResponse)
    async def point(
        latitude: float = Query(ge=-90, le=90),
        longitude: float = Query(ge=-180, le=180),
        model: Literal["ifs"] = "ifs",
        cycle: datetime = DEFAULT_CYCLE,
    ):
        try:
            dataset = await anyio.to_thread.run_sync(service.dataset, model, cycle)
        except HTTPException:
            raise
        except Exception as exc:
            LOGGER.exception("forecast_load_failed", extra={"model": model})
            raise HTTPException(status_code=503, detail={"code": "forecast_unavailable"}) from exc
        grid = dataset.fields[0].grid
        index = grid.index(latitude, longitude)
        cell_lat, cell_lon = grid.coordinate_at(index)
        steps = []
        for interval in dataset.intervals:
            value = value_at(interval, index)
            steps.append(ForecastStep(
                interval_start_hour=interval.interval_start_hours,
                interval_end_hour=interval.interval_end_hours,
                valid_time=interval.valid_time,
                amount_mm=to_millimetres(value, interval.units),
                below_encoding_resolution=is_below_encoding_resolution(interval, index),
                unit="mm",
                encoding_uncertainty_mm=_mm_uncertainty(interval),
                values_zeroed_as_indeterminate=interval.values_zeroed_as_indeterminate,
                source=source_metadata(interval),
            ))
        return PointForecastResponse(
            model=model, selected_location={"latitude": latitude, "longitude": longitude},
            grid_cell={"latitude": cell_lat, "longitude": cell_lon},
            sampling="nearest_grid_cell", interval_semantics="interval_amount", steps=steps,
        )

    @app.get("/v1/forecast/region", response_model=RegionForecastResponse)
    async def region(
        west: float = Query(ge=-180, le=180),
        south: float = Query(ge=-90, le=90),
        east: float = Query(ge=-180, le=180),
        north: float = Query(ge=-90, le=90),
        end_step: int = Query(ge=1, le=384),
        stride: int = Query(default=1, ge=1, le=32),
        model: Literal["ifs"] = "ifs",
        cycle: datetime = DEFAULT_CYCLE,
    ):
        if south > north:
            raise HTTPException(status_code=422, detail={"code": "invalid_latitude_bounds"})
        try:
            dataset = await anyio.to_thread.run_sync(service.dataset, model, cycle)
        except HTTPException:
            raise
        except Exception as exc:
            LOGGER.exception("forecast_load_failed", extra={"model": model})
            raise HTTPException(status_code=503, detail={"code": "forecast_unavailable"}) from exc
        interval = next((x for x in dataset.intervals if x.interval_end_hours == end_step), None)
        if interval is None:
            raise HTTPException(status_code=404, detail={"code": "forecast_step_unavailable"})
        grid = interval.source_field.grid
        rows = []
        for row in range(0, grid.nj, stride):
            lat, _ = grid.coordinate_at(row * grid.ni)
            if south <= lat <= north:
                rows.append((row, lat))
        crosses_dateline = west > east
        cols = []
        for col in range(0, grid.ni, stride):
            _, lon = grid.coordinate_at(col)
            inside = (lon >= west or lon <= east) if crosses_dateline else (west <= lon <= east)
            if inside:
                cols.append((col, lon))
        if not rows or not cols:
            raise HTTPException(status_code=422, detail={"code": "region_contains_no_grid_cells"})
        if len(rows) * len(cols) > MAX_REGION_CELLS:
            raise HTTPException(status_code=413, detail={"code": "region_too_large", "max_cells": MAX_REGION_CELLS})
        cells = []
        for row, lat in rows:
            base = row * grid.ni
            for col, lon in cols:
                cells.append(GridCell(
                    latitude=lat, longitude=lon,
                    amount_mm=to_millimetres(value_at(interval, base + col), interval.units),
                    below_encoding_resolution=is_below_encoding_resolution(interval, base + col),
                ))
        return RegionForecastResponse(
            model=model, interval_start_hour=interval.interval_start_hours,
            interval_end_hour=interval.interval_end_hours, valid_time=interval.valid_time,
            unit="mm", source_units=interval.units, encoding_uncertainty_mm=_mm_uncertainty(interval),
            values_zeroed_as_indeterminate=interval.values_zeroed_as_indeterminate,
            grid_type=grid.grid_type,
            grid_resolution_degrees={"longitude": grid.i_increment, "latitude": grid.j_increment},
            missing_value_semantics="null", cells=cells, source=source_metadata(interval),
        )

    return app


app = create_app()

