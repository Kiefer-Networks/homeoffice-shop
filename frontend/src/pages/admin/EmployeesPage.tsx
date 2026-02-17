import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { formatCents, formatDate } from '@/lib/utils'
import { RefreshCcw, Shield, ShieldOff } from 'lucide-react'
import type { UserAdmin } from '@/types'

export function AdminEmployeesPage() {
  const [users, setUsers] = useState<UserAdmin[]>([])
  const [total, setTotal] = useState(0)
  const [syncing, setSyncing] = useState(false)
  const { addToast } = useUiStore()

  const load = () => adminApi.listUsers({ per_page: 100 }).then(({ data }) => { setUsers(data.items); setTotal(data.total) })
  useEffect(() => { load() }, [])

  const handleSync = async () => {
    setSyncing(true)
    try { await adminApi.triggerSync(); load(); addToast({ title: 'Sync complete' }) }
    catch (err: any) { addToast({ title: 'Sync failed', description: err.response?.data?.detail, variant: 'destructive' }) }
    finally { setSyncing(false) }
  }

  const toggleRole = async (user: UserAdmin) => {
    const newRole = user.role === 'admin' ? 'employee' : 'admin'
    try { await adminApi.updateUserRole(user.id, newRole); load(); addToast({ title: `Role changed to ${newRole}` }) }
    catch (err: any) { addToast({ title: 'Error', description: err.response?.data?.detail, variant: 'destructive' }) }
  }

  const toggleProbation = async (user: UserAdmin) => {
    try { await adminApi.updateProbationOverride(user.id, !user.probation_override); load()
      addToast({ title: user.probation_override ? 'Early access revoked' : 'Early access granted' })
    } catch (err: any) { addToast({ title: 'Error', description: err.response?.data?.detail, variant: 'destructive' }) }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Employees ({total})</h1>
        <Button onClick={handleSync} disabled={syncing}>
          <RefreshCcw className={`h-4 w-4 mr-1 ${syncing ? 'animate-spin' : ''}`} /> Sync from HiBob
        </Button>
      </div>
      <div className="space-y-2">
        {users.map((u) => (
          <Card key={u.id}>
            <CardContent className="flex items-center justify-between p-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{u.display_name}</span>
                  <Badge variant={u.role === 'admin' ? 'default' : 'secondary'}>{u.role}</Badge>
                  {!u.is_active && <Badge variant="destructive">Inactive</Badge>}
                  {u.probation_override && <Badge variant="warning">Early Access</Badge>}
                </div>
                <div className="text-sm text-[hsl(var(--muted-foreground))]">
                  {u.email} {u.department && `| ${u.department}`}
                  {u.start_date && ` | Started ${formatDate(u.start_date)}`}
                </div>
                <div className="text-xs text-[hsl(var(--muted-foreground))]">
                  Budget: {formatCents(u.total_budget_cents)} | Spent: {formatCents(u.cached_spent_cents)} | Adjustments: {formatCents(u.cached_adjustment_cents)}
                </div>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => toggleRole(u)}>
                  {u.role === 'admin' ? <ShieldOff className="h-3 w-3 mr-1" /> : <Shield className="h-3 w-3 mr-1" />}
                  {u.role === 'admin' ? 'Remove Admin' : 'Make Admin'}
                </Button>
                <Button size="sm" variant="outline" onClick={() => toggleProbation(u)}>
                  {u.probation_override ? 'Revoke Early Access' : 'Grant Early Access'}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
