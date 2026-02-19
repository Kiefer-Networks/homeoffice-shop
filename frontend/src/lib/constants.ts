export const DEFAULT_PAGE_SIZE = 20

export const ORDER_STATUS_VARIANT: Record<string, 'default' | 'secondary' | 'success' | 'destructive' | 'warning'> = {
  pending: 'warning',
  ordered: 'default',
  delivered: 'success',
  rejected: 'destructive',
  cancelled: 'secondary',
}

export const PURCHASE_STATUS_VARIANT: Record<string, 'default' | 'secondary' | 'success' | 'destructive' | 'warning'> = {
  pending: 'warning',
  matched: 'success',
  adjusted: 'default',
  dismissed: 'secondary',
}
