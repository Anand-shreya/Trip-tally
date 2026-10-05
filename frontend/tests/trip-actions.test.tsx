import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { queryKeys } from '../src/lib/queryKeys'
import type { Trip } from '../src/lib/types'
import { DashboardPage } from '../src/pages/DashboardPage'
import { OverviewPage } from '../src/pages/OverviewPage'

const activeTrip: Trip = {
  id: 'trip-1',
  name: 'Quiet coast',
  departure_city: 'Bengaluru',
  destination: 'Gokarna',
  start_date: '2026-11-10',
  end_date: '2026-11-13',
  number_of_days: 4,
  base_currency: 'INR',
  budget: '24000.00',
  travel_style: 'BUDGET',
  status: 'PLANNING',
  is_archived: false,
  archived_at: null,
  weather_score: null,
  weather_rating: null,
  weather_summary: null,
  estimated_cost_min: null,
  estimated_cost: null,
  estimated_cost_max: null,
  travelers: [],
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
}

function renderDashboard(trips = [activeTrip]) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } },
  })
  client.setQueryData(queryKeys.trips, trips)
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter><DashboardPage /></MemoryRouter>
    </QueryClientProvider>,
  )
  return client
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('dashboard trip actions', () => {
  it('moves an archived trip into a separate section and can restore it', async () => {
    let storedTrip = activeTrip
    vi.stubGlobal('fetch', vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/trips/trip-1/archive') && init?.method === 'POST') {
        storedTrip = { ...storedTrip, is_archived: true, archived_at: '2026-10-05T06:00:00Z' }
        return new Response(JSON.stringify(storedTrip))
      }
      if (url.endsWith('/trips/trip-1/archive') && init?.method === 'DELETE') {
        storedTrip = { ...storedTrip, is_archived: false, archived_at: null }
        return new Response(JSON.stringify(storedTrip))
      }
      return new Response('{}', { status: 404 })
    }))
    renderDashboard()
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Archive Quiet coast' }))

    const archived = await screen.findByRole('region', { name: 'Archived trips' })
    expect(within(archived).getByText('Gokarna')).toBeInTheDocument()
    await user.click(within(archived).getByRole('button', { name: 'Restore Quiet coast' }))

    await waitFor(() => expect(screen.queryByRole('region', { name: 'Archived trips' })).not.toBeInTheDocument())
    expect(screen.getByText('Gokarna')).toBeInTheDocument()
  })

  it('requires confirmation before permanently deleting a trip', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)
    renderDashboard()
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Delete Quiet coast' }))
    const dialog = screen.getByRole('dialog', { name: 'Delete Quiet coast?' })
    expect(dialog).toHaveTextContent('expenses and itinerary')
    await user.click(within(dialog).getByRole('button', { name: 'Delete permanently' }))

    await screen.findByRole('heading', { name: 'Where to next?' })
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/trips/trip-1'),
      expect.objectContaining({ method: 'DELETE' }),
    )
  })
})

describe('trip overview actions', () => {
  it('shows archive and delete controls for the open trip', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
    client.setQueryData(queryKeys.trip('trip-1'), activeTrip)
    client.setQueryData(queryKeys.places('trip-1'), [])

    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/trips/trip-1']}>
          <Routes><Route path="/trips/:id" element={<OverviewPage />} /></Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByRole('button', { name: 'Archive Quiet coast' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Delete Quiet coast' })).toBeInTheDocument()
  })
})
