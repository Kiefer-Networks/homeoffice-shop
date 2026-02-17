import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/services/authApi'
import { setAccessToken } from '@/lib/token'
import { ShopLayout } from '@/components/layout/ShopLayout'
import { AdminLayout } from '@/components/layout/AdminLayout'
import { LoginPage } from '@/pages/auth/LoginPage'
import { CallbackPage } from '@/pages/auth/CallbackPage'
import { ProbationBlockedPage } from '@/pages/auth/ProbationBlockedPage'
import { CatalogPage } from '@/pages/shop/CatalogPage'
import { OrdersPage } from '@/pages/shop/OrdersPage'
import { DashboardPage } from '@/pages/admin/DashboardPage'
import { AdminProductsPage } from '@/pages/admin/ProductsPage'
import { AdminOrdersPage } from '@/pages/admin/OrdersPage'
import { AdminCategoriesPage } from '@/pages/admin/CategoriesPage'
import { AdminEmployeesPage } from '@/pages/admin/EmployeesPage'
import { AdminBudgetAdjustmentsPage } from '@/pages/admin/BudgetAdjustmentsPage'
import { AdminSettingsPage } from '@/pages/admin/SettingsPage'
import { AdminAuditLogPage } from '@/pages/admin/AuditLogPage'
import { AdminSyncLogPage } from '@/pages/admin/SyncLogPage'
import { useUiStore } from '@/stores/uiStore'

interface Toast {
  id: string
  title: string
  description?: string
  variant?: 'default' | 'destructive'
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

  if (user?.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

function AppInit({ children }: { children: React.ReactNode }) {
  const { setAccessToken: setStoreToken, setUser, logout } = useAuthStore()

  useEffect(() => {
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
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {toasts.map((toast: Toast) => (
        <div
          key={toast.id}
          className={`rounded-lg shadow-lg p-4 max-w-sm border ${
            toast.variant === 'destructive'
              ? 'bg-red-50 border-red-200 text-red-800'
              : 'bg-white border-gray-200'
          }`}
          onClick={() => removeToast(toast.id)}
        >
          <p className="font-medium text-sm">{toast.title}</p>
          {toast.description && <p className="text-xs mt-1 opacity-75">{toast.description}</p>}
        </div>
      ))}
    </div>
  )
}

export default function App() {
  return (
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
          </Route>

          {/* Admin routes */}
          <Route element={<AuthGuard><AdminGuard><AdminLayout /></AdminGuard></AuthGuard>}>
            <Route path="/admin" element={<DashboardPage />} />
            <Route path="/admin/products" element={<AdminProductsPage />} />
            <Route path="/admin/orders" element={<AdminOrdersPage />} />
            <Route path="/admin/categories" element={<AdminCategoriesPage />} />
            <Route path="/admin/employees" element={<AdminEmployeesPage />} />
            <Route path="/admin/budgets" element={<AdminBudgetAdjustmentsPage />} />
            <Route path="/admin/settings" element={<AdminSettingsPage />} />
            <Route path="/admin/audit" element={<AdminAuditLogPage />} />
            <Route path="/admin/sync-log" element={<AdminSyncLogPage />} />
          </Route>
        </Routes>
        <ToastContainer />
      </AppInit>
    </BrowserRouter>
  )
}
