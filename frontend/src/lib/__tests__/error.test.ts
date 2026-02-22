import { describe, it, expect } from 'vitest'
import { AxiosError, AxiosHeaders } from 'axios'
import { getErrorMessage } from '../error'

function makeAxiosError(
  status: number | null,
  data?: Record<string, unknown>,
): AxiosError {
  const headers = new AxiosHeaders()
  const config = { headers } as import('axios').InternalAxiosRequestConfig

  if (status === null) {
    // Network error — no response
    const error = new AxiosError('Network Error', 'ERR_NETWORK', config)
    return error
  }

  const error = new AxiosError(
    `Request failed with status code ${status}`,
    'ERR_BAD_RESPONSE',
    config,
    undefined,
    {
      status,
      statusText: 'Error',
      headers: {},
      config,
      data: data ?? {},
    },
  )
  return error
}

describe('getErrorMessage', () => {
  it('extracts detail from AxiosError response', () => {
    const err = makeAxiosError(400, { detail: 'Validation failed' })
    expect(getErrorMessage(err)).toBe('Validation failed')
  })

  it('returns network error message when no response', () => {
    const err = makeAxiosError(null)
    expect(getErrorMessage(err)).toBe(
      'Network error — please check your connection and try again',
    )
  })

  it('returns permission message for 403', () => {
    const err = makeAxiosError(403)
    expect(getErrorMessage(err)).toBe('You do not have permission for this action')
  })

  it('returns not found message for 404', () => {
    const err = makeAxiosError(404)
    expect(getErrorMessage(err)).toBe('The requested resource was not found')
  })

  it('returns conflict message for 409', () => {
    const err = makeAxiosError(409)
    expect(getErrorMessage(err)).toBe('This action conflicts with the current state')
  })

  it('returns rate limit message for 429', () => {
    const err = makeAxiosError(429)
    expect(getErrorMessage(err)).toBe('Too many requests — please wait a moment')
  })

  it('returns server error message for 500+', () => {
    const err = makeAxiosError(500)
    expect(getErrorMessage(err)).toBe('Server error — please try again later')

    const err502 = makeAxiosError(502)
    expect(getErrorMessage(err502)).toBe('Server error — please try again later')
  })

  it('handles plain Error instances', () => {
    const err = new Error('Something broke')
    expect(getErrorMessage(err)).toBe('Something broke')
  })

  it('handles unknown error types', () => {
    expect(getErrorMessage('a string error')).toBe('An unexpected error occurred')
    expect(getErrorMessage(42)).toBe('An unexpected error occurred')
    expect(getErrorMessage(null)).toBe('An unexpected error occurred')
    expect(getErrorMessage(undefined)).toBe('An unexpected error occurred')
  })
})
