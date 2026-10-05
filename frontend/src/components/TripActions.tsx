import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Archive, ArchiveRestore, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../lib/api'
import { queryKeys } from '../lib/queryKeys'
import type { Trip } from '../lib/types'
import { Button, Modal } from './ui'

export function TripActions({ trip, className = '' }: { trip: Trip; className?: string }) {
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  function updateTrip(updated: Trip) {
    queryClient.setQueryData(queryKeys.trip(updated.id), updated)
    queryClient.setQueryData<Trip[]>(queryKeys.trips, (trips) => (
      trips?.map((candidate) => candidate.id === updated.id ? updated : candidate)
    ))
  }

  const archive = useMutation({
    mutationFn: () => trip.is_archived
      ? api.delete<Trip>(`/trips/${trip.id}/archive`)
      : api.post<Trip>(`/trips/${trip.id}/archive`),
    onSuccess: updateTrip,
  })

  const remove = useMutation({
    mutationFn: () => api.delete(`/trips/${trip.id}`),
    onSuccess: () => {
      queryClient.setQueryData<Trip[]>(queryKeys.trips, (trips) => (
        trips?.filter((candidate) => candidate.id !== trip.id)
      ))
      queryClient.removeQueries({ queryKey: queryKeys.trip(trip.id) })
      setConfirmingDelete(false)
      navigate('/')
    },
  })

  const archiveLabel = trip.is_archived ? `Restore ${trip.name}` : `Archive ${trip.name}`
  const ArchiveIcon = trip.is_archived ? ArchiveRestore : Archive

  return (
    <>
      <div className={`trip-actions ${className}`}>
        <button
          type="button"
          className="trip-action"
          aria-label={archiveLabel}
          disabled={archive.isPending || remove.isPending}
          onClick={() => archive.mutate()}
        >
          <ArchiveIcon size={17} aria-hidden="true" />
          {archive.isPending ? 'Saving…' : trip.is_archived ? 'Restore' : 'Archive'}
        </button>
        <button
          type="button"
          className="trip-action trip-action-danger"
          aria-label={`Delete ${trip.name}`}
          disabled={archive.isPending || remove.isPending}
          onClick={() => setConfirmingDelete(true)}
        >
          <Trash2 size={17} aria-hidden="true" />
          Delete
        </button>
      </div>
      {archive.isError && <p className="trip-action-error" role="alert">{archive.error.message}</p>}
      {confirmingDelete && (
        <Modal title={`Delete ${trip.name}?`} onClose={() => !remove.isPending && setConfirmingDelete(false)}>
          <div className="delete-warning">
            <Trash2 aria-hidden="true" />
            <p>This permanently deletes the trip, including its travelers, expenses and itinerary. This cannot be undone.</p>
          </div>
          {remove.isError && <p className="trip-action-error" role="alert">{remove.error.message}</p>}
          <div className="modal-actions">
            <Button className="ghost" disabled={remove.isPending} onClick={() => setConfirmingDelete(false)}>Keep trip</Button>
            <Button className="danger" disabled={remove.isPending} onClick={() => remove.mutate()}>
              {remove.isPending ? 'Deleting…' : 'Delete permanently'}
            </Button>
          </div>
        </Modal>
      )}
    </>
  )
}
