import { Check, Copy, Download, Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { downloadLyrics, getErrorMessage } from '../services/api';
import type { DownloadFormat } from '../types';
import Alert from './Alert';

interface DownloadButtonsProps {
  jobId: string;
  /** Plain lyrics for the Copy button; the button is hidden when empty. */
  fullText?: string | null;
  formats?: DownloadFormat[];
  compact?: boolean;
}

async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  // Fallback for non-secure contexts (plain http on a LAN address).
  const area = document.createElement('textarea');
  area.value = text;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.opacity = '0';
  document.body.appendChild(area);
  area.select();
  const ok = document.execCommand('copy');
  area.remove();
  if (!ok) throw new Error('copy failed');
}

export default function DownloadButtons({
  jobId,
  fullText,
  formats = ['txt', 'srt', 'vtt'],
  compact = false,
}: DownloadButtonsProps) {
  const [busy, setBusy] = useState<DownloadFormat | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const onCopy = async () => {
    if (!fullText) return;
    try {
      await copyText(fullText);
      setError(null);
      setCopied(true);
    } catch {
      setError("Couldn't copy the lyrics. Select the text and copy it manually.");
    }
  };

  const onDownload = async (format: DownloadFormat) => {
    setBusy(format);
    setError(null);
    try {
      await downloadLyrics(jobId, format);
    } catch (downloadError) {
      setError(getErrorMessage(downloadError, "Couldn't download the file. Please try again."));
    } finally {
      setBusy(null);
    }
  };

  const buttonClass = compact ? 'btn-secondary min-h-[40px] px-3 py-2 text-xs' : 'btn-secondary';

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {fullText && (
          <button type="button" className={compact ? buttonClass : 'btn-primary'} onClick={() => void onCopy()}>
            {copied ? <Check className="h-4 w-4" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
            {copied ? 'Copied' : 'Copy lyrics'}
          </button>
        )}
        {formats.map((format) => (
          <button
            key={format}
            type="button"
            className={buttonClass}
            disabled={busy !== null}
            onClick={() => void onDownload(format)}
            aria-label={`Download ${format.toUpperCase()}`}
          >
            {busy === format ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Download className="h-4 w-4" aria-hidden="true" />
            )}
            {format.toUpperCase()}
          </button>
        ))}
      </div>
      <span className="sr-only" role="status" aria-live="polite">
        {copied ? 'Lyrics copied to clipboard.' : ''}
      </span>
      {error && <Alert className="mt-3">{error}</Alert>}
    </div>
  );
}
