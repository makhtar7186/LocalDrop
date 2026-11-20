// Textes de l'interface, centralisés pour préparer l'internationalisation.
export const messages = {
  appName: "LocalDrop",
  tagline: "Scanner, connecter, transférer.",
  trustedNetworkWarning:
    "Utilisez un réseau de confiance et évitez les Wi-Fi publics : la connexion n'est pas chiffrée.",
  notPaired: "Scannez le QR Code affiché sur votre PC pour commencer.",
  joining: "Connexion au PC…",
  checking: "Vérification de la connexion…",
  pendingTitle: "En attente d'autorisation",
  pending: (name: string) =>
    `Acceptez « ${name} » sur le PC pour autoriser ce téléphone. Gardez cette page ouverte.`,
  connectedTitle: "Connecté",
  connected: (server: string) => `Ce téléphone est connecté à ${server}.`,
  rejected: "Le PC a refusé ce téléphone. Scannez à nouveau le QR Code pour réessayer.",
  sessionExpired: "La session a expiré. Scannez à nouveau le QR Code affiché sur le PC.",
  sessionRevoked: "Session terminée. Scannez à nouveau le QR Code affiché sur le PC.",
  invalidQr:
    "Ce QR Code a expiré ou a déjà été utilisé. Affichez un nouveau QR Code sur le PC puis scannez-le.",
  offline:
    "PC injoignable. Vérifiez que le téléphone et le PC sont sur le même réseau. Nouvelle tentative…",
  genericError: (message: string) => `Erreur : ${message}`,

  sendTitle: "Envoyer vers le PC",
  chooseFiles: "Choisir des fichiers",
  keepPageOpen: "Gardez cette page ouverte et l'écran allumé pendant le transfert.",
  noUploads: "Aucun envoi pour le moment.",
  uploadsListLabel: "Envois en cours et terminés",
  uploadQueued: "En attente…",
  uploadRetrying: "PC injoignable, nouvelle tentative…",
  uploadVerifying: "Vérification de l'intégrité…",
  uploadCompleted: "Reçu sur le PC ✓",
  uploadCancelled: "Annulé",
  uploadFailed: (code: string) => uploadErrors[code] ?? `Échec (${code})`,
} as const;

const uploadErrors: Record<string, string> = {
  INSUFFICIENT_DISK_SPACE: "Échec : espace disque insuffisant sur le PC",
  FILE_TOO_LARGE: "Échec : fichier trop volumineux",
  FILE_HASH_MISMATCH: "Échec : fichier altéré pendant le transfert, renvoyez-le",
  FILE_SIZE_MISMATCH: "Échec : taille incorrecte, renvoyez le fichier",
  NETWORK_UNREACHABLE: "Échec : PC injoignable",
  DEVICE_UNAUTHORIZED: "Échec : session terminée",
};
