import { LogOut, Menu, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import Logo from './Logo';

const LINKS = [
  { to: '/upload', label: 'Upload' },
  { to: '/history', label: 'History' },
  { to: '/about', label: 'How it works' },
];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
    isActive ? 'bg-ink-800 text-white' : 'text-slate-300 hover:bg-ink-800 hover:text-white'
  }`;

export default function Navbar() {
  const { user, loading, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => setOpen(false), [location.pathname]);

  const authArea = loading ? null : user ? (
    <>
      <span className="max-w-[12rem] truncate px-3 py-2 text-sm text-slate-300" title={user.email}>
        {user.name}
      </span>
      <button type="button" onClick={logout} className="btn-ghost">
        <LogOut className="h-4 w-4" aria-hidden="true" />
        Log out
      </button>
    </>
  ) : (
    <>
      <NavLink to="/login" className={linkClass}>
        Log in
      </NavLink>
      <Link to="/register" className="btn-secondary">
        Sign up
      </Link>
    </>
  );

  return (
    <header className="sticky top-0 z-30 border-b border-ink-700 bg-ink-950/90 backdrop-blur">
      <div className="container-page flex h-16 items-center justify-between gap-4">
        <Link to="/" aria-label="LyricalAI home" className="rounded-lg">
          <Logo />
        </Link>

        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} className={linkClass}>
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden items-center gap-1 md:flex">{authArea}</div>

        <button
          type="button"
          className="btn-ghost px-3 md:hidden"
          aria-expanded={open}
          aria-controls="mobile-menu"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X className="h-5 w-5" aria-hidden="true" /> : <Menu className="h-5 w-5" aria-hidden="true" />}
          <span className="sr-only">{open ? 'Close menu' : 'Open menu'}</span>
        </button>
      </div>

      {open && (
        <div id="mobile-menu" className="border-t border-ink-700 md:hidden">
          <nav aria-label="Mobile" className="container-page flex flex-col gap-1 py-3">
            {LINKS.map((link) => (
              <NavLink key={link.to} to={link.to} className={linkClass}>
                {link.label}
              </NavLink>
            ))}
            <div className="mt-2 flex flex-col gap-1 border-t border-ink-700 pt-3">{authArea}</div>
          </nav>
        </div>
      )}
    </header>
  );
}
