import { describe, it, expect } from 'vitest'
import { cn, formatCents, formatDate, parseEuroToCents, centsToEuroInput } from '../utils'

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar')
  })

  it('handles conditional classes', () => {
    const isHidden = false
    expect(cn('base', isHidden && 'hidden', 'extra')).toBe('base extra')
  })

  it('merges Tailwind classes correctly', () => {
    // tailwind-merge should resolve conflicting utilities
    expect(cn('px-4', 'px-2')).toBe('px-2')
  })

  it('handles undefined and null inputs', () => {
    expect(cn('foo', undefined, null, 'bar')).toBe('foo bar')
  })

  it('returns empty string with no inputs', () => {
    expect(cn()).toBe('')
  })
})

describe('formatCents', () => {
  it('formats positive amounts in EUR', () => {
    const result = formatCents(129999)
    // de-DE locale: 1.299,99 €
    expect(result).toContain('1.299,99')
    expect(result).toContain('€')
  })

  it('formats zero', () => {
    const result = formatCents(0)
    expect(result).toContain('0,00')
    expect(result).toContain('€')
  })

  it('formats negative amounts', () => {
    const result = formatCents(-5000)
    expect(result).toContain('50,00')
    expect(result).toContain('-')
  })

  it('formats small amounts', () => {
    const result = formatCents(99)
    expect(result).toContain('0,99')
  })
})

describe('formatDate', () => {
  it('formats a valid date string', () => {
    const result = formatDate('2024-06-15')
    // de-DE short month format: 15. Jun. 2024 (or similar)
    expect(result).toContain('2024')
    expect(result).toContain('15')
  })

  it('formats a Date object', () => {
    const result = formatDate(new Date('2024-01-01'))
    expect(result).toContain('2024')
  })

  it('formats an ISO datetime string', () => {
    const result = formatDate('2024-12-25T10:30:00Z')
    expect(result).toContain('2024')
    expect(result).toContain('25')
  })
})

describe('parseEuroToCents', () => {
  it('parses German format "1.234,56"', () => {
    expect(parseEuroToCents('1.234,56')).toBe(123456)
  })

  it('parses simple Euro format "49,90"', () => {
    expect(parseEuroToCents('49,90')).toBe(4990)
  })

  it('parses plain amount "750,00"', () => {
    expect(parseEuroToCents('750,00')).toBe(75000)
  })

  it('parses negative values', () => {
    expect(parseEuroToCents('-100,00')).toBe(-10000)
  })

  it('returns 0 for empty string', () => {
    expect(parseEuroToCents('')).toBe(0)
  })

  it('returns 0 for non-numeric string', () => {
    expect(parseEuroToCents('abc')).toBe(0)
  })

  it('parses value with Euro sign', () => {
    expect(parseEuroToCents('€ 1.299,99')).toBe(129999)
  })

  it('parses large amounts correctly', () => {
    expect(parseEuroToCents('10.000,00')).toBe(1000000)
  })
})

describe('centsToEuroInput', () => {
  it('formats cents to German locale string', () => {
    const result = centsToEuroInput(129999)
    // de-DE: 1.299,99
    expect(result).toBe('1.299,99')
  })

  it('returns empty string for zero', () => {
    expect(centsToEuroInput(0)).toBe('')
  })

  it('formats small amounts', () => {
    expect(centsToEuroInput(4990)).toBe('49,90')
  })

  it('round-trips with parseEuroToCents', () => {
    const original = 129999
    const formatted = centsToEuroInput(original)
    const parsed = parseEuroToCents(formatted)
    expect(parsed).toBe(original)
  })

  it('round-trips small amount', () => {
    const original = 4990
    const formatted = centsToEuroInput(original)
    const parsed = parseEuroToCents(formatted)
    expect(parsed).toBe(original)
  })
})
