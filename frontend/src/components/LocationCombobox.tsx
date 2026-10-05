import { Check, LoaderCircle, MapPin, Search } from 'lucide-react'
import { useEffect, useId, useState } from 'react'

import { api } from '../lib/api'
import type { LocationKind, LocationSuggestion } from '../lib/types'

interface LocationComboboxProps {
  label: string
  kind: LocationKind
  placeholder: string
  value: LocationSuggestion | null
  onChange: (value: LocationSuggestion | null) => void
  error?: string
}

export function LocationCombobox({
  label,
  kind,
  placeholder,
  value,
  onChange,
  error,
}: LocationComboboxProps) {
  const generatedId = useId()
  const inputId = `${generatedId}-input`
  const listboxId = `${generatedId}-listbox`
  const helpId = `${generatedId}-help`
  const [inputValue, setInputValue] = useState(value?.label ?? '')
  const [options, setOptions] = useState<LocationSuggestion[]>([])
  const [activeIndex, setActiveIndex] = useState(-1)
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [hasSearched, setHasSearched] = useState(false)

  useEffect(() => {
    const query = inputValue.trim()
    if (value && query === value.label) {
      return
    }
    if (query.length < 2) {
      return
    }

    let cancelled = false
    const timeout = window.setTimeout(async () => {
      setIsLoading(true)
      setIsOpen(true)
      setSearchError('')
      try {
        const params = new URLSearchParams({ q: query, kind })
        const results = await api.get<LocationSuggestion[]>(`/locations/search?${params}`)
        if (!cancelled) {
          setOptions(results)
          setActiveIndex(-1)
          setHasSearched(true)
        }
      } catch {
        if (!cancelled) {
          setOptions([])
          setHasSearched(true)
          setSearchError('Location search is unavailable. Try again.')
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }, 300)

    return () => {
      cancelled = true
      window.clearTimeout(timeout)
    }
  }, [inputValue, kind, value])

  const selectOption = (option: LocationSuggestion) => {
    setInputValue(option.label)
    setOptions([])
    setActiveIndex(-1)
    setIsOpen(false)
    onChange(option)
  }

  const activeOptionId = activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined

  return (
    <div className="location-combobox">
      <label htmlFor={inputId}>{label}</label>
      <div className={`location-input ${value ? 'selected' : ''}`}>
        <Search size={18} aria-hidden="true" />
        <input
          id={inputId}
          type="text"
          role="combobox"
          autoComplete="off"
          aria-autocomplete="list"
          aria-expanded={isOpen}
          aria-controls={listboxId}
          aria-activedescendant={activeOptionId}
          aria-describedby={helpId}
          aria-invalid={Boolean(error)}
          placeholder={placeholder}
          value={inputValue}
          onChange={(event) => {
            const nextValue = event.target.value
            setInputValue(nextValue)
            setOptions([])
            setActiveIndex(-1)
            setIsOpen(false)
            setIsLoading(false)
            setHasSearched(false)
            setSearchError('')
            if (value) onChange(null)
          }}
          onFocus={() => {
            if (inputValue.trim().length >= 2 && !value) setIsOpen(true)
          }}
          onBlur={() => window.setTimeout(() => setIsOpen(false), 120)}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown' && options.length > 0) {
              event.preventDefault()
              setIsOpen(true)
              setActiveIndex((current) => Math.min(current + 1, options.length - 1))
            } else if (event.key === 'ArrowUp' && options.length > 0) {
              event.preventDefault()
              setActiveIndex((current) => Math.max(current - 1, 0))
            } else if (
              event.key === 'Enter'
              && isOpen
              && activeIndex >= 0
              && options[activeIndex]
            ) {
              event.preventDefault()
              selectOption(options[activeIndex])
            } else if (event.key === 'Escape') {
              setIsOpen(false)
              setActiveIndex(-1)
            }
          }}
        />
        {isLoading && <LoaderCircle className="location-spinner" size={18} aria-label="Searching" />}
        {!isLoading && value && <Check className="location-check" size={18} aria-hidden="true" />}
      </div>
      <small id={helpId} className={error ? 'location-error' : 'location-help'}>
        {error ?? (kind === 'departure'
          ? 'Choose a city or town from the suggestions.'
          : 'Choose a city, region, island, or country.')}
      </small>

      {isOpen && !value && inputValue.trim().length >= 2 && (
        <div className="location-results">
          {options.length > 0 && (
            <ul id={listboxId} role="listbox" aria-label={`${label} suggestions`}>
              {options.map((option, index) => (
                <li
                  id={`${listboxId}-option-${index}`}
                  key={`${option.id}-${option.latitude}-${option.longitude}`}
                  role="option"
                  aria-selected={index === activeIndex}
                  className={index === activeIndex ? 'active' : ''}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => selectOption(option)}
                  onMouseEnter={() => setActiveIndex(index)}
                >
                  <MapPin size={17} aria-hidden="true" />
                  <span>
                    <strong>{option.label}</strong>
                    <small>{option.location_type} · {option.country_code}</small>
                  </span>
                </li>
              ))}
            </ul>
          )}
          {!isLoading && hasSearched && options.length === 0 && !searchError && (
            <p>No matching locations. Try a broader name.</p>
          )}
          {searchError && <p className="location-search-error">{searchError}</p>}
        </div>
      )}
    </div>
  )
}
