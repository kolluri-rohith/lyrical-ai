import { forwardRef, useImperativeHandle, useRef, useState } from 'react';
import type { FileType } from '../types';
import Alert from './Alert';

export interface MediaPlayerHandle {
  /** Jump to a position (seconds) and start playing. */
  seek: (seconds: number) => void;
}

interface MediaPlayerProps {
  src: string;
  fileType: FileType;
  title: string;
  onTimeUpdate: (seconds: number) => void;
}

const MediaPlayer = forwardRef<MediaPlayerHandle, MediaPlayerProps>(function MediaPlayer(
  { src, fileType, title, onTimeUpdate },
  ref,
) {
  const mediaRef = useRef<HTMLMediaElement | null>(null);
  const [failed, setFailed] = useState(false);

  useImperativeHandle(ref, () => ({
    seek(seconds: number) {
      const media = mediaRef.current;
      if (!media) return;
      media.currentTime = seconds;
      onTimeUpdate(seconds);
      // Autoplay can be blocked until the user interacts with the player; that's fine.
      void media.play().catch(() => undefined);
    },
  }));

  if (failed) {
    return (
      <Alert tone="info">
        This file can't be played in your browser. The lyrics and downloads below still work.
      </Alert>
    );
  }

  const shared = {
    src,
    controls: true,
    preload: 'metadata' as const,
    'aria-label': `Player for ${title}`,
    onError: () => setFailed(true),
  };
  const report = (media: HTMLMediaElement) => onTimeUpdate(media.currentTime);

  return fileType === 'video' ? (
    <video
      {...shared}
      ref={(element) => {
        mediaRef.current = element;
      }}
      playsInline
      className="max-h-[50vh] w-full rounded-2xl bg-black"
      onTimeUpdate={(event) => report(event.currentTarget)}
      onSeeked={(event) => report(event.currentTarget)}
    />
  ) : (
    <audio
      {...shared}
      ref={(element) => {
        mediaRef.current = element;
      }}
      className="w-full"
      onTimeUpdate={(event) => report(event.currentTarget)}
      onSeeked={(event) => report(event.currentTarget)}
    />
  );
});

export default MediaPlayer;
