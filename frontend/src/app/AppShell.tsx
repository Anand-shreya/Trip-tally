import { Compass, Plus } from 'lucide-react'
import { Link, NavLink, Outlet, useParams } from 'react-router-dom'

import { AIProviderStatus } from '../components/AIProviderStatus'

const tripStops = [
  ['Overview', ''],
  ['Plan', 'plan'],
  ['Itinerary', 'itinerary'],
  ['Expenses', 'expenses'],
  ['People', 'people'],
  ['Summary', 'summary'],
] as const

export function RootShell() {
  return (
    <div className="root-shell">
      <header className="topbar">
        <Link className="brand" to="/"><Compass aria-hidden="true" /><span>TripWise</span></Link>
        <div className="topbar-actions">
          <AIProviderStatus />
          <Link className="topbar-action" to="/trips/new"><Plus size={18} /> New trip</Link>
        </div>
      </header>
      <Outlet />
    </div>
  )
}

export function TripLayout() {
  const { id = '' } = useParams()
  return (
    <div className="trip-shell">
      <aside className="route-rail">
        <Link className="route-back" to="/">All trips</Link>
        <div className="route-mark"><span>TW</span></div>
        <nav aria-label="Trip route">
          {tripStops.map(([label, segment], index) => (
            <NavLink key={label} end={!segment} to={`/trips/${id}${segment ? `/${segment}` : ''}`}>
              <span className="route-dot">{index + 1}</span><span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="trip-content"><Outlet /></main>
    </div>
  )
}
