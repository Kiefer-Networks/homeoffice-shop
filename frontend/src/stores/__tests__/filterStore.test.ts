import { describe, it, expect, beforeEach } from 'vitest'
import { useFilterStore } from '../filterStore'

describe('filterStore', () => {
  beforeEach(() => {
    useFilterStore.getState().resetFilters()
  })

  describe('syncFromUrl', () => {
    it('correctly parses URL params', () => {
      const params = new URLSearchParams(
        'q=keyboard&category=cat1&brand=Logitech&color=black&material=plastic&price_min=1000&price_max=50000&sort=price_asc&page=3',
      )
      useFilterStore.getState().syncFromUrl(params)

      const state = useFilterStore.getState()
      expect(state.q).toBe('keyboard')
      expect(state.category).toBe('cat1')
      expect(state.brand).toBe('Logitech')
      expect(state.color).toBe('black')
      expect(state.material).toBe('plastic')
      expect(state.priceMin).toBe('1000')
      expect(state.priceMax).toBe('50000')
      expect(state.sort).toBe('price_asc')
      expect(state.page).toBe(3)
    })

    it('handles missing params with defaults', () => {
      const params = new URLSearchParams('')
      useFilterStore.getState().syncFromUrl(params)

      const state = useFilterStore.getState()
      expect(state.q).toBe('')
      expect(state.category).toBe('')
      expect(state.brand).toBe('')
      expect(state.sort).toBe('relevance')
      expect(state.page).toBe(1)
    })

    it('clamps invalid page values (NaN) to 1', () => {
      const params = new URLSearchParams('page=abc')
      useFilterStore.getState().syncFromUrl(params)

      const state = useFilterStore.getState()
      // parseInt('abc', 10) returns NaN, which is clamped to 1
      expect(state.page).toBe(1)
    })

    it('clamps negative page value to 1', () => {
      const params = new URLSearchParams('page=-5')
      useFilterStore.getState().syncFromUrl(params)

      const state = useFilterStore.getState()
      // Math.max(1, -5) => 1
      expect(state.page).toBe(1)
    })

    it('handles partial URL params', () => {
      const params = new URLSearchParams('q=mouse&sort=newest')
      useFilterStore.getState().syncFromUrl(params)

      const state = useFilterStore.getState()
      expect(state.q).toBe('mouse')
      expect(state.sort).toBe('newest')
      expect(state.category).toBe('')
      expect(state.page).toBe(1)
    })
  })

  describe('setFilter', () => {
    it('updates the specified filter value', () => {
      useFilterStore.getState().setFilter('q', 'monitor')
      expect(useFilterStore.getState().q).toBe('monitor')
    })

    it('resets page to 1 when changing a non-page filter', () => {
      useFilterStore.getState().setFilter('page', 5)
      expect(useFilterStore.getState().page).toBe(5)

      useFilterStore.getState().setFilter('brand', 'Dell')
      expect(useFilterStore.getState().brand).toBe('Dell')
      expect(useFilterStore.getState().page).toBe(1)
    })

    it('does not reset page when changing the page filter', () => {
      useFilterStore.getState().setFilter('page', 3)
      expect(useFilterStore.getState().page).toBe(3)
    })

    it('updates category filter', () => {
      useFilterStore.getState().setFilter('category', 'monitors')
      expect(useFilterStore.getState().category).toBe('monitors')
    })

    it('updates sort filter and resets page', () => {
      useFilterStore.getState().setFilter('page', 4)
      useFilterStore.getState().setFilter('sort', 'price_desc')
      expect(useFilterStore.getState().sort).toBe('price_desc')
      expect(useFilterStore.getState().page).toBe(1)
    })
  })

  describe('resetFilters', () => {
    it('resets all filters to their defaults', () => {
      useFilterStore.getState().setFilter('q', 'keyboard')
      useFilterStore.getState().setFilter('brand', 'Apple')
      useFilterStore.getState().setFilter('page', 5)
      useFilterStore.getState().setFilter('sort', 'price_asc')

      useFilterStore.getState().resetFilters()

      const state = useFilterStore.getState()
      expect(state.q).toBe('')
      expect(state.brand).toBe('')
      expect(state.category).toBe('')
      expect(state.color).toBe('')
      expect(state.material).toBe('')
      expect(state.priceMin).toBe('')
      expect(state.priceMax).toBe('')
      expect(state.sort).toBe('relevance')
      expect(state.page).toBe(1)
    })
  })

  describe('toSearchParams', () => {
    it('generates correct URLSearchParams with all filters set', () => {
      const { setFilter } = useFilterStore.getState()
      setFilter('q', 'desk')
      setFilter('category', 'furniture')
      setFilter('brand', 'IKEA')
      setFilter('color', 'white')
      setFilter('material', 'wood')
      setFilter('priceMin', '5000')
      setFilter('priceMax', '50000')
      setFilter('sort', 'name_asc')
      setFilter('page', 2)

      const params = useFilterStore.getState().toSearchParams()
      expect(params.get('q')).toBe('desk')
      expect(params.get('category')).toBe('furniture')
      expect(params.get('brand')).toBe('IKEA')
      expect(params.get('color')).toBe('white')
      expect(params.get('material')).toBe('wood')
      expect(params.get('price_min')).toBe('5000')
      expect(params.get('price_max')).toBe('50000')
      expect(params.get('sort')).toBe('name_asc')
      expect(params.get('page')).toBe('2')
    })

    it('omits empty or default values', () => {
      const params = useFilterStore.getState().toSearchParams()
      expect(params.toString()).toBe('')
    })

    it('omits sort when it is "relevance" (default)', () => {
      useFilterStore.getState().setFilter('q', 'chair')
      const params = useFilterStore.getState().toSearchParams()
      expect(params.has('sort')).toBe(false)
      expect(params.get('q')).toBe('chair')
    })

    it('omits page when it is 1 (default)', () => {
      useFilterStore.getState().setFilter('q', 'mouse')
      const params = useFilterStore.getState().toSearchParams()
      expect(params.has('page')).toBe(false)
    })

    it('includes page when greater than 1', () => {
      useFilterStore.getState().setFilter('page', 3)
      const params = useFilterStore.getState().toSearchParams()
      expect(params.get('page')).toBe('3')
    })
  })
})
