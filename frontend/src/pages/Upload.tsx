import { Loader2, Sparkles } from 'lucide-react';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import Alert from '../components/Alert';
import FilePreview from '../components/FilePreview';
import LanguageSelector from '../components/LanguageSelector';
import UploadDropzone from '../components/UploadDropzone';
import { useConfig } from '../hooks/useConfig';
import { usePendingFile } from '../hooks/usePendingFile';
import { createTranscription, getErrorMessage } from '../services/api';
import type { LanguageCode } from '../types';
import { detectFileType } from '../utils/file';
import { AUTO_LANGUAGE } from '../utils/language';

export default function Upload() {
  const config = useConfig();
  const navigate = useNavigate();
  const { file, setFile } = usePendingFile();
  const [language, setLanguage] = useState<LanguageCode>(AUTO_LANGUAGE.code);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const fileType = file ? (detectFileType(file.name, config) ?? 'audio') : null;

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || uploading) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setUploading(true);
    setProgress(0);
    setError(null);
    try {
      const job = await createTranscription(file, language, setProgress, controller.signal);
      setFile(null);
      navigate(`/processing/${job.jobId}`);
    } catch (uploadError) {
      if (controller.signal.aborted) return;
      setError(getErrorMessage(uploadError, "The upload didn't go through. Please try again."));
      setUploading(false);
    }
  };

  const cancelUpload = () => {
    abortRef.current?.abort();
    setUploading(false);
    setProgress(0);
  };

  return (
    <div className="container-page max-w-2xl py-10 sm:py-14">
      <h1 className="text-3xl">Generate lyrics</h1>
      <p className="muted mt-2">
        Upload a song or music video, pick the language, and LyricalAI does the rest.
      </p>

      <form onSubmit={(event) => void onSubmit(event)} className="mt-8 space-y-6" noValidate>
        {file && fileType ? (
          <FilePreview file={file} fileType={fileType} onRemove={() => setFile(null)} disabled={uploading} />
        ) : (
          <UploadDropzone config={config} onFileSelected={setFile} />
        )}

        <LanguageSelector languages={config.languages} value={language} onChange={setLanguage} disabled={uploading} />

        {error && <Alert>{error}</Alert>}

        {uploading && (
          <div>
            <div className="mb-1.5 flex items-center justify-between text-sm">
              <span className="text-slate-200" role="status" aria-live="polite">
                {progress < 100 ? 'Uploading…' : 'Upload complete. Starting the job…'}
              </span>
              <span className="tabular-nums text-slate-300">{progress}%</span>
            </div>
            <div
              role="progressbar"
              aria-label="Upload progress"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress}
              className="h-2 overflow-hidden rounded-full bg-ink-600"
            >
              <div className="h-full rounded-full bg-violet-500 transition-[width]" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}

        <div className="flex flex-col gap-3 sm:flex-row">
          <button type="submit" className="btn-primary w-full px-6 sm:w-auto" disabled={!file || uploading}>
            {uploading ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Sparkles className="h-4 w-4" aria-hidden="true" />
            )}
            {uploading ? 'Uploading…' : 'Generate Lyrics'}
          </button>
          {uploading && (
            <button type="button" className="btn-secondary w-full sm:w-auto" onClick={cancelUpload}>
              Cancel
            </button>
          )}
        </div>

        {!file && <p className="muted">Choose a file to enable Generate Lyrics.</p>}
        <p className="muted">
          Songs up to about {config.maxDurationMinutes} minutes work best. Only upload music you have the right to
          use.
        </p>
      </form>
    </div>
  );
}
