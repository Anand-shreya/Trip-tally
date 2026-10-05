import { useQuery } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'

import { getAIProviderStatus } from '../lib/ai'
import { queryKeys } from '../lib/queryKeys'

export function AIProviderStatus() {
  const status = useQuery({
    queryKey: queryKeys.aiProvider,
    queryFn: getAIProviderStatus,
    staleTime: 30_000,
  })
  const label = status.data?.label ?? (status.isError ? 'Local planning' : 'Checking AI…')
  const detail = status.data?.model ?? (status.isError ? 'AI unavailable' : 'Secure provider')

  return (
    <div
      aria-label="AI provider"
      className={`ai-provider-status${status.data?.ai_enabled ? ' ai-provider-active' : ''}`}
      role="status"
    >
      <Sparkles aria-hidden="true" size={17} />
      <span>
        <strong>{label}</strong>
        <small>{detail}</small>
      </span>
    </div>
  )
}
