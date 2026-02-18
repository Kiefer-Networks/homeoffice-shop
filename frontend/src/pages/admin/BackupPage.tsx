import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { Download, Trash2, Plus, Clock, Save } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import type { BackupFile, BackupSchedule } from '@/types'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function AdminBackupPage() {
  const [backups, setBackups] = useState<BackupFile[]>([])
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [schedule, setSchedule] = useState<BackupSchedule>({ enabled: false, hour: 2, minute: 0 })
  const [scheduleForm, setScheduleForm] = useState<BackupSchedule>({ enabled: false, hour: 2, minute: 0 })
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

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Database Backup</h1>

      <div className="space-y-6">
        {/* Create Backup */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">Create Backup</h2>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">
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
          <CardContent className="space-y-4 pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-[hsl(var(--muted-foreground))]" />
                <h2 className="text-lg font-semibold">Automatic Backup Schedule</h2>
              </div>
              <Button
                size="sm"
                onClick={handleSaveSchedule}
                disabled={!scheduleDirty || savingSchedule}
              >
                <Save className="h-4 w-4 mr-1" />
                {savingSchedule ? 'Saving...' : 'Save'}
              </Button>
            </div>

            <div className="flex items-center gap-6 flex-wrap">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={scheduleForm.enabled}
                  onChange={(e) => {
                    setScheduleForm(f => ({ ...f, enabled: e.target.checked }))
                    setScheduleDirty(true)
                  }}
                  className="h-4 w-4 rounded border-gray-300"
                />
                <span className="text-sm font-medium">Enable daily backup</span>
              </label>

              <div className="flex items-center gap-2">
                <label className="text-sm font-medium">Time (UTC):</label>
                <select
                  value={scheduleForm.hour}
                  onChange={(e) => {
                    setScheduleForm(f => ({ ...f, hour: parseInt(e.target.value) }))
                    setScheduleDirty(true)
                  }}
                  className="border rounded px-2 py-1 text-sm bg-white"
                >
                  {Array.from({ length: 24 }, (_, i) => (
                    <option key={i} value={i}>{String(i).padStart(2, '0')}</option>
                  ))}
                </select>
                <span className="text-sm">:</span>
                <select
                  value={scheduleForm.minute}
                  onChange={(e) => {
                    setScheduleForm(f => ({ ...f, minute: parseInt(e.target.value) }))
                    setScheduleDirty(true)
                  }}
                  className="border rounded px-2 py-1 text-sm bg-white"
                >
                  {[0, 15, 30, 45].map(m => (
                    <option key={m} value={m}>{String(m).padStart(2, '0')}</option>
                  ))}
                </select>
              </div>
            </div>

            {schedule.enabled && (
              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                Next backup runs daily at {String(schedule.hour).padStart(2, '0')}:{String(schedule.minute).padStart(2, '0')} UTC.
                Oldest backups are automatically removed when the retention limit is reached.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Backup List */}
        <Card>
          <CardContent className="space-y-4 pt-6">
            <h2 className="text-lg font-semibold">Stored Backups</h2>

            {loading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => <div key={i} className="h-12 bg-gray-100 rounded animate-pulse" />)}
              </div>
            ) : backups.length === 0 ? (
              <p className="text-sm text-[hsl(var(--muted-foreground))]">No backups found. Create your first backup above.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                      <th className="text-left px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Filename</th>
                      <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Size</th>
                      <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Created</th>
                      <th className="text-right px-4 py-2 font-medium text-[hsl(var(--muted-foreground))]">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {backups.map(backup => (
                      <tr key={backup.filename} className="border-b border-[hsl(var(--border))] last:border-b-0">
                        <td className="px-4 py-2 font-mono text-xs">{backup.filename}</td>
                        <td className="px-4 py-2 text-right">{formatBytes(backup.size_bytes)}</td>
                        <td className="px-4 py-2 text-right">
                          {new Date(backup.created_at).toLocaleString()}
                        </td>
                        <td className="px-4 py-2 text-right">
                          <div className="flex justify-end gap-1">
                            <Button size="sm" variant="ghost" onClick={() => handleDownload(backup.filename)}>
                              <Download className="h-3.5 w-3.5" />
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => handleDelete(backup.filename)}>
                              <Trash2 className="h-3.5 w-3.5 text-red-500" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
