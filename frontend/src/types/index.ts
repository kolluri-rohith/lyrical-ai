export const JOB_STATUSES = [
  'QUEUED',
  'VALIDATING',
  'EXTRACTING_AUDIO',
  'PREPROCESSING',
  'SEPARATING_VOCALS',
  'DETECTING_LANGUAGE',
  'TRANSCRIBING',
  'POST_PROCESSING',
  'COMPLETED',
  'FAILED',
] as const;

export type JobStatus = (typeof JOB_STATUSES)[number];
export type FileType = 'audio' | 'video';
export type DownloadFormat = 'txt' | 'srt' | 'vtt';

/** "auto" or a language code returned by GET /config. */
export type LanguageCode = string;

export interface Language {
  code: string;
  name: string;
  nativeName: string;
}

export interface AppConfig {
  maxFileSizeMb: number;
  maxDurationMinutes: number;
  languages: Language[];
  audioExtensions: string[];
  videoExtensions: string[];
}

export interface HealthResponse {
  status: string;
  version: string;
  database: string;
  ffmpeg: boolean;
  device: string;
  whisperModel: string;
  modelsLoaded: { whisper: boolean; demucs: boolean };
}

export interface CreateJobResponse {
  jobId: string;
  status: JobStatus;
  createdAt: string;
}

export interface JobStatusResponse {
  jobId: string;
  status: JobStatus;
  fileType: FileType;
  transcriptionProgress: number | null;
  queuePosition: number | null;
  detectedLanguage: string | null;
  warning: string | null;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface Segment {
  index: number;
  start: number;
  end: number;
  text: string;
}

interface JobBase {
  jobId: string;
  originalFilename: string;
  fileType: FileType;
  fileSize: number;
  requestedLanguage: string;
  detectedLanguage: string | null;
  status: JobStatus;
  duration: number | null;
  createdAt: string;
  completedAt: string | null;
  errorMessage: string | null;
}

export interface JobSummary extends JobBase {
  preview: string | null;
}

export interface JobDetail extends JobBase {
  warning: string | null;
  mediaAvailable: boolean;
  fullText: string | null;
  modelName: string | null;
  processingTime: number | null;
  device: string | null;
  segments: Segment[];
}

export interface JobListResponse {
  items: JobSummary[];
  total: number;
}

export interface User {
  id: string | number;
  name: string;
  email: string;
  createdAt: string;
}

export interface AuthResponse {
  accessToken: string;
  tokenType: string;
  user: User;
}

export interface ApiErrorBody {
  detail?: unknown;
  code?: string;
}
