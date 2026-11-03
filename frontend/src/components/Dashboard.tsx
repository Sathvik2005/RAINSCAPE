import { useEffect, useState } from 'react'
import { ForecastChart } from './ForecastChart'
import { ForecastMap } from './ForecastMap'
import { LocationSearch } from './LocationSearch'
import { getMetadata, getPointForecast, getRegionForecast } from '../lib/api'
import { formatStepValue, formatUpperBound, formatUtc, summarizeForecast } from '../lib/forecastSummary'
import type { ForecastMetadata, ForecastStep, Place, PointForecast, RegionForecast } from '../types/api'

const INITIAL_PLACE: Place = {
  name: 'Bengaluru',
  admin1: 'Karnataka',
  country: 'India',
  countryCode: 'IN',
  latitude: 12.9716,
  longitude: 77.5946,
}
const EMPTY_STEPS: ForecastStep[] = []

function placeLabel(place: Place) {
  return [place.name, place.admin1, place.country].filter((part, index, list) => part && list.indexOf(part) === index).join(', ')
}

function describeStep(step: ForecastStep | null) {
  return step ? `${step.interval_start_hour}–${step.interval_end_hour} h` : '—'
}

export function Dashboard() {
  const [place, setPlace] = useState<Place>(INITIAL_PLACE)
  const [metadata, setMetadata] = useState<ForecastMetadata | null>(null)
  const [point, setPoint] = useState<PointForecast | null>(null)
  const [region, setRegion] = useState<RegionForecast | null>(null)
  const [bounds, setBounds] = useState<{ west: number; south: number; east: number; north: number } | null>(null)
  const [selectedEndStep, setSelectedEndStep] = useState(3)
  const [metadataError, setMetadataError] = useState<string | null>(null)
  const [forecastError, setForecastError] = useState<string | null>(null)
  const [regionError, setRegionError] = useState<string | null>(null)
  const [pointLoading, setPointLoading] = useState(true)
  const [regionLoading, setRegionLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    void getMetadata(controller.signal)
      .then((data) => {
        setMetadata(data)
        setSelectedEndStep((current) => data.steps.some((step) => step.interval_end_hour === current)
          ? current : data.steps[0]?.interval_end_hour ?? current)
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setMetadataError(error instanceof Error ? error.message : 'Forecast metadata is unavailable.')
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void getPointForecast(place.latitude, place.longitude, controller.signal)
      .then((data) => setPoint(data))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setForecastError(error instanceof Error ? error.message : 'Point forecast is unavailable.')
      })
      .finally(() => { if (!controller.signal.aborted) setPointLoading(false) })
    return () => controller.abort()
  }, [place.latitude, place.longitude])

  useEffect(() => {
    if (!bounds) return
    const controller = new AbortController()
    void getRegionForecast(bounds, selectedEndStep, controller.signal)
      .then((data) => setRegion(data))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setRegionError(error instanceof Error ? error.message : 'Map data is unavailable.')
      })
      .finally(() => { if (!controller.signal.aborted) setRegionLoading(false) })
    return () => controller.abort()
  }, [bounds, selectedEndStep])

  const steps = point?.steps ?? EMPTY_STEPS
  const selectedStep = steps.find((step) => step.interval_end_hour === selectedEndStep) ?? null
  const summary = summarizeForecast(steps)
  const totalWindow = steps.length ? `${steps[0].interval_start_hour}–${steps[steps.length - 1].interval_end_hour} h` : 'forecast window'
  const peak = summary.peakStep
  const cycle = metadata?.cycle ?? selectedStep?.source.cycle

  function choosePlace(next: Place) {
    setPoint(null)
    setForecastError(null)
    setPointLoading(true)
    setRegion(null)
    setRegionError(null)
    setRegionLoading(true)
    setPlace(next)
  }

  function chooseCell(latitude: number, longitude: number) {
    choosePlace({ name: 'Model grid cell', latitude, longitude })
  }

  function updateBounds(next: { west: number; south: number; east: number; north: number }) {
    setRegion(null)
    setRegionError(null)
    setRegionLoading(true)
    setBounds(next)
  }

  function selectStep(step: ForecastStep) {
    setRegion(null)
    setRegionError(null)
    setRegionLoading(true)
    setSelectedEndStep(step.interval_end_hour)
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="RAINSCAPE home">
          <span className="brand-mark" aria-hidden="true"><span>⌁</span></span>
          <span className="brand-name">RAINSCAPE</span>
          <span className="brand-subtitle">Forecast field notes</span>
        </a>
        <div className="topbar-meta">
          <span className="sample-badge">Saved ECMWF sample</span>
          <span>IFS · Total precipitation</span>
        </div>
      </header>

      <section className="hero" aria-labelledby="page-title">
        <div>
          <p className="eyebrow">Model precipitation · nearest grid cell</p>
          <h1 id="page-title">See how rain moves across a forecast.</h1>
          <p>Explore interval precipitation from an ECMWF IFS cycle. This is a saved sample, not a live feed; each value is a model estimate at a grid cell, not a ground observation.</p>
        </div>
        <div className="hero-cycle" aria-live="polite">
          <span>Forecast initialization · UTC</span>
          <strong>{cycle ? formatUtc(cycle) : metadataError ? 'Source unavailable' : 'Loading source…'}</strong>
          {selectedStep?.source.retrieved_at && <small className="local-copy-time">Local file timestamp · {formatUtc(selectedStep.source.retrieved_at)}</small>}
        </div>
      </section>

      <div className="dashboard-grid">
        <section className="card map-card" aria-label="Interactive precipitation forecast map">
          <div className="map-toolbar">
            <div className="map-title">
              <div><strong>Forecast map</strong><span>0.25° source grid · click a cell to sample it</span></div>
            </div>
            <LocationSearch onSelect={choosePlace} />
          </div>
          <ForecastMap
            place={place}
            region={region}
            selectedStep={selectedStep}
            loading={regionLoading}
            error={regionError}
            onBoundsChange={updateBounds}
            onCellSelect={chooseCell}
          />
        </section>

        <aside className="side-stack" aria-label="Selected forecast details">
          <section className="card forecast-card" aria-labelledby="point-title">
            <div className="section-head">
              <h2 id="point-title">Point forecast</h2>
              <span>{pointLoading ? 'FETCHING…' : point ? 'SOURCE VERIFIED' : 'UNAVAILABLE'}</span>
            </div>
            <div className="place-row">
              <div>
                <div className="place-name">{placeLabel(place)}</div>
                <div className="place-coords">{place.latitude.toFixed(4)}° , {place.longitude.toFixed(4)}°</div>
                {point && <div className="place-coords">Grid cell {point.grid_cell.latitude.toFixed(2)}°, {point.grid_cell.longitude.toFixed(2)}° · nearest cell</div>}
              </div>
              <div className="rain-total">
                <strong>{summary.totalMm === null ? '—' : `${summary.totalMm.toFixed(2)} mm`}</strong>
                <span>{totalWindow} displayed sum</span>
              </div>
            </div>
            <div className="stats-grid">
              <div className="stat"><label>Peak valid interval</label><strong>{peak ? `${formatStepValue(peak)} · ${describeStep(peak)}` : 'No valid values'}</strong></div>
              <div className="stat"><label>Valid intervals</label><strong>{steps.length ? `${summary.validIntervals} / ${steps.length}` : '—'}</strong></div>
            </div>
            {summary.belowResolutionIntervals > 0 && (
              <p className="uncertainty-note" role="note">
                {summary.belowResolutionIntervals} displayed interval value(s) fall within the combined GRIB packing-error bound and are set to zero by the processing rule. The sum uses those displayed zeros; it is not an observation.
              </p>
            )}
            {pointLoading && !point && <p className="loading-label" role="status">Loading genuine forecast values…</p>}
            {metadataError && <p className="notice error" role="alert">{metadataError}</p>}
            {forecastError && <p className="notice error" role="alert">{forecastError}</p>}
          </section>

          <section className="card chart-card" aria-labelledby="timeline-title">
            <div className="section-head">
              <h2 id="timeline-title">Precipitation timeline</h2>
              <span>interval amount · mm</span>
            </div>
            {steps.length > 0 ? (
              <ForecastChart steps={steps} selectedEndStep={selectedEndStep} onSelect={selectStep} />
            ) : (
              <p className="loading-label" role="status">{pointLoading ? 'Loading forecast intervals…' : 'No forecast intervals are available.'}</p>
            )}
            {selectedStep && (
              <div className="current-interval" aria-live="polite">
                <span>Selected interval · valid {formatUtc(selectedStep.valid_time)}</span>
                <strong>{describeStep(selectedStep)} · {formatStepValue(selectedStep)}</strong>
              </div>
            )}
            {selectedStep?.below_encoding_resolution && (
              <p className="uncertainty-note" role="note">This displayed zero falls within the ≤{formatUpperBound(selectedStep.encoding_uncertainty_mm)} mm combined packing-error bound.</p>
            )}
          </section>
        </aside>
      </div>

      <footer className="footer">
        <div className="footer-note">
          This data/output is based on data and products of the European Centre for Medium-Range Weather Forecasts (ECMWF).{' '}
          <a href="https://www.ecmwf.int/en/forecasts/datasets/open-data" target="_blank" rel="noreferrer">ECMWF Open Data</a> ·{' '}
          <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a>. Modified for interval amounts, uncertainty handling and display units. Model output is not a ground observation.
        </div>
        <div>Search text and IP go to GeoNames via Open‑Meteo; RAINSCAPE stores no search history. <a href="https://open-meteo.com/en/terms" target="_blank" rel="noreferrer">Terms & privacy</a></div>
      </footer>
    </main>
  )
}
