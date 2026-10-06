import { Loader2 } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { getErrorMessage } from '../services/api';
import Alert from './Alert';

const MIN_PASSWORD_LENGTH = 8;

/** Shared form for the Login and Register pages. */
export default function AuthForm({ mode }: { mode: 'login' | 'register' }) {
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const isRegister = mode === 'register';
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user && !submitting) return <Navigate to="/history" replace />;

  const validate = (): string | null => {
    if (isRegister && !name.trim()) return 'Enter your name.';
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return 'Enter a valid email address.';
    if (isRegister && password.length < MIN_PASSWORD_LENGTH) {
      return `Use a password with at least ${MIN_PASSWORD_LENGTH} characters.`;
    }
    if (!password) return 'Enter your password.';
    return null;
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const problem = validate();
    if (problem) {
      setError(problem);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      if (isRegister) await register(name.trim(), email.trim(), password);
      else await login(email.trim(), password);
      navigate('/history', { replace: true });
    } catch (submitError) {
      setError(
        getErrorMessage(
          submitError,
          isRegister ? "We couldn't create your account. Please try again." : "We couldn't log you in. Please try again.",
        ),
      );
      setSubmitting(false);
    }
  };

  return (
    <div className="container-page max-w-md py-12 sm:py-16">
      <h1 className="text-3xl">{isRegister ? 'Create your account' : 'Log in'}</h1>
      <p className="muted mt-2">
        An account is optional. It keeps your transcription history available on any device.
      </p>

      <form onSubmit={(event) => void onSubmit(event)} className="card mt-8 space-y-4 p-5 sm:p-6" noValidate>
        {error && <Alert>{error}</Alert>}

        {isRegister && (
          <div>
            <label htmlFor="auth-name" className="label">
              Name
            </label>
            <input
              id="auth-name"
              className="input"
              type="text"
              autoComplete="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </div>
        )}

        <div>
          <label htmlFor="auth-email" className="label">
            Email
          </label>
          <input
            id="auth-email"
            className="input"
            type="email"
            inputMode="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>

        <div>
          <label htmlFor="auth-password" className="label">
            Password
          </label>
          <input
            id="auth-password"
            className="input"
            type="password"
            autoComplete={isRegister ? 'new-password' : 'current-password'}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-describedby={isRegister ? 'auth-password-hint' : undefined}
            minLength={isRegister ? MIN_PASSWORD_LENGTH : undefined}
            required
          />
          {isRegister && (
            <p id="auth-password-hint" className="muted mt-1.5">
              At least {MIN_PASSWORD_LENGTH} characters.
            </p>
          )}
        </div>

        <button type="submit" className="btn-primary w-full" disabled={submitting}>
          {submitting && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {isRegister ? 'Create account' : 'Log in'}
        </button>
      </form>

      <p className="muted mt-5 text-center">
        {isRegister ? 'Already have an account? ' : 'New to LyricalAI? '}
        <Link
          to={isRegister ? '/login' : '/register'}
          className="rounded text-violet-300 underline underline-offset-4 hover:text-violet-200"
        >
          {isRegister ? 'Log in' : 'Create an account'}
        </Link>
      </p>
    </div>
  );
}
