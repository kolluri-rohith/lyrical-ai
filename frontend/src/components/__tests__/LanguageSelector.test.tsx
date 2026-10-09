import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DEFAULT_CONFIG } from '../../utils/file';
import LanguageSelector from '../LanguageSelector';

describe('LanguageSelector', () => {
  it('offers Auto Detect plus every configured language', () => {
    render(<LanguageSelector languages={DEFAULT_CONFIG.languages} value="auto" onChange={() => undefined} />);
    expect(screen.getByRole('group', { name: /select lyrics language/i })).toBeInTheDocument();
    expect(screen.getAllByRole('radio')).toHaveLength(4);
    expect(screen.getByRole('radio', { name: /auto detect/i })).toBeChecked();
    expect(screen.getByRole('radio', { name: /english/i })).not.toBeChecked();
    expect(screen.getByRole('radio', { name: /hindi/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /telugu/i })).toBeInTheDocument();
  });

  it('reports the chosen language code', async () => {
    const onChange = vi.fn();
    render(<LanguageSelector languages={DEFAULT_CONFIG.languages} value="auto" onChange={onChange} />);
    await userEvent.click(screen.getByRole('radio', { name: /telugu/i }));
    expect(onChange).toHaveBeenCalledWith('te');
  });

  it('reflects the selected value', () => {
    render(<LanguageSelector languages={DEFAULT_CONFIG.languages} value="hi" onChange={() => undefined} />);
    expect(screen.getByRole('radio', { name: /hindi/i })).toBeChecked();
    expect(screen.getByRole('radio', { name: /auto detect/i })).not.toBeChecked();
  });
});
