import { Check, Circle, Loader2 } from 'lucide-react';
import type { FileType, JobStatus } from '../types';

interface Stage {
  status: JobStatus;
  label: string;
  description: string;
  videoOnly?: boolean;
}

export const STAGES: Stage[] = [
  { status: 'QUEUED', label: 'Queued', description: 'Waiting for the processor to pick up your file.' },
  { status: 'VALIDATING', label: 'Validating file', description: 'Checking the media is readable.' },
  {
    status: 'EXTRACTING_AUDIO',
    label: 'Extracting audio',
    description: 'Pulling the soundtrack out of your video with FFmpeg.',
    videoOnly: true,
  },
  { status: 'PREPROCESSING', label: 'Preparing audio', description: 'Converting and normalising the audio.' },
  {
    status: 'SEPARATING_VOCALS',
    label: 'Separating vocals',
    description: 'Demucs isolates the singing from the instruments.',
  },
  { status: 'DETECTING_LANGUAGE', label: 'Detecting language', description: 'Working out which language is sung.' },
  { status: 'TRANSCRIBING', label: 'Transcribing lyrics', description: 'Whisper writes out the lyrics with timestamps.' },
  { status: 'POST_PROCESSING', label: 'Cleaning up lyrics', description: 'Tidying lines and saving the result.' },
];

interface ProcessingStatusProps {
  status: JobStatus;
  fileType: FileType;
  transcriptionProgress?: number | null;
  queuePosition?: number | null;
}

type StepState = 'done' | 'active' | 'pending';

function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, Math.round(value)));
}

export default function ProcessingStatus({
  status,
  fileType,
  transcriptionProgress = null,
  queuePosition = null,
}: ProcessingStatusProps) {
  const stages = STAGES.filter((stage) => !stage.videoOnly || fileType === 'video');
  const activeIndex = stages.findIndex((stage) => stage.status === status);
  const activeStage = activeIndex >= 0 ? stages[activeIndex] : null;

  const stateOf = (index: number): StepState => {
    if (status === 'COMPLETED') return 'done';
    if (activeIndex < 0) return 'pending'; // FAILED: the failing stage is unknown, so claim nothing
    if (index < activeIndex) return 'done';
    return index === activeIndex ? 'active' : 'pending';
  };

  const announcement =
    status === 'COMPLETED'
      ? 'Processing complete.'
      : status === 'FAILED'
        ? 'Processing failed.'
        : `Step ${activeIndex + 1} of ${stages.length}: ${activeStage?.label ?? ''}`;

  return (
    <div>
      <p className="sr-only" role="status" aria-live="polite">
        {announcement}
      </p>
      <ol className="space-y-1">
        {stages.map((stage, index) => {
          const state = stateOf(index);
          const showProgress =
            state === 'active' && stage.status === 'TRANSCRIBING' && transcriptionProgress != null;
          const showQueue =
            state === 'active' && stage.status === 'QUEUED' && queuePosition != null && queuePosition > 0;
          return (
            <li
              key={stage.status}
              data-state={state}
              aria-current={state === 'active' ? 'step' : undefined}
              className={`flex items-start gap-3 rounded-xl px-3 py-2.5 ${state === 'active' ? 'bg-ink-800' : ''}`}
            >
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center">
                {state === 'done' && (
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-violet-600">
                    <Check className="h-3.5 w-3.5 text-white" aria-hidden="true" />
                  </span>
                )}
                {state === 'active' && <Loader2 className="h-5 w-5 animate-spin text-violet-300" aria-hidden="true" />}
                {state === 'pending' && <Circle className="h-4 w-4 text-ink-600" aria-hidden="true" />}
              </span>
              <div className="min-w-0 flex-1">
                <p className={`text-sm font-medium ${state === 'pending' ? 'text-slate-500' : 'text-white'}`}>
                  {stage.label}
                  <span className="sr-only">
                    {state === 'done' ? ' — done' : state === 'active' ? ' — in progress' : ' — waiting'}
                  </span>
                </p>
                {state === 'active' && <p className="muted mt-0.5">{stage.description}</p>}
                {showQueue && (
                  <p className="muted mt-0.5">
                    {queuePosition} {queuePosition === 1 ? 'job is' : 'jobs are'} ahead of yours.
                  </p>
                )}
                {showProgress && (
                  <div className="mt-2 flex items-center gap-3">
                    <div
                      role="progressbar"
                      aria-label="Transcription progress"
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={clampPercent(transcriptionProgress)}
                      className="h-2 flex-1 overflow-hidden rounded-full bg-ink-600"
                    >
                      <div
                        className="h-full rounded-full bg-violet-500 transition-[width] duration-500"
                        style={{ width: `${clampPercent(transcriptionProgress)}%` }}
                      />
                    </div>
                    <span className="w-10 text-right text-xs tabular-nums text-slate-300">
                      {clampPercent(transcriptionProgress)}%
                    </span>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
