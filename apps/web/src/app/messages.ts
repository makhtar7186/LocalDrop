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

  receiveTitle: "Recevoir du PC",
  receiveLoading: "Recherche des fichiers proposés par le PC…",
  receiveEmpty: "Aucun fichier proposé. Envoyez un fichier depuis le PC pour le voir ici.",
  receiveOffline: "Impossible d'actualiser la liste : PC injoignable.",
  receiveListLabel: "Fichiers proposés par le PC",
  download: "Télécharger",
  preparingLink: "Préparation du lien…",
  downloadStarted:
    "Téléchargement lancé par le navigateur. Une fois terminé, confirmez la réception.",
  confirmReceived: "J'ai reçu le fichier",
  dismiss: "Ignorer",
  received: "Reçu ✓",
  actionFailed: "Action impossible, réessayez.",

  interruptedListLabel: "Envois interrompus",
  interruptedHint: (pct: number) =>
    `Envoi interrompu à ${pct} %. Choisissez à nouveau le même fichier pour reprendre : seule la partie manquante sera envoyée.`,
  resumeUpload: "Reprendre",
  resumeUploadOf: (name: string) => `Reprendre l'envoi de ${name}`,
  abandonUpload: "Abandonner",
  wrongFile: (name: string) =>
    `Ce n'est pas le même fichier. Sélectionnez « ${name} » (même nom et même taille).`,

  historyTitle: "Historique",
  historyAll: "Tous",
  historySent: "Envoyés",
  historyReceived: "Reçus",
  historySearch: "Rechercher un fichier",
  historyLoading: "Chargement de l'historique…",
  historyEmpty: "Aucun transfert pour le moment.",
  historyNoMatch: "Aucun transfert ne correspond à la recherche.",
  historyError: "Impossible de charger l'historique : PC injoignable.",
  historyMore: "Afficher plus",
  historyListLabel: "Transferts passés",
  directionSent: "Envoyé au PC",
  directionReceived: "Reçu du PC",
  transferStatus: {
    created: "Créé",
    waiting: "En attente",
    transferring: "En cours",
    paused: "En pause",
    verifying: "Vérification",
    completed: "Terminé",
    failed: "Échec",
    cancelled: "Annulé",
  } as Record<string, string>,
  expired: "Annulé (expiré)",

  cancelUpload: "Annuler",
  cancelUploadOf: (name: string) => `Annuler l'envoi de ${name}`,

  navLabel: "Navigation principale",
  navHome: "Accueil",
  navSend: "Envoyer",
  navReceive: "Recevoir",
  navHistory: "Historique",
  badgeSend: (count: number) => (count > 1 ? `${count} envois en cours` : "1 envoi en cours"),
  badgeReceive: (count: number) =>
    count > 1 ? `${count} fichiers à recevoir` : "1 fichier à recevoir",
  homeTitle: "Accueil",
  homeConnectedTo: (server: string) => `Connecté à ${server}`,
  homeSendAction: "Envoyer des fichiers au PC",
  homeReceiveAction: "Recevoir des fichiers du PC",
  homeReceiveWaiting: (count: number) =>
    count > 1 ? `${count} fichiers vous attendent` : "1 fichier vous attend",
  homeSendActive: (count: number) =>
    count > 1 ? `${count} envois en cours ou interrompus` : "1 envoi en cours ou interrompu",
  crashTitle: "Une erreur inattendue est survenue",
  crashText: "Rechargez la page. Les envois interrompus pourront être repris.",
  crashReload: "Recharger la page",

  liveOn: "● En direct",
  liveReconnecting: "○ Reconnexion…",
} as const;

const uploadErrors: Record<string, string> = {
  INSUFFICIENT_DISK_SPACE: "Échec : espace disque insuffisant sur le PC",
  FILE_TOO_LARGE: "Échec : fichier trop volumineux",
  TOO_MANY_ACTIVE_TRANSFERS: "Échec : trop d'envois inachevés sur le PC, réessayez plus tard",
  FILE_HASH_MISMATCH: "Échec : fichier altéré pendant le transfert, renvoyez-le",
  FILE_SIZE_MISMATCH: "Échec : taille incorrecte, renvoyez le fichier",
  NETWORK_UNREACHABLE: "Échec : PC injoignable",
  DEVICE_UNAUTHORIZED: "Échec : session terminée",
};
