import { useState } from 'react';
import { loginWithEmail, loginWithGoogle, isEmailAllowed, type User } from './firebase';

interface LoginScreenProps {
  onLogin: (user: User) => void;
}

export default function LoginScreen({ onLogin }: LoginScreenProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleEmailLogin(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const cred = await loginWithEmail(email, password);
      if (!isEmailAllowed(cred.user.email)) {
        setError('Access denied. This email is not authorized.');
        return;
      }
      onLogin(cred.user);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Login failed';
      if (msg.includes('invalid-credential') || msg.includes('wrong-password')) {
        setError('Invalid email or password.');
      } else if (msg.includes('user-not-found')) {
        setError('No account found for this email.');
      } else if (msg.includes('too-many-requests')) {
        setError('Too many attempts. Please try again later.');
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleLogin() {
    setError(null);
    setLoading(true);
    try {
      const cred = await loginWithGoogle();
      if (!isEmailAllowed(cred.user.email)) {
        setError('Access denied. This email is not authorized.');
        return;
      }
      onLogin(cred.user);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Google login failed';
      if (msg.includes('popup-closed-by-user')) {
        // User closed the popup — no error needed
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 transition-colors duration-300">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-full bg-gaa-text flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-bold text-2xl" style={{ fontFamily: 'var(--font-display)' }}>G</span>
          </div>
          <h1 className="text-xl font-bold gaa-text-primary tracking-tight" style={{ fontFamily: 'var(--font-display)' }}>
            Gernetzke & Associates
          </h1>
          <p className="text-sm gaa-text-muted mt-1">Financial Services Dashboard</p>
        </div>

        {/* Card */}
        <div className="gaa-card p-6 sm:p-8">
          <h2 className="gaa-heading text-lg mb-1">Sign in</h2>
          <p className="text-xs gaa-text-muted mb-6">Authorized personnel only.</p>

          {/* Error */}
          {error && (
            <div className="mb-4 p-3 rounded-lg text-xs font-medium"
              style={{
                background: 'var(--color-gaa-danger-bg, #fef2f2)',
                color: 'var(--color-gaa-danger, #dc2626)',
                border: '1px solid var(--color-gaa-danger, #dc2626)',
                opacity: 0.9,
              }}>
              {error}
            </div>
          )}

          {/* Google Sign-In */}
          <button
            onClick={handleGoogleLogin}
            disabled={loading}
            className="w-full flex items-center justify-center gap-3 px-4 py-2.5 rounded-lg border text-sm font-medium transition-all duration-200 mb-5"
            style={{
              borderColor: 'var(--color-gaa-border)',
              background: 'var(--color-gaa-surface)',
              color: 'var(--color-gaa-text)',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 48 48">
              <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
              <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
              <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
              <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
            </svg>
            Sign in with Google
          </button>

          {/* Divider */}
          <div className="flex items-center gap-3 mb-5">
            <div className="flex-1 h-px" style={{ background: 'var(--color-gaa-border)' }} />
            <span className="text-xs gaa-text-muted">or</span>
            <div className="flex-1 h-px" style={{ background: 'var(--color-gaa-border)' }} />
          </div>

          {/* Email/Password Form */}
          <form onSubmit={handleEmailLogin} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-xs font-medium gaa-text-secondary mb-1.5">Email</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="gaa-input w-full"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-xs font-medium gaa-text-secondary mb-1.5">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="gaa-input w-full"
                placeholder="Enter password"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="gaa-btn-primary w-full justify-center text-sm py-2.5"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-xs gaa-text-muted mt-6">
          Secured by Firebase Authentication
        </p>
      </div>
    </div>
  );
}
