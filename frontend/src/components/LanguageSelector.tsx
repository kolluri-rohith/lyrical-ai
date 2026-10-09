import { useId } from 'react';
import type { Language, LanguageCode } from '../types';
import { AUTO_LANGUAGE } from '../utils/language';

interface LanguageSelectorProps {
  languages: Language[];
  value: LanguageCode;
  onChange: (code: LanguageCode) => void;
  disabled?: boolean;
}

export default function LanguageSelector({ languages, value, onChange, disabled = false }: LanguageSelectorProps) {
  const name = useId();
  const options = [AUTO_LANGUAGE, ...languages];

  return (
    <fieldset disabled={disabled}>
      <legend className="label">Select lyrics language</legend>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {options.map((language) => {
          const checked = value === language.code;
          const showNative = language.code !== AUTO_LANGUAGE.code && language.nativeName !== language.name;
          return (
            <label
              key={language.code}
              className={`flex min-h-[52px] cursor-pointer flex-col justify-center rounded-xl border px-3 py-2 text-sm transition-colors focus-within:ring-2 focus-within:ring-violet-400 focus-within:ring-offset-2 focus-within:ring-offset-ink-950 ${
                checked
                  ? 'border-violet-500 bg-violet-500/15 text-white'
                  : 'border-ink-600 bg-ink-800 text-slate-300 hover:border-ink-600 hover:bg-ink-700'
              } ${disabled ? 'cursor-not-allowed opacity-50' : ''}`}
            >
              <input
                type="radio"
                className="sr-only"
                name={name}
                value={language.code}
                checked={checked}
                onChange={() => onChange(language.code)}
              />
              <span className="font-medium">{language.name}</span>
              {showNative && (
                <span className="text-xs text-slate-400" lang={language.code}>
                  {language.nativeName}
                </span>
              )}
            </label>
          );
        })}
      </div>
      <p className="muted mt-2">
        Auto Detect picks the most likely language. Choosing the language yourself usually gives better lyrics.
      </p>
    </fieldset>
  );
}
