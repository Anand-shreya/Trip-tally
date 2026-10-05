export function googleMapsSearchUrl(placeName: string, destination: string): string {
  const query = encodeURIComponent(`${placeName} ${destination}`)
  return `https://www.google.com/maps/search/?api=1&query=${query}`
}
