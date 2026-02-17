import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import type { Category } from '@/types'

export function AdminCategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([])
  const [showDialog, setShowDialog] = useState(false)
  const [editing, setEditing] = useState<Category | null>(null)
  const [form, setForm] = useState({ name: '', slug: '', description: '', icon: '', sort_order: 0 })
  const { addToast } = useUiStore()

  const load = () => adminApi.listCategories().then(({ data }) => setCategories(data))
  useEffect(() => { load() }, [])

  const openCreate = () => { setEditing(null); setForm({ name: '', slug: '', description: '', icon: '', sort_order: 0 }); setShowDialog(true) }
  const openEdit = (cat: Category) => { setEditing(cat); setForm({ name: cat.name, slug: cat.slug, description: cat.description || '', icon: cat.icon || '', sort_order: cat.sort_order }); setShowDialog(true) }

  const handleSave = async () => {
    try {
      if (editing) {
        await adminApi.updateCategory(editing.id, form)
      } else {
        await adminApi.createCategory(form)
      }
      setShowDialog(false); load()
      addToast({ title: editing ? 'Category updated' : 'Category created' })
    } catch (err: unknown) { addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' }) }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this category?')) return
    try { await adminApi.deleteCategory(id); load(); addToast({ title: 'Category deleted' }) }
    catch (err: unknown) { addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' }) }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Categories</h1>
        <Button onClick={openCreate}><Plus className="h-4 w-4 mr-1" /> Add Category</Button>
      </div>
      <div className="space-y-2">
        {categories.map((cat) => (
          <Card key={cat.id}>
            <CardContent className="flex items-center justify-between p-4">
              <div>
                <div className="font-medium">{cat.name}</div>
                <div className="text-sm text-[hsl(var(--muted-foreground))]">/{cat.slug} {cat.description && `- ${cat.description}`}</div>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={() => openEdit(cat)}><Pencil className="h-3 w-3" /></Button>
                <Button size="sm" variant="ghost" className="text-red-600" onClick={() => handleDelete(cat.id)}><Trash2 className="h-3 w-3" /></Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent>
          <DialogHeader><DialogTitle>{editing ? 'Edit Category' : 'Add Category'}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Input placeholder="Name *" value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} />
            <Input placeholder="Slug *" value={form.slug} onChange={(e) => setForm(f => ({ ...f, slug: e.target.value }))} />
            <Input placeholder="Description" value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))} />
            <Input placeholder="Icon (e.g. monitor)" value={form.icon} onChange={(e) => setForm(f => ({ ...f, icon: e.target.value }))} />
            <Input type="number" placeholder="Sort Order" value={form.sort_order} onChange={(e) => setForm(f => ({ ...f, sort_order: parseInt(e.target.value) || 0 }))} />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={!form.name || !form.slug}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
