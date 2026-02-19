import { formatCents } from '@/lib/utils'
import type { ProductVariant } from '@/types'

interface VariantTableProps {
  variants: ProductVariant[]
}

export function VariantTable({ variants }: VariantTableProps) {
  if (variants.length === 0) return null

  return (
    <div>
      <h4 className="font-medium text-sm mb-2">Variants ({variants.length})</h4>
      <div className="border rounded-md max-h-48 overflow-y-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b bg-[hsl(var(--muted))]">
              <th className="text-left px-2 py-1">Group</th>
              <th className="text-left px-2 py-1">Value</th>
              <th className="text-left px-2 py-1">ASIN</th>
              <th className="text-right px-2 py-1">Price</th>
            </tr>
          </thead>
          <tbody>
            {variants.map((v) => (
              <tr key={v.asin} className="border-b last:border-b-0">
                <td className="px-2 py-1 capitalize">{v.group}</td>
                <td className="px-2 py-1">{v.value}</td>
                <td className="px-2 py-1 font-mono">{v.asin}</td>
                <td className="px-2 py-1 text-right">{v.price_cents > 0 ? formatCents(v.price_cents) : '\u2014'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
