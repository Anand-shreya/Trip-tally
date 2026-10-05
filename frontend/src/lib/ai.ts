import { api } from './api'
import type { AIProviderStatus } from './types'

export function getAIProviderStatus() {
  return api.get<AIProviderStatus>('/ai/status')
}
