import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { adminApi } from '@/services/adminApi'
import { useUiStore } from '@/stores/uiStore'
import { Plus, Pencil, Trash2, GripVertical } from 'lucide-react'
import { getErrorMessage } from '@/lib/error'
import type { Category } from '@/types'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

function SortableCategory({
  cat,
  onEdit,
  onDelete,
}: {
  cat: Category
  onEdit: (cat: Category) => void
  onDelete: (id: string) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: cat.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div ref={setNodeRef} style={style}>
      <Card>
        <CardContent className="flex items-center justify-between p-4">
          <div className="flex items-center gap-3">
            <button {...attributes} {...listeners} className="cursor-grab touch-none text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]">
              <GripVertical className="h-4 w-4" />
            </button>
            <div>
              <div className="font-medium">{cat.name}</div>
              <div className="text-sm text-[hsl(var(--muted-foreground))]">/{cat.slug} {cat.description && `- ${cat.description}`}</div>
            </div>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => onEdit(cat)}><Pencil className="h-3 w-3" /></Button>
            <Button size="sm" variant="ghost" className="text-red-600" onClick={() => onDelete(cat.id)}><Trash2 className="h-3 w-3" /></Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export function AdminCategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([])
  const [showDialog, setShowDialog] = useState(false)
  const [editing, setEditing] = useState<Category | null>(null)
  const [form, setForm] = useState({ name: '', slug: '', description: '', icon: '', sort_order: 0 })
  const { addToast } = useUiStore()

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const load = () => adminApi.listCategories().then(({ data }) => setCategories(data))
  useEffect(() => { load() }, [])

  const toSlug = (name: string) =>
    name.toLowerCase().replace(/[äöüß]/g, (c) => ({ ä: 'ae', ö: 'oe', ü: 'ue', ß: 'ss' })[c] || c)
      .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

  const openCreate = () => {
    setEditing(null)
    setForm({ name: '', slug: '', description: '', icon: '', sort_order: categories.length })
    setShowDialog(true)
  }

  const openEdit = (cat: Category) => {
    setEditing(cat)
    setForm({ name: cat.name, slug: cat.slug, description: cat.description || '', icon: cat.icon || '', sort_order: cat.sort_order })
    setShowDialog(true)
  }

  const handleNameChange = (name: string) => {
    const autoSlug = !editing && (form.slug === '' || form.slug === toSlug(form.name))
    setForm(f => ({ ...f, name, ...(autoSlug ? { slug: toSlug(name) } : {}) }))
  }

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

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const oldIndex = categories.findIndex(c => c.id === active.id)
    const newIndex = categories.findIndex(c => c.id === over.id)
    const reordered = arrayMove(categories, oldIndex, newIndex)
    setCategories(reordered)

    const items = reordered.map((cat, i) => ({ id: cat.id, sort_order: i }))
    try {
      await adminApi.reorderCategories(items)
    } catch (err: unknown) {
      addToast({ title: 'Error', description: getErrorMessage(err), variant: 'destructive' })
      load()
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Categories</h1>
        <Button onClick={openCreate}><Plus className="h-4 w-4 mr-1" /> Add Category</Button>
      </div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={categories.map(c => c.id)} strategy={verticalListSortingStrategy}>
          <div className="space-y-2">
            {categories.map((cat) => (
              <SortableCategory key={cat.id} cat={cat} onEdit={openEdit} onDelete={handleDelete} />
            ))}
          </div>
        </SortableContext>
      </DndContext>
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent>
          <DialogHeader><DialogTitle>{editing ? 'Edit Category' : 'Add Category'}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Input placeholder="Name *" value={form.name} onChange={(e) => handleNameChange(e.target.value)} />
            <Input placeholder="Slug *" value={form.slug} onChange={(e) => setForm(f => ({ ...f, slug: e.target.value }))} />
            <Input placeholder="Description" value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))} />
            <Input placeholder="Icon (e.g. monitor)" value={form.icon} onChange={(e) => setForm(f => ({ ...f, icon: e.target.value }))} />
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
