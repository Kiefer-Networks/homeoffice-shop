import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/services/authApi'
import { setAccessToken as setGlobalToken } from '@/lib/token'

export function CallbackPage() {
  const navigate = useNavigate()
  const { setAccessToken, setUser } = useAuthStore()

  useEffect(() => {
    const hash = window.location.hash.substring(1)
    const params = new URLSearchParams(hash)
    const token = params.get('access_token')
    if (token) {
      window.history.replaceState(null, '', window.location.pathname)
      setGlobalToken(token)
      setAccessToken(token)
      authApi.getMe().then(({ data }) => {
        setUser(data)
        navigate('/')
      }).catch(() => navigate('/login'))
    } else {
      navigate('/login')
    }
  }, [navigate, setAccessToken, setUser])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <p className="text-lg text-[hsl(var(--muted-foreground))]">Signing you in...</p>
    </div>
  )
}
