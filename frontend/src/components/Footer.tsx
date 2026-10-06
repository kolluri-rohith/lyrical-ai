import { Link } from 'react-router-dom';
import Logo from './Logo';

export default function Footer() {
  return (
    <footer className="mt-16 border-t border-ink-700">
      <div className="container-page flex flex-col gap-4 py-8 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Logo className="text-base" />
          <p className="muted mt-2 max-w-sm">
            Multilingual lyric transcription with Demucs vocal separation and Whisper.
          </p>
        </div>
        <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-300">
          <Link to="/upload" className="rounded hover:text-white">
            Upload
          </Link>
          <Link to="/history" className="rounded hover:text-white">
            History
          </Link>
          <Link to="/about" className="rounded hover:text-white">
            How it works
          </Link>
        </nav>
      </div>
    </footer>
  );
}
