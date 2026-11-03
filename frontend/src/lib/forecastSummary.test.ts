import { describe, expect, it } from 'vitest'
import { formatStepValue, summarizeForecast } from './forecastSummary'
import type { ForecastStep } from '../types/api'

function step(start: number, end: number, amount: number | null, below = false): ForecastStep {
  return {
    interval_start_hour: start,
    interval_end_hour: end,
    valid_time: `2026-11-03T${String(end).padStart(2, '0')}:00:00Z`,
    amount_mm: amount,
    below_encoding_resolution: below,
    unit: 'mm',
    encoding_uncertainty_mm: below ? 0.047 : 0,
    values_zeroed_as_indeterminate: below ? 100 : 0,
    source: {} as ForecastStep['source'],
  }
}

describe('forecast summaries', () => {
  it('sums only when the full window has valid intervals and reports the peak interval', () => {
    const summary = summarizeForecast([step(0, 3, 0), step(3, 6, 1.25), step(6, 12, 0.5)])
    expect(summary.totalMm).toBe(1.75)
    expect(summary.peakStep?.interval_start_hour).toBe(3)
    expect(summary.validIntervals).toBe(3)
  })

  it('does not fill a missing interval into the window sum', () => {
    const summary = summarizeForecast([step(0, 3, 0.2), step(3, 9, null)])
    expect(summary.totalMm).toBeNull()
    expect(summary.validIntervals).toBe(1)
    expect(summary.peakStep?.interval_end_hour).toBe(3)
  })

  it('keeps a valid zero distinct from a value within encoding resolution', () => {
    const exactZero = step(0, 3, 0)
    const indeterminate = step(3, 6, 0, true)
    expect(formatStepValue(exactZero)).toBe('0.00 mm')
    expect(formatStepValue(indeterminate)).toBe('≤0.047 mm')
    expect(formatStepValue({ ...indeterminate, encoding_uncertainty_mm: 0.015258 })).toBe('≤0.016 mm')
    expect(summarizeForecast([exactZero, indeterminate]).belowResolutionIntervals).toBe(1)
  })

  it('returns an empty summary for an empty series', () => {
    expect(summarizeForecast([])).toEqual({
      totalMm: null, peakStep: null, validIntervals: 0, belowResolutionIntervals: 0,
    })
  })
})
