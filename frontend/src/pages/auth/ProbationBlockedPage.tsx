import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Link } from 'react-router-dom'
import { useBrandingStore } from '@/stores/brandingStore'

export function ProbationBlockedPage() {
  const companyName = useBrandingStore((s) => s.companyName)
  return (
    <div className="min-h-screen flex items-center justify-center bg-[hsl(var(--muted))] px-4">
      <Card className="w-full max-w-md text-center">
        <CardHeader>
          <CardTitle>Access Restricted</CardTitle>
          <CardDescription>
            Your probation period has not ended yet. You will be able to access the
            {' '}{companyName} once your probation is complete.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-[hsl(var(--muted-foreground))] mb-4">
            If you believe this is an error, please contact your administrator.
          </p>
          <Button variant="outline" asChild>
            <Link to="/login">Back to Login</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
