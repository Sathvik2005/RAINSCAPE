// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ForecastMetadata, ForecastStep, PointForecast, RegionForecast } from '../types/api'

const mocks = vi.hoisted(() => ({
  getMetadata: vi.fn(),
  getPointForecast: vi.fn(),
  getRegionForecast: vi.fn(),
}))

vi.mock('../lib/api', () => ({
  ...mocks,
  searchPlaces: vi.fn(),
  geocodedPlaceToPlace: vi.fn(),
}))

vi.mock('./ForecastMap', () => ({
  ForecastMap: ({ selectedStep, onBoundsChange, onCellSelect }: {
    selectedStep: ForecastStep | null
    onBoundsChange: (bounds: { west: number; south: number; east: number; north: number }) => void
    onCellSelect: (latitude: number, longitude: number) => void
  }) => (
    <section aria-label="Test-only map fixture">
      <p data-testid="map-step">{selectedStep ? `${selectedStep.interval_start_hour}–${selectedStep.interval_end_hour} h` : 'No interval'}</p>
      <button type="button" onClick={() => onBoundsChange({ west: 77.4, south: 12.9, east: 77.6, north: 13.1 })}>Load test map area</button>
      <button type="button" onClick={() => onCellSelect(13, 77.5)}>Select test grid cell</button>
    </section>
  ),
}))

import { Dashboard } from './Dashboard'

const testSource: ForecastStep['source'] = {
  model: 'ifs', product: 'oper-fc', cycle: '2026-11-03T00:00:00Z', source_sha256: 'test-current',
  baseline_source_sha256: null, retrieved_at: '2026-11-03T01:00:00Z', parameter_short_name: 'tp',
  parameter_name: 'Total precipitation', parameter_id: 228, source_units: 'm', step_type: 'accum',
  statistical_processing: 1, accumulation_start_hour: 0, accumulation_end_hour: 3,
  interval_start_hour: 0, interval_end_hour: 3, valid_time: '2026-11-03T03:00:00Z',
  grid_type: 'regular_ll', ni: 1440, nj: 721, number_of_points: 1_038_240, scanning_mode: 0,
  bitmap_present: false, missing_count: 0, packing_error_source_units: 0.00001,
  processing_version: 'test-fixture-only',
}

const testSteps: ForecastStep[] = [
  { interval_start_hour: 0, interval_end_hour: 3, valid_time: '2026-11-03T03:00:00Z', amount_mm: 0, below_encoding_resolution: false, unit: 'mm', encoding_uncertainty_mm: 0, values_zeroed_as_indeterminate: 0, source: testSource },
  { interval_start_hour: 3, interval_end_hour: 6, valid_time: '2026-11-03T06:00:00Z', amount_mm: 0.4, below_encoding_resolution: false, unit: 'mm', encoding_uncertainty_mm: 0.04, values_zeroed_as_indeterminate: 0, source: testSource },
  { interval_start_hour: 6, interval_end_hour: 12, valid_time: '2026-11-03T12:00:00Z', amount_mm: 1.2, below_encoding_resolution: false, unit: 'mm', encoding_uncertainty_mm: 0.04, values_zeroed_as_indeterminate: 0, source: testSource },
]

const metadataFixture: ForecastMetadata = {
  model: 'ifs', product: 'oper-fc', cycle: '2026-11-03T00:00:00Z', parameter: 'tp', source_units: 'm',
  display_units: 'mm', grid_type: 'regular_ll', ni: 1440, nj: 721, number_of_points: 1_038_240,
  grid_resolution_degrees: { longitude: 0.25, latitude: 0.25 },
  steps: testSteps.map(({ interval_start_hour, interval_end_hour, valid_time }) => ({ interval_start_hour, interval_end_hour, valid_time })),
}

function pointFixture(latitude = 12.9716, longitude = 77.5946): PointForecast {
  return {
    model: 'ifs', selected_location: { latitude, longitude },
    grid_cell: { latitude: 13, longitude: 77.5 }, sampling: 'nearest_grid_cell',
    interval_semantics: 'interval_amount', steps: testSteps,
  }
}

function regionFixture(endStep: number): RegionForecast {
  const step = testSteps.find((record) => record.interval_end_hour === endStep) ?? testSteps[0]
  return {
    model: 'ifs', interval_start_hour: step.interval_start_hour, interval_end_hour: step.interval_end_hour,
    valid_time: step.valid_time, unit: 'mm', source_units: 'm', encoding_uncertainty_mm: 0.04,
    values_zeroed_as_indeterminate: 0, grid_type: 'regular_ll',
    grid_resolution_degrees: { longitude: 0.25, latitude: 0.25 }, missing_value_semantics: 'null',
    cells: [{ latitude: 13, longitude: 77.5, amount_mm: step.amount_mm, below_encoding_resolution: false }],
    source: testSource,
  }
}

describe('Dashboard integration state', () => {
  beforeEach(() => {
    mocks.getMetadata.mockReset().mockResolvedValue(metadataFixture)
    mocks.getPointForecast.mockReset().mockImplementation(async (latitude: number, longitude: number) => pointFixture(latitude, longitude))
    mocks.getRegionForecast.mockReset().mockImplementation(async (_bounds, endStep: number) => regionFixture(endStep))
  })
  afterEach(cleanup)

  it('keeps the chart selection and map interval synchronized', async () => {
    render(<Dashboard />)
    await screen.findByText('Bengaluru, Karnataka, India')
    fireEvent.click(screen.getByRole('button', { name: /load test map area/i }))
    await waitFor(() => expect(mocks.getRegionForecast).toHaveBeenCalledWith(
      { west: 77.4, south: 12.9, east: 77.6, north: 13.1 }, 3, expect.any(AbortSignal),
    ))
    expect(screen.getByTestId('map-step')).toHaveTextContent('0–3 h')

    fireEvent.click(screen.getByRole('button', { name: /6 to 12 hour interval/i }))
    await waitFor(() => expect(mocks.getRegionForecast).toHaveBeenLastCalledWith(
      { west: 77.4, south: 12.9, east: 77.6, north: 13.1 }, 12, expect.any(AbortSignal),
    ))
    expect(screen.getByTestId('map-step')).toHaveTextContent('6–12 h')
    expect(screen.getByText(/Selected interval · valid/)).toBeInTheDocument()
  })

  it('requests point values at the grid cell selected on the map', async () => {
    render(<Dashboard />)
    await screen.findByText('Bengaluru, Karnataka, India')
    fireEvent.click(screen.getByRole('button', { name: /select test grid cell/i }))
    await waitFor(() => expect(mocks.getPointForecast).toHaveBeenLastCalledWith(13, 77.5, expect.any(AbortSignal)))
    expect(await screen.findByText('Model grid cell')).toBeInTheDocument()
    expect(screen.getByText('13.0000° , 77.5000°')).toBeInTheDocument()
  })
})
