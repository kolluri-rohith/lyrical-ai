import { AlertTriangle, CircleAlert, Info } from 'lucide-react';
import type { ReactNode } from 'react';

type Tone = 'error' | 'warning' | 'info';

const TONES: Record<Tone, { box: string; icon: typeof Info }> = {
  error: { box: 'border-red-500/40 bg-red-500/10 text-red-100', icon: CircleAlert },
  warning: { box: 'border-amber-500/40 bg-amber-500/10 text-amber-100', icon: AlertTriangle },
  info: { box: 'border-ink-600 bg-ink-800 text-slate-200', icon: Info },
};

interface AlertProps {
  tone?: Tone;
  children: ReactNode;
  className?: string;
  id?: string;
}

export default function Alert({ tone = 'error', children, className = '', id }: AlertProps) {
  const { box, icon: Icon } = TONES[tone];
  return (
    <div
      id={id}
      role={tone === 'error' ? 'alert' : 'status'}
      className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${box} ${className}`}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 break-words">{children}</div>
    </div>
  );
}
