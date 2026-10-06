import { useEffect, useRef } from 'react';
import type { Segment } from '../types';
import { formatTimestamp } from '../utils/time';

interface LyricsViewerProps {
  segments: Segment[];
  /** Playback position in seconds; omit when there is no player. */
  currentTime?: number | null;
  onSeek?: (seconds: number) => void;
  /** BCP 47 code of the lyrics, so screen readers and fonts pick the right script. */
  lang?: string;
}

/** Index (in array order) of the segment being sung at `time`, or -1 between lines. */
export function findActiveSegment(segments: Segment[], time: number | null | undefined): number {
  if (time == null) return -1;
  return segments.findIndex((segment) => time >= segment.start && time < segment.end);
}

export default function LyricsViewer({ segments, currentTime = null, onSeek, lang }: LyricsViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLLIElement>(null);
  const activeIndex = findActiveSegment(segments, currentTime);

  // Keep the active line in view by scrolling the lyrics box only (never the page).
  useEffect(() => {
    const container = containerRef.current;
    const line = activeRef.current;
    if (activeIndex < 0 || !container || !line || typeof container.scrollTo !== 'function') return;
    const reduceMotion =
      typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const top = line.offsetTop - container.clientHeight / 2 + line.clientHeight / 2;
    container.scrollTo({ top: Math.max(0, top), behavior: reduceMotion ? 'auto' : 'smooth' });
  }, [activeIndex]);

  if (segments.length === 0) {
    return (
      <div className="card px-5 py-10 text-center">
        <p className="font-medium text-white">No lyrics were detected</p>
        <p className="muted mt-1">
          The track may be instrumental, or the vocals were too quiet to transcribe.
        </p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      role="region"
      aria-label="Timestamped lyrics"
      className="card relative max-h-[60vh] overflow-y-auto p-2 sm:max-h-[32rem]"
    >
      <ol lang={lang}>
        {segments.map((segment, position) => {
          const active = position === activeIndex;
          const rowClass = `flex w-full items-baseline gap-4 rounded-xl px-3 py-2.5 text-left transition-colors ${
            active ? 'bg-violet-500/15 text-white' : 'text-slate-300'
          }`;
          const content = (
            <>
              <span className={`shrink-0 text-xs tabular-nums ${active ? 'text-violet-300' : 'text-slate-500'}`}>
                {formatTimestamp(segment.start)}
              </span>
              <span className={`min-w-0 break-words leading-relaxed ${active ? 'font-medium' : ''}`}>
                {segment.text}
              </span>
            </>
          );
          return (
            <li
              key={`${segment.index}-${segment.start}`}
              ref={active ? activeRef : undefined}
              aria-current={active ? 'true' : undefined}
            >
              {onSeek ? (
                <button
                  type="button"
                  className={`${rowClass} hover:bg-ink-800`}
                  onClick={() => onSeek(segment.start)}
                  title={`Play from ${formatTimestamp(segment.start)}`}
                >
                  {content}
                </button>
              ) : (
                <div className={rowClass}>{content}</div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
