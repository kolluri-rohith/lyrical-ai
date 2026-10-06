import { Loader2 } from 'lucide-react';
import { useEffect } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Alert from '../components/Alert';
import ProcessingStatus from '../components/ProcessingStatus';
import { useConfig } from '../hooks/useConfig';
import { useJobStatus } from '../hooks/useJobStatus';
import { languageName } from '../utils/language';

export default function Processing() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const config = useConfig();
  const { data, connectionError, notFound } = useJobStatus(jobId);

  useEffect(() => {
    if (data?.status === 'COMPLETED') navigate(`/result/${data.jobId}`, { replace: true });
  }, [data?.status, data?.jobId, navigate]);

  if (notFound) {
    return (
      <div className="container-page max-w-2xl py-14">
        <h1 className="text-3xl">We couldn't find that job</h1>
        <p className="muted mt-2">
          It may have been deleted, or it was started from a different browser or account.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/upload" className="btn-primary">
            New transcription
          </Link>
          <Link to="/history" className="btn-secondary">
            History
          </Link>
        </div>
      </div>
    );
  }

  const failed = data?.status === 'FAILED';

  return (
    <div className="container-page max-w-2xl py-10 sm:py-14">
      <h1 className="text-3xl">{failed ? "We couldn't transcribe this file" : 'Transcribing your song'}</h1>
      {!failed && (
        <p className="muted mt-2">
          This page updates as each step finishes. On a CPU a full song takes a few minutes, and the very first run
          takes longer while the AI models download. You can leave this page and come back from History.
        </p>
      )}

      {connectionError && !failed && (
        <Alert tone="warning" className="mt-6">
          {connectionError} Still trying…
        </Alert>
      )}

      {!data && !connectionError && (
        <p className="muted mt-8 flex items-center gap-2" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Checking on your job…
        </p>
      )}

      {data && failed && (
        <>
          <Alert className="mt-6">
            {data.errorMessage ?? 'Something went wrong while processing this file.'}
          </Alert>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/upload" className="btn-primary">
              Try again
            </Link>
            <Link to="/history" className="btn-secondary">
              History
            </Link>
          </div>
        </>
      )}

      {data && !failed && (
        <div className="card mt-8 p-3 sm:p-5">
          <ProcessingStatus
            status={data.status}
            fileType={data.fileType}
            transcriptionProgress={data.transcriptionProgress}
            queuePosition={data.queuePosition}
          />
        </div>
      )}

      {data && !failed && data.detectedLanguage && (
        <p className="muted mt-4">
          Detected language:{' '}
          <span className="text-slate-200">{languageName(data.detectedLanguage, config.languages)}</span>
        </p>
      )}

      {data && !failed && data.warning && (
        <Alert tone="warning" className="mt-4">
          {data.warning}
        </Alert>
      )}
    </div>
  );
}
