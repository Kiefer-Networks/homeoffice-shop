import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/services/authApi'

export function CallbackPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { setAccessToken, setUser } = useAuthStore()

  useEffect(() => {
    const token = searchParams.get('access_token')
    if (token) {
      ;(window as any).__accessToken = token
      setAccessToken(token)
      authApi.getMe().then(({ data }) => {
        setUser(data)
        navigate('/')
      }).catch(() => navigate('/login'))
    } else {
      navigate('/login')
    }
  }, [])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <p className="text-lg text-[hsl(var(--muted-foreground))]">Signing you in...</p>
    </div>
  )
}
