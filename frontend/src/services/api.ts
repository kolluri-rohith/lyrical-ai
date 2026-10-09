import axios, { AxiosError, type AxiosProgressEvent } from 'axios';
import type {
  ApiErrorBody,
  AppConfig,
  AuthResponse,
  CreateJobResponse,
  DownloadFormat,
  HealthResponse,
  JobDetail,
  JobListResponse,
  JobStatusResponse,
  LanguageCode,
  User,
} from '../types';
import { clearToken, getClientId, getToken } from '../utils/clientId';

export function resolveApiBase(value?: string): string {
  const raw = (value ?? '/api').trim();
  if (!raw || raw === '/') return '/api';

  const normalized = raw.replace(/\/+$/, '');
  if (normalized.endsWith('/api')) return normalized;
  if (normalized === '' || normalized === '/') return '/api';

  return `${normalized}/api`;
}

export const API_BASE = resolveApiBase(import.meta.env.VITE_API_BASE_URL);
export const UNAUTHORIZED_EVENT = 'lyricalai:unauthorized';

const GENERIC_ERROR = 'Something went wrong. Please try again.';
const NETWORK_ERROR = "Can't reach the server. Check your connection and try again.";

export const http = axios.create({ baseURL: API_BASE });

http.interceptors.request.use((config) => {
  config.headers.set('X-Client-Id', getClientId());
  const token = getToken();
  if (token) config.headers.set('Authorization', `Bearer ${token}`);
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    // A stored token the server no longer accepts: drop it so the app keeps
    // working anonymously instead of failing every request.
    if (axios.isAxiosError(error) && error.response?.status === 401 && getToken()) {
      const url = error.config?.url ?? '';
      if (!url.includes('/auth/login') && !url.includes('/auth/register')) {
        clearToken();
        window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
      }
    }
    return Promise.reject(error);
  },
);

/** Turns any thrown value into a message that is safe to show to users. */
export function getErrorMessage(error: unknown, fallback: string = GENERIC_ERROR): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorBody>;
    if (!axiosError.response) return NETWORK_ERROR;
    const detail = axiosError.response.data?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
  }
  return fallback;
}

export function getErrorStatus(error: unknown): number | null {
  return axios.isAxiosError(error) ? (error.response?.status ?? null) : null;
}

// ---- System ----

export async function fetchConfig(): Promise<AppConfig> {
  const { data } = await http.get<AppConfig>('/config');
  return data;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await http.get<HealthResponse>('/health');
  return data;
}

// ---- Transcriptions ----

export async function createTranscription(
  file: File,
  language: LanguageCode,
  onProgress?: (percent: number) => void,
  signal?: AbortSignal,
): Promise<CreateJobResponse> {
  const form = new FormData();
  form.append('file', file);
  form.append('language', language);
  const { data } = await http.post<CreateJobResponse>('/transcriptions', form, {
    signal,
    onUploadProgress: (event: AxiosProgressEvent) => {
      if (onProgress && event.total) {
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    },
  });
  return data;
}

export async function fetchJobStatus(jobId: string, signal?: AbortSignal): Promise<JobStatusResponse> {
  const { data } = await http.get<JobStatusResponse>(
    `/transcriptions/${encodeURIComponent(jobId)}/status`,
    { signal },
  );
  return data;
}

export async function fetchJob(jobId: string, signal?: AbortSignal): Promise<JobDetail> {
  const { data } = await http.get<JobDetail>(`/transcriptions/${encodeURIComponent(jobId)}`, {
    signal,
  });
  return data;
}

export async function fetchJobs(limit = 20, offset = 0, signal?: AbortSignal): Promise<JobListResponse> {
  const { data } = await http.get<JobListResponse>('/transcriptions', {
    params: { limit, offset },
    signal,
  });
  return data;
}

export async function deleteJob(jobId: string): Promise<void> {
  await http.delete(`/transcriptions/${encodeURIComponent(jobId)}`);
}

/** Direct URL for <audio>/<video>; this endpoint needs no auth headers. */
export function mediaUrl(jobId: string): string {
  return `${API_BASE}/transcriptions/${encodeURIComponent(jobId)}/media`;
}

export function parseContentDispositionFilename(header: unknown): string | null {
  if (typeof header !== 'string') return null;
  const encoded = /filename\*\s*=\s*(?:UTF-8'')?([^;]+)/i.exec(header);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1].trim().replace(/^"|"$/g, ''));
    } catch {
      /* fall back to the plain filename */
    }
  }
  const plain = /filename\s*=\s*("?)([^";]+)\1/i.exec(header);
  return plain ? plain[2].trim() : null;
}

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function downloadLyrics(
  jobId: string,
  format: DownloadFormat,
  options: { timestamps?: boolean } = {},
): Promise<void> {
  const response = await http.get<Blob>(
    `/transcriptions/${encodeURIComponent(jobId)}/download/${format}`,
    {
      responseType: 'blob',
      params: format === 'txt' && options.timestamps ? { timestamps: true } : undefined,
    },
  );
  const filename =
    parseContentDispositionFilename(response.headers['content-disposition']) ?? `lyrics.${format}`;
  saveBlob(response.data, filename);
}

// ---- Auth ----

export async function register(name: string, email: string, password: string): Promise<AuthResponse> {
  const { data } = await http.post<AuthResponse>('/auth/register', { name, email, password });
  return data;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const { data } = await http.post<AuthResponse>('/auth/login', { email, password });
  return data;
}

export async function fetchMe(): Promise<User> {
  const { data } = await http.get<User>('/auth/me');
  return data;
}
