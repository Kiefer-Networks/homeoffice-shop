import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/services/authApi'
import { setAccessToken as setGlobalToken } from '@/lib/token'

export function CallbackPage() {
  const navigate = useNavigate()
  const { setAccessToken, setUser } = useAuthStore()

  useEffect(() => {
    // Exchange refresh token cookie for access token via API
    authApi.refresh()
      .then(({ data }) => {
        const token = data.access_token
        setGlobalToken(token)
        setAccessToken(token)
        return authApi.getMe()
      })
      .then(({ data }) => {
        setUser(data)
        navigate('/')
      })
      .catch(() => navigate('/login'))
  }, [navigate, setAccessToken, setUser])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <p className="text-lg text-[hsl(var(--muted-foreground))]">Signing you in...</p>
    </div>
  )
}
