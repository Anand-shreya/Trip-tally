import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { request } from '../src/lib/api'
import { AppRouter } from '../src/app/AppRouter'


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
  it('renders the dashboard route and primary action', () => {
    render(<MemoryRouter initialEntries={['/']}><AppRouter /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: /where to next/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /plan a trip/i })).toHaveAttribute('href', '/trips/new')
  })

  it('keeps all trip stages in a labelled navigation region', () => {
    render(<MemoryRouter initialEntries={['/trips/demo']}><AppRouter /></MemoryRouter>)
    const navigation = screen.getByRole('navigation', { name: /trip route/i })
    expect(navigation).toHaveTextContent('Overview')
    expect(navigation).toHaveTextContent('Plan')
    expect(navigation).toHaveTextContent('Itinerary')
    expect(navigation).toHaveTextContent('Expenses')
    expect(navigation).toHaveTextContent('People')
    expect(navigation).toHaveTextContent('Summary')
  })
})
