import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ExternalLink, LogOut, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import {
  disconnectChatGPT,
  getChatGPTStatus,
  selectChatGPTModel,
  startChatGPTAuthorization,
} from '../lib/chatgpt'
import { queryKeys } from '../lib/queryKeys'
import type { ChatGPTStatus } from '../lib/types'


interface ChatGPTConnectionProps {
  onStartAuthorization?: () => void
}

interface CallbackState {
  result: string | null
  reason: string | null
  welcome: boolean
}

function readCallbackState(): CallbackState {
  const parameters = new URLSearchParams(window.location.search)
  return {
    result: parameters.get('chatgpt'),
    reason: parameters.get('reason'),
    welcome: parameters.get('welcome') === '1',
  }
}

function clearCallbackState() {
  const url = new URL(window.location.href)
  url.searchParams.delete('chatgpt')
  url.searchParams.delete('reason')
  url.searchParams.delete('welcome')
  const cleanUrl = `${url.pathname}${url.search}${url.hash}`
  window.history.replaceState(window.history.state, '', cleanUrl)
}

function callbackErrorMessage(reason: string | null) {
  if (reason === 'state_mismatch') {
    return 'The ChatGPT sign-in expired. Start again to connect.'
  }
  if (reason === 'registration_incomplete') {
    return 'ChatGPT did not finish registering TripWise. Start the connection again.'
  }
  if (reason === 'token_exchange_invalid_grant') {
    return 'That ChatGPT sign-in code was already used or expired. Start again.'
  }
  if (reason === 'token_exchange_invalid_client') {
    return 'ChatGPT rejected this TripWise registration. Start the connection again.'
  }
  if (reason === 'token_exchange_unavailable') {
    return 'ChatGPT sign-in is temporarily unavailable. Try again in a moment.'
  }
  if (reason === 'token_exchange_failed') {
    return 'TripWise could not complete the ChatGPT token exchange. Start again.'
  }
  if (reason === 'identity_validation_failed') {
    return 'TripWise could not verify the ChatGPT account. Start the connection again.'
  }
  if (reason === 'model_discovery_failed') {
    return 'ChatGPT is connected, but its model list could not be loaded. Try connecting again.'
  }
  return 'ChatGPT could not be connected. Try again.'
}

export function ChatGPTConnection({
  onStartAuthorization = startChatGPTAuthorization,
}: ChatGPTConnectionProps) {
  const queryClient = useQueryClient()
  const containerRef = useRef<HTMLDivElement>(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const [callback] = useState(readCallbackState)
  const [welcomeOpen, setWelcomeOpen] = useState(
    callback.result === 'connected' && callback.welcome,
  )
  const statusQuery = useQuery({
    queryKey: queryKeys.chatgpt,
    queryFn: getChatGPTStatus,
    staleTime: 15_000,
  })

  const updateCachedStatus = (status: ChatGPTStatus) => {
    queryClient.setQueryData(queryKeys.chatgpt, status)
  }
  const modelMutation = useMutation({
    mutationFn: selectChatGPTModel,
    onSuccess: updateCachedStatus,
  })
  const disconnectMutation = useMutation({
    mutationFn: disconnectChatGPT,
    onSuccess: (status) => {
      updateCachedStatus(status)
      setPanelOpen(false)
    },
  })

  useEffect(() => {
    if (callback.result) clearCallbackState()
  }, [callback.result])

  useEffect(() => {
    const closeOnOutsidePress = (event: PointerEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setPanelOpen(false)
      }
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setPanelOpen(false)
        setWelcomeOpen(false)
      }
    }
    document.addEventListener('pointerdown', closeOnOutsidePress)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsidePress)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [])

  const status = statusQuery.data
  const isConnected = status?.plan_enabled === true
  const needsScope = status?.state === 'scope_required'
  const needsModel = status?.state === 'model_required'
  const mutationError = modelMutation.error ?? disconnectMutation.error

  return (
    <div className="chatgpt-connection" ref={containerRef}>
      {isConnected ? (
        <button
          aria-expanded={panelOpen}
          aria-haspopup="dialog"
          className="chatgpt-plan-trigger"
          onClick={() => setPanelOpen((open) => !open)}
          type="button"
        >
          <span className="chatgpt-status-dot" aria-hidden="true" />
          <span className="chatgpt-trigger-copy">
            <strong>Using ChatGPT plan</strong>
            <small>{status.selected_model}</small>
          </span>
          <ChevronDown size={16} aria-hidden="true" />
        </button>
      ) : (
        <button
          className="chatgpt-connect-button"
          disabled={statusQuery.isLoading}
          onClick={onStartAuthorization}
          type="button"
        >
          <img alt="" src="/chatgpt-logo-white.svg" />
          {statusQuery.isLoading ? 'Checking ChatGPT…' : 'Continue with ChatGPT'}
        </button>
      )}

      {needsScope && (
        <div className="chatgpt-inline-notice" role="status">
          ChatGPT is connected, but plan access wasn’t granted. Continue again to approve it.
        </div>
      )}

      {needsModel && (
        <div className="chatgpt-inline-notice" role="status">
          This account is connected, but no supported ChatGPT models are available.
        </div>
      )}

      {callback.result === 'error' && (
        <div className="chatgpt-inline-notice chatgpt-inline-error" role="alert">
          {callbackErrorMessage(callback.reason)}
        </div>
      )}

      {panelOpen && isConnected && status && (
        <section
          aria-label="ChatGPT connection settings"
          className="chatgpt-panel"
          role="dialog"
        >
          <header>
            <div>
              <strong>{status.name || 'ChatGPT account'}</strong>
              {status.email && <span>{status.email}</span>}
            </div>
            <span className="chatgpt-plan-badge">Plan active</span>
          </header>

          <label className="chatgpt-model-field">
            <span>Model</span>
            <select
              disabled={modelMutation.isPending}
              onChange={(event) => modelMutation.mutate(event.target.value)}
              value={status.selected_model || ''}
            >
              {status.models.map((model) => <option key={model} value={model}>{model}</option>)}
            </select>
          </label>

          {mutationError && (
            <p className="chatgpt-panel-error" role="alert">
              {mutationError instanceof Error ? mutationError.message : 'The change could not be saved.'}
            </p>
          )}

          <footer>
            <a href={status.manage_usage_url} rel="noreferrer" target="_blank">
              <ExternalLink size={15} aria-hidden="true" /> Manage usage
            </a>
            <button
              disabled={disconnectMutation.isPending}
              onClick={() => disconnectMutation.mutate()}
              type="button"
            >
              <LogOut size={15} aria-hidden="true" /> Disconnect
            </button>
          </footer>
        </section>
      )}

      {welcomeOpen && isConnected && (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="chatgpt-welcome-title"
            aria-modal="true"
            className="modal chatgpt-welcome"
            role="dialog"
          >
            <button
              aria-label="Close"
              className="icon-button chatgpt-welcome-close"
              onClick={() => setWelcomeOpen(false)}
              type="button"
            >
              <X aria-hidden="true" />
            </button>
            <span className="chatgpt-welcome-mark" aria-hidden="true">
              <img alt="" src="/chatgpt-logo-white.svg" />
            </span>
            <h2 id="chatgpt-welcome-title">ChatGPT is connected</h2>
            <p>
              You’re using your ChatGPT plan. Eligible AI requests in TripWise will use your
              plan, and you can manage usage in ChatGPT settings.
            </p>
            <button className="button secondary" onClick={() => setWelcomeOpen(false)} type="button">
              Got it
            </button>
          </section>
        </div>
      )}
    </div>
  )
}
