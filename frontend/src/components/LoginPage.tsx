import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const UserIcon = () => (
  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
  </svg>
);

const LockIcon = () => (
  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
  </svg>
);

const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (e: React.SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMessage('');

    if (!username.trim() || !password) {
      setErrorMessage('Please enter your username and password.');
      return;
    }

    setIsSubmitting(true);
    try {
      await login(username, password);
      setUsername('');
      setPassword('');
      void navigate('/');
    } catch (error) {
      const message = error instanceof Error ? error.message : '';
      setErrorMessage(message || 'Invalid username or password.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-b from-[var(--sidebar)] via-[var(--sidebar)] to-[var(--sidebar-accent)]">
      {/* Containerul principal este acum max-w-sm (mai îngust) */}
      <div className="max-w-sm w-full flex flex-col items-center">

        {/* LOGO SECTION - Micșorat distanțele */}
        <div className="flex flex-col items-center mb-8">
          <div className="bg-[var(--primary)] rounded-xl p-3 mb-3 shadow-lg">
            <span className="text-white text-3xl font-black leading-none">M</span>
          </div>
          <h1 className="text-white text-2xl font-bold tracking-[0.2em]">M.I.E.Z</h1>
          <p className="text-white/50 mt-1 text-xs font-light">Enterprise Resource Planning</p>
        </div>

        {/* MAIN CARD - Padding redus la p-8 și rotunjire ajustată */}
        <div className="bg-[var(--card)] rounded-[2rem] shadow-2xl p-8 w-full mb-8">
          <h2 className="text-[var(--foreground)] text-2xl font-bold text-center mb-8">Sign In</h2>

          <form onSubmit={(e) => void handleLogin(e)} className="space-y-5">
            {errorMessage && (
              <div
                className="bg-red-50 text-red-700 border border-red-200 rounded-2xl px-4 py-3 text-sm"
                role="alert"
                aria-live="polite"
              >
                {errorMessage}
              </div>
            )}

            <div>
              <label className="block text-xs font-bold text-gray-500 mb-1.5 ml-1">Username</label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <UserIcon />
                </span>
                <input
                  type="text"
                  placeholder="Enter username"
                  className="w-full pl-12 pr-4 py-3 bg-[var(--card)] border border-[var(--border)] rounded-full focus:ring-2 focus:ring-[var(--primary)]/20 focus:border-[var(--primary)] outline-none transition-all text-sm placeholder:text-gray-300"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={isSubmitting}
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-500 mb-1.5 ml-1">Password</label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <LockIcon />
                </span>
                <input
                  type="password"
                  placeholder="Enter password"
                  className="w-full pl-12 pr-4 py-3 bg-[var(--card)] border border-[var(--border)] rounded-full focus:ring-2 focus:ring-[var(--primary)]/20 focus:border-[var(--primary)] outline-none transition-all text-sm placeholder:text-gray-300"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isSubmitting}
                />
              </div>
            </div>

            <button
              type="submit"
              className="w-full py-3.5 bg-[var(--primary)] hover:bg-[var(--primary-foreground)] text-[var(--primary-foreground)] font-bold rounded-full transition-colors shadow-lg shadow-[var(--primary)]/20 mt-2 text-sm disabled:opacity-60 disabled:cursor-not-allowed"
              disabled={isSubmitting}

            >
              {isSubmitting ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          <div className="relative my-8">
            <div className="absolute inset-0 flex items-center"><span className="w-full border-t border-gray-50"></span></div>
          </div>
        </div>
        

        {/* FOOTER */}
        <p className="text-white/30 text-[9px] tracking-[0.3em] uppercase">
          © 2026 M.I.E.Z. All rights reserved.
        </p>
      </div>
    </div>
  );
};

export default LoginPage;