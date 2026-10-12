import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import { useAuth } from '@/lib/auth/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export const S1: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, signInWithEmail, signInWithGoogle } = useAuth();

  const [email, setEmail] = useState('demo@vixenone.app');
  const [password, setPassword] = useState('demo1234');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // If already authenticated, redirect to destination
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/evaluations';

  React.useEffect(() => {
    if (user) {
      navigate(from, { replace: true });
    }
  }, [user, navigate, from]);

  const handleEmailSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await signInWithEmail(email, password);
      navigate(from, { replace: true });
    } catch (err: any) {
      console.error('[Sign-in Error]', err?.code, err?.message);
      setError(`Invalid email or password (${err?.code || 'auth/error'}). Please try again.`);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError(null);
    setGoogleLoading(true);

    try {
      await signInWithGoogle();
      navigate(from, { replace: true });
    } catch {
      setError('Google sign-in was cancelled or failed.');
    } finally {
      setGoogleLoading(false);
    }
  };

  const handleForgotPassword = (e: React.MouseEvent) => {
    e.preventDefault();
    setToastMessage('Not available in the prototype');
    setTimeout(() => {
      setToastMessage(null);
    }, 3000);
  };

  return (
    <div className="min-h-screen bg-surface flex flex-col items-center justify-center p-4 relative select-none">
      {/* Toast notification */}
      {toastMessage && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 rounded-lg bg-text text-background text-xs px-4 py-2 shadow-dropdown transition-all animate-in fade-in slide-in-from-top-2">
          {toastMessage}
        </div>
      )}

      {/* Main card */}
      <div className="w-[400px] max-w-full rounded-lg border border-border bg-background p-8 space-y-6">
        {/* Wordmark and Tagline */}
        <div className="text-center space-y-1.5">
          <div className="flex items-center justify-center">
            <span className="text-2xl font-semibold text-text tracking-tight">
              VixenOne
            </span>
            <span className="w-2 h-2 rounded-full bg-accent inline-block ml-1" />
          </div>
          <p className="text-body text-muted">
            Evidence-backed vendor proposal evaluation.
          </p>
        </div>

        {/* Continue with Google button */}
        <div>
          <Button
            type="button"
            variant="secondary"
            onClick={handleGoogleSignIn}
            disabled={googleLoading || loading}
            className="w-full h-10 font-normal justify-center gap-2.5 text-text"
          >
            {googleLoading ? (
              <Loader2 className="w-4 h-4 animate-spin text-muted" />
            ) : (
              <svg className="w-4 h-4" viewBox="0 0 24 24">
                <path
                  fill="var(--google-blue)"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="var(--google-green)"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="var(--google-yellow)"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="var(--google-red)"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
            )}
            <span>Continue with Google</span>
          </Button>
        </div>

        {/* Divider */}
        <div className="relative flex items-center justify-center">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t border-border" />
          </div>
          <span className="relative bg-background px-3 text-xs text-muted">
            or
          </span>
        </div>

        {/* Error message */}
        {error && (
          <div className="rounded-md border border-status-noncompliant-text/30 bg-status-noncompliant-bg px-3 py-2 text-xs text-status-noncompliant-text">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleEmailSignIn} className="space-y-4">
          <div className="space-y-1.5 text-left">
            <label
              htmlFor="email-input"
              className="text-xs font-medium text-text block"
            >
              Email
            </label>
            <Input
              id="email-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
              className="h-9"
            />
          </div>

          <div className="space-y-1.5 text-left">
            <div className="flex items-center justify-between">
              <label
                htmlFor="password-input"
                className="text-xs font-medium text-text block"
              >
                Password
              </label>
              <button
                type="button"
                onClick={handleForgotPassword}
                className="text-xs text-accent hover:underline focus:outline-none"
              >
                Forgot password?
              </button>
            </div>
            <div className="relative">
              <Input
                id="password-input"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="h-9 pr-9"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-text focus:outline-none"
              >
                {showPassword ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          <Button
            type="submit"
            variant="primary"
            disabled={loading || googleLoading}
            className="w-full h-10 font-medium justify-center"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              'Sign in'
            )}
          </Button>
        </form>
      </div>

      {/* Info box below card */}
      <div className="w-[400px] max-w-full mt-4 text-center space-y-2">
        <div className="rounded-lg border border-border bg-surface px-4 py-2 text-xs text-muted">
          Demo account: demo@vixenone.app
        </div>
        <p className="text-xs text-muted">
          Prototype · AI Builder Cup 2026
        </p>
      </div>
    </div>
  );
};

export default S1;
