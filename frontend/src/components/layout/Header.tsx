import { useState } from 'react'
import { ShoppingCart, LogOut, Settings, Menu, ClipboardList } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useAuthStore } from '@/stores/authStore'
import { useCartStore } from '@/stores/cartStore'
import { useUiStore } from '@/stores/uiStore'
import { useBrandingStore } from '@/stores/brandingStore'
import { formatCents } from '@/lib/utils'
import { authApi } from '@/services/authApi'
import { setAccessToken } from '@/lib/token'

function UserAvatar({ name, avatarUrl, size = 32 }: { name: string; avatarUrl?: string | null; size?: number }) {
  const [imgError, setImgError] = useState(false)

  const initials = name
    .split(' ')
    .map(w => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  // Deterministic color from name
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  const hue = Math.abs(hash) % 360

  if (avatarUrl && !imgError) {
    return (
      <img
        src={avatarUrl}
        alt={name}
        className="rounded-full object-cover shrink-0"
        style={{ width: size, height: size }}
        onError={() => setImgError(true)}
      />
    )
  }

  return (
    <div
      className="rounded-full flex items-center justify-center text-white font-medium shrink-0"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.38,
        backgroundColor: `hsl(${hue}, 55%, 50%)`,
      }}
    >
      {initials}
    </div>
  )
}

export function Header() {
  const { user, logout: logoutStore } = useAuthStore()
  const { cart, setOpen: setCartOpen } = useCartStore()
  const { setSidebarOpen } = useUiStore()
  const { companyName } = useBrandingStore()
  const navigate = useNavigate()

  const cartItemCount = cart?.items.length || 0
  const availableBudget = cart?.available_budget_cents || user?.available_budget_cents || 0

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch {
      // Server-side cleanup may fail, but we still logout locally
    }
    setAccessToken(null)
    logoutStore()
    navigate('/login')
  }

  return (
    <header className="sticky top-0 z-40 border-b bg-white">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-4">
          {(user?.role === 'admin' || user?.role === 'manager') && (
            <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(true)} className="lg:hidden">
              <Menu className="h-5 w-5" />
            </Button>
          )}
          <Link to="/" className="flex items-center gap-2">
            <img src="/logo-dark.svg" alt={companyName} className="h-8" />
          </Link>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[hsl(var(--muted))] text-sm">
            <span className="text-[hsl(var(--muted-foreground))]">Budget</span>
            <span className="font-semibold text-[hsl(var(--foreground))]">{formatCents(availableBudget)}</span>
          </div>

          <Link to="/orders">
            <Button variant="ghost" size="icon" aria-label="My orders">
              <ClipboardList className="h-5 w-5" />
            </Button>
          </Link>

          <Button variant="ghost" size="icon" className="relative" onClick={() => setCartOpen(true)} aria-label={`Shopping cart${cartItemCount > 0 ? ` (${cartItemCount} items)` : ''}`}>
            <ShoppingCart className="h-5 w-5" />
            {cartItemCount > 0 && (
              <Badge className="absolute -top-1 -right-1 h-5 w-5 rounded-full p-0 flex items-center justify-center text-[10px]">
                {cartItemCount}
              </Badge>
            )}
          </Button>

          {(user?.role === 'admin' || user?.role === 'manager') && (
            <Link to="/admin">
              <Button variant="ghost" size="icon" aria-label="Admin settings"><Settings className="h-5 w-5" /></Button>
            </Link>
          )}

          <div className="flex items-center gap-2.5 ml-1 pl-3 border-l border-[hsl(var(--border))]">
            <Link to="/profile" className="flex items-center gap-2.5 hover:opacity-80 transition-opacity">
              {user && (
                <UserAvatar name={user.display_name} avatarUrl={user.avatar_url} size={34} />
              )}
              <div className="hidden md:block text-sm">
                <div className="font-medium leading-tight">{user?.display_name}</div>
                <div className="text-xs text-[hsl(var(--muted-foreground))] leading-tight">{user?.department}</div>
              </div>
            </Link>
            <Button variant="ghost" size="icon" onClick={handleLogout} aria-label="Log out">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </header>
  )
}
