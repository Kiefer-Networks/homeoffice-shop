import React, { Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useBrandingStore } from '@/stores/brandingStore'
import { authApi } from '@/services/authApi'
import { setAccessToken } from '@/lib/token'
import { ShopLayout } from '@/components/layout/ShopLayout'
import { AdminLayout } from '@/components/layout/AdminLayout'
import { LoginPage } from '@/pages/auth/LoginPage'
import { CallbackPage } from '@/pages/auth/CallbackPage'
import { ProbationBlockedPage } from '@/pages/auth/ProbationBlockedPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
const CatalogPage = React.lazy(() => import('@/pages/shop/CatalogPage').then(m => ({ default: m.CatalogPage })))
const OrdersPage = React.lazy(() => import('@/pages/shop/OrdersPage').then(m => ({ default: m.OrdersPage })))
const ProfilePage = React.lazy(() => import('@/pages/ProfilePage').then(m => ({ default: m.ProfilePage })))
import { useUiStore, type Toast } from '@/stores/uiStore'

const DashboardPage = React.lazy(() => import('@/pages/admin/DashboardPage').then(m => ({ default: m.DashboardPage })))
const AdminProductsPage = React.lazy(() => import('@/pages/admin/ProductsPage').then(m => ({ default: m.AdminProductsPage })))
const AdminOrdersPage = React.lazy(() => import('@/pages/admin/OrdersPage').then(m => ({ default: m.AdminOrdersPage })))
const AdminCategoriesPage = React.lazy(() => import('@/pages/admin/CategoriesPage').then(m => ({ default: m.AdminCategoriesPage })))
const AdminEmployeesPage = React.lazy(() => import('@/pages/admin/EmployeesPage').then(m => ({ default: m.AdminEmployeesPage })))
const AdminBudgetAdjustmentsPage = React.lazy(() => import('@/pages/admin/BudgetAdjustmentsPage').then(m => ({ default: m.AdminBudgetAdjustmentsPage })))
const AdminSettingsPage = React.lazy(() => import('@/pages/admin/SettingsPage').then(m => ({ default: m.AdminSettingsPage })))
const AdminAuditLogPage = React.lazy(() => import('@/pages/admin/AuditLogPage').then(m => ({ default: m.AdminAuditLogPage })))
const AdminSyncLogPage = React.lazy(() => import('@/pages/admin/SyncLogPage').then(m => ({ default: m.AdminSyncLogPage })))
const AdminBrandsPage = React.lazy(() => import('@/pages/admin/BrandsPage').then(m => ({ default: m.AdminBrandsPage })))
const PurchaseReviewsPage = React.lazy(() => import('@/pages/admin/PurchaseReviewsPage').then(m => ({ default: m.PurchaseReviewsPage })))
const AdminBackupPage = React.lazy(() => import('@/pages/admin/BackupPage').then(m => ({ default: m.AdminBackupPage })))

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fullPage?: boolean; fallback?: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode; fullPage?: boolean; fallback?: React.ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo)
  }
  render() {
    if (this.state.hasError) {
      // If a custom fallback is provided (including null), render it directly
      if (this.props.fallback !== undefined) {
        return <>{this.props.fallback}</>
      }
      const wrapper = this.props.fullPage
        ? 'min-h-screen flex items-center justify-center'
        : 'flex items-center justify-center py-12'
      return (
        <div className={wrapper}>
          <div className="text-center">
            <p className="text-lg font-medium">
              {this.props.fullPage ? 'An unexpected error occurred.' : 'This page encountered an error.'}
            </p>
            {!this.props.fullPage && this.state.error?.message && (
              <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
                {this.state.error.message}
              </p>
            )}
            <button
              className="mt-4 px-4 py-2 bg-[hsl(var(--primary))] text-white rounded-md"
              onClick={() => this.props.fullPage
                ? window.location.reload()
                : this.setState({ hasError: false, error: null })
              }
            >
              {this.props.fullPage ? 'Reload page' : 'Try again'}
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthStore()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[hsl(var(--primary))]" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function AdminGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore()

  if (user?.role !== 'admin' && user?.role !== 'manager') {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

function AdminOnlyGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore()

  if (user?.role !== 'admin') {
    return <Navigate to="/admin" replace />
  }

  return <>{children}</>
}

function AppInit({ children }: { children: React.ReactNode }) {
  const { setAccessToken: setStoreToken, setUser, logout } = useAuthStore()
  const { fetchBranding } = useBrandingStore()

  useEffect(() => {
    fetchBranding()
    authApi.refresh()
      .then(({ data }) => {
        const token = data.access_token
        setAccessToken(token)
        setStoreToken(token)
        return authApi.getMe()
      })
      .then(({ data }) => {
        setUser(data)
      })
      .catch(() => {
        logout()
      })
  }, [])

  return <>{children}</>
}

function ToastContainer() {
  const { toasts, removeToast } = useUiStore()

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2" role="region" aria-live="polite" aria-label="Notifications">
      {toasts.map((toast: Toast) => (
        <div
          key={toast.id}
          role="alert"
          className={`rounded-lg shadow-lg p-4 max-w-sm border cursor-pointer ${
            toast.variant === 'destructive'
              ? 'bg-red-50 border-red-200 text-red-800'
              : 'bg-white border-gray-200'
          }`}
          onClick={() => removeToast(toast.id)}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') removeToast(toast.id) }}
          tabIndex={0}
        >
          <p className="font-medium text-sm">{toast.title}</p>
          {toast.description && <p className="text-xs mt-1 opacity-75">{toast.description}</p>}
        </div>
      ))}
    </div>
  )
}

function PageFallback() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[hsl(var(--primary))]" />
    </div>
  )
}

