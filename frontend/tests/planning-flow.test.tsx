import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NewTripPage } from '../src/pages/NewTripPage'
import { PlanPage } from '../src/pages/PlanPage'


function renderPage(node: ReactNode, path = '/', pattern = '*') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes><Route path={pattern} element={node} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('trip creation', () => {
  it('creates the trip then adds every named traveler', async () => {
    const calls: Array<{ url: string; body: any }> = []
    vi.stubGlobal('fetch', vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      const body = init?.body ? JSON.parse(String(init.body)) : null
      calls.push({ url, body })
      if (url.endsWith('/trips')) return new Response(JSON.stringify({ trip_id: 'trip-1', status: 'PLANNING' }), { status: 201 })
      return new Response(JSON.stringify({ id: `person-${calls.length}`, name: body.name, email: null, created_at: '2026-01-01T00:00:00Z' }), { status: 201 })
    }))
    renderPage(<NewTripPage />)
    const user = userEvent.setup()

    await user.type(screen.getByLabelText(/trip name/i), 'Island loop')
    await user.type(screen.getByLabelText(/destination/i), 'Sri Lanka')
    await user.type(screen.getByLabelText(/start date/i), '2026-09-05')
    await user.clear(screen.getByLabelText(/days/i))
    await user.type(screen.getByLabelText(/days/i), '3')
    await user.type(screen.getByLabelText(/traveler names/i), 'Shreya, Rahul, Amit')
    await user.click(screen.getByRole('button', { name: /create trip/i }))

    await waitFor(() => expect(calls).toHaveLength(4))
    expect(calls.slice(1).map((call) => call.body.name)).toEqual(['Shreya', 'Rahul', 'Amit'])
  })
})

describe('trip planning', () => {
  it('runs analysis, selects a place, and saves the route', async () => {
    const trip = {
      id: 'trip-1', name: 'Island loop', destination: 'Sri Lanka', start_date: '2026-09-05',
      end_date: '2026-09-07', number_of_days: 3, base_currency: 'INR', budget: '30000.00',
      travel_style: 'COMFORTABLE', status: 'PLANNING', weather_score: null, weather_rating: null,
      weather_summary: null, estimated_cost_min: null, estimated_cost: null, estimated_cost_max: null,
      travelers: [], created_at: '', updated_at: '',
    }
    const place = {
      id: 'ella', name: 'Ella', description: 'Tea country and ridge hikes', latitude: 1, longitude: 1,
      recommended_days: '2.0', estimated_food: '1000', estimated_transport: '500', estimated_tickets: '300',
      estimated_activity: '700', estimated_stay: '2000', estimated_cost: '4500', weather_score: '8.2',
      overall_score: '8.5', best_for: ['Nature', 'Hiking'], selected: false,
    }
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input)
      if (!init?.method && url.endsWith('/trips/trip-1')) return new Response(JSON.stringify(trip))
      if (!init?.method && url.endsWith('/places')) return new Response(JSON.stringify([]))
      if (url.endsWith('/analyze')) return new Response(JSON.stringify({
        weather: { score: '8.0', rating: 'EXCELLENT', summary: 'Clear days', temperature_c: '24', rain_probability: 20, humidity: 60, wind_kph: '8' },
        estimated_budget: { minimum: '20000', typical: '26000', maximum: '35000', currency: 'INR' },
        places: [place], status: 'READY',
      }))
      if (url.endsWith('/select')) return new Response(JSON.stringify([{ ...place, selected: true }]))
      return new Response('{}', { status: 404 })
    })
    vi.stubGlobal('fetch', fetchMock)
    renderPage(<PlanPage />, '/trips/trip-1/plan', '/trips/:id/plan')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /analyze trip/i }))
    await user.click(await screen.findByRole('checkbox', { name: /select ella/i }))
    await user.click(screen.getByRole('button', { name: /save selected places/i }))

    await screen.findByText(/route saved/i)
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/places/select'), expect.objectContaining({ method: 'POST' }))
  })
})
