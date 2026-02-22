import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

const LOCALE = 'de-DE'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCents(cents: number): string {
  return new Intl.NumberFormat(LOCALE, {
    style: 'currency',
    currency: 'EUR',
  }).format(cents / 100)
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat(LOCALE, {
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
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(cents / 100)
}

export interface DetectedCarrier {
  name: string
  trackingUrl: string
}

const CARRIER_PATTERNS: { name: string; pattern: RegExp; url: (n: string) => string }[] = [
  // Amazon Swiship DE: DE + 10 digits
  { name: 'Amazon (Swiship)', pattern: /^DE\d{10}$/i, url: n => `https://www.swiship.com/track?id=${n}` },
  // Amazon Logistics US: TBA/TBC/TBM + 12 digits
  { name: 'Amazon Logistics', pattern: /^TB[ACM]\d{12}$/i, url: n => `https://track.amazon.com/tracking/${n}` },
  // UPS: 1Z + 6 alphanum + 2 alphanum + 7 alphanum + 1 check digit
  { name: 'UPS', pattern: /^1Z[A-Z0-9]{16}$/i, url: n => `https://wwwapps.ups.com/WebTracking/track?track=yes&trackNums=${n}` },
  // DHL Express: JJD + 18-20 digits
  { name: 'DHL Express', pattern: /^JJD\d{18,20}$/i, url: n => `https://www.dhl.com/de-de/home/tracking/tracking-parcel.html?submit=1&tracking-id=${n}` },
  // DHL Paket: 12-20 pure digits (common DE domestic)
  { name: 'DHL Paket', pattern: /^\d{12,20}$/, url: n => `https://www.dhl.de/de/privatkunden/dhl-sendungsverfolgung.html?piececode=${n}` },
  // DPD: 14-15 digits
  { name: 'DPD', pattern: /^\d{14,15}$/, url: n => `https://tracking.dpd.de/parcelstatus?query=${n}&locale=de_DE` },
  // Hermes: 16 digits
  { name: 'Hermes', pattern: /^\d{16}$/, url: n => `https://www.myhermes.de/empfangen/sendungsverfolgung/sendungsinformation#${n}` },
  // GLS: 11-12 digits or alphanumeric
  { name: 'GLS', pattern: /^[A-Z0-9]{11,12}$/i, url: n => `https://gls-group.eu/DE/de/paketverfolgung?match=${n}` },
]

/** Detect carrier from tracking number and return name + tracking URL */
export function detectCarrier(trackingNumber: string): DetectedCarrier | null {
  const cleaned = trackingNumber.trim()
  if (!cleaned) return null
  for (const c of CARRIER_PATTERNS) {
    if (c.pattern.test(cleaned)) {
      return { name: c.name, trackingUrl: c.url(cleaned) }
    }
  }
  return null
}

/** Check if a URL is an authenticated Amazon page (not useful for employees) */
export function isAmazonAuthUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    return parsed.hostname.includes('amazon.') && parsed.pathname.includes('/your-account/')
  } catch {
    return false
  }
}
