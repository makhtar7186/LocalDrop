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
} as const;
