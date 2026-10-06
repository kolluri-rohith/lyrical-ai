import { FileAudio, FileVideo, Loader2, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { JobStatus, JobSummary, Language } from '../types';
import { formatBytes } from '../utils/file';
import { languageName } from '../utils/language';
import { formatDate, formatDuration } from '../utils/time';
import DownloadButtons from './DownloadButtons';

interface HistoryCardProps {
  job: JobSummary;
  languages: Language[];
  onDelete: (jobId: string) => Promise<void>;
}

function statusBadge(status: JobStatus): { label: string; className: string } {
  if (status === 'COMPLETED') return { label: 'Completed', className: 'border-emerald-500/40 text-emerald-300' };
  if (status === 'FAILED') return { label: 'Failed', className: 'border-red-500/40 text-red-300' };
  if (status === 'QUEUED') return { label: 'Queued', className: 'border-ink-600 text-slate-300' };
  return { label: 'Processing', className: 'border-violet-500/40 text-violet-300' };
}

export default function HistoryCard({ job, languages, onDelete }: HistoryCardProps) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const badge = statusBadge(job.status);
  const Icon = job.fileType === 'video' ? FileVideo : FileAudio;
  const completed = job.status === 'COMPLETED';
  const failed = job.status === 'FAILED';
  const language = job.detectedLanguage ?? job.requestedLanguage;

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await onDelete(job.jobId);
    } finally {
      setDeleting(false);
      setConfirming(false);
    }
  };

  return (
    <article className="card p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-500/15">
          <Icon className="h-5 w-5 text-violet-300" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="min-w-0 truncate text-sm font-medium" title={job.originalFilename}>
              {job.originalFilename}
            </h3>
            <span className={`rounded-full border px-2 py-0.5 text-xs ${badge.className}`}>{badge.label}</span>
          </div>
          <p className="muted mt-1">
            {formatDate(job.createdAt)} · {languageName(language, languages)} · {formatBytes(job.fileSize)}
            {job.duration != null && ` · ${formatDuration(job.duration)}`}
          </p>
          {completed && job.preview && <p className="mt-2 line-clamp-2 text-sm text-slate-300">{job.preview}</p>}
          {failed && job.errorMessage && <p className="mt-2 text-sm text-red-200">{job.errorMessage}</p>}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {!failed && (
          <Link
            to={completed ? `/result/${job.jobId}` : `/processing/${job.jobId}`}
            className="btn-secondary min-h-[40px] px-3 py-2 text-xs"
          >
            {completed ? 'View lyrics' : 'View progress'}
          </Link>
        )}
        {completed && <DownloadButtons jobId={job.jobId} formats={['txt', 'srt']} compact />}

        <div className="ml-auto flex items-center gap-2">
          {confirming ? (
            <>
              <span className="text-xs text-slate-300">Delete this transcription?</span>
              <button
                type="button"
                className="btn-danger min-h-[40px] px-3 py-2 text-xs"
                onClick={() => void confirmDelete()}
                disabled={deleting}
              >
                {deleting && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
                Delete
              </button>
              <button
                type="button"
                className="btn-ghost min-h-[40px] px-3 py-2 text-xs"
                onClick={() => setConfirming(false)}
                disabled={deleting}
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              type="button"
              className="btn-ghost min-h-[40px] px-3 py-2 text-xs"
              onClick={() => setConfirming(true)}
              aria-label={`Delete ${job.originalFilename}`}
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
              Delete
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
