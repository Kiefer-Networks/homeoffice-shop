import { useEffect, useState, useCallback, useMemo } from 'react'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { Avatar } from '@/components/ui/Avatar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Pagination } from '@/components/ui/Pagination'
import { Badge } from '@/components/ui/badge'
import { DataTable } from '@/components/ui/data-table'
import type { Column } from '@/components/ui/data-table'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { formatCents, formatDate } from '@/lib/utils'
import { RefreshCcw, MoreHorizontal } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import { useAuthStore } from '@/stores/authStore'
import { getErrorMessage } from '@/lib/error'
import { SortHeader } from '@/components/ui/SortHeader'
import { DEFAULT_PAGE_SIZE, SEARCH_DEBOUNCE_MS } from '@/lib/constants'
import { EmployeeDetailModal } from './EmployeeDetailModal'
import type { UserAdmin } from '@/types'

type SortKey = 'name_asc' | 'name_desc' | 'department' | 'start_date' | 'budget'

export function AdminEmployeesPage() {
  const [users, setUsers] = useState<UserAdmin[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState<SortKey>('name_asc')
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, SEARCH_DEBOUNCE_MS)
  const [roleFilter, setRoleFilter] = useState<string>('')
  const [departmentFilter, setDepartmentFilter] = useState<string>('')
  const [activeFilter, setActiveFilter] = useState<string>('')
  const [departments, setDepartments] = useState<string[]>([])
  const [syncing, setSyncing] = useState(false)
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
  const { addToast } = useUiStore()
  const { user: currentUser } = useAuthStore()

  // Load departments once
  useEffect(() => {
    adminApi.listDepartments().then(({ data }) => {
      setDepartments(data.sort())
    }).catch((err) => console.error('Failed to load departments:', err))
  }, [])

  const load = useCallback(() => {
    const params: Record<string, string | number> = { page, per_page: DEFAULT_PAGE_SIZE, sort }
    if (debouncedSearch) params.q = debouncedSearch
    if (roleFilter) params.role = roleFilter
    if (departmentFilter) params.department = departmentFilter
    if (activeFilter) params.is_active = activeFilter === 'active' ? 1 : 0
    adminApi.listUsers(params).then(({ data }) => {
      setUsers(data.items)
      setTotal(data.total)
    }).catch((err: unknown) => {
      addToast({ title: 'Failed to load employees', description: getErrorMessage(err), variant: 'destructive' })
    }).finally(() => setLoading(false))
  }, [page, sort, debouncedSearch, roleFilter, departmentFilter, activeFilter])

  useEffect(() => { load() }, [load])

  // Reset to page 1 when filters change
  useEffect(() => { setPage(1) }, [debouncedSearch, roleFilter, departmentFilter, activeFilter, sort])

  const totalPages = Math.max(1, Math.ceil(total / DEFAULT_PAGE_SIZE))

  const handleSync = async () => {
    setSyncing(true)
    try {
      await adminApi.triggerSync()
      addToast({ title: 'Sync started', description: 'Running in background. Results will appear shortly.' })
      setTimeout(() => { load(); setSyncing(false) }, 5000)
      setTimeout(() => load(), 15000)
    } catch (err: unknown) {
      addToast({ title: 'Sync failed', description: getErrorMessage(err), variant: 'destructive' })
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

  const columns = useMemo<Column<UserAdmin>[]>(() => [
    {
      header: <SortHeader label="Name" ascKey="name_asc" descKey="name_desc" currentSort={sort} onSort={setSort} />,
      accessor: (u) => (
        <div className="flex items-center gap-3">
          <Avatar name={u.display_name} src={u.avatar_url} size="sm" />
          <div>
            <div className="font-medium">{u.display_name}</div>
            <div className="text-xs text-[hsl(var(--muted-foreground))]">{u.email}</div>
          </div>
        </div>
      ),
    },
    {
      header: <SortHeader label="Department" ascKey="department" descKey="department" currentSort={sort} onSort={setSort} />,
      accessor: (u) => <>{u.department || '—'}</>,
    },
    {
      header: 'Role',
      accessor: (u) => (
        <Badge variant={u.role === 'admin' ? 'default' : u.role === 'manager' ? 'warning' : 'secondary'}>{u.role}</Badge>
      ),
    },
    {
      header: <SortHeader label="Start Date" ascKey="start_date" descKey="start_date" currentSort={sort} onSort={setSort} />,
      accessor: (u) => <>{u.start_date ? formatDate(u.start_date) : '—'}</>,
    },
    {
      header: <SortHeader label="Budget / Spent" ascKey="budget" descKey="budget" currentSort={sort} onSort={setSort} />,
      accessor: (u) => (
        <>
          <div>{formatCents(u.total_budget_cents)}</div>
          <div className="text-xs text-[hsl(var(--muted-foreground))]">
            Spent: {formatCents(u.cached_spent_cents)}
          </div>
        </>
      ),
    },
    {
      header: 'Status',
      accessor: (u) => (
        <div className="flex flex-wrap gap-1">
          <Badge variant={u.is_active ? 'success' : 'destructive'}>
            {u.is_active ? 'Active' : 'Inactive'}
          </Badge>
          {u.probation_override && <Badge variant="warning">Early Access</Badge>}
        </div>
      ),
    },
    {
      header: 'Actions',
      className: 'text-right',
      accessor: (u) => (
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
      ),
    },
  ], [sort, currentUser?.role])

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
      {loading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={users}
          rowKey={(u) => u.id}
          emptyMessage="No employees found."
          onRowClick={(u) => setSelectedUserId(u.id)}
        >
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </DataTable>
      )}

      {selectedUserId && (
        <EmployeeDetailModal
          userId={selectedUserId}
          onClose={() => setSelectedUserId(null)}
        />
      )}
    </div>
  )
}
