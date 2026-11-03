// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ForecastChart } from './ForecastChart'
import type { ForecastStep } from '../types/api'

function makeStep(start: number, end: number, amount: number | null, below = false): ForecastStep {
  return {
    interval_start_hour: start, interval_end_hour: end,
    valid_time: `2026-11-03T${String(end).padStart(2, '0')}:00:00Z`, amount_mm: amount,
    below_encoding_resolution: below, unit: 'mm', encoding_uncertainty_mm: below ? 0.05 : 0,
    values_zeroed_as_indeterminate: below ? 42 : 0, source: {} as ForecastStep['source'],
  }
}

describe('ForecastChart', () => {
  afterEach(cleanup)
  it('shows interval amount units and synchronizes the selected step', () => {
    const steps = [makeStep(0, 3, 0), makeStep(3, 6, 0, true), makeStep(6, 12, 1.2)]
    const onSelect = vi.fn()
    render(<ForecastChart steps={steps} selectedEndStep={3} onSelect={onSelect} />)
    expect(screen.getByRole('img', { name: /interval precipitation amounts/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /3 to 6 hour interval, ≤0.05 mm/i })).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(screen.getByRole('button', { name: /6 to 12 hour interval, 1.20 mm/i }))
    expect(onSelect).toHaveBeenCalledWith(steps[2])
  })

  it('preserves irregular durations in the timeline controls', () => {
    render(<ForecastChart steps={[makeStep(0, 3, null), makeStep(3, 9, 0.3)]} selectedEndStep={9} onSelect={vi.fn()} />)
    expect(screen.getByRole('button', { name: /0 to 3 hour interval/ })).toHaveStyle({ flexGrow: '3' })
    expect(screen.getByRole('button', { name: /3 to 9 hour interval/ })).toHaveStyle({ flexGrow: '6' })
    expect(screen.getByRole('img')).toHaveAccessibleName(/missing data/i)
  })
})
