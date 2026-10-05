import { Archive, ArrowUpRight, CalendarDays, Map, Users } from 'lucide-react'
import { Link } from 'react-router-dom'

import { TripActions } from '../components/TripActions'
import { ErrorState, LoadingState } from '../components/ui'
import { formatDate, formatMoney } from '../lib/format'
import { useTrips } from '../lib/queries'
import type { Trip } from '../lib/types'

function TripCard({ trip, index }: { trip: Trip; index: number }) {
  return (
    <article className={`trip-card${trip.is_archived ? ' trip-card-archived' : ''}`}>
      <Link className="trip-card-main" to={`/trips/${trip.id}`}>
        <span className="trip-card-index">{String(index + 1).padStart(2, '0')}</span>
        <div><p className="trip-status">{trip.is_archived ? 'Archived' : trip.status.toLowerCase()}</p><h2>{trip.destination}</h2><p>{trip.name}</p></div>
        <dl>
          <div><CalendarDays /><dt>Dates</dt><dd>{formatDate(trip.start_date)}</dd></div>
          <div><Users /><dt>Group</dt><dd>{trip.travelers.length || '—'} travelers</dd></div>
          <div><Map /><dt>Budget</dt><dd>{trip.budget ? formatMoney(trip.budget, trip.base_currency) : 'Open'}</dd></div>
        </dl>
        <ArrowUpRight className="trip-card-arrow" />
      </Link>
      <TripActions trip={trip} className="trip-card-actions" />
    </article>
  )
}

export function DashboardPage() {
  const trips = useTrips()
  if (trips.isLoading) return <main className="standalone"><LoadingState label="Finding your saved routes…" /></main>
  if (trips.isError) return <main className="standalone"><ErrorState error={trips.error} retry={() => trips.refetch()} /></main>
  if (!trips.data?.length) return (
    <main className="dashboard-hero">
      <p className="kicker">Your routes, costs, and shared memories</p>
      <h1>Where to next?</h1>
      <p>Build a thoughtful itinerary, keep the group budget visible, and finish with fair settlements.</p>
      <Link className="button" to="/trips/new">Plan a trip</Link>
    </main>
  )
  const activeTrips = trips.data.filter((trip) => !trip.is_archived)
  const archivedTrips = trips.data.filter((trip) => trip.is_archived)
  return (
    <main className="standalone dashboard-page">
      <header className="dashboard-heading"><div><p className="kicker">Saved routes</p><h1>Your next chapters</h1></div><Link className="button" to="/trips/new">Plan another trip</Link></header>
      {activeTrips.length > 0 ? (
        <section aria-label="Active trips"><div className="trip-card-grid">
          {activeTrips.map((trip, index) => <TripCard trip={trip} index={index} key={trip.id} />)}
        </div></section>
      ) : <p className="dashboard-note">No active trips. Restore one below or plan a new route.</p>}
      {archivedTrips.length > 0 && (
        <section className="archived-trips" aria-label="Archived trips">
          <header><Archive aria-hidden="true" /><div><h2>Archived trips</h2><p>Stored out of the way, ready whenever you want them back.</p></div></header>
          <div className="trip-card-grid">
            {archivedTrips.map((trip, index) => <TripCard trip={trip} index={index} key={trip.id} />)}
          </div>
        </section>
      )}
    </main>
  )
}
