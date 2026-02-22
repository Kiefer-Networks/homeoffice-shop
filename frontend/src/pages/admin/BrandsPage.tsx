import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { formatDate } from '@/lib/utils'
import { Plus, Pencil, Trash2, Search } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import type { Brand } from '@/types'

export function AdminBrandsPage() {
  const [brands, setBrands] = useState<Brand[]>([])
  const [search, setSearch] = useState('')
  const [showDialog, setShowDialog] = useState(false)
  const [editing, setEditing] = useState<Brand | null>(null)
  const [name, setName] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<Brand | null>(null)
  const { addToast } = useUiStore()

  const load = () => adminApi.listBrands().then(({ data }) => setBrands(data))
  useEffect(() => { load() }, [])

  const openCreate = () => {
    setEditing(null)
    setName('')
    setShowDialog(true)
  }

  const openEdit = (brand: Brand) => {
    setEditing(brand)
    setName(brand.name)
    setShowDialog(true)
  }

  const handleSave = async () => {
    try {
      if (editing) {
        await adminApi.updateBrand(editing.id, { name })
      } else {
        await adminApi.createBrand({ name })
      }
      setShowDialog(false)
      load()
      addToast({ title: editing ? 'Brand updated' : 'Brand created' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await adminApi.deleteBrand(deleteTarget.id)
      load()
      addToast({ title: 'Brand deleted' })
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
    } finally {
      setDeleteTarget(null)
    }
  }

  const filteredBrands = search.trim()
    ? brands.filter(b => b.name.toLowerCase().includes(search.toLowerCase()))
    : brands

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Brands</h1>
        <Button onClick={openCreate}><Plus className="h-4 w-4 mr-1" /> Add Brand</Button>
      </div>

      {/* Search */}
      <div className="mb-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input placeholder="Search brands..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10 max-w-sm" />
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Name</th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Slug</th>
                  <th className="text-left px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Created</th>
                  <th className="text-right px-4 py-3 font-medium text-[hsl(var(--muted-foreground))]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredBrands.map((brand) => (
                  <tr key={brand.id} className="border-b border-[hsl(var(--border))] hover:bg-[hsl(var(--muted)/0.5)]">
                    <td className="px-4 py-3 font-medium">{brand.name}</td>
                    <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">{brand.slug}</td>
                    <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">{formatDate(brand.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" onClick={() => openEdit(brand)}>
                          <Pencil className="h-3 w-3" />
                        </Button>
                        <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleteTarget(brand)}>
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredBrands.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
                      {search.trim() ? 'No brands matching your search.' : 'No brands found.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Create / Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit Brand' : 'Add Brand'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Input placeholder="Name *" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={!name.trim()}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
        title="Delete Brand"
        description={`Are you sure you want to delete \u201c${deleteTarget?.name}\u201d? This action cannot be undone.`}
      />
    </div>
  )
}
