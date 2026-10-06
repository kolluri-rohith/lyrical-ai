import { ArrowRight, Captions, Clock, Download, Languages, MicVocal, Video, type LucideIcon } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import HowItWorksSteps from '../components/HowItWorksSteps';
import UploadDropzone from '../components/UploadDropzone';
import { useConfig } from '../hooks/useConfig';
import { usePendingFile } from '../hooks/usePendingFile';
import { formatExtensions } from '../utils/file';

const FEATURES: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: MicVocal, title: 'Vocal separation', text: 'Instruments are removed before transcription, so lyrics come out cleaner.' },
  { icon: Languages, title: 'Multilingual', text: 'English, Hindi and Telugu, with automatic language detection.' },
  { icon: Video, title: 'Audio and video', text: 'Upload a music video directly; the audio is extracted for you.' },
  { icon: Captions, title: 'Synced lyrics', text: 'Each line is timestamped and highlights as the song plays.' },
  { icon: Download, title: 'TXT and SRT export', text: 'Copy the lyrics or download subtitle-ready files.' },
  { icon: Clock, title: 'History', text: 'Come back to earlier transcriptions whenever you need them.' },
];

export default function Home() {
  const config = useConfig();
  const navigate = useNavigate();
  const { setFile } = usePendingFile();

  const onFileSelected = (file: File) => {
    setFile(file);
    navigate('/upload');
  };

  return (
    <>
      <section className="relative overflow-hidden border-b border-ink-700">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-[28rem] bg-[radial-gradient(ellipse_at_top,rgba(139,92,246,0.18),transparent_65%)]"
        />
        <div className="container-page relative py-14 sm:py-20">
          <div className="mx-auto max-w-2xl text-center">
            <p className="chip mx-auto">Demucs + Whisper · runs on your own server</p>
            <h1 className="mt-5 text-4xl sm:text-5xl">Turn any song into timestamped lyrics</h1>
            <p className="mx-auto mt-4 max-w-xl text-base text-slate-300 sm:text-lg">
              Upload a song or music video. LyricalAI separates the vocals, transcribes them in English, Hindi or
              Telugu, and gives you lyrics that follow the music.
            </p>
            <div className="mt-7 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:items-center">
              <Link to="/upload" className="btn-primary px-6">
                Generate Lyrics
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link to="/about" className="btn-secondary px-6">
                How it works
              </Link>
            </div>
          </div>

          <div className="mx-auto mt-10 max-w-2xl">
            <UploadDropzone config={config} onFileSelected={onFileSelected} />
          </div>
        </div>
      </section>

      <section aria-labelledby="supported-heading" className="container-page py-12">
        <h2 id="supported-heading" className="text-2xl">
          What you can upload
        </h2>
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <div className="card p-5">
            <h3 className="text-sm">Languages</h3>
            <ul className="mt-3 flex flex-wrap gap-2">
              {config.languages.map((language) => (
                <li key={language.code} className="chip">
                  {language.name}
                  {language.nativeName !== language.name && (
                    <span className="text-slate-400" lang={language.code}>
                      {language.nativeName}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
          <div className="card p-5">
            <h3 className="text-sm">Audio files</h3>
            <p className="mt-3 text-sm text-slate-300">{formatExtensions(config.audioExtensions)}</p>
            <p className="muted mt-1">Up to {config.maxFileSizeMb} MB</p>
          </div>
          <div className="card p-5">
            <h3 className="text-sm">Video files</h3>
            <p className="mt-3 text-sm text-slate-300">{formatExtensions(config.videoExtensions)}</p>
            <p className="muted mt-1">Audio is extracted automatically</p>
          </div>
        </div>
      </section>

      <section aria-labelledby="how-heading" className="container-page py-12">
        <h2 id="how-heading" className="text-2xl">
          How it works
        </h2>
        <div className="mt-5">
          <HowItWorksSteps />
        </div>
      </section>

      <section aria-labelledby="features-heading" className="container-page py-12">
        <h2 id="features-heading" className="text-2xl">
          Features
        </h2>
        <ul className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <li key={feature.title} className="card p-5">
              <feature.icon className="h-5 w-5 text-violet-300" aria-hidden="true" />
              <h3 className="mt-3 text-sm">{feature.title}</h3>
              <p className="muted mt-1">{feature.text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="container-page pt-6">
        <div className="card flex flex-col items-start gap-4 bg-gradient-to-br from-ink-900 to-ink-800 p-6 sm:flex-row sm:items-center sm:justify-between sm:p-8">
          <div>
            <h2 className="text-xl">Ready to try it with your own song?</h2>
            <p className="muted mt-1">No account needed. Your history stays with this browser.</p>
          </div>
          <Link to="/upload" className="btn-primary w-full px-6 sm:w-auto">
            Generate Lyrics
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      </section>
    </>
  );
}
