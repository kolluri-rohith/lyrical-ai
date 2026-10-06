import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import HowItWorksSteps from '../components/HowItWorksSteps';

const DETAILS = [
  {
    title: 'Why separate the vocals first?',
    text: 'Speech models are trained mostly on spoken audio. Drums, bass and guitars confuse them, so LyricalAI uses Demucs to split the song and sends only the vocal track to Whisper. If separation fails, the original audio is used instead and you are told that accuracy may be lower.',
  },
  {
    title: 'How is the language chosen?',
    text: 'With Auto Detect, Whisper listens to the vocals and picks the most likely of the supported languages. If you already know the language, selecting it guides the transcription and usually improves the result.',
  },
  {
    title: 'Where do the timestamps come from?',
    text: 'Every lyric line carries the start and end time Whisper produced for that segment. The same timings drive the highlighted line during playback and the SRT and VTT subtitle files.',
  },
  {
    title: 'What are the limits?',
    text: 'Lyrics are transcribed, not looked up, so fast rap, heavy effects, layered harmonies and mixed-language songs can contain mistakes. Nothing is invented to fill gaps. Processing runs on your own server and takes a few minutes per song on a CPU.',
  },
];

export default function About() {
  return (
    <div className="container-page py-10 sm:py-14">
      <h1 className="text-3xl">How it works</h1>
      <p className="mt-3 max-w-2xl text-slate-300">
        LyricalAI is an end-to-end lyric transcription pipeline. One upload goes through five stages, all running on
        open-source models with no paid AI service involved.
      </p>

      <div className="mt-8">
        <HowItWorksSteps />
      </div>

      <dl className="mt-10 grid gap-3 md:grid-cols-2">
        {DETAILS.map((detail) => (
          <div key={detail.title} className="card p-5">
            <dt className="font-medium text-white">{detail.title}</dt>
            <dd className="muted mt-2 leading-relaxed">{detail.text}</dd>
          </div>
        ))}
      </dl>

      <section aria-labelledby="stack-heading" className="mt-10">
        <h2 id="stack-heading" className="text-xl">
          Built with
        </h2>
        <ul className="mt-4 flex flex-wrap gap-2">
          {['React', 'TypeScript', 'Tailwind CSS', 'FastAPI', 'PyTorch', 'Whisper', 'Demucs', 'FFmpeg', 'PostgreSQL', 'Docker'].map(
            (name) => (
              <li key={name} className="chip">
                {name}
              </li>
            ),
          )}
        </ul>
      </section>

      <Link to="/upload" className="btn-primary mt-10 px-6">
        Generate Lyrics
        <ArrowRight className="h-4 w-4" aria-hidden="true" />
      </Link>
    </div>
  );
}
