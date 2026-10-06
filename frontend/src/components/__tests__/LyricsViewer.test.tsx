import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { Segment } from '../../types';
import LyricsViewer, { findActiveSegment } from '../LyricsViewer';

const segments: Segment[] = [
  { index: 0, start: 12.3, end: 17.2, text: 'First lyric line' },
  { index: 1, start: 17.2, end: 22.8, text: 'Second lyric line' },
  { index: 2, start: 75, end: 80, text: 'మూడవ పంక్తి' },
];

describe('findActiveSegment', () => {
  it('returns the segment containing the playback time, or -1 between lines', () => {
    expect(findActiveSegment(segments, null)).toBe(-1);
    expect(findActiveSegment(segments, 5)).toBe(-1);
    expect(findActiveSegment(segments, 12.3)).toBe(0);
    expect(findActiveSegment(segments, 17.2)).toBe(1);
    expect(findActiveSegment(segments, 40)).toBe(-1);
    expect(findActiveSegment(segments, 79.9)).toBe(2);
  });
});

describe('LyricsViewer', () => {
  it('renders every line with its mm:ss timestamp', () => {
    render(<LyricsViewer segments={segments} />);
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    expect(screen.getByText('00:12')).toBeInTheDocument();
    expect(screen.getByText('00:17')).toBeInTheDocument();
    expect(screen.getByText('01:15')).toBeInTheDocument();
    expect(screen.getByText('First lyric line')).toBeInTheDocument();
    expect(screen.getByText('మూడవ పంక్తి')).toBeInTheDocument();
  });

  it('highlights only the line for the current playback time', () => {
    const { rerender } = render(<LyricsViewer segments={segments} currentTime={13} />);
    const lineFor = (text: string) => screen.getByText(text).closest('li');

    expect(lineFor('First lyric line')).toHaveAttribute('aria-current', 'true');
    expect(lineFor('Second lyric line')).not.toHaveAttribute('aria-current');

    rerender(<LyricsViewer segments={segments} currentTime={18} />);
    expect(lineFor('First lyric line')).not.toHaveAttribute('aria-current');
    expect(lineFor('Second lyric line')).toHaveAttribute('aria-current', 'true');

    rerender(<LyricsViewer segments={segments} currentTime={40} />);
    expect(document.querySelector('[aria-current]')).toBeNull();
  });

  it('seeks to a line when it is selected', async () => {
    const onSeek = vi.fn();
    render(<LyricsViewer segments={segments} currentTime={0} onSeek={onSeek} />);
    await userEvent.click(screen.getByRole('button', { name: /second lyric line/i }));
    expect(onSeek).toHaveBeenCalledWith(17.2);
  });

  it('shows an empty state when nothing was transcribed', () => {
    render(<LyricsViewer segments={[]} />);
    expect(screen.getByText(/no lyrics were detected/i)).toBeInTheDocument();
  });
});
