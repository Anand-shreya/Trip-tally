import type { Job } from './types'

interface PollOptions {
  intervalMs?: number
  maxPolls?: number
}

const pause = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds))

export async function waitForJob(
  initial: Job,
  fetchJob: (jobId: string) => Promise<Job>,
  { intervalMs = 1200, maxPolls = 250 }: PollOptions = {},
): Promise<Job> {
  let current = initial
  for (let poll = 0; poll <= maxPolls; poll += 1) {
    if (current.status === 'SUCCESS') return current
    if (current.status === 'DEAD' || current.status === 'FAILED') {
      throw new Error(current.error || 'Itinerary generation failed.')
    }
    if (poll === maxPolls) break
    await pause(intervalMs)
    current = await fetchJob(current.id)
  }
  throw new Error('Itinerary generation timed out. Check the job again shortly.')
}
