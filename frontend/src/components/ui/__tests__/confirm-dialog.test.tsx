import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConfirmDialog } from '../confirm-dialog'

describe('ConfirmDialog', () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
    onConfirm: vi.fn(),
    title: 'Delete item?',
    description: 'This action cannot be undone.',
  }

  it('renders title and description when open', () => {
    render(<ConfirmDialog {...defaultProps} />)

    expect(screen.getByText('Delete item?')).toBeInTheDocument()
    expect(screen.getByText('This action cannot be undone.')).toBeInTheDocument()
  })

  it('does not render content when closed', () => {
    render(<ConfirmDialog {...defaultProps} open={false} />)

    expect(screen.queryByText('Delete item?')).not.toBeInTheDocument()
  })

  it('calls onConfirm when confirm button is clicked', async () => {
    const onConfirm = vi.fn()
    const user = userEvent.setup()

    render(<ConfirmDialog {...defaultProps} onConfirm={onConfirm} />)

    await user.click(screen.getByRole('button', { name: 'Delete' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when cancel button is clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()

    render(<ConfirmDialog {...defaultProps} onClose={onClose} />)

    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('shows loading text when loading=true', () => {
    render(<ConfirmDialog {...defaultProps} loading={true} />)

    expect(screen.getByRole('button', { name: 'Deleting...' })).toBeInTheDocument()
  })

  it('disables buttons when loading', () => {
    render(<ConfirmDialog {...defaultProps} loading={true} />)

    const buttons = screen.getAllByRole('button').filter(
      (btn) => btn.textContent === 'Cancel' || btn.textContent === 'Deleting...',
    )
    buttons.forEach((btn) => {
      expect(btn).toBeDisabled()
    })
  })

  it('uses custom labels', () => {
    render(
      <ConfirmDialog
        {...defaultProps}
        confirmLabel="Yes, remove"
        cancelLabel="No, keep it"
      />,
    )

    expect(screen.getByRole('button', { name: 'Yes, remove' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'No, keep it' })).toBeInTheDocument()
  })

  it('renders children content', () => {
    render(
      <ConfirmDialog {...defaultProps}>
        <p>Extra warning content</p>
      </ConfirmDialog>,
    )

    expect(screen.getByText('Extra warning content')).toBeInTheDocument()
  })
})
