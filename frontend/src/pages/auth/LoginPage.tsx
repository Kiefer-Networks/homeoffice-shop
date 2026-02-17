import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[hsl(var(--muted))] px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">Home Office Shop</CardTitle>
          <CardDescription>Sign in with your company account to start ordering equipment.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button className="w-full" variant="outline" asChild>
            <a href={`${API_URL}/api/auth/google/login`}>
              Sign in with Google
            </a>
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
