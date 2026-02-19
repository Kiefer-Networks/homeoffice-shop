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
import { CatalogPage } from '@/pages/shop/CatalogPage'
import { OrdersPage } from '@/pages/shop/OrdersPage'
import { ProfilePage } from '@/pages/ProfilePage'
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

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false }
  }
  static getDerivedStateFromError() {
    return { hasError: true }
  }
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <p className="text-lg font-medium">An unexpected error occurred.</p>
            <button
              className="mt-4 px-4 py-2 bg-[hsl(var(--primary))] text-white rounded-md"
              onClick={() => window.location.reload()}
            >
              Reload page
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

function AdminFallback() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[hsl(var(--primary))]" />
    </div>
  )
}

class RouteErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Route error:', error, errorInfo)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <p className="text-lg font-medium">This page encountered an error.</p>
            <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
              {this.state.error?.message || 'An unexpected error occurred.'}
            </p>
            <button
              className="mt-4 px-4 py-2 bg-[hsl(var(--primary))] text-white rounded-md"
              onClick={() => this.setState({ hasError: false, error: null })}
            >
              Try again
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  return (
    <ErrorBoundary>
    <BrowserRouter>
      <AppInit>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/callback" element={<CallbackPage />} />
          <Route path="/probation-blocked" element={<ProbationBlockedPage />} />

          {/* Shop routes */}
          <Route element={<AuthGuard><ShopLayout /></AuthGuard>}>
            <Route path="/" element={<CatalogPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Route>

          {/* Admin routes */}
          <Route element={<AuthGuard><AdminGuard><AdminLayout /></AdminGuard></AuthGuard>}>
            <Route path="/admin" element={<RouteErrorBoundary><Suspense fallback={<AdminFallback />}><DashboardPage /></Suspense></RouteErrorBoundary>} />
            <Route path="/admin/products" element={<RouteErrorBoundary><Suspense fallback={<AdminFallback />}><AdminProductsPage /></Suspense></RouteErrorBoundary>} />
            <Route path="/admin/brands" element={<RouteErrorBoundary><Suspense fallback={<AdminFallback />}><AdminBrandsPage /></Suspense></RouteErrorBoundary>} />
            <Route path="/admin/orders" element={<RouteErrorBoundary><Suspense fallback={<AdminFallback />}><AdminOrdersPage /></Suspense></RouteErrorBoundary>} />
            <Route path="/admin/categories" element={<RouteErrorBoundary><Suspense fallback={<AdminFallback />}><AdminCategoriesPage /></Suspense></RouteErrorBoundary>} />
            <Route path="/admin/employees" element={<RouteErrorBoundary><Suspense fallback={<AdminFallback />}><AdminEmployeesPage /></Suspense></RouteErrorBoundary>} />
            <Route path="/admin/budgets" element={<RouteErrorBoundary><Suspense fallback={<AdminFallback />}><AdminBudgetAdjustmentsPage /></Suspense></RouteErrorBoundary>} />
            <Route path="/admin/purchase-reviews" element={<RouteErrorBoundary><Suspense fallback={<AdminFallback />}><PurchaseReviewsPage /></Suspense></RouteErrorBoundary>} />
            <Route path="/admin/settings" element={<AdminOnlyGuard><RouteErrorBoundary><Suspense fallback={<AdminFallback />}><AdminSettingsPage /></Suspense></RouteErrorBoundary></AdminOnlyGuard>} />
            <Route path="/admin/audit" element={<AdminOnlyGuard><RouteErrorBoundary><Suspense fallback={<AdminFallback />}><AdminAuditLogPage /></Suspense></RouteErrorBoundary></AdminOnlyGuard>} />
            <Route path="/admin/sync-log" element={<AdminOnlyGuard><RouteErrorBoundary><Suspense fallback={<AdminFallback />}><AdminSyncLogPage /></Suspense></RouteErrorBoundary></AdminOnlyGuard>} />
            <Route path="/admin/backups" element={<AdminOnlyGuard><RouteErrorBoundary><Suspense fallback={<AdminFallback />}><AdminBackupPage /></Suspense></RouteErrorBoundary></AdminOnlyGuard>} />
          </Route>
        </Routes>
        <ToastContainer />
      </AppInit>
    </BrowserRouter>
    </ErrorBoundary>
  )
}
