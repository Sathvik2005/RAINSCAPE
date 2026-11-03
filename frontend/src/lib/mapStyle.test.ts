import { describe, expect, it } from 'vitest'
import { PRECIPITATION_COLORS, precipitationColor } from './mapStyle'

describe('forecast map colour scale', () => {
  it('maps numeric interval amounts to the documented breaks', () => {
    expect(precipitationColor(0, false)).toBe(PRECIPITATION_COLORS.zero)
    expect(precipitationColor(0.1, false)).toBe(PRECIPITATION_COLORS.trace)
    expect(precipitationColor(0.5, false)).toBe(PRECIPITATION_COLORS.light)
    expect(precipitationColor(2, false)).toBe(PRECIPITATION_COLORS.moderate)
    expect(precipitationColor(5, false)).toBe(PRECIPITATION_COLORS.heavy)
    expect(precipitationColor(15, false)).toBe(PRECIPITATION_COLORS.veryHeavy)
  })

  it('keeps missing, zero, and below-resolution cells visually distinct', () => {
    expect(precipitationColor(null, false)).toBe(PRECIPITATION_COLORS.missing)
    expect(precipitationColor(0, false)).toBe(PRECIPITATION_COLORS.zero)
    expect(precipitationColor(0, true)).toBe(PRECIPITATION_COLORS.indeterminate)
  })
})
