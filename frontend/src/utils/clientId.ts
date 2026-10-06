import { readStored, removeStored, writeStored } from './storage';

const CLIENT_ID_KEY = 'lyricalai.clientId';
const TOKEN_KEY = 'lyricalai.token';

let memoryClientId: string | null = null;

function generateId(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
  } catch {
    /* fall through to the manual generator */
  }
  // RFC 4122 v4 layout for browsers without crypto.randomUUID (non-secure contexts).
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    const value = char === 'x' ? random : (random & 0x3) | 0x8;
    return value.toString(16);
  });
}

/** Stable anonymous id for this browser; scopes history for users who are not logged in. */
export function getClientId(): string {
  if (memoryClientId) return memoryClientId;
  const stored = readStored(CLIENT_ID_KEY);
  if (stored) {
    memoryClientId = stored;
    return stored;
  }
  const created = generateId();
  memoryClientId = created;
  writeStored(CLIENT_ID_KEY, created);
  return created;
}

export function getToken(): string | null {
  return readStored(TOKEN_KEY);
}

export function setToken(token: string): void {
  writeStored(TOKEN_KEY, token);
}

export function clearToken(): void {
  removeStored(TOKEN_KEY);
}
