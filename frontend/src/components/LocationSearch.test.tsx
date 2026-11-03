// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  searchPlaces: vi.fn(),
  geocodedPlaceToPlace: vi.fn((place: { name: string; latitude: number; longitude: number }) => place),
}))

vi.mock('../lib/api', () => mocks)

import { LocationSearch } from './LocationSearch'

const places = [
  { id: 1, name: 'Springfield', latitude: 39.8, longitude: -89.6, admin1: 'Illinois', country: 'United States', country_code: 'US' },
  { id: 2, name: 'Springfield', latitude: 42.1, longitude: -72.6, admin1: 'Massachusetts', country: 'United States', country_code: 'US' },
]

async function queryPlaces(query = 'Springfield') {
  fireEvent.change(screen.getByRole('combobox'), { target: { value: query } })
  await act(async () => { await vi.advanceTimersByTimeAsync(350) })
}

describe('LocationSearch', () => {
  beforeEach(() => { vi.useFakeTimers(); mocks.searchPlaces.mockReset(); mocks.geocodedPlaceToPlace.mockClear() })
  afterEach(() => { cleanup(); vi.useRealTimers() })

  it('debounces search and exposes ambiguous results accessibly', async () => {
    mocks.searchPlaces.mockResolvedValue(places)
    render(<LocationSearch onSelect={vi.fn()} />)
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'Springfield' } })
    expect(mocks.searchPlaces).not.toHaveBeenCalled()
    await act(async () => { await vi.advanceTimersByTimeAsync(350) })
    expect(mocks.searchPlaces).toHaveBeenCalledTimes(1)
    expect(screen.getAllByRole('option')).toHaveLength(2)
    expect(screen.getByRole('combobox')).toHaveAttribute('aria-expanded', 'true')
  })

  it('selects the active result with the keyboard and returns its coordinates', async () => {
    mocks.searchPlaces.mockResolvedValue(places)
    const onSelect = vi.fn()
    render(<LocationSearch onSelect={onSelect} />)
    await queryPlaces()
    const input = screen.getByRole('combobox')
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(onSelect).toHaveBeenCalledWith(places[0])
    expect(input).toHaveValue('Springfield, Illinois, United States')
  })

  it('reports no results and provider errors without selecting a place', async () => {
    mocks.searchPlaces.mockResolvedValueOnce([]).mockRejectedValueOnce(new Error('Provider offline'))
    const onSelect = vi.fn()
    render(<LocationSearch onSelect={onSelect} />)
    await queryPlaces('Atlantis')
    expect(screen.getByRole('status')).toHaveTextContent('No matching places')
    await queryPlaces('Somewhere')
    expect(screen.getByRole('status')).toHaveTextContent('Provider offline')
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('does not query the provider for one-character searches', async () => {
    render(<LocationSearch onSelect={vi.fn()} />)
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'x' } })
    expect(screen.getByRole('status')).toHaveTextContent('at least two characters')
    await act(async () => { await vi.advanceTimersByTimeAsync(400) })
    expect(mocks.searchPlaces).not.toHaveBeenCalled()
  })
})
