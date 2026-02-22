import { useState, useEffect } from 'react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useFilterStore } from '@/stores/filterStore'
import type { Facets, Category } from '@/types'

interface Props {
  facets: Facets | null
  categories: Category[]
  idPrefix?: string
}

export function ProductFilters({ facets, categories, idPrefix = '' }: Props) {
  const { category, brand, color, material, priceMin, priceMax, sort, setFilter, resetFilters } = useFilterStore()

  const [localPriceMin, setLocalPriceMin] = useState(priceMin)
  const [localPriceMax, setLocalPriceMax] = useState(priceMax)

  // Sync local state when store changes externally (e.g. reset filters)
  useEffect(() => { setLocalPriceMin(priceMin) }, [priceMin])
  useEffect(() => { setLocalPriceMax(priceMax) }, [priceMax])

  // Debounce local price min -> store
  useEffect(() => {
    const timer = setTimeout(() => {
      if (localPriceMin !== priceMin) setFilter('priceMin', localPriceMin)
    }, 300)
    return () => clearTimeout(timer)
  }, [localPriceMin])

  // Debounce local price max -> store
  useEffect(() => {
    const timer = setTimeout(() => {
      if (localPriceMax !== priceMax) setFilter('priceMax', localPriceMax)
    }, 300)
    return () => clearTimeout(timer)
  }, [localPriceMax])

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-semibold mb-2 text-sm">Category</h3>
        <div className="space-y-1">
          <button
            role="checkbox"
            aria-checked={!category}
            aria-label="Filter by category: All Categories"
            onClick={() => setFilter('category', '')}
            className={`block w-full text-left px-2 py-1 rounded text-sm ${!category ? 'bg-[hsl(var(--primary))] text-white' : 'hover:bg-gray-100'}`}
          >
            All Categories
          </button>
          {categories.map((cat) => (
            <button
              key={cat.id}
              role="checkbox"
              aria-checked={category === cat.id}
              aria-label={`Filter by category: ${cat.name}`}
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
              role="checkbox"
              aria-checked={!brand}
              aria-label="Filter by brand: All Brands"
              onClick={() => setFilter('brand', '')}
              className={`block w-full text-left px-2 py-1 rounded text-sm ${!brand ? 'font-medium' : 'hover:bg-gray-100'}`}
            >
              All Brands
            </button>
            {facets.brands.map((b) => (
              <button
                key={b.value}
                role="checkbox"
                aria-checked={brand === b.value}
                aria-label={`Filter by brand: ${b.value}`}
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
              role="checkbox"
              aria-checked={!color}
              aria-label="Filter by color: All Colors"
              onClick={() => setFilter('color', '')}
              className={`block w-full text-left px-2 py-1 rounded text-sm ${!color ? 'font-medium' : 'hover:bg-gray-100'}`}
            >
              All Colors
            </button>
            {facets.colors.map((c) => (
              <button
                key={c.value}
                role="checkbox"
                aria-checked={color === c.value}
                aria-label={`Filter by color: ${c.value}`}
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
              role="checkbox"
              aria-checked={!material}
              aria-label="Filter by material: All Materials"
              onClick={() => setFilter('material', '')}
              className={`block w-full text-left px-2 py-1 rounded text-sm ${!material ? 'font-medium' : 'hover:bg-gray-100'}`}
            >
              All Materials
            </button>
            {facets.materials.map((m) => (
              <button
                key={m.value}
                role="checkbox"
                aria-checked={material === m.value}
                aria-label={`Filter by material: ${m.value}`}
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
          <div>
            <label htmlFor={`${idPrefix}price-min`} className="sr-only">Minimum price</label>
            <Input
              id={`${idPrefix}price-min`}
              type="number"
              placeholder="Min"
              value={localPriceMin}
              onChange={(e) => setLocalPriceMin(e.target.value)}
              className="w-20"
            />
          </div>
          <span className="text-gray-400 self-center">-</span>
          <div>
            <label htmlFor={`${idPrefix}price-max`} className="sr-only">Maximum price</label>
            <Input
              id={`${idPrefix}price-max`}
              type="number"
              placeholder="Max"
              value={localPriceMax}
              onChange={(e) => setLocalPriceMax(e.target.value)}
              className="w-20"
            />
          </div>
        </div>
      </div>

      <div>
        <h3 className="font-semibold mb-2 text-sm">Sort</h3>
        <label htmlFor={`${idPrefix}sort-select`} className="sr-only">Sort</label>
        <select
          id={`${idPrefix}sort-select`}
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
