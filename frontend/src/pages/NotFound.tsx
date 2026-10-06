import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="container-page max-w-2xl py-16 text-center">
      <p className="text-sm text-violet-300">404</p>
      <h1 className="mt-2 text-3xl">This page doesn't exist</h1>
      <p className="muted mt-2">The link may be out of date. Head home or start a new transcription.</p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Link to="/" className="btn-secondary">
          Home
        </Link>
        <Link to="/upload" className="btn-primary">
          Generate Lyrics
        </Link>
      </div>
    </div>
  );
}
