import { UploadCloud } from 'lucide-react';
import { useId, useState, type ChangeEvent, type DragEvent } from 'react';
import type { AppConfig } from '../types';
import { formatExtensions, validateFile } from '../utils/file';
import Alert from './Alert';

interface UploadDropzoneProps {
  config: Pick<AppConfig, 'maxFileSizeMb' | 'audioExtensions' | 'videoExtensions'>;
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export default function UploadDropzone({ config, onFileSelected, disabled = false }: UploadDropzoneProps) {
  const id = useId();
  const inputId = `${id}-input`;
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = (file: File | undefined) => {
    if (!file || disabled) return;
    const result = validateFile(file, config);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    setError(null);
    onFileSelected(file);
  };

  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    handleFile(event.target.files?.[0]);
    event.target.value = ''; // let the same file be picked again after an error
  };

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(false);
    handleFile(event.dataTransfer.files?.[0]);
  };

  const onDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    if (!disabled) setDragging(true);
  };

  const accept = [...config.audioExtensions, ...config.videoExtensions, 'audio/*', 'video/*'].join(',');

  return (
    <div>
      {/* The whole zone is the file input's label: click, tap, drop, or focus + Enter/Space all work. */}
      <label
        htmlFor={inputId}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={() => setDragging(false)}
        className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-5 py-10 text-center transition-colors focus-within:ring-2 focus-within:ring-violet-400 focus-within:ring-offset-2 focus-within:ring-offset-ink-950 sm:py-14 ${
          dragging ? 'border-violet-400 bg-violet-500/10' : 'border-ink-600 bg-ink-900 hover:border-violet-500/60'
        } ${disabled ? 'pointer-events-none opacity-50' : ''}`}
      >
        <input
          id={inputId}
          type="file"
          className="sr-only"
          accept={accept}
          disabled={disabled}
          onChange={onChange}
          aria-describedby={error ? `${hintId} ${errorId}` : hintId}
          aria-invalid={error ? true : undefined}
        />
        <span className="flex h-14 w-14 items-center justify-center rounded-full bg-violet-500/15">
          <UploadCloud className="h-7 w-7 text-violet-300" aria-hidden="true" />
        </span>
        <span className="text-base font-medium text-white">
          <span className="hidden sm:inline">Drop a song or video here, or </span>
          <span className="text-violet-300 underline underline-offset-4">
            <span className="sm:hidden">Choose a song or video</span>
            <span className="hidden sm:inline">browse files</span>
          </span>
        </span>
        <span id={hintId} className="muted max-w-md">
          Audio: {formatExtensions(config.audioExtensions)} · Video: {formatExtensions(config.videoExtensions)} · up
          to {config.maxFileSizeMb} MB
        </span>
      </label>

      {error && (
        <Alert id={errorId} className="mt-3">
          {error}
        </Alert>
      )}
    </div>
  );
}
