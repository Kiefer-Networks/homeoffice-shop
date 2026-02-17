import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useFilterStore } from '@/stores/filterStore'
import type { Facets, Category } from '@/types'

interface Props {
  facets: Facets | null
  categories: Category[]
}

export function ProductFilters({ facets, categories }: Props) {
  const { category, brand, color, material, priceMin, priceMax, sort, setFilter, resetFilters } = useFilterStore()

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-semibold mb-2 text-sm">Category</h3>
        <div className="space-y-1">
          <button
            onClick={() => setFilter('category', '')}
            className={`block w-full text-left px-2 py-1 rounded text-sm ${!category ? 'bg-[hsl(var(--primary))] text-white' : 'hover:bg-gray-100'}`}
          >
            All Categories
          </button>
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setFilter('category', cat.id)}
              className={`block w-full text-left px-2 py-1 rounded text-sm ${category === cat.id ? 'bg-[hsl(var(--primary))] text-white' : 'hover:bg-gray-100'}`}
            >
              {cat.name}
              {facets?.categories.find(f => f.id === cat.id) && (
                <span className="text-xs ml-1 opacity-60">
                  ({facets.categories.find(f => f.id === cat.id)?.count})
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {facets?.brands && facets.brands.length > 0 && (
        <div>
          <h3 className="font-semibold mb-2 text-sm">Brand</h3>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            <button
              onClick={() => setFilter('brand', '')}
              className={`block w-full text-left px-2 py-1 rounded text-sm ${!brand ? 'font-medium' : 'hover:bg-gray-100'}`}
            >
              All Brands
            </button>
            {facets.brands.map((b) => (
              <button
                key={b.value}
                onClick={() => setFilter('brand', b.value)}
                className={`block w-full text-left px-2 py-1 rounded text-sm ${brand === b.value ? 'bg-[hsl(var(--primary))] text-white' : 'hover:bg-gray-100'}`}
              >
                {b.value} <span className="text-xs opacity-60">({b.count})</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {facets?.colors && facets.colors.length > 0 && (
        <div>
          <h3 className="font-semibold mb-2 text-sm">Color</h3>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            <button
              onClick={() => setFilter('color', '')}
              className={`block w-full text-left px-2 py-1 rounded text-sm ${!color ? 'font-medium' : 'hover:bg-gray-100'}`}
            >
              All Colors
            </button>
            {facets.colors.map((c) => (
              <button
                key={c.value}
                onClick={() => setFilter('color', c.value)}
                className={`block w-full text-left px-2 py-1 rounded text-sm ${color === c.value ? 'bg-[hsl(var(--primary))] text-white' : 'hover:bg-gray-100'}`}
              >
                {c.value} <span className="text-xs opacity-60">({c.count})</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {facets?.materials && facets.materials.length > 0 && (
        <div>
          <h3 className="font-semibold mb-2 text-sm">Material</h3>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            <button
              onClick={() => setFilter('material', '')}
              className={`block w-full text-left px-2 py-1 rounded text-sm ${!material ? 'font-medium' : 'hover:bg-gray-100'}`}
            >
              All Materials
            </button>
            {facets.materials.map((m) => (
              <button
                key={m.value}
                onClick={() => setFilter('material', m.value)}
                className={`block w-full text-left px-2 py-1 rounded text-sm ${material === m.value ? 'bg-[hsl(var(--primary))] text-white' : 'hover:bg-gray-100'}`}
              >
                {m.value} <span className="text-xs opacity-60">({m.count})</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div>
        <h3 className="font-semibold mb-2 text-sm">Price Range</h3>
        <div className="flex gap-2">
          <Input
            type="number"
            placeholder="Min"
            value={priceMin}
            onChange={(e) => setFilter('priceMin', e.target.value)}
            className="w-20"
          />
          <span className="text-gray-400 self-center">-</span>
          <Input
            type="number"
            placeholder="Max"
            value={priceMax}
            onChange={(e) => setFilter('priceMax', e.target.value)}
            className="w-20"
          />
        </div>
      </div>

      <div>
        <h3 className="font-semibold mb-2 text-sm">Sort</h3>
        <select
          value={sort}
          onChange={(e) => setFilter('sort', e.target.value)}
          className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
        >
          <option value="relevance">Relevance</option>
          <option value="price_asc">Price: Low to High</option>
          <option value="price_desc">Price: High to Low</option>
          <option value="name_asc">Name: A-Z</option>
          <option value="newest">Newest</option>
        </select>
      </div>

      <Button variant="outline" size="sm" onClick={resetFilters} className="w-full">
        Reset Filters
      </Button>
    </div>
  )
}
