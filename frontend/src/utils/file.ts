import type { AppConfig, FileType } from '../types';

export const DEFAULT_CONFIG: AppConfig = {
  maxFileSizeMb: 50,
  maxDurationMinutes: 15,
  languages: [
    { code: 'en', name: 'English', nativeName: 'English' },
    { code: 'hi', name: 'Hindi', nativeName: 'हिन्दी' },
    { code: 'te', name: 'Telugu', nativeName: 'తెలుగు' },
  ],
  audioExtensions: ['.mp3', '.wav', '.m4a', '.aac', '.flac'],
  videoExtensions: ['.mp4', '.mov', '.mkv'],
};

export type FileValidation = { ok: true; fileType: FileType } | { ok: false; message: string };

type FileRules = Pick<AppConfig, 'maxFileSizeMb' | 'audioExtensions' | 'videoExtensions'>;

export function getExtension(filename: string): string {
  const dot = filename.lastIndexOf('.');
  return dot <= 0 ? '' : filename.slice(dot).toLowerCase();
}

export function formatExtensions(extensions: string[]): string {
  return extensions.map((ext) => ext.replace('.', '').toUpperCase()).join(', ');
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 KB';
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function detectFileType(filename: string, rules: FileRules): FileType | null {
  const extension = getExtension(filename);
  if (rules.audioExtensions.includes(extension)) return 'audio';
  if (rules.videoExtensions.includes(extension)) return 'video';
  return null;
}

/** Client-side pre-check; the backend validates again and is the source of truth. */
export function validateFile(file: File, rules: FileRules): FileValidation {
  const fileType = detectFileType(file.name, rules);
  if (!fileType) {
    return {
      ok: false,
      message: `That file type isn't supported. Choose an audio file (${formatExtensions(
        rules.audioExtensions,
      )}) or a video file (${formatExtensions(rules.videoExtensions)}).`,
    };
  }
  if (file.size === 0) {
    return { ok: false, message: 'That file is empty. Choose a different file.' };
  }
  if (file.size > rules.maxFileSizeMb * 1024 * 1024) {
    return {
      ok: false,
      message: `That file is ${formatBytes(file.size)}. The limit is ${rules.maxFileSizeMb} MB — try a shorter or more compressed file.`,
    };
  }
  return { ok: true, fileType };
}