export default function App() {
  return (
    <ErrorBoundary fullPage>
    <BrowserRouter>
      <AppInit>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/callback" element={<CallbackPage />} />
          <Route path="/probation-blocked" element={<ProbationBlockedPage />} />

          {/* Shop routes */}
          <Route element={<AuthGuard><ShopLayout /></AuthGuard>}>
            <Route path="/" element={<ErrorBoundary><Suspense fallback={<PageFallback />}><CatalogPage /></Suspense></ErrorBoundary>} />
            <Route path="/orders" element={<ErrorBoundary><Suspense fallback={<PageFallback />}><OrdersPage /></Suspense></ErrorBoundary>} />
            <Route path="/profile" element={<ErrorBoundary><Suspense fallback={<PageFallback />}><ProfilePage /></Suspense></ErrorBoundary>} />
          </Route>

          {/* Admin routes */}
          <Route element={<AuthGuard><AdminGuard><AdminLayout /></AdminGuard></AuthGuard>}>
            <Route path="/admin" element={<ErrorBoundary><Suspense fallback={<PageFallback />}><DashboardPage /></Suspense></ErrorBoundary>} />
            <Route path="/admin/products" element={<ErrorBoundary><Suspense fallback={<PageFallback />}><AdminProductsPage /></Suspense></ErrorBoundary>} />
            <Route path="/admin/brands" element={<ErrorBoundary><Suspense fallback={<PageFallback />}><AdminBrandsPage /></Suspense></ErrorBoundary>} />
            <Route path="/admin/orders" element={<ErrorBoundary><Suspense fallback={<PageFallback />}><AdminOrdersPage /></Suspense></ErrorBoundary>} />
            <Route path="/admin/categories" element={<ErrorBoundary><Suspense fallback={<PageFallback />}><AdminCategoriesPage /></Suspense></ErrorBoundary>} />
            <Route path="/admin/employees" element={<ErrorBoundary><Suspense fallback={<PageFallback />}><AdminEmployeesPage /></Suspense></ErrorBoundary>} />
            <Route path="/admin/budgets" element={<ErrorBoundary><Suspense fallback={<PageFallback />}><AdminBudgetAdjustmentsPage /></Suspense></ErrorBoundary>} />
            <Route path="/admin/purchase-reviews" element={<ErrorBoundary><Suspense fallback={<PageFallback />}><PurchaseReviewsPage /></Suspense></ErrorBoundary>} />
            <Route path="/admin/settings" element={<AdminOnlyGuard><ErrorBoundary><Suspense fallback={<PageFallback />}><AdminSettingsPage /></Suspense></ErrorBoundary></AdminOnlyGuard>} />
            <Route path="/admin/audit" element={<AdminOnlyGuard><ErrorBoundary><Suspense fallback={<PageFallback />}><AdminAuditLogPage /></Suspense></ErrorBoundary></AdminOnlyGuard>} />
            <Route path="/admin/sync-log" element={<AdminOnlyGuard><ErrorBoundary><Suspense fallback={<PageFallback />}><AdminSyncLogPage /></Suspense></ErrorBoundary></AdminOnlyGuard>} />
            <Route path="/admin/backups" element={<AdminOnlyGuard><ErrorBoundary><Suspense fallback={<PageFallback />}><AdminBackupPage /></Suspense></ErrorBoundary></AdminOnlyGuard>} />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
        <ToastContainer />
      </AppInit>
    </BrowserRouter>
    </ErrorBoundary>
  )
}
