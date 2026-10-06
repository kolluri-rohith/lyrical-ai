import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DEFAULT_CONFIG, validateFile } from '../../utils/file';
import UploadDropzone from '../UploadDropzone';

const config = { ...DEFAULT_CONFIG, maxFileSizeMb: 1 };

function makeFile(name: string, sizeBytes: number, type = 'audio/mpeg'): File {
  return new File([new Uint8Array(sizeBytes)], name, { type });
}

function renderDropzone() {
  const onFileSelected = vi.fn();
  // applyAccept:false lets the test hand over files the picker would normally filter out.
  const user = userEvent.setup({ applyAccept: false });
  render(<UploadDropzone config={config} onFileSelected={onFileSelected} />);
  const input = screen.getByLabelText(/song or video/i);
  return { onFileSelected, user, input };
}

describe('validateFile', () => {
  it('accepts supported audio and video extensions regardless of case', () => {
    expect(validateFile(makeFile('Song.MP3', 10), config)).toEqual({ ok: true, fileType: 'audio' });
    expect(validateFile(makeFile('clip.mp4', 10, 'video/mp4'), config)).toEqual({ ok: true, fileType: 'video' });
  });

  it('rejects unsupported, empty and oversized files', () => {
    expect(validateFile(makeFile('notes.pdf', 10, 'application/pdf'), config).ok).toBe(false);
    expect(validateFile(makeFile('noextension', 10), config).ok).toBe(false);
    expect(validateFile(makeFile('empty.mp3', 0), config).ok).toBe(false);
    expect(validateFile(makeFile('big.wav', 1024 * 1024 + 1), config).ok).toBe(false);
  });
});

describe('UploadDropzone', () => {
  it('shows the supported formats and size limit', () => {
    renderDropzone();
    expect(screen.getByText(/MP3, WAV, M4A, AAC, FLAC/)).toBeInTheDocument();
    expect(screen.getByText(/up to 1 MB/)).toBeInTheDocument();
  });

  it('passes a valid file to onFileSelected', async () => {
    const { onFileSelected, user, input } = renderDropzone();
    const file = makeFile('song.mp3', 2048);
    await user.upload(input, file);
    expect(onFileSelected).toHaveBeenCalledTimes(1);
    expect(onFileSelected).toHaveBeenCalledWith(file);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('rejects an unsupported file type with a friendly message', async () => {
    const { onFileSelected, user, input } = renderDropzone();
    await user.upload(input, makeFile('document.pdf', 2048, 'application/pdf'));
    expect(onFileSelected).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(/isn't supported/i);
  });

  it('rejects a file over the size limit', async () => {
    const { onFileSelected, user, input } = renderDropzone();
    await user.upload(input, makeFile('long.mp3', 2 * 1024 * 1024));
    expect(onFileSelected).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(/limit is 1 MB/i);
  });
});
