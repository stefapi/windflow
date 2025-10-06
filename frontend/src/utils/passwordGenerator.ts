/**
 * Générateur de mots de passe sécurisés.
 *
 * Utilise l'API Web Crypto pour générer des mots de passe
 * cryptographiquement sécurisés.
 */

/**
 * Charset pour mots de passe
 */
const CHARSET = {
  lowercase: 'abcdefghijklmnopqrstuvwxyz',
  uppercase: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
  numbers: '0123456789',
  symbols: '!@#$%^&*()_+-=[]{}|;:,.<>?'
}

interface PasswordOptions {
  length?: number
  useLowercase?: boolean
  useUppercase?: boolean
  useNumbers?: boolean
  useSymbols?: boolean
}

/**
 * Génère un mot de passe sécurisé.
 *
 * @param options - Options de génération
 * @returns Mot de passe généré
 *
 * @example
 * ```typescript
 * const password = generateSecurePassword({ length: 16 })
 * // => "aB3!dEf7Gh9@kL2mN"
 * ```
 */
export function generateSecurePassword(options: PasswordOptions = {}): string {
  const {
    length = 16,
    useLowercase = true,
    useUppercase = true,
    useNumbers = true,
    useSymbols = true
  } = options

  // Construire le charset selon les options
  let charset = ''
  if (useLowercase) charset += CHARSET.lowercase
  if (useUppercase) charset += CHARSET.uppercase
  if (useNumbers) charset += CHARSET.numbers
  if (useSymbols) charset += CHARSET.symbols

  if (charset.length === 0) {
    throw new Error('Au moins un type de caractère doit être activé')
  }

  // Utiliser Web Crypto API pour génération sécurisée
  const randomValues = new Uint32Array(length)
  crypto.getRandomValues(randomValues)

  let password = ''
  for (let i = 0; i < length; i++) {
    const randomIndex = randomValues[i] % charset.length
    password += charset[randomIndex]
  }

  // Vérifier qu'au moins un caractère de chaque type requis est présent
  if (useLowercase && !/[a-z]/.test(password)) {
    password = ensureCharType(password, CHARSET.lowercase)
  }
  if (useUppercase && !/[A-Z]/.test(password)) {
    password = ensureCharType(password, CHARSET.uppercase)
  }
  if (useNumbers && !/[0-9]/.test(password)) {
    password = ensureCharType(password, CHARSET.numbers)
  }
  if (useSymbols && !/[!@#$%^&*()_+\-=[\]{}|;:,.<>?]/.test(password)) {
    password = ensureCharType(password, CHARSET.symbols)
  }

  return password
}

/**
 * S'assure qu'au moins un caractère du type spécifié est présent.
 *
 * @param password - Mot de passe à modifier
 * @param charset - Charset du type de caractère
 * @returns Mot de passe avec au moins un caractère du type
 */
function ensureCharType(password: string, charset: string): string {
  const randomIndex = Math.floor(Math.random() * password.length)
  const randomChar = charset[Math.floor(Math.random() * charset.length)]

  return password.substring(0, randomIndex) + randomChar + password.substring(randomIndex + 1)
}

/**
 * Génère un mot de passe adapté au champ password d'un schéma.
 *
 * @param minLength - Longueur minimale
 * @param maxLength - Longueur maximale
 * @returns Mot de passe généré
 */
export function generatePasswordForField(
  minLength: number = 12,
  maxLength: number = 32
): string {
  // Utiliser une longueur entre min et max, ou la longueur min si max non spécifié
  const length = Math.min(Math.max(minLength, 16), maxLength || 32)

  return generateSecurePassword({ length })
}

/**
 * Évalue la force d'un mot de passe.
 *
 * @param password - Mot de passe à évaluer
 * @returns Score de 0 (faible) à 4 (très fort)
 *
 * @example
 * ```typescript
 * const strength = evaluatePasswordStrength('password123')
 * // => 1 (faible)
 *
 * const strongPassword = evaluatePasswordStrength('aB3!dEf7Gh9@kL2mN')
 * // => 4 (très fort)
 * ```
 */
export function evaluatePasswordStrength(password: string): number {
  let score = 0

  // Longueur
  if (password.length >= 8) score++
  if (password.length >= 12) score++
  if (password.length >= 16) score++

  // Diversité des caractères
  if (/[a-z]/.test(password)) score++
  if (/[A-Z]/.test(password)) score++
  if (/[0-9]/.test(password)) score++
  if (/[!@#$%^&*()_+\-=[\]{}|;:,.<>?]/.test(password)) score++

  // Pas de patterns communs
  const commonPatterns = [
    /^[0-9]+$/,  // Que des chiffres
    /^[a-z]+$/,  // Que des minuscules
    /password/i,
    /123456/,
    /qwerty/i,
    /admin/i
  ]

  const hasCommonPattern = commonPatterns.some(pattern => pattern.test(password))
  if (hasCommonPattern) {
    score = Math.max(0, score - 2)
  }

  // Normaliser le score entre 0 et 4
  return Math.min(4, Math.max(0, Math.floor(score / 2)))
}

/**
 * Obtient le label de force du mot de passe.
 *
 * @param score - Score de force (0-4)
 * @returns Label et couleur
 */
export function getPasswordStrengthLabel(score: number): {
  label: string
  color: string
} {
  const labels = [
    { label: 'Très faible', color: 'error' },
    { label: 'Faible', color: 'warning' },
    { label: 'Moyen', color: 'warning' },
    { label: 'Fort', color: 'success' },
    { label: 'Très fort', color: 'success' }
  ]

  return labels[score] || labels[0]
}

/**
 * Génère plusieurs mots de passe pour un formulaire complet.
 *
 * @param fields - Liste des champs nécessitant un mot de passe
 * @returns Objet avec les mots de passe générés
 *
 * @example
 * ```typescript
 * const passwords = generatePasswordsForFields([
 *   { name: 'db_password', minLength: 12 },
 *   { name: 'admin_password', minLength: 16 }
 * ])
 * // => { db_password: 'aB3!...', admin_password: 'xY9@...' }
 * ```
 */
export function generatePasswordsForFields(
  fields: Array<{ name: string; minLength?: number; maxLength?: number }>
): Record<string, string> {
  const passwords: Record<string, string> = {}

  fields.forEach(field => {
    passwords[field.name] = generatePasswordForField(
      field.minLength,
      field.maxLength
    )
  })

  return passwords
}

/**
 * Copie un mot de passe dans le presse-papiers.
 *
 * @param password - Mot de passe à copier
 * @returns Promise résolue si succès
 */
export async function copyPasswordToClipboard(password: string): Promise<void> {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(password)
  } else {
    // Fallback pour navigateurs plus anciens
    const textarea = document.createElement('textarea')
    textarea.value = password
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
}
