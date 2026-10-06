import { Loader2, Music } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Alert from '../components/Alert';
import HistoryCard from '../components/HistoryCard';
import { useAuth } from '../hooks/useAuth';
import { useConfig } from '../hooks/useConfig';
import { deleteJob, fetchJobs, getErrorMessage } from '../services/api';
import type { JobSummary } from '../types';

const PAGE_SIZE = 20;

export default function History() {
  const config = useConfig();
  const { user, loading: authLoading } = useAuth();
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const userId = user?.id ?? null;

  const loadFirstPage = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const page = await fetchJobs(PAGE_SIZE, 0, signal);
      setJobs(page.items);
      setTotal(page.total);
    } catch (loadError) {
      if (signal?.aborted) return;
      setError(getErrorMessage(loadError, "We couldn't load your history."));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  // Reload when the signed-in user changes: history is scoped to the account or to this browser.
  useEffect(() => {
    if (authLoading) return;
    const controller = new AbortController();
    void loadFirstPage(controller.signal);
    return () => controller.abort();
  }, [authLoading, userId, loadFirstPage]);

  const loadMore = async () => {
    setLoadingMore(true);
    setError(null);
    try {
      const page = await fetchJobs(PAGE_SIZE, jobs.length);
      setJobs((previous) => {
        const known = new Set(previous.map((job) => job.jobId));
        return [...previous, ...page.items.filter((job) => !known.has(job.jobId))];
      });
      setTotal(page.total);
    } catch (loadError) {
      setError(getErrorMessage(loadError, "We couldn't load more transcriptions."));
    } finally {
      setLoadingMore(false);
    }
  };

  const onDelete = async (jobId: string) => {
    setError(null);
    try {
      await deleteJob(jobId);
      setJobs((previous) => previous.filter((job) => job.jobId !== jobId));
      setTotal((previous) => Math.max(0, previous - 1));
    } catch (deleteError) {
      setError(getErrorMessage(deleteError, "We couldn't delete that transcription."));
    }
  };

  return (
    <div className="container-page max-w-3xl py-10 sm:py-14">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl">History</h1>
          <p className="muted mt-2">
            {user
              ? `Transcriptions saved to ${user.email}.`
              : 'Transcriptions made in this browser. Log in to keep them with your account.'}
          </p>
        </div>
        <Link to="/upload" className="btn-primary shrink-0">
          New transcription
        </Link>
      </div>

      {error && (
        <Alert className="mt-6">
          {error}{' '}
          {jobs.length === 0 && (
            <button type="button" className="rounded underline underline-offset-2" onClick={() => void loadFirstPage()}>
              Try again
            </button>
          )}
        </Alert>
      )}

      {loading ? (
        <p className="muted mt-8 flex items-center gap-2" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Loading history…
        </p>
      ) : jobs.length === 0 && !error ? (
        <div className="card mt-8 px-5 py-12 text-center">
          <Music className="mx-auto h-8 w-8 text-violet-300" aria-hidden="true" />
          <p className="mt-3 font-medium text-white">No transcriptions yet</p>
          <p className="muted mt-1">Upload a song and its lyrics will show up here.</p>
          <Link to="/upload" className="btn-primary mt-5">
            Generate Lyrics
          </Link>
        </div>
      ) : (
        <>
          <ul className="mt-8 space-y-3">
            {jobs.map((job) => (
              <li key={job.jobId}>
                <HistoryCard job={job} languages={config.languages} onDelete={onDelete} />
              </li>
            ))}
          </ul>
          {jobs.length < total && (
            <div className="mt-6 text-center">
              <button type="button" className="btn-secondary" onClick={() => void loadMore()} disabled={loadingMore}>
                {loadingMore && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
                Load more
              </button>
              <p className="muted mt-2">
                Showing {jobs.length} of {total}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
