import { AudioLines, Captions, FileMusic, MicVocal, UploadCloud, type LucideIcon } from 'lucide-react';

interface Step {
  icon: LucideIcon;
  title: string;
  text: string;
}

const STEPS: Step[] = [
  { icon: UploadCloud, title: 'Upload', text: 'Add a song or a music video. No conversion needed.' },
  { icon: FileMusic, title: 'Extract audio', text: 'FFmpeg pulls the soundtrack out of videos and normalises it.' },
  { icon: AudioLines, title: 'Separate vocals', text: 'Demucs isolates the singing from the instruments.' },
  { icon: MicVocal, title: 'AI transcription', text: 'Whisper detects the language and writes the lyrics.' },
  { icon: Captions, title: 'Timestamped lyrics', text: 'Read along with playback, copy, or download TXT and SRT.' },
];

export default function HowItWorksSteps() {
  return (
    <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {STEPS.map((step, index) => (
        <li key={step.title} className="card p-4">
          <div className="flex items-center gap-3 lg:flex-col lg:items-start">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-500/15">
              <step.icon className="h-5 w-5 text-violet-300" aria-hidden="true" />
            </span>
            <h3 className="text-sm">
              <span className="text-violet-300">{index + 1}.</span> {step.title}
            </h3>
          </div>
          <p className="muted mt-2">{step.text}</p>
        </li>
      ))}
    </ol>
  );
}
