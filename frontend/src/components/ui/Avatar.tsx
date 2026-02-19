import { useState } from 'react'

interface AvatarProps {
  src?: string | null
  name: string
  size?: 'sm' | 'md' | 'lg'
  colorful?: boolean
}

export function Avatar({ src, name, size = 'md', colorful = false }: AvatarProps) {
  const [imgError, setImgError] = useState(false)

  const sizeClasses = { sm: 'h-8 w-8 text-xs', md: 'h-10 w-10 text-sm', lg: 'h-16 w-16 text-xl' }
  const sizeClass = sizeClasses[size]

  const sizePx = { sm: 32, md: 40, lg: 64 }
  const px = sizePx[size]

  if (src && !imgError) {
    return (
      <img
        src={src}
        alt={name}
        className={`${sizeClass} rounded-full object-cover shrink-0`}
        onError={() => setImgError(true)}
      />
    )
  }

  const initials = name
    .split(' ')
    .map(n => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  if (colorful) {
    let hash = 0
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash)
    }
    const hue = Math.abs(hash) % 360

    return (
      <div
        className="rounded-full flex items-center justify-center text-white font-medium shrink-0"
        style={{
          width: px,
          height: px,
          fontSize: px * 0.38,
          backgroundColor: `hsl(${hue}, 55%, 50%)`,
        }}
      >
        {initials}
      </div>
    )
  }

  return (
    <div className={`${sizeClass} rounded-full bg-[hsl(var(--muted))] flex items-center justify-center font-medium`}>
      {initials}
    </div>
  )
}
