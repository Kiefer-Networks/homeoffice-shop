import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCents(cents: number): string {
  return new Intl.NumberFormat('de-DE', {
    style: 'currency',
    currency: 'EUR',
  }).format(cents / 100)
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat('de-DE', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(new Date(date))
}

/** Parse a Euro string like "1.299,99" or "49,90" or "-100,00" to cents */
export function parseEuroToCents(value: string): number {
  if (!value) return 0
  const negative = value.trim().startsWith('-')
  const cleaned = value.replace(/[^\d.,]/g, '')
  if (!cleaned) return 0
  // German format: dot=thousands, comma=decimal
  const normalized = cleaned.replace(/\./g, '').replace(',', '.')
  const num = parseFloat(normalized)
  if (isNaN(num)) return 0
  return Math.round(num * 100) * (negative ? -1 : 1)
}

/** Format cents to Euro input value like "1.299,99" */
export function centsToEuroInput(cents: number): string {
  if (!cents) return ''
  return new Intl.NumberFormat('de-DE', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(cents / 100)
}
