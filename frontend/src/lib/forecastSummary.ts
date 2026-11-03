import type { ForecastStep } from '../types/api'

export interface ForecastSummary {
  totalMm: number | null
  peakStep: ForecastStep | null
  validIntervals: number
  belowResolutionIntervals: number
}

export function summarizeForecast(steps: ForecastStep[]): ForecastSummary {
  const valid = steps.filter((step) => step.amount_mm !== null && Number.isFinite(step.amount_mm))
  const complete = steps.length > 0 && valid.length === steps.length
  const totalMm = complete ? valid.reduce((sum, step) => sum + (step.amount_mm ?? 0), 0) : null
  const peakStep = valid.reduce<ForecastStep | null>(
    (peak, step) => peak === null || (step.amount_mm ?? -Infinity) > (peak.amount_mm ?? -Infinity) ? step : peak,
    null,
  )
  return {
    totalMm,
    peakStep,
    validIntervals: valid.length,
    belowResolutionIntervals: valid.filter((step) => step.below_encoding_resolution).length,
  }
}

export function formatUtc(date: string) {
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    hour12: false, timeZone: 'UTC',
  }).format(new Date(date)) + ' UTC'
}

export function formatStepValue(step: ForecastStep) {
  if (step.amount_mm === null) return '—'
  if (step.below_encoding_resolution) return `≤${formatUpperBound(step.encoding_uncertainty_mm)} mm`
  return `${step.amount_mm.toFixed(2)} mm`
}

export function formatUpperBound(value: number) {
  const digits = value >= 1 ? 1 : value >= 0.1 ? 2 : 3
  const factor = 10 ** digits
  return (Math.ceil(value * factor) / factor).toFixed(digits).replace(/\.?0+$/, '')
}
