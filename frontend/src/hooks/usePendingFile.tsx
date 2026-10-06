import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';

interface PendingFileValue {
  file: File | null;
  setFile: (file: File | null) => void;
}

const PendingFileContext = createContext<PendingFileValue | null>(null);

/** Carries a file picked on the Home page over to the Upload page. */
export function PendingFileProvider({ children }: { children: ReactNode }) {
  const [file, setFile] = useState<File | null>(null);
  const value = useMemo(() => ({ file, setFile }), [file]);
  return <PendingFileContext.Provider value={value}>{children}</PendingFileContext.Provider>;
}

export function usePendingFile(): PendingFileValue {
  const context = useContext(PendingFileContext);
  if (!context) throw new Error('usePendingFile must be used inside <PendingFileProvider>');
  return context;
}
