import { Loader2, Plus } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import Alert from '../components/Alert';
import DownloadButtons from '../components/DownloadButtons';
import LyricsViewer from '../components/LyricsViewer';
import MediaPlayer, { type MediaPlayerHandle } from '../components/MediaPlayer';
import { useConfig } from '../hooks/useConfig';
import { fetchJob, getErrorMessage, getErrorStatus, mediaUrl } from '../services/api';
import type { JobDetail } from '../types';
import { languageName } from '../utils/language';
import { formatDuration } from '../utils/time';

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string; notFound: boolean }
  | { kind: 'ready'; job: JobDetail };

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="card px-4 py-3">
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className="mt-0.5 truncate text-sm font-medium text-white" title={value}>
        {value}
      </dd>
    </div>
  );
}

export default function Result() {
  const { jobId } = useParams<{ jobId: string }>();
  const config = useConfig();
  const playerRef = useRef<MediaPlayerHandle>(null);
  const [state, setState] = useState<LoadState>({ kind: 'loading' });
  const [currentTime, setCurrentTime] = useState<number | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    setState({ kind: 'loading' });
    setCurrentTime(null);
    fetchJob(jobId, controller.signal)
      .then((job) => setState({ kind: 'ready', job }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const notFound = getErrorStatus(error) === 404 || getErrorStatus(error) === 403;
        setState({
          kind: 'error',
          notFound,
          message: notFound
            ? "We couldn't find that transcription. It may have been deleted, or it belongs to a different browser or account."
            : getErrorMessage(error, "We couldn't load this transcription."),
        });
      });
    return () => controller.abort();
  }, [jobId, attempt]);

  if (state.kind === 'loading') {
    return (
      <div className="container-page py-14">
        <p className="muted flex items-center gap-2" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Loading lyrics…
        </p>
      </div>
    );
  }

  if (state.kind === 'error') {
    return (
      <div className="container-page max-w-2xl py-14">
        <h1 className="text-3xl">Lyrics unavailable</h1>
        <Alert className="mt-6">{state.message}</Alert>
        <div className="mt-6 flex flex-wrap gap-3">
          {!state.notFound && (
            <button type="button" className="btn-primary" onClick={() => setAttempt((value) => value + 1)}>
              Try again
            </button>
          )}
          <Link to="/upload" className={state.notFound ? 'btn-primary' : 'btn-secondary'}>
            New transcription
          </Link>
          <Link to="/history" className="btn-secondary">
            History
          </Link>
        </div>
      </div>
    );
  }

  const { job } = state;
  if (job.status !== 'COMPLETED') {
    // Still running (or failed): the processing page shows live status and the failure reason.
    return <Navigate to={`/processing/${job.jobId}`} replace />;
  }

  const hasPlayer = job.mediaAvailable;

  return (
    <div className="container-page py-10 sm:py-12">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm text-violet-300">Lyrics ready</p>
          <h1 className="mt-1 break-words text-2xl sm:text-3xl">{job.originalFilename}</h1>
        </div>
        <Link to="/upload" className="btn-secondary shrink-0">
          <Plus className="h-4 w-4" aria-hidden="true" />
          New transcription
        </Link>
      </div>

      <dl className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Fact label="Detected language" value={languageName(job.detectedLanguage, config.languages)} />
        <Fact label="Duration" value={formatDuration(job.duration)} />
        <Fact label="Model" value={[job.modelName, job.device].filter(Boolean).join(' · ') || '—'} />
        <Fact label="Processing time" value={formatDuration(job.processingTime)} />
      </dl>

      {job.warning && (
        <Alert tone="warning" className="mt-4">
          {job.warning}
        </Alert>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <section aria-labelledby="player-heading" className="lg:col-span-2">
          <h2 id="player-heading" className="text-lg">
            Playback
          </h2>
          <div className="mt-3 lg:sticky lg:top-20">
            {hasPlayer ? (
              <MediaPlayer
                ref={playerRef}
                src={mediaUrl(job.jobId)}
                fileType={job.fileType}
                title={job.originalFilename}
                onTimeUpdate={setCurrentTime}
              />
            ) : (
              <Alert tone="info">
                The original media is no longer available for playback. The lyrics and downloads still work.
              </Alert>
            )}
            <div className="mt-5">
              <DownloadButtons jobId={job.jobId} fullText={job.fullText} />
            </div>
          </div>
        </section>

        <section aria-labelledby="lyrics-heading" className="lg:col-span-3">
          <h2 id="lyrics-heading" className="text-lg">
            Lyrics
          </h2>
          {hasPlayer && job.segments.length > 0 && (
            <p className="muted mt-1">Select a line to play from that point.</p>
          )}
          <div className="mt-3">
            <LyricsViewer
              segments={job.segments}
              currentTime={currentTime}
              onSeek={hasPlayer ? (seconds) => playerRef.current?.seek(seconds) : undefined}
              lang={job.detectedLanguage ?? undefined}
            />
          </div>
        </section>
      </div>
    </div>
  );
}
