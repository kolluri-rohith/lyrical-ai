import type { Language } from '../types';
import { DEFAULT_CONFIG } from './file';

export const AUTO_LANGUAGE: Language = { code: 'auto', name: 'Auto Detect', nativeName: 'Auto' };

/** Display name for a language code, falling back to the code itself for unknown languages. */
export function languageName(
  code: string | null | undefined,
  languages: Language[] = DEFAULT_CONFIG.languages,
): string {
  if (!code) return 'Unknown';
  if (code === AUTO_LANGUAGE.code) return AUTO_LANGUAGE.name;
  const match =
    languages.find((language) => language.code === code) ??
    DEFAULT_CONFIG.languages.find((language) => language.code === code);
  return match ? match.name : code.toUpperCase();
}
