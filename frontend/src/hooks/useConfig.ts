import { useEffect, useState } from 'react';
import { fetchConfig } from '../services/api';
import type { AppConfig } from '../types';
import { DEFAULT_CONFIG } from '../utils/file';

let cached: AppConfig | null = null;
let pending: Promise<AppConfig> | null = null;

function isValidConfig(value: unknown): value is AppConfig {
  if (!value || typeof value !== 'object') return false;
  const config = value as Partial<AppConfig>;
  return (
    typeof config.maxFileSizeMb === 'number' &&
    Array.isArray(config.languages) &&
    Array.isArray(config.audioExtensions) &&
    Array.isArray(config.videoExtensions)
  );
}

function loadConfig(): Promise<AppConfig> {
  if (!pending) {
    pending = fetchConfig()
      .then((config) => {
        if (!isValidConfig(config)) return DEFAULT_CONFIG;
        cached = {
          ...DEFAULT_CONFIG,
          ...config,
          audioExtensions: config.audioExtensions.map((ext) => ext.toLowerCase()),
          videoExtensions: config.videoExtensions.map((ext) => ext.toLowerCase()),
        };
        return cached;
      })
      .catch(() => {
        pending = null; // allow a retry on the next mount
        return DEFAULT_CONFIG;
      });
  }
  return pending;
}

/** Server limits and languages, with built-in defaults until (or unless) the API answers. */
export function useConfig(): AppConfig {
  const [config, setConfig] = useState<AppConfig>(cached ?? DEFAULT_CONFIG);

  useEffect(() => {
    if (cached) return;
    let active = true;
    void loadConfig().then((loaded) => {
      if (active) setConfig(loaded);
    });
    return () => {
      active = false;
    };
  }, []);

  return config;
}
