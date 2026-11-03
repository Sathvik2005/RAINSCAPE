import type { ForecastMetadata, GeocodedPlace, Place, PointForecast, RegionForecast } from '../types/api'

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
const GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'

async function fetchWithTimeout(url: string, signal?: AbortSignal): Promise<Response> {
  const controller = new AbortController()
  let timedOut = false
  const abortFromCaller = () => controller.abort(signal?.reason)
  if (signal?.aborted) abortFromCaller()
  else signal?.addEventListener('abort', abortFromCaller, { once: true })
  const timer = globalThis.setTimeout(() => { timedOut = true; controller.abort() }, 10_000)
  try {
    return await fetch(url, { signal: controller.signal, headers: { Accept: 'application/json' } })
  } catch (error) {
    if (signal?.aborted) throw error
    if (timedOut) throw new Error('Request timed out after 10 seconds. Please try again.')
    throw error
  } finally {
    globalThis.clearTimeout(timer)
    signal?.removeEventListener('abort', abortFromCaller)
  }
}

async function requestJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetchWithTimeout(url, signal)
  if (!response.ok) {
    const body = await response.json().catch(() => undefined) as { detail?: { code?: string } } | undefined
    const code = body?.detail?.code
    const message = code === 'forecast_unavailable'
      ? 'The selected forecast sample is unavailable.'
      : code === 'region_too_large'
        ? 'Zoom in to a smaller map area to view precipitation cells.'
        : `Request failed (${response.status}).`
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export function getMetadata(signal?: AbortSignal): Promise<ForecastMetadata> {
  return requestJson(`${API_BASE}/v1/forecast/metadata`, signal)
}

export function getPointForecast(latitude: number, longitude: number, signal?: AbortSignal): Promise<PointForecast> {
  const params = new URLSearchParams({ latitude: String(latitude), longitude: String(longitude) })
  return requestJson(`${API_BASE}/v1/forecast/point?${params}`, signal)
}

export function getRegionForecast(
  bounds: { west: number; south: number; east: number; north: number },
  endStep: number,
  signal?: AbortSignal,
): Promise<RegionForecast> {
  const params = new URLSearchParams({
    ...Object.fromEntries(Object.entries(bounds).map(([key, value]) => [key, String(value)])),
    end_step: String(endStep),
  })
  return requestJson(`${API_BASE}/v1/forecast/region?${params}`, signal)
}

export async function searchPlaces(query: string, signal?: AbortSignal): Promise<GeocodedPlace[]> {
  const params = new URLSearchParams({ name: query, count: '6', language: 'en', format: 'json' })
  const response = await fetchWithTimeout(`${GEOCODING_URL}?${params}`, signal)
  if (!response.ok) throw new Error('Place search is temporarily unavailable.')
  const result = await response.json() as { results?: GeocodedPlace[] }
  return result.results ?? []
}

export function geocodedPlaceToPlace(place: GeocodedPlace): Place {
  return {
    name: place.name,
    latitude: place.latitude,
    longitude: place.longitude,
    country: place.country,
    admin1: place.admin1,
    countryCode: place.country_code,
  }
}
