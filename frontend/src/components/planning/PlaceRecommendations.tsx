import { ExternalLink, MapPinned } from 'lucide-react'

import { googleMapsSearchUrl } from '../../lib/maps'
import type { Place } from '../../lib/types'
import { Button } from '../ui'

export function PlaceRecommendations({
  places,
  destination,
  selection,
  onToggle,
  onSave,
  isSaving,
  saved,
}: {
  places: Place[]
  destination: string
  selection: Set<string>
  onToggle: (placeId: string) => void
  onSave: () => void
  isSaving: boolean
  saved: boolean
}) {
  return (
    <section className="places-section">
      <header className="section-heading">
        <div><MapPinned /><div><h2>Places worth your time</h2><p>Suggested in Gemini relevance order.</p></div></div>
        <span>{selection.size} selected</span>
      </header>
      <div className="place-grid">
        {places.map((place) => {
          const checked = selection.has(place.id)
          return (
            <article className={`place-card ${checked ? 'selected' : ''}`} key={place.id} aria-label={place.name}>
              <div className="place-card-topline">
                <span className="place-score">{place.relevance_score}</span>
                <label><input type="checkbox" checked={checked} onChange={() => onToggle(place.id)} aria-label={`Select ${place.name}`} /> Add to route</label>
              </div>
              <h3>{place.name}</h3>
              <p>{place.description}</p>
              <div className="tag-row">{place.best_for.map((tag) => <span key={tag}>{tag}</span>)}</div>
              <dl>
                <div><dt>Time</dt><dd>{place.recommended_days} days</dd></div>
                <div><dt>Fit</dt><dd>{place.relevance_score}/10 relevance</dd></div>
              </dl>
              <a
                className="map-link"
                href={googleMapsSearchUrl(place.name, destination)}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Open ${place.name} in Google Maps`}
              >
                Open in Google Maps <ExternalLink size={16} />
              </a>
            </article>
          )
        })}
      </div>
      <div className="selection-bar">
        <span>{saved ? 'Route saved. Ready for an itinerary.' : `${selection.size} places in this route`}</span>
        <Button onClick={onSave} disabled={!selection.size || isSaving}>
          {isSaving ? 'Saving…' : 'Save selected places'}
        </Button>
      </div>
    </section>
  )
}
