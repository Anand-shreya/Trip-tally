import { api } from './api'
import type { ChatGPTStatus } from './types'


export const CHATGPT_START_URL = import.meta.env.VITE_CHATGPT_AUTH_URL
  ?? 'http://127.0.0.1:8000/api/v1/auth/chatgpt/start'

export function getChatGPTStatus() {
  return api.get<ChatGPTStatus>('/auth/chatgpt/status')
}

export function selectChatGPTModel(model: string) {
  return api.post<ChatGPTStatus>('/auth/chatgpt/model', { model })
}

export function disconnectChatGPT() {
  return api.post<ChatGPTStatus>('/auth/chatgpt/disconnect')
}

export function startChatGPTAuthorization() {
  window.location.assign(CHATGPT_START_URL)
}
