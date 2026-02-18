import { useEffect, useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { formatCents, formatDate } from '@/lib/utils'
import { RefreshCcw, MoreHorizontal, ChevronUp, ChevronDown } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import { useAuthStore } from '@/stores/authStore'
import { getErrorMessage } from '@/lib/error'
import { EmployeeDetailModal } from './EmployeeDetailModal'
import type { UserAdmin } from '@/types'

const PER_PAGE = 20

type SortKey = 'name_asc' | 'name_desc' | 'department' | 'start_date' | 'budget'

function Avatar({ user }: { user: UserAdmin }) {
  const [imgError, setImgError] = useState(false)
  if (user.avatar_url && !imgError) {
    return (
      <img
        src={user.avatar_url}
        alt={user.display_name}
        className="h-8 w-8 rounded-full object-cover"
        onError={() => setImgError(true)}
      />
    )
  }
  const initials = user.display_name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
  return (
    <div className="h-8 w-8 rounded-full bg-[hsl(var(--muted))] flex items-center justify-center text-xs font-medium">
      {initials}
    </div>
  )
}

function SortHeader({
  label,
  sortKey,
  currentSort,
  onSort,
}: {
  label: string
  sortKey: SortKey
  currentSort: SortKey
  onSort: (key: SortKey) => void
}) {
  const isNameSort = sortKey === 'name_asc'
  const isActive = isNameSort
    ? currentSort === 'name_asc' || currentSort === 'name_desc'
    : currentSort === sortKey

  const handleClick = () => {
    if (isNameSort) {
      onSort(currentSort === 'name_asc' ? 'name_desc' : 'name_asc')
    } else {
      onSort(sortKey)
    }
  }

  return (
    <button
      onClick={handleClick}
      className="inline-flex items-center gap-1 hover:text-[hsl(var(--foreground))] transition-colors"
    >
      {label}
      {isActive && (
        isNameSort ? (
          currentSort === 'name_desc' ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />
        ) : (
          <ChevronDown className="h-3 w-3" />
        )
      )}
    </button>
  )
}

export function AdminEmployeesPage() {
  const [users, setUsers] = useState<UserAdmin[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState<SortKey>('name_asc')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<string>('')
  const [departmentFilter, setDepartmentFilter] = useState<string>('')
  const [activeFilter, setActiveFilter] = useState<string>('')
  const [departments, setDepartments] = useState<string[]>([])
  const [syncing, setSyncing] = useState(false)
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
  const { addToast } = useUiStore()
  const { user: currentUser } = useAuthStore()

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(timer)
  }, [search])

  // Load departments once
  useEffect(() => {
    adminApi.listUsers({ per_page: 100 }).then(({ data }) => {
      const depts = [...new Set(data.items.map((u) => u.department).filter(Boolean))] as string[]
      setDepartments(depts.sort())
    })
  }, [])

  const load = useCallback(() => {
    const params: Record<string, string | number> = { page, per_page: PER_PAGE, sort }
    if (debouncedSearch) params.q = debouncedSearch
    if (roleFilter) params.role = roleFilter
    if (departmentFilter) params.department = departmentFilter
    if (activeFilter) params.is_active = activeFilter === 'active' ? 1 : 0
    adminApi.listUsers(params).then(({ data }) => {
      setUsers(data.items)
      setTotal(data.total)
    })
  }, [page, sort, debouncedSearch, roleFilter, departmentFilter, activeFilter])

  useEffect(() => { load() }, [load])

  // Reset to page 1 when filters change
  useEffect(() => { setPage(1) }, [debouncedSearch, roleFilter, departmentFilter, activeFilter, sort])

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE))

  const handleSync = async () => {
    setSyncing(true)
    try {
      await adminApi.triggerSync()
      load()
      addToast({ title: 'Sync complete' })
    } catch (err: unknown) {
      addToast({ title: 'Sync failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setSyncing(false)
    }
  }

  const changeRole = async (user: UserAdmin, newRole: string) => {
    try {
      await adminApi.updateUserRole(user.id, newRole)
      load()
      addToast({ title: `Role changed to ${newRole}` })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const toggleProbation = async (user: UserAdmin) => {
    try {
      await adminApi.updateProbationOverride(user.id, !user.probation_override)
      load()
      addToast({ title: user.probation_override ? 'Early access revoked' : 'Early access granted' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Employees ({total})</h1>
        {currentUser?.role === 'admin' && (
          <Button onClick={handleSync} disabled={syncing}>
            <RefreshCcw className={`h-4 w-4 mr-1 ${syncing ? 'animate-spin' : ''}`} />
            Sync from HiBob
          </Button>
        )}
      </div>

      {/* Search */}
      <div className="mb-4">
        <Input
          placeholder="Search by name or email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-4 items-center">
        {/* Role filter */}
        <div className="flex gap-1">
          {[
            { label: 'All', value: '' },
            { label: 'Admin', value: 'admin' },
            { label: 'Manager', value: 'manager' },
            { label: 'Employee', value: 'employee' },
          ].map((r) => (
            <Button
              key={r.value}
              size="sm"
              variant={roleFilter === r.value ? 'default' : 'outline'}
              onClick={() => setRoleFilter(r.value)}
            >
              {r.label}
            </Button>
          ))}
        </div>

        {/* Department dropdown */}
        <select
          value={departmentFilter}
          onChange={(e) => setDepartmentFilter(e.target.value)}
          className="h-9 rounded-md border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-3 text-sm"
          aria-label="Filter by department"
        >
          <option value="">All Departments</option>
          {departments.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>

        {/* Active filter */}
        <div className="flex gap-1">
          {[
            { label: 'All', value: '' },
            { label: 'Active', value: 'active' },
            { label: 'Inactive', value: 'inactive' },
          ].map((a) => (
            <Button
              key={a.value}
              size="sm"
              variant={activeFilter === a.value ? 'default' : 'outline'}
              onClick={() => setActiveFilter(a.value)}
            >
              {a.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
                    <SortHeader label="Name" sortKey="name_asc" currentSort={sort} onSort={setSort} />
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
                    <SortHeader label="Department" sortKey="department" currentSort={sort} onSort={setSort} />
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Role</th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
                    <SortHeader label="Start Date" sortKey="start_date" currentSort={sort} onSort={setSort} />
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">
                    <SortHeader label="Budget / Spent" sortKey="budget" currentSort={sort} onSort={setSort} />
                  </th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Status</th>
                  <th className="text-right px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-[hsl(var(--border))] hover:bg-[hsl(var(--muted)/0.5)] cursor-pointer" onClick={() => setSelectedUserId(u.id)}>
                    {/* Avatar + Name */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <Avatar user={u} />
                        <div>
                          <div className="font-medium">{u.display_name}</div>
                          <div className="text-xs text-[hsl(var(--muted-foreground))]">{u.email}</div>
                        </div>
                      </div>
                    </td>
                    {/* Department */}
                    <td className="px-4 py-3">{u.department || '—'}</td>
                    {/* Role */}
                    <td className="px-4 py-3">
                      <Badge variant={u.role === 'admin' ? 'default' : u.role === 'manager' ? 'warning' : 'secondary'}>{u.role}</Badge>
                    </td>
                    {/* Start Date */}
                    <td className="px-4 py-3">{u.start_date ? formatDate(u.start_date) : '—'}</td>
                    {/* Budget / Spent */}
                    <td className="px-4 py-3">
                      <div>{formatCents(u.total_budget_cents)}</div>
                      <div className="text-xs text-[hsl(var(--muted-foreground))]">
                        Spent: {formatCents(u.cached_spent_cents)}
                      </div>
                    </td>
                    {/* Status */}
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        <Badge variant={u.is_active ? 'success' : 'destructive'}>
                          {u.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                        {u.probation_override && <Badge variant="warning">Early Access</Badge>}
                      </div>
                    </td>
                    {/* Actions */}
                    <td className="px-4 py-3 text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button size="sm" variant="ghost" className="h-8 w-8 p-0" onClick={(e) => e.stopPropagation()}>
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          {currentUser?.role === 'admin' && (
                            <>
                              {u.role !== 'admin' && (
                                <DropdownMenuItem onClick={(e) => { e.stopPropagation(); changeRole(u, 'admin') }}>
                                  Make Admin
                                </DropdownMenuItem>
                              )}
                              {u.role !== 'manager' && (
                                <DropdownMenuItem onClick={(e) => { e.stopPropagation(); changeRole(u, 'manager') }}>
                                  Make Manager
                                </DropdownMenuItem>
                              )}
                              {u.role !== 'employee' && (
                                <DropdownMenuItem onClick={(e) => { e.stopPropagation(); changeRole(u, 'employee') }}>
                                  Remove Role
                                </DropdownMenuItem>
                              )}
                              <DropdownMenuSeparator />
                            </>
                          )}
                          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); toggleProbation(u) }}>
                            {u.probation_override ? 'Revoke Early Access' : 'Grant Early Access'}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
                      No employees found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-[hsl(var(--border))]">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <span className="text-sm text-[hsl(var(--muted-foreground))]">
                Page {page} of {totalPages}
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {selectedUserId && (
        <EmployeeDetailModal
          userId={selectedUserId}
          onClose={() => setSelectedUserId(null)}
        />
      )}
    </div>
  )
}
