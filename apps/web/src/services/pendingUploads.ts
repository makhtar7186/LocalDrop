// Envois en cours mémorisés localement, pour les reprendre après un rechargement de la
// page (FR-026). L'objet File est perdu au rechargement : l'utilisateur resélectionne
// le fichier, dont on vérifie le nom et la taille. Le SHA-256 global vérifié par le
// serveur garantit de toute façon qu'un fichier différent ne sera jamais publié.
// localStorage peut être indisponible : jamais bloquant.

const KEY = "localdrop.uploads";

export interface PendingUpload {
  transferId: string;
  name: string;
  size: number;
  lastModified?: number;
}

function readAll(): Record<string, PendingUpload> {
  try {
    const raw = window.localStorage.getItem(KEY);
    const value: unknown = raw ? JSON.parse(raw) : {};
    return typeof value === "object" && value !== null
      ? (value as Record<string, PendingUpload>)
      : {};
  } catch {
    return {};
  }
}

function writeAll(entries: Record<string, PendingUpload>): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(entries));
  } catch {
    // stockage indisponible : la reprise après rechargement ne sera pas proposée
  }
}

export function rememberUpload(upload: PendingUpload): void {
  writeAll({ ...readAll(), [upload.transferId]: upload });
}

export function forgetUpload(transferId: string): void {
  const entries = readAll();
  if (transferId in entries) {
    writeAll(Object.fromEntries(Object.entries(entries).filter(([id]) => id !== transferId)));
  }
}

export function findUpload(transferId: string): PendingUpload | undefined {
  return readAll()[transferId];
}

/** Le fichier resélectionné correspond-il à l'envoi interrompu ? */
export function sameFile(
  file: { readonly name: string; readonly size: number },
  expected: { name: string; size: number },
): boolean {
  return file.name === expected.name && file.size === expected.size;
}
