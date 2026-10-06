import { FileAudio, FileVideo, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { FileType } from '../types';
import { formatBytes } from '../utils/file';

interface FilePreviewProps {
  file: File;
  fileType: FileType;
  onRemove: () => void;
  disabled?: boolean;
}

export default function FilePreview({ file, fileType, onRemove, disabled = false }: FilePreviewProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewFailed, setPreviewFailed] = useState(false);

  useEffect(() => {
    setPreviewFailed(false);
    if (typeof URL.createObjectURL !== 'function') return;
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const Icon = fileType === 'video' ? FileVideo : FileAudio;

  return (
    <div className="card p-4">
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-violet-500/15">
          <Icon className="h-5 w-5 text-violet-300" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-white" title={file.name}>
            {file.name}
          </p>
          <p className="muted">
            {fileType === 'video' ? 'Video' : 'Audio'} · {formatBytes(file.size)}
          </p>
        </div>
        <button
          type="button"
          onClick={onRemove}
          disabled={disabled}
          className="btn-ghost px-3"
          aria-label={`Remove ${file.name}`}
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      {previewUrl && !previewFailed && (
        <div className="mt-4">
          {fileType === 'video' ? (
            <video
              src={previewUrl}
              controls
              playsInline
              preload="metadata"
              className="max-h-64 w-full rounded-xl bg-black"
              onError={() => setPreviewFailed(true)}
            />
          ) : (
            <audio
              src={previewUrl}
              controls
              preload="metadata"
              className="w-full"
              onError={() => setPreviewFailed(true)}
            />
          )}
        </div>
      )}
      {previewFailed && (
        <p className="muted mt-3">Your browser can't preview this format, but it can still be transcribed.</p>
      )}
    </div>
  );
}
