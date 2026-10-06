import { AudioLines } from 'lucide-react';

export default function Logo({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 text-lg font-semibold text-white ${className}`}>
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-violet-700">
        <AudioLines className="h-5 w-5 text-white" aria-hidden="true" />
      </span>
      <span>
        Lyrical<span className="text-violet-400">AI</span>
      </span>
    </span>
  );
}
