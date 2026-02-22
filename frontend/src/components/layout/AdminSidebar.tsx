import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Package, ShoppingBag, FolderOpen, Users,
  Wallet, Settings, ScrollText, RefreshCcw, Store, X, Tag, ClipboardCheck, HardDrive
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useUiStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { adminApi } from '@/services/adminApi'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/admin', icon: LayoutDashboard, label: 'Dashboard', exact: true },
  { to: '/admin/products', icon: Package, label: 'Products' },
  { to: '/admin/brands', icon: Tag, label: 'Brands' },
  { to: '/admin/orders', icon: ShoppingBag, label: 'Orders' },
  { to: '/admin/categories', icon: FolderOpen, label: 'Categories' },
  { to: '/admin/employees', icon: Users, label: 'Employees' },
  { to: '/admin/budgets', icon: Wallet, label: 'Budget Adjustments' },
  { to: '/admin/purchase-reviews', icon: ClipboardCheck, label: 'Purchase Reviews', badge: true },
  { to: '/admin/settings', icon: Settings, label: 'Settings', adminOnly: true },
  { to: '/admin/audit', icon: ScrollText, label: 'Audit Log', adminOnly: true },
  { to: '/admin/sync-log', icon: RefreshCcw, label: 'Sync Log', adminOnly: true },
  { to: '/admin/backups', icon: HardDrive, label: 'Backups', adminOnly: true },
]

export function AdminSidebar() {
  const location = useLocation()
  const { sidebarOpen, setSidebarOpen } = useUiStore()
  const { user } = useAuthStore()
  const [pendingCount, setPendingCount] = useState(0)

  useEffect(() => {
    adminApi.getPendingReviewCount()
      .then(({ data }) => setPendingCount(data.count))
      .catch((err) => console.error('Failed to load pending review count:', err))
  }, [location.pathname])

  const filteredNavItems = navItems.filter(
    (item) => !item.adminOnly || user?.role === 'admin'
  )

  const isActive = (to: string, exact?: boolean) =>
    exact ? location.pathname === to : location.pathname.startsWith(to)

  const nav = (
    <nav className="flex flex-col gap-1 p-4">
      <Link to="/" className="flex items-center gap-2 px-3 py-2 mb-4 text-sm text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]">
        <Store className="h-4 w-4" /> Back to Shop
      </Link>
      {filteredNavItems.map((item) => (
        <Link
          key={item.to}
          to={item.to}
          onClick={() => setSidebarOpen(false)}
          className={cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
            isActive(item.to, item.exact)
              ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
              : "text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))] hover:text-[hsl(var(--accent-foreground))]"
          )}
        >
          <item.icon className="h-4 w-4" />
          {item.label}
          {item.badge && pendingCount > 0 && (
            <span className="ml-auto inline-flex items-center justify-center rounded-full bg-red-500 text-white text-xs font-medium h-5 min-w-[20px] px-1.5">
              {pendingCount}
            </span>
          )}
        </Link>
      ))}
    </nav>
  )

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden lg:block w-64 border-r bg-white min-h-[calc(100vh-4rem)]">
        {nav}
      </aside>

      {/* Mobile sidebar */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="fixed inset-0 bg-black/50" aria-label="Close sidebar" role="button" tabIndex={0} onClick={() => setSidebarOpen(false)} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), setSidebarOpen(false))} />
          <aside className="fixed left-0 top-0 bottom-0 w-64 bg-white shadow-xl">
            <div className="flex items-center justify-between p-4 border-b">
              <span className="font-semibold">Admin Menu</span>
              <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            {nav}
          </aside>
        </div>
      )}
    </>
  )
}
