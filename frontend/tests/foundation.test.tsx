import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { request } from '../src/lib/api'
import { AppRouter } from '../src/app/AppRouter'
import { queryKeys } from '../src/lib/queryKeys'


describe('API client', () => {
  it('normalizes JSON error details', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'Trip not found' }),
      { status: 404, headers: { 'Content-Type': 'application/json' } },
    )))

    await expect(request('/trips/missing')).rejects.toEqual(
      expect.objectContaining({ status: 404, message: 'Trip not found', name: 'ApiError' }),
    )
  })
})

describe('application router', () => {
  function renderRouter(path: string) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
    client.setQueryData(queryKeys.trips, [])
    return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><AppRouter /></MemoryRouter></QueryClientProvider>)
  }

  it('renders the dashboard route and primary action', () => {
    renderRouter('/')
    expect(screen.getByRole('heading', { name: /where to next/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /plan a trip/i })).toHaveAttribute('href', '/trips/new')
  })

  it('keeps all trip stages in a labelled navigation region', () => {
    renderRouter('/trips/demo')
    const navigation = screen.getByRole('navigation', { name: /trip route/i })
    expect(navigation).toHaveTextContent('Overview')
    expect(navigation).toHaveTextContent('Plan')
    expect(navigation).toHaveTextContent('Itinerary')
    expect(navigation).toHaveTextContent('Expenses')
    expect(navigation).toHaveTextContent('People')
    expect(navigation).toHaveTextContent('Summary')
  })
})
