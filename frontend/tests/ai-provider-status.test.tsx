import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AIProviderStatus } from '../src/components/AIProviderStatus'


function renderStatus(response: Record<string, unknown>) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(response), {
    headers: { 'Content-Type': 'application/json' },
  })))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <AIProviderStatus />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('AI provider status', () => {
  it('shows the configured Gemini free-tier model', async () => {
    renderStatus({
      provider: 'gemini',
      label: 'Gemini free tier',
      model: 'gemini-3.5-flash-lite',
      ai_enabled: true,
    })

    await screen.findByText('Gemini free tier')
    const status = screen.getByRole('status', { name: /ai provider/i })
    expect(status).toHaveTextContent('Gemini free tier')
    expect(status).toHaveTextContent('gemini-3.5-flash-lite')
  })

  it('labels deterministic planning when hosted AI is unavailable', async () => {
    renderStatus({
      provider: 'local',
      label: 'Local planning',
      model: null,
      ai_enabled: false,
    })

    await screen.findByText('Local planning')
    const status = screen.getByRole('status', { name: /ai provider/i })
    expect(status).toHaveTextContent('Local planning')
    expect(status).not.toHaveTextContent('Gemini')
  })
})
