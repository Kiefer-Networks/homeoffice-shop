import { AxiosError } from 'axios'

export function getErrorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    // API error with detail
    if (err.response?.data?.detail) {
      return err.response.data.detail
    }
    // Network error
    if (!err.response) {
      return 'Network error — please check your connection and try again'
    }
    // HTTP status fallbacks
    const status = err.response.status
    if (status === 403) return 'You do not have permission for this action'
    if (status === 404) return 'The requested resource was not found'
    if (status === 409) return 'This action conflicts with the current state'
    if (status === 429) return 'Too many requests — please wait a moment'
    if (status >= 500) return 'Server error — please try again later'
  }
  if (err instanceof Error) return err.message
  return 'An unexpected error occurred'
}
