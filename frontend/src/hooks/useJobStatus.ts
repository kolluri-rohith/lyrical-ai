import { useEffect, useState } from 'react';
import { fetchJobStatus, getErrorMessage, getErrorStatus } from '../services/api';
import type { JobStatus, JobStatusResponse } from '../types';

const POLL_INTERVAL_MS = 2000;
const FAILURES_BEFORE_WARNING = 3;

export const isTerminalStatus = (status: JobStatus): boolean =>
  status === 'COMPLETED' || status === 'FAILED';

export interface JobStatusState {
  data: JobStatusResponse | null;
  /** Set when polling keeps failing; polling continues in the background. */
  connectionError: string | null;
  /** The job does not exist or belongs to someone else; polling has stopped. */
  notFound: boolean;
}

/** Polls the job status until it reaches COMPLETED or FAILED. */
export function useJobStatus(jobId: string | undefined): JobStatusState {
  const [state, setState] = useState<JobStatusState>({
    data: null,
    connectionError: null,
    notFound: false,
  });

  useEffect(() => {
    if (!jobId) return;
    setState({ data: null, connectionError: null, notFound: false });

    const controller = new AbortController();
    let timer: number | undefined;
    let failures = 0;

    const poll = async (): Promise<void> => {
      try {
        const data = await fetchJobStatus(jobId, controller.signal);
        failures = 0;
        setState({ data, connectionError: null, notFound: false });
        if (isTerminalStatus(data.status)) return;
      } catch (error) {
        if (controller.signal.aborted) return;
        const status = getErrorStatus(error);
        if (status === 404 || status === 403) {
          setState((previous) => ({ ...previous, notFound: true }));
          return;
        }
        failures += 1;
        if (failures >= FAILURES_BEFORE_WARNING) {
          const message = getErrorMessage(error, "We're having trouble checking on your job.");
          setState((previous) => ({ ...previous, connectionError: message }));
        }
      }
      timer = window.setTimeout(() => void poll(), POLL_INTERVAL_MS);
    };

    void poll();

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [jobId]);

  return state;
}
