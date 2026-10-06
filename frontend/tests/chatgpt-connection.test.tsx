import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ChatGPTConnection } from '../src/components/ChatGPTConnection'
import type { ChatGPTStatus } from '../src/lib/types'


const disconnectedStatus: ChatGPTStatus = {
  state: 'disconnected',
  signed_in: false,
  plan_enabled: false,
  name: null,
  email: null,
  models: [],
  selected_model: null,
  manage_usage_url: 'https://chatgpt.com/settings/usage',
}

const connectedStatus: ChatGPTStatus = {
  state: 'connected',
  signed_in: true,
  plan_enabled: true,
  name: 'TripWise Traveler',
  email: 'traveler@example.com',
  models: ['gpt-listable', 'gpt-second'],
  selected_model: 'gpt-listable',
  manage_usage_url: 'https://chatgpt.com/settings/usage',
}

function renderConnection(
  initialStatus: ChatGPTStatus,
  {
    path = '/',
    extras = {},
  }: { path?: string; extras?: Record<string, unknown> } = {},
) {
  window.history.replaceState({}, '', path)
  let status = initialStatus
  const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/auth/chatgpt/status')) {
      return new Response(JSON.stringify({ ...status, ...extras }), {
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (url.endsWith('/auth/chatgpt/model') && init?.method === 'POST') {
      const payload = JSON.parse(String(init.body)) as { model: string }
      status = { ...status, selected_model: payload.model }
      return new Response(JSON.stringify(status), {
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (url.endsWith('/auth/chatgpt/disconnect') && init?.method === 'POST') {
      status = disconnectedStatus
      return new Response(JSON.stringify(status), {
        headers: { 'Content-Type': 'application/json' },
      })
    }
    return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })
  })
  vi.stubGlobal('fetch', fetchMock)
  const startAuthorization = vi.fn()
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })

  render(
    <QueryClientProvider client={client}>
      <ChatGPTConnection onStartAuthorization={startAuthorization} />
    </QueryClientProvider>,
  )
  return { fetchMock, startAuthorization }
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  window.history.replaceState({}, '', '/')
})

describe('ChatGPT connection control', () => {
  it('starts the required ChatGPT connection flow', async () => {
    const { startAuthorization } = renderConnection(disconnectedStatus)
    const user = userEvent.setup()

    const button = await screen.findByRole('button', { name: 'Continue with ChatGPT' })
    expect(button.querySelector('img')).toHaveAttribute('src', '/chatgpt-logo-white.svg')
    await user.click(button)

    expect(startAuthorization).toHaveBeenCalledOnce()
  })

  it('shows plan state, selects a model, and disconnects', async () => {
    const { fetchMock } = renderConnection(connectedStatus)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: /using chatgpt plan/i }))
    expect(screen.getByText('TripWise Traveler')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Manage usage' })).toHaveAttribute(
      'href',
      'https://chatgpt.com/settings/usage',
    )

    await user.selectOptions(screen.getByLabelText('Model'), 'gpt-second')
    await waitFor(() => expect(screen.getByLabelText('Model')).toHaveValue('gpt-second'))
    await user.click(screen.getByRole('button', { name: 'Disconnect' }))

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/auth/chatgpt/disconnect'),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(await screen.findByRole('button', { name: 'Continue with ChatGPT' })).toBeInTheDocument()
  })

  it('welcomes the user after a successful callback and removes the marker', async () => {
    renderConnection(connectedStatus, { path: '/?chatgpt=connected&welcome=1' })

    const dialog = await screen.findByRole('dialog', { name: /chatgpt is connected/i })
    expect(dialog).toHaveTextContent('You’re using your ChatGPT plan.')
    expect(window.location.search).toBe('')
  })

  it('does not repeat the welcome after a returning sign-in', async () => {
    renderConnection(connectedStatus, { path: '/?chatgpt=connected' })

    await screen.findByRole('button', { name: /using chatgpt plan/i })
    expect(screen.queryByRole('dialog', { name: /chatgpt is connected/i })).not.toBeInTheDocument()
  })

  it('offers reconnection when direct plan scope was declined', async () => {
    const scopeRequired: ChatGPTStatus = {
      ...connectedStatus,
      state: 'scope_required',
      plan_enabled: false,
      models: [],
      selected_model: null,
    }
    renderConnection(scopeRequired, { path: '/?chatgpt=scope_required' })

    expect(await screen.findByText(/plan access wasn’t granted/i)).toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: 'Continue with ChatGPT' }),
    ).toBeInTheDocument()
  })

  it('explains when the account has no listable ChatGPT models', async () => {
    const noModelsStatus = {
      ...connectedStatus,
      state: 'model_required' as ChatGPTStatus['state'],
      plan_enabled: false,
      models: [],
      selected_model: null,
    }
    renderConnection(noModelsStatus)

    expect(
      await screen.findByText(/no supported chatgpt models are available/i),
    ).toBeInTheDocument()
  })

  it('shows a safe callback failure with a retry action', async () => {
    renderConnection(disconnectedStatus, {
      path: '/?chatgpt=error&reason=authorization_failed',
    })

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'ChatGPT could not be connected. Try again.',
    )
    expect(
      await screen.findByRole('button', { name: 'Continue with ChatGPT' }),
    ).toBeInTheDocument()
    expect(window.location.search).toBe('')
  })

  it.each([
    [
      'registration_incomplete',
      'ChatGPT did not finish registering TripTally. Start the connection again.',
    ],
    [
      'token_exchange_invalid_grant',
      'That ChatGPT sign-in code was already used or expired. Start again.',
    ],
    [
      'token_exchange_invalid_client',
      'ChatGPT rejected this TripTally registration. Start the connection again.',
    ],
    [
      'token_exchange_unavailable',
      'ChatGPT sign-in is temporarily unavailable. Try again in a moment.',
    ],
    [
      'token_exchange_failed',
      'TripTally could not complete the ChatGPT token exchange. Start again.',
    ],
    [
      'identity_validation_failed',
      'TripTally could not verify the ChatGPT account. Start the connection again.',
    ],
    [
      'model_discovery_failed',
      'ChatGPT is connected, but its model list could not be loaded. Try connecting again.',
    ],
  ])('explains the safe %s callback stage', async (reason, message) => {
    renderConnection(disconnectedStatus, {
      path: `/?chatgpt=error&reason=${reason}`,
    })

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(window.location.search).toBe('')
  })

  it('ignores credential fields from a malformed status response', async () => {
    renderConnection(connectedStatus, {
      extras: {
        access_token: 'secret-access-token',
        refresh_token: 'secret-refresh-token',
        client_id: 'secret-client-id',
        host_id: 'secret-host-id',
      },
    })

    await screen.findByRole('button', { name: /using chatgpt plan/i })
    expect(document.body).not.toHaveTextContent('secret-access-token')
    expect(document.body).not.toHaveTextContent('secret-refresh-token')
    expect(document.body).not.toHaveTextContent('secret-client-id')
    expect(document.body).not.toHaveTextContent('secret-host-id')
  })
})
