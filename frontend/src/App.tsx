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
            <Route path="/admin" element={<Suspense fallback={<AdminFallback />}><DashboardPage /></Suspense>} />
            <Route path="/admin/products" element={<Suspense fallback={<AdminFallback />}><AdminProductsPage /></Suspense>} />
            <Route path="/admin/brands" element={<Suspense fallback={<AdminFallback />}><AdminBrandsPage /></Suspense>} />
            <Route path="/admin/orders" element={<Suspense fallback={<AdminFallback />}><AdminOrdersPage /></Suspense>} />
            <Route path="/admin/categories" element={<Suspense fallback={<AdminFallback />}><AdminCategoriesPage /></Suspense>} />
            <Route path="/admin/employees" element={<Suspense fallback={<AdminFallback />}><AdminEmployeesPage /></Suspense>} />
            <Route path="/admin/budgets" element={<Suspense fallback={<AdminFallback />}><AdminBudgetAdjustmentsPage /></Suspense>} />
            <Route path="/admin/purchase-reviews" element={<Suspense fallback={<AdminFallback />}><PurchaseReviewsPage /></Suspense>} />
            <Route path="/admin/settings" element={<AdminOnlyGuard><Suspense fallback={<AdminFallback />}><AdminSettingsPage /></Suspense></AdminOnlyGuard>} />
            <Route path="/admin/audit" element={<AdminOnlyGuard><Suspense fallback={<AdminFallback />}><AdminAuditLogPage /></Suspense></AdminOnlyGuard>} />
            <Route path="/admin/sync-log" element={<AdminOnlyGuard><Suspense fallback={<AdminFallback />}><AdminSyncLogPage /></Suspense></AdminOnlyGuard>} />
            <Route path="/admin/backups" element={<AdminOnlyGuard><Suspense fallback={<AdminFallback />}><AdminBackupPage /></Suspense></AdminOnlyGuard>} />
          </Route>
        </Routes>
        <ToastContainer />
      </AppInit>
    </BrowserRouter>
    </ErrorBoundary>
  )
}
