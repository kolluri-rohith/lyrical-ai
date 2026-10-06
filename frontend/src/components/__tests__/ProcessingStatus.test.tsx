import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ProcessingStatus from '../ProcessingStatus';

// Scoped to the step list: the live-region announcement repeats the active label.
const stepFor = (label: RegExp) => within(screen.getByRole('list')).getByText(label).closest('li');

describe('ProcessingStatus', () => {
  it('hides the audio extraction step for audio uploads', () => {
    render(<ProcessingStatus status="PREPROCESSING" fileType="audio" />);
    expect(screen.queryByText(/extracting audio/i)).not.toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(7);
  });

  it('shows the audio extraction step for video uploads', () => {
    render(<ProcessingStatus status="EXTRACTING_AUDIO" fileType="video" />);
    expect(screen.getAllByRole('listitem')).toHaveLength(8);
    expect(stepFor(/extracting audio/i)).toHaveAttribute('aria-current', 'step');
  });

  it('marks earlier stages done, the backend stage active and later stages pending', () => {
    render(<ProcessingStatus status="SEPARATING_VOCALS" fileType="audio" />);
    expect(stepFor(/validating file/i)).toHaveAttribute('data-state', 'done');
    expect(stepFor(/preparing audio/i)).toHaveAttribute('data-state', 'done');
    expect(stepFor(/separating vocals/i)).toHaveAttribute('data-state', 'active');
    expect(stepFor(/transcribing lyrics/i)).toHaveAttribute('data-state', 'pending');
    expect(screen.getByRole('status')).toHaveTextContent('Step 4 of 7: Separating vocals');
  });

  it('shows a progress bar only while transcribing', () => {
    const { rerender } = render(
      <ProcessingStatus status="SEPARATING_VOCALS" fileType="audio" transcriptionProgress={42} />,
    );
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();

    rerender(<ProcessingStatus status="TRANSCRIBING" fileType="audio" transcriptionProgress={42} />);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '42');

    rerender(<ProcessingStatus status="TRANSCRIBING" fileType="audio" transcriptionProgress={null} />);
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('shows the queue position while queued', () => {
    render(<ProcessingStatus status="QUEUED" fileType="audio" queuePosition={2} />);
    expect(screen.getByText(/2 jobs are ahead of yours/i)).toBeInTheDocument();
  });

  it('marks every stage done when completed', () => {
    render(<ProcessingStatus status="COMPLETED" fileType="audio" />);
    for (const item of screen.getAllByRole('listitem')) {
      expect(item).toHaveAttribute('data-state', 'done');
    }
  });
});
