import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import { useAuth } from '@/lib/auth/AuthContext';
import { UserRole, ROLE_LABELS, USER_ROLES } from '@/lib/auth/roles';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

// Screen S1/S1b: Authentication (Sign in / Sign up)
export const AuthPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, loading: authLoading, signInWithEmail, signUpWithEmail, signInWithGoogle } = useAuth();

  const isInitialSignUp = location.pathname === '/sign-up';
  const [activeTab, setActiveTab] = useState<'sign-in' | 'sign-up'>(
    isInitialSignUp ? 'sign-up' : 'sign-in'
  );

  // Sign-in states
  const [signInEmail, setSignInEmail] = useState('demo@vixenone.app');
  const [signInPassword, setSignInPassword] = useState('demo1234');

  // Sign-up states
  const [signUpName, setSignUpName] = useState('');
  const [signUpEmail, setSignUpEmail] = useState('');
  const [signUpPassword, setSignUpPassword] = useState('');
  const [role, setRole] = useState<UserRole>('facilities_manager');

  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Redirect signed-in users visiting /sign-in or /sign-up straight to /evaluations
  const initialAuthChecked = useRef(false);

  useEffect(() => {
    if (authLoading) return;
    if (!initialAuthChecked.current) {
      initialAuthChecked.current = true;
      if (user) {
        navigate('/evaluations', { replace: true });
      }
    }
  }, [user, authLoading, navigate]);

  useEffect(() => {
    if (location.pathname === '/sign-up') {
      setActiveTab('sign-up');
    } else if (location.pathname === '/sign-in') {
      setActiveTab('sign-in');
    }
  }, [location.pathname]);

  const handleTabChange = (tab: 'sign-in' | 'sign-up') => {
    setActiveTab(tab);
    setError(null);
    if (tab === 'sign-in') {
      navigate('/sign-in');
    } else {
      navigate('/sign-up');
    }
  };

  const handleEmailSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedEmail = signInEmail.trim();
    if (!trimmedEmail || !signInPassword) {
      setError('Please fill in all required fields.');
      return;
    }

    setLoading(true);

    try {
      await signInWithEmail(trimmedEmail, signInPassword);
      navigate('/evaluations', { replace: true });
    } catch (err: any) {
      console.error('[Sign-in Error]', err?.code, err?.message);
      setError(`Invalid email or password (${err?.code || 'auth/error'}). Please try again.`);
    } finally {
      setLoading(false);
    }
  };

  const handleEmailSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedName = signUpName.trim();
    const trimmedEmail = signUpEmail.trim();

    if (!trimmedName || !trimmedEmail || !signUpPassword) {
      setError('Please fill in all required fields.');
      return;
    }

    if (signUpPassword.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    setLoading(true);

    try {
      await signUpWithEmail(trimmedEmail, signUpPassword, trimmedName, role);
      navigate('/evaluations', { replace: true });
    } catch (err: any) {
      console.error('[Sign-up Error]', err);
      if (err?.code === 'auth/email-already-in-use' || err?.message?.includes('email-already-in-use')) {
        setError('Email already in use. Please sign in instead.');
      } else if (err?.code === 'auth/weak-password' || err?.message?.includes('weak-password')) {
        setError('Password must be at least 8 characters.');
      } else if (err?.code === 'auth/invalid-email' || err?.message?.includes('invalid-email')) {
        setError('Please enter a valid work email address.');
      } else {
        setError(err?.message || 'Unable to create account. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError(null);
    setGoogleLoading(true);

    try {
      await signInWithGoogle();
      navigate('/evaluations', { replace: true });
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
        {/* Brand Header */}
        <div className="flex items-center justify-center select-none">
          <img src="/logo.png" alt="VixenOne" className="h-10 w-auto max-w-full object-contain" />
        </div>

        {/* Tab switcher: Sign in · Sign up */}
        <div className="flex border-b border-border">
          <button
            type="button"
            onClick={() => handleTabChange('sign-in')}
            className={`flex-1 pb-2.5 text-sm text-center font-medium transition-colors focus:outline-none ${
              activeTab === 'sign-in'
                ? 'text-text font-semibold border-b-2 border-accent'
                : 'text-muted hover:text-text'
            }`}
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={() => handleTabChange('sign-up')}
            className={`flex-1 pb-2.5 text-sm text-center font-medium transition-colors focus:outline-none ${
              activeTab === 'sign-up'
                ? 'text-text font-semibold border-b-2 border-accent'
                : 'text-muted hover:text-text'
            }`}
          >
            Sign up
          </button>
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

        {/* Tab 1: Sign in Form */}
        {activeTab === 'sign-in' ? (
          <form onSubmit={handleEmailSignIn} noValidate className="space-y-4">
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
                value={signInEmail}
                onChange={(e) => setSignInEmail(e.target.value)}
                placeholder="you@company.com"
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
                  className="text-xs text-navy font-medium hover:underline focus:outline-none"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <Input
                  id="password-input"
                  type={showPassword ? 'text' : 'password'}
                  value={signInPassword}
                  onChange={(e) => setSignInPassword(e.target.value)}
                  className="h-9 pr-9"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
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
        ) : (
          /* Tab 2: Sign up Form */
          <form onSubmit={handleEmailSignUp} noValidate className="space-y-4">
            <div className="space-y-1.5 text-left">
              <label
                htmlFor="signup-name"
                className="text-xs font-medium text-text block"
              >
                Full name
              </label>
              <Input
                id="signup-name"
                type="text"
                value={signUpName}
                onChange={(e) => setSignUpName(e.target.value)}
                placeholder="Priya Sharma"
                className="h-9"
              />
            </div>

            <div className="space-y-1.5 text-left">
              <label
                htmlFor="signup-email"
                className="text-xs font-medium text-text block"
              >
                Work email
              </label>
              <Input
                id="signup-email"
                type="email"
                value={signUpEmail}
                onChange={(e) => setSignUpEmail(e.target.value)}
                placeholder="you@company.com"
                className="h-9"
              />
            </div>

            <div className="space-y-1.5 text-left">
              <label
                htmlFor="signup-password"
                className="text-xs font-medium text-text block"
              >
                Password
              </label>
              <div className="relative">
                <Input
                  id="signup-password"
                  type={showPassword ? 'text' : 'password'}
                  value={signUpPassword}
                  onChange={(e) => setSignUpPassword(e.target.value)}
                  placeholder=""
                  className="h-9 pr-9"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-text focus:outline-none"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
              <p className="text-xs text-muted">At least 8 characters</p>
            </div>

            <div className="space-y-1.5 text-left">
              <label
                htmlFor="signup-role"
                className="text-xs font-medium text-text block"
              >
                Role
              </label>
              <Select value={role} onValueChange={(val) => setRole(val as UserRole)}>
                <SelectTrigger id="signup-role" className="h-9">
                  <SelectValue placeholder="Select role">{ROLE_LABELS[role]}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {USER_ROLES.map((roleKey) => (
                    <SelectItem key={roleKey} value={roleKey}>
                      {ROLE_LABELS[roleKey]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
                'Create account'
              )}
            </Button>

            <div className="text-center pt-1">
              <button
                type="button"
                onClick={() => handleTabChange('sign-in')}
                className="text-xs text-muted hover:text-text"
              >
                Already have an account?{' '}
                <span className="text-navy font-semibold hover:underline">Sign in</span>
              </button>
            </div>
          </form>
        )}
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

export default AuthPage;
