import { describe, expect, it } from 'vitest'

import { waitForJob } from '../src/lib/jobs'
import type { Job } from '../src/lib/types'

const job = (status: string): Job => ({
  id: 'job-1', trip_id: 'trip-1', type: 'GENERATE_ITINERARY', status,
  attempt: status === 'PENDING' ? 0 : 1, max_attempts: 3, result: null, error: null,
})

describe('queued itinerary jobs', () => {
  it('polls until the worker reports success', async () => {
    const responses = [job('RUNNING'), job('SUCCESS')]
    let requestCount = 0

    const result = await waitForJob(
      job('PENDING'),
      async () => responses[requestCount++],
      { intervalMs: 0, maxPolls: 3 },
    )

    expect(result.status).toBe('SUCCESS')
    expect(requestCount).toBe(2)
  })

  it('surfaces a terminal worker error', async () => {
    await expect(waitForJob(
      job('PENDING'),
      async () => ({ ...job('DEAD'), error: 'provider unavailable' }),
      { intervalMs: 0, maxPolls: 2 },
    )).rejects.toThrow('provider unavailable')
  })
})
