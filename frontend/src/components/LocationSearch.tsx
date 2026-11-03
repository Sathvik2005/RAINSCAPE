import { useEffect, useId, useState } from 'react'
import { geocodedPlaceToPlace, searchPlaces } from '../lib/api'
import type { GeocodedPlace, Place } from '../types/api'

interface Props { onSelect: (place: Place) => void }

function labelOf(place: GeocodedPlace) {
  return [place.name, place.admin1, place.country].filter((part, index, list) => part && list.indexOf(part) === index).join(', ')
}

function contextOf(place: GeocodedPlace) {
  return [place.admin2, place.country_code, `${place.latitude.toFixed(3)}, ${place.longitude.toFixed(3)}`]
    .filter(Boolean).join(' · ')
}

export function LocationSearch({ onSelect }: Props) {
  const id = useId()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<GeocodedPlace[]>([])
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [active, setActive] = useState(-1)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const search = query.trim()
    if (search.length < 2) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLoading(true)
      setMessage('')
      void searchPlaces(search, controller.signal)
        .then((places) => {
          setResults(places)
          setMessage(places.length ? '' : 'No matching places. Try a city and country.')
        })
        .catch((error: unknown) => {
          if (!controller.signal.aborted) {
            setResults([])
            setMessage(error instanceof Error ? error.message : 'Place search is temporarily unavailable.')
          }
        })
        .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    }, 350)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [query])

  function choose(place: GeocodedPlace) {
    onSelect(geocodedPlaceToPlace(place))
    setQuery(labelOf(place))
    setResults([])
    setMessage('')
    setOpen(false)
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') { setOpen(false); setActive(-1); return }
    if (event.key === 'ArrowDown' && results.length) {
      event.preventDefault(); setOpen(true); setActive((index) => (index + 1) % results.length)
    } else if (event.key === 'ArrowUp' && results.length) {
      event.preventDefault(); setOpen(true); setActive((index) => (index <= 0 ? results.length - 1 : index - 1))
    } else if (event.key === 'Enter') {
      const result = results[active] ?? (results.length === 1 ? results[0] : undefined)
      if (result) { event.preventDefault(); choose(result) }
      else if (results.length > 1) { event.preventDefault(); setOpen(true) }
    }
  }

  return (
    <div className="location-search">
      <label className="sr-only" htmlFor={id}>Search for a place</label>
      <span className="search-icon" aria-hidden="true">⌕</span>
      <input
        id={id}
        type="search"
        value={query}
        placeholder="Search a city or postal code"
        autoComplete="off"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open && results.length > 0}
        aria-controls={`${id}-results`}
        aria-activedescendant={active >= 0 ? `${id}-option-${active}` : undefined}
        onFocus={() => setOpen(true)}
        onBlur={(event) => { if (!event.currentTarget.parentElement?.contains(event.relatedTarget as Node)) setOpen(false) }}
        onChange={(event) => { setQuery(event.target.value); setResults([]); setMessage(''); setLoading(false); setActive(-1); setOpen(true) }}
        onKeyDown={handleKeyDown}
      />
      {open && (loading || message || (query.trim().length === 1) || results.length > 0) && (
        <ul id={`${id}-results`} className="search-results" role="listbox" aria-label="Place search results">
          {loading && <li className="search-status" role="status">Searching locations…</li>}
          {!loading && message && <li className="search-status" role="status">{message}</li>}
          {!loading && !message && query.trim().length === 1 && <li className="search-status" role="status">Enter at least two characters.</li>}
          {results.map((place, index) => (
            <li key={place.id}>
              <button id={`${id}-option-${index}`} className="search-result" type="button" role="option" aria-selected={active === index} onMouseDown={(event) => event.preventDefault()} onClick={() => choose(place)}>
                <strong>{labelOf(place)}</strong><small>{contextOf(place)}</small>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
