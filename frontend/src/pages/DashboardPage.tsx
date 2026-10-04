import { ArrowUpRight, CalendarDays, Map, Users } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ErrorState, LoadingState } from '../components/ui'
import { formatDate, formatMoney } from '../lib/format'
import { useTrips } from '../lib/queries'

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
  return (
    <main className="standalone dashboard-page">
      <header className="dashboard-heading"><div><p className="kicker">Saved routes</p><h1>Your next chapters</h1></div><Link className="button" to="/trips/new">Plan another trip</Link></header>
      <div className="trip-card-grid">
        {trips.data.map((trip, index) => (
          <Link className="trip-card" to={`/trips/${trip.id}`} key={trip.id}>
            <span className="trip-card-index">{String(index + 1).padStart(2, '0')}</span>
            <div><p className="trip-status">{trip.status.toLowerCase()}</p><h2>{trip.destination}</h2><p>{trip.name}</p></div>
            <dl>
              <div><CalendarDays /><dt>Dates</dt><dd>{formatDate(trip.start_date)}</dd></div>
              <div><Users /><dt>Group</dt><dd>{trip.travelers.length || '—'} travelers</dd></div>
              <div><Map /><dt>Budget</dt><dd>{trip.budget ? formatMoney(trip.budget, trip.base_currency) : 'Open'}</dd></div>
            </dl>
            <ArrowUpRight className="trip-card-arrow" />
          </Link>
        ))}
      </div>
    </main>
  )
}
