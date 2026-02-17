import { Outlet } from 'react-router-dom'
import { Header } from './Header'

export function ShopLayout() {
  return (
    <div className="min-h-screen bg-[hsl(var(--background))]">
      <Header />
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
