import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { Download, Trash2, Plus, Clock, Save, Database, HardDrive, Calendar, Shield } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import type { BackupFile, BackupSchedule } from '@/types'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

const defaultSchedule: BackupSchedule = { enabled: false, hour: 2, minute: 0, max_backups: 10 }

export function AdminBackupPage() {
  const [backups, setBackups] = useState<BackupFile[]>([])
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [schedule, setSchedule] = useState<BackupSchedule>(defaultSchedule)
  const [scheduleForm, setScheduleForm] = useState<BackupSchedule>(defaultSchedule)
  const [scheduleDirty, setScheduleDirty] = useState(false)
  const [savingSchedule, setSavingSchedule] = useState(false)
  const { addToast } = useUiStore()

  const loadBackups = () => {
    adminApi.listBackups()
      .then(({ data }) => setBackups(data.items))
      .catch(() => addToast({ title: 'Failed to load backups', variant: 'destructive' }))
      .finally(() => setLoading(false))
  }

  const loadSchedule = () => {
    adminApi.getBackupSchedule()
      .then(({ data }) => {
        setSchedule(data)
        setScheduleForm(data)
      })
      .catch(() => addToast({ title: 'Failed to load schedule', variant: 'destructive' }))
  }

  useEffect(() => {
    loadBackups()
    loadSchedule()
  }, [])

  const updateForm = (patch: Partial<BackupSchedule>) => {
    setScheduleForm(f => ({ ...f, ...patch }))
    setScheduleDirty(true)
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const { data } = await adminApi.exportBackup()
      const url = window.URL.createObjectURL(data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `homeoffice_shop_${new Date().toISOString().slice(0, 10)}.dump`
      a.click()
      window.URL.revokeObjectURL(url)
      addToast({ title: 'Backup exported successfully' })
      loadBackups()
    } catch (err: unknown) {
      addToast({ title: 'Backup failed', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setExporting(false)
    }
  }

  const handleDownload = async (filename: string) => {
    try {
      const { data } = await adminApi.downloadBackup(filename)
      const url = window.URL.createObjectURL(data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (err: unknown) {
      addToast({ title: 'Download failed', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const handleDelete = async (filename: string) => {
    if (!confirm(`Delete backup "${filename}"?`)) return
    try {
      await adminApi.deleteBackup(filename)
      addToast({ title: 'Backup deleted' })
      loadBackups()
    } catch (err: unknown) {
      addToast({ title: 'Delete failed', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const handleSaveSchedule = async () => {
    setSavingSchedule(true)
    try {
      const { data } = await adminApi.updateBackupSchedule(scheduleForm)
      setSchedule(data)
      setScheduleForm(data)
      setScheduleDirty(false)
      addToast({ title: 'Schedule saved' })
    } catch (err: unknown) {
      addToast({ title: 'Failed to save schedule', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setSavingSchedule(false)
    }
  }

  const totalSize = backups.reduce((sum, b) => sum + b.size_bytes, 0)

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Database Backup</h1>

      {/* Stats row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-50">
                <Database className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{backups.length}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">Stored Backups</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-purple-50">
                <HardDrive className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{formatBytes(totalSize)}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">Total Size</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-green-50">
                <Calendar className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {backups.length > 0 ? timeAgo(backups[0].created_at) : '--'}
                </p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">Last Backup</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-6">
        {/* Create Backup */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">Create Backup</h2>
                <p className="text-sm text-[hsl(var(--muted-foreground))]">
                  Export a full database dump. Backups are stored on the server and available for download.
                </p>
              </div>
              <Button onClick={handleExport} disabled={exporting}>
                <Plus className="h-4 w-4 mr-1" />
                {exporting ? 'Exporting...' : 'Create Backup'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Schedule */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-orange-50">
                  <Clock className="h-5 w-5 text-orange-600" />
                </div>
                <div>
                  <CardTitle>Automatic Backup</CardTitle>
                  <CardDescription>Configure daily backups and retention policy</CardDescription>
                </div>
              </div>
              <Badge variant={schedule.enabled ? 'success' : 'secondary'}>
                {schedule.enabled ? 'Active' : 'Inactive'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            {/* Enable toggle */}
            <label className="flex items-center justify-between p-3 rounded-lg border border-[hsl(var(--border))] cursor-pointer hover:bg-[hsl(var(--muted)/0.5)] transition-colors">
              <div className="flex items-center gap-3">
                <Shield className="h-4 w-4 text-[hsl(var(--muted-foreground))]" />
                <div>
                  <p className="text-sm font-medium">Enable daily backup</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Automatically create a backup every day</p>
                </div>
              </div>
              <div
                role="switch"
                aria-checked={scheduleForm.enabled}
                tabIndex={0}
                onClick={() => updateForm({ enabled: !scheduleForm.enabled })}
                onKeyDown={(e) => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); updateForm({ enabled: !scheduleForm.enabled }) } }}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${scheduleForm.enabled ? 'bg-[hsl(var(--primary))]' : 'bg-[hsl(var(--muted))]'}`}
              >
                <span className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform ${scheduleForm.enabled ? 'translate-x-5' : 'translate-x-0'}`} />
              </div>
            </label>

            {/* Settings grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Time picker */}
              <div className="p-4 rounded-lg border border-[hsl(var(--border))] space-y-2">
                <label className="text-sm font-medium flex items-center gap-2">
                  <Clock className="h-3.5 w-3.5 text-[hsl(var(--muted-foreground))]" />
                  Backup Time (UTC)
                </label>
                <div className="flex items-center gap-2">
                  <select
                    value={scheduleForm.hour}
                    onChange={(e) => updateForm({ hour: parseInt(e.target.value) })}
                    className="flex-1 border border-[hsl(var(--border))] rounded-md px-3 py-2 text-sm bg-[hsl(var(--background))]"
                  >
                    {Array.from({ length: 24 }, (_, i) => (
                      <option key={i} value={i}>{String(i).padStart(2, '0')}</option>
                    ))}
                  </select>
                  <span className="text-lg font-medium text-[hsl(var(--muted-foreground))]">:</span>
                  <select
                    value={scheduleForm.minute}
                    onChange={(e) => updateForm({ minute: parseInt(e.target.value) })}
                    className="flex-1 border border-[hsl(var(--border))] rounded-md px-3 py-2 text-sm bg-[hsl(var(--background))]"
                  >
                    {[0, 15, 30, 45].map(m => (
                      <option key={m} value={m}>{String(m).padStart(2, '0')}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Retention count */}
              <div className="p-4 rounded-lg border border-[hsl(var(--border))] space-y-2">
                <label className="text-sm font-medium flex items-center gap-2">
                  <Database className="h-3.5 w-3.5 text-[hsl(var(--muted-foreground))]" />
                  Maximum Backups
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={scheduleForm.max_backups}
                    onChange={(e) => {
                      const v = parseInt(e.target.value)
                      if (!isNaN(v) && v >= 1 && v <= 100) updateForm({ max_backups: v })
                    }}
                    className="w-20 border border-[hsl(var(--border))] rounded-md px-3 py-2 text-sm bg-[hsl(var(--background))]"
                  />
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">
                    Older backups are automatically deleted when this limit is exceeded.
                  </p>
                </div>
              </div>
            </div>

            {/* Save button */}
            <div className="flex items-center justify-between pt-1">
              {schedule.enabled ? (
                <p className="text-xs text-[hsl(var(--muted-foreground))]">
                  Daily at {String(schedule.hour).padStart(2, '0')}:{String(schedule.minute).padStart(2, '0')} UTC
                  {' '}&middot; keeping max. {schedule.max_backups} backups
                </p>
              ) : (
                <p className="text-xs text-[hsl(var(--muted-foreground))]">
                  Automatic backups are disabled.
                </p>
              )}
              <Button
                onClick={handleSaveSchedule}
                disabled={!scheduleDirty || savingSchedule}
              >
                <Save className="h-4 w-4 mr-1" />
                {savingSchedule ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Backup List */}
        <Card>
          <CardHeader>
            <CardTitle>Stored Backups</CardTitle>
            <CardDescription>
              {backups.length} backup{backups.length !== 1 ? 's' : ''} stored
              {schedule.max_backups ? ` (limit: ${schedule.max_backups})` : ''}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => <div key={i} className="h-14 bg-[hsl(var(--muted))] rounded-lg animate-pulse" />)}
              </div>
            ) : backups.length === 0 ? (
              <div className="text-center py-8">
                <Database className="h-10 w-10 text-[hsl(var(--muted-foreground))] mx-auto mb-3 opacity-40" />
                <p className="text-sm text-[hsl(var(--muted-foreground))]">No backups found. Create your first backup above.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {backups.map((backup, i) => (
                  <div
                    key={backup.filename}
                    className="flex items-center justify-between p-3 rounded-lg border border-[hsl(var(--border))] hover:bg-[hsl(var(--muted)/0.3)] transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className={`p-1.5 rounded-md ${i === 0 ? 'bg-green-50' : 'bg-[hsl(var(--muted))]'}`}>
                        <Database className={`h-4 w-4 ${i === 0 ? 'text-green-600' : 'text-[hsl(var(--muted-foreground))]'}`} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium font-mono truncate">{backup.filename}</p>
                        <p className="text-xs text-[hsl(var(--muted-foreground))]">
                          {new Date(backup.created_at).toLocaleString()} &middot; {formatBytes(backup.size_bytes)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 ml-2">
                      {i === 0 && <Badge variant="success" className="mr-1">Latest</Badge>}
                      <Button size="sm" variant="ghost" onClick={() => handleDownload(backup.filename)} title="Download">
                        <Download className="h-3.5 w-3.5" />
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => handleDelete(backup.filename)} title="Delete">
                        <Trash2 className="h-3.5 w-3.5 text-red-500" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
