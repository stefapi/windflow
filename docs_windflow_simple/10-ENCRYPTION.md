# Chiffrement des Secrets

[← Scheduler](09-SCHEDULER.md) | [Suivant : Terminal WebSocket →](11-TERMINAL-WEBSOCKET.md)

## 🔐 Vue d'ensemble

Système de chiffrement AES-256-GCM pour protéger les secrets (mots de passe, clés SSH, tokens) stockés en base de données. Supporte la gestion hybride des clés (fichier + variable d'environnement) et la rotation automatique.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Gestion des clés de chiffrement            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Aucun fichier, aucune env var                      │
│     → Génération automatique + sauvegarde fichier       │
│                                                         │
│  2. Fichier existe, pas d'env var                      │
│     → Utilisation clé fichier                          │
│                                                         │
│  3. Pas de fichier, env var définie                    │
│     → Utilisation env var (pas de sauvegarde)          │
│                                                         │
│  4. Fichier existe, env var identique                  │
│     → Utilisation env var + suppression fichier        │
│                                                         │
│  5. Fichier existe, env var différente                 │
│     → Re-chiffrement + suppression fichier             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 1. Algorithme de chiffrement

### Configuration

```typescript
// src/lib/server/encryption.ts

/** Algorithme: AES-256 avec mode GCM (authenticated encryption) */
const ALGORITHM = 'aes-256-gcm';

/** Longueur de l'IV (Initialization Vector) en bytes */
const IV_LENGTH = 12;

/** Longueur de l'authentication tag en bytes */
const AUTH_TAG_LENGTH = 16;

/** Longueur de la clé de chiffrement en bytes (256 bits) */
const KEY_LENGTH = 32;

/** Préfixe pour valeurs chiffrées (versioning) */
const ENCRYPTED_PREFIX = 'enc:v1:';

/** Nom du fichier de clé auto-générée */
const KEY_FILE_NAME = '.encryption_key';
```

### Format des données chiffrées

```
enc:v1:<base64(iv + authTag + ciphertext)>

Où:
- iv: 12 bytes (nonce aléatoire)
- authTag: 16 bytes (tag d'authentification GCM)
- ciphertext: longueur variable (données chiffrées)
```

## 2. Gestion des clés

### Obtention ou création de la clé

```typescript
function getOrCreateKey(): Buffer {
    // Retourner clé en cache si disponible
    if (cachedKey) {
        return cachedKey;
    }

    const dataDir = getDataDir();
    const keyPath = join(dataDir, KEY_FILE_NAME);
    const envKey = process.env.ENCRYPTION_KEY;

    // 1. Fichier existe?
    if (existsSync(keyPath)) {
        const fileKey = readFileSync(keyPath);
        
        if (fileKey.length !== KEY_LENGTH) {
            throw new Error('Key file has invalid length');
        }

        // Env var aussi définie?
        if (envKey) {
            const envKeyBuffer = Buffer.from(envKey, 'base64');
            
            if (envKeyBuffer.length !== KEY_LENGTH) {
                console.warn('Invalid ENCRYPTION_KEY env var');
                // Utiliser clé fichier
            } else if (!fileKey.equals(envKeyBuffer)) {
                // Clés différentes → rotation
                console.log('Key change detected - will re-encrypt');
                pendingKeyRotation = { 
                    oldKey: fileKey, 
                    newKey: envKeyBuffer 
                };
                cachedKey = fileKey; // Retourner ancienne clé d'abord
                return cachedKey;
            } else {
                // Même clé → supprimer fichier
                unlinkSync(keyPath);
                console.log('Using ENCRYPTION_KEY from environment');
                cachedKey = envKeyBuffer;
                return cachedKey;
            }
        }

        // Pas d'env var → utiliser fichier
        cachedKey = fileKey;
        return cachedKey;
    }

    // 2. Pas de fichier - env var définie?
    if (envKey) {
        const keyBuffer = Buffer.from(envKey, 'base64');
        
        if (keyBuffer.length !== KEY_LENGTH) {
            throw new Error('ENCRYPTION_KEY must be 32 bytes');
        }
        
        cachedKey = keyBuffer;
        console.log('Using ENCRYPTION_KEY from environment');
        return cachedKey;
    }

    // 3. Aucune clé → générer nouvelle clé
    console.log('Generating new encryption key...');
    cachedKey = randomBytes(KEY_LENGTH);

    // Sauvegarder avec permissions restrictives (0600)
    writeFileSync(keyPath, cachedKey, { mode: 0o600 });
    console.log('Saved new encryption key to', keyPath);

    return cachedKey;
}
```

### Génération de clé pour env var

```typescript
export function generateKey(): string {
    return randomBytes(KEY_LENGTH).toString('base64');
}

// Exemple d'utilisation (CLI)
// poetry run -e "console.log(require('./encryption').generateKey())"
// Output: "abc123...xyz789=="
```

## 3. Chiffrement et déchiffrement

### Fonction encrypt

```typescript
export function encrypt(plaintext: string | null | undefined): string | null {
    // Passer null/undefined/vide tel quel
    if (plaintext === null || plaintext === undefined || plaintext === '') {
        return plaintext as string | null;
    }

    // Éviter double chiffrement
    if (plaintext.startsWith(ENCRYPTED_PREFIX)) {
        return plaintext;
    }

    const key = getOrCreateKey();
    const iv = randomBytes(IV_LENGTH);

    // Créer cipher AES-256-GCM
    const cipher = createCipheriv(ALGORITHM, key, iv);
    
    // Chiffrer
    const ciphertext = Buffer.concat([
        cipher.update(plaintext, 'utf8'),
        cipher.final()
    ]);

    // Récupérer authentication tag
    const authTag = cipher.getAuthTag();

    // Combiner: iv (12) + authTag (16) + ciphertext
    const combined = Buffer.concat([iv, authTag, ciphertext]);

    return ENCRYPTED_PREFIX + combined.toString('base64');
}
```

### Fonction decrypt

```typescript
export function decrypt(value: string | null | undefined): string | null {
    // Passer null/undefined/vide tel quel
    if (value === null || value === undefined || value === '') {
        return value as string | null;
    }

    // RÉTROCOMPATIBILITÉ: Sans préfixe = texte en clair
    if (!value.startsWith(ENCRYPTED_PREFIX)) {
        return value;
    }

    // Extraire le payload base64
    const payload = value.substring(ENCRYPTED_PREFIX.length);
    const combined = Buffer.from(payload, 'base64');

    // Valider longueur minimale: iv(12) + authTag(16) + 1 byte
    if (combined.length < IV_LENGTH + AUTH_TAG_LENGTH + 1) {
        console.error('Encrypted payload too short');
        return value; // Retourner original pour éviter perte de données
    }

    // Extraire composants
    const iv = combined.subarray(0, IV_LENGTH);
    const authTag = combined.subarray(IV_LENGTH, IV_LENGTH + AUTH_TAG_LENGTH);
    const ciphertext = combined.subarray(IV_LENGTH + AUTH_TAG_LENGTH);

    try {
        const key = getOrCreateKey();
        
        // Créer decipher
        const decipher = createDecipheriv(ALGORITHM, key, iv);
        decipher.setAuthTag(authTag);

        // Déchiffrer
        const decrypted = Buffer.concat([
            decipher.update(ciphertext),
            decipher.final()
        ]);

        return decrypted.toString('utf8');
    } catch (error) {
        console.error('Decryption failed:', error.message);
        return value; // Retourner original (peut être corrompu)
    }
}
```

### Fonction helper

```typescript
export function isEncrypted(value: string | null | undefined): boolean {
    return typeof value === 'string' && value.startsWith(ENCRYPTED_PREFIX);
}
```

## 4. Migration automatique

### Migration au démarrage

```typescript
export async function migrateCredentials(): Promise<void> {
    // IMPORTANT: Initialiser la clé au démarrage
    getOrCreateKey();

    console.log('Checking for unencrypted credentials...');

    // Import DB dynamique pour éviter dépendance circulaire
    const {
        db, eq,
        registries, gitCredentials, environments,
        oidcConfig, ldapConfig, notificationSettings,
        stackEnvironmentVariables
    } = await import('./db/drizzle.js');

    let migrated = 0;

    // 1. Vérifier rotation de clé
    if (pendingKeyRotation) {
        console.log('Performing key rotation...');
        
        // Collecter toutes les valeurs chiffrées
        const allEncrypted = [];
        
        // Registries
        const regs = await db.select().from(registries);
        for (const reg of regs) {
            if (reg.password && isEncrypted(reg.password)) {
                allEncrypted.push({
                    table: 'registries',
                    id: reg.id,
                    field: 'password',
                    value: reg.password
                });
            }
        }

        // Git Credentials
        const gitCreds = await db.select().from(gitCredentials);
        for (const cred of gitCreds) {
            if (cred.password && isEncrypted(cred.password)) {
                allEncrypted.push({
                    table: 'gitCredentials',
                    id: cred.id,
                    field: 'password',
                    value: cred.password
                });
            }
            if (cred.sshPrivateKey && isEncrypted(cred.sshPrivateKey)) {
                allEncrypted.push({
                    table: 'gitCredentials',
                    id: cred.id,
                    field: 'sshPrivateKey',
                    value: cred.sshPrivateKey
                });
            }
            if (cred.sshPassphrase && isEncrypted(cred.sshPassphrase)) {
                allEncrypted.push({
                    table: 'gitCredentials',
                    id: cred.id,
                    field: 'sshPassphrase',
                    value: cred.sshPassphrase
                });
            }
        }

        // Environments (Hawser tokens, TLS keys)
        const envs = await db.select().from(environments);
        for (const env of envs) {
            if (env.hawserToken && isEncrypted(env.hawserToken)) {
                allEncrypted.push({
                    table: 'environments',
                    id: env.id,
                    field: 'hawserToken',
                    value: env.hawserToken
                });
            }
            if (env.tlsKey && isEncrypted(env.tlsKey)) {
                allEncrypted.push({
                    table: 'environments',
                    id: env.id,
                    field: 'tlsKey',
                    value: env.tlsKey
                });
            }
        }

        // OIDC Config
        const oidcConfigs = await db.select().from(oidcConfig);
        for (const config of oidcConfigs) {
            if (config.clientSecret && isEncrypted(config.clientSecret)) {
                allEncrypted.push({
                    table: 'oidcConfig',
                    id: config.id,
                    field: 'clientSecret',
                    value: config.clientSecret
                });
            }
        }

        // LDAP Config
        const ldapConfigs = await db.select().from(ldapConfig);
        for (const config of ldapConfigs) {
            if (config.bindPassword && isEncrypted(config.bindPassword)) {
                allEncrypted.push({
                    table: 'ldapConfig',
                    id: config.id,
                    field: 'bindPassword',
                    value: config.bindPassword
                });
            }
        }

        // Notification Settings (SMTP password dans JSON)
        const notifSettings = await db.select().from(notificationSettings);
        for (const notif of notifSettings) {
            if (notif.config) {
                const config = JSON.parse(notif.config);
                if (config.smtpPassword && isEncrypted(config.smtpPassword)) {
                    allEncrypted.push({
                        table: 'notificationSettings',
                        id: notif.id,
                        field: 'config.smtpPassword',
                        value: config.smtpPassword
                    });
                }
            }
        }

        // Stack Environment Variables (secrets)
        const stackEnvVars = await db.select().from(stackEnvironmentVariables);
        for (const envVar of stackEnvVars) {
            if (envVar.isSecret && envVar.value && isEncrypted(envVar.value)) {
                allEncrypted.push({
                    table: 'stackEnvironmentVariables',
                    id: envVar.id,
                    field: 'value',
                    value: envVar.value
                });
            }
        }

        // Déchiffrer avec ancienne clé
        const decryptedValues = new Map();
        for (const item of allEncrypted) {
            const decrypted = decrypt(item.value);
            if (decrypted) {
                const key = `${item.table}:${item.id}:${item.field}`;
                decryptedValues.set(key, decrypted);
            }
        }

        // Basculer vers nouvelle clé
        cachedKey = pendingKeyRotation.newKey;

        // Re-chiffrer et mettre à jour
        for (const item of allEncrypted) {
            const key = `${item.table}:${item.id}:${item.field}`;
            const decrypted = decryptedValues.get(key);
            
            if (decrypted) {
                const reEncrypted = encrypt(decrypted);
                
                // Mettre à jour selon la table
                if (item.table === 'registries') {
                    await db.update(registries)
                        .set({ [item.field]: reEncrypted })
                        .where(eq(registries.id, item.id));
                } else if (item.table === 'gitCredentials') {
                    await db.update(gitCredentials)
                        .set({ [item.field]: reEncrypted })
                        .where(eq(gitCredentials.id, item.id));
                } else if (item.table === 'environments') {
                    await db.update(environments)
                        .set({ [item.field]: reEncrypted })
                        .where(eq(environments.id, item.id));
                } else if (item.table === 'oidcConfig') {
                    await db.update(oidcConfig)
                        .set({ [item.field]: reEncrypted })
                        .where(eq(oidcConfig.id, item.id));
                } else if (item.table === 'ldapConfig') {
                    await db.update(ldapConfig)
                        .set({ [item.field]: reEncrypted })
                        .where(eq(ldapConfig.id, item.id));
                } else if (item.table === 'notificationSettings') {
                    const notif = notifSettings.find(n => n.id === item.id);
                    if (notif) {
                        const config = JSON.parse(notif.config);
                        config.smtpPassword = reEncrypted;
                        await db.update(notificationSettings)
                            .set({ config: JSON.stringify(config) })
                            .where(eq(notificationSettings.id, item.id));
                    }
                } else if (item.table === 'stackEnvironmentVariables') {
                    await db.update(stackEnvironmentVariables)
                        .set({ value: reEncrypted })
                        .where(eq(stackEnvironmentVariables.id, item.id));
                }
                
                migrated++;
            }
        }

        // Supprimer fichier de clé
        const keyPath = join(getDataDir(), KEY_FILE_NAME);
        if (existsSync(keyPath)) {
            unlinkSync(keyPath);
            console.log('Deleted key file - using ENCRYPTION_KEY from env');
        }

        pendingKeyRotation = null;
        console.log(`Re-encrypted ${migrated} credentials with new key`);
        return;
    }

    // 2. Migration normale (chiffrer valeurs non chiffrées)
    
    // Registries
    const regs = await db.select().from(registries);
    for (const reg of regs) {
        if (reg.password && !isEncrypted(reg.password)) {
            await db.update(registries)
                .set({ password: encrypt(reg.password) })
                .where(eq(registries.id, reg.id));
            migrated++;
        }
    }

    // Git Credentials
    const gitCreds = await db.select().from(gitCredentials);
    for (const cred of gitCreds) {
        const updates: Record<string, string | null> = {};
        
        if (cred.password && !isEncrypted(cred.password)) {
            updates.password = encrypt(cred.password);
            migrated++;
        }
        if (cred.sshPrivateKey && !isEncrypted(cred.sshPrivateKey)) {
            updates.sshPrivateKey = encrypt(cred.sshPrivateKey);
            migrated++;
        }
        if (cred.sshPassphrase && !isEncrypted(cred.sshPassphrase)) {
            updates.sshPassphrase = encrypt(cred.sshPassphrase);
            migrated++;
        }
        
        if (Object.keys(updates).length > 0) {
            await db.update(gitCredentials)
                .set(updates)
                .where(eq(gitCredentials.id, cred.id));
        }
    }

    // ... autres tables similaires

    if (migrated > 0) {
        console.log(`Migrated ${migrated} credentials to encrypted storage`);
    }
}
```

## 5. Champs chiffrés

### Tables concernées

```typescript
// src/lib/server/db/drizzle.ts

// 1. registries
export const registries = sqliteTable('registries', {
    id: integer('id').primaryKey({ autoIncrement: true }),
    name: text('name').notNull().unique(),
    url: text('url').notNull(),
    username: text('username'),
    password: text('password'), // ← CHIFFRÉ
    // ...
});

// 2. git_credentials
export const gitCredentials = sqliteTable('git_credentials', {
    id: integer('id').primaryKey({ autoIncrement: true }),
    name: text('name').notNull().unique(),
    username: text('username'),
    password: text('password'), // ← CHIFFRÉ
    sshPrivateKey: text('ssh_private_key'), // ← CHIFFRÉ
    sshPassphrase: text('ssh_passphrase'), // ← CHIFFRÉ
    // ...
});

// 3. environments
export const environments = sqliteTable('environments', {
    id: integer('id').primaryKey({ autoIncrement: true }),
    name: text('name').notNull(),
    hawserToken: text('hawser_token'), // ← CHIFFRÉ
    tlsKey: text('tls_key'), // ← CHIFFRÉ
    // ...
});

// 4. oidc_config
export const oidcConfig = sqliteTable('oidc_config', {
    id: integer('id').primaryKey({ autoIncrement: true }),
    clientId: text('client_id').notNull(),
    clientSecret: text('client_secret'), // ← CHIFFRÉ
    // ...
});

// 5. ldap_config
export const ldapConfig = sqliteTable('ldap_config', {
    id: integer('id').primaryKey({ autoIncrement: true }),
    bindDn: text('bind_dn'),
    bindPassword: text('bind_password'), // ← CHIFFRÉ
    // ...
});

// 6. notification_settings
export const notificationSettings = sqliteTable('notification_settings', {
    id: integer('id').primaryKey({ autoIncrement: true }),
    config: text('config'), // JSON: { smtpPassword: "..." } ← CHIFFRÉ
    // ...
});

// 7. stack_environment_variables
export const stackEnvironmentVariables = sqliteTable('stack_environment_variables', {
    id: integer('id').primaryKey({ autoIncrement: true }),
    key: text('key').notNull(),
    value: text('value'), // ← CHIFFRÉ si isSecret=true
    isSecret: integer('is_secret', { mode: 'boolean' }).default(false),
    // ...
});
```

## 6. Utilisation dans le code

### Chiffrement lors de la création

```typescript
// routes/api/registries/+server.ts
export async function POST({ request, locals }) {
    const data = await request.json();
    
    await db.insert(registries).values({
        name: data.name,
        url: data.url,
        username: data.username,
        password: encrypt(data.password), // ← Chiffrer avant insertion
        createdAt: new Date().toISOString()
    });
    
    return json({ success: true });
}
```

### Déchiffrement lors de la lecture

```typescript
// routes/api/registries/[id]/+server.ts
export async function GET({ params, locals }) {
    const registry = await db
        .select()
        .from(registries)
        .where(eq(registries.id, Number(params.id)))
        .get();
    
    if (!registry) {
        return json({ error: 'Not found' }, { status: 404 });
    }
    
    // Ne jamais exposer le mot de passe déchiffré dans l'API
    return json({
        id: registry.id,
        name: registry.name,
        url: registry.url,
        username: registry.username,
        hasPassword: !!registry.password // Indiquer présence seulement
    });
}
```

### Utilisation interne (Docker login)

```typescript
// lib/server/docker.ts
async function dockerLogin(registry: Registry) {
    const auth = {
        username: registry.username,
        password: decrypt(registry.password), // ← Déchiffrer pour usage
        serveraddress: registry.url
    };
    
    await dockerClient.post('/auth', { body: auth });
}
```

## 7. Sécurité

### Bonnes pratiques

1. **Variable d'environnement en production**
   ```bash
   # Générer une nouvelle clé
   ENCRYPTION_KEY=$(poetry run -e "console.log(require('./encryption').generateKey())")
   
   # Définir dans l'environnement
   export ENCRYPTION_KEY="abc123...xyz789=="
   # OU dans docker-compose.yml
   environment:
     - ENCRYPTION_KEY=abc123...xyz789==
   ```

2. **Permissions fichier (si auto-généré)**
   - Mode: 0600 (lecture/écriture propriétaire uniquement)
   - Emplacement: `./data/.encryption_key`
   - Exclure du contrôle de version (`.gitignore`)

3. **Rotation de clé**
   - Définir nouvelle `ENCRYPTION_KEY` dans env
   - Redémarrer Windflow-sample
   - Migration automatique au démarrage
   - Fichier supprimé automatiquement

4. **Ne jamais exposer les secrets**
   - Ne pas retourner secrets déchiffrés dans l'API
   - Utiliser `hasPassword: boolean` plutôt que le mot de passe
   - Logs: masquer les valeurs chiffrées

5. **Rétrocompatibilité**
   - Valeurs sans préfixe = texte en clair (migration transparente)
   - `decrypt()` gère automatiquement les deux formats
   - Ne jamais perdre de données en cas d'erreur

### Limitations

- **Clé unique**: Une seule clé pour tous les secrets
- **Pas de rotation manuelle**: Rotation automatique seulement lors du changement de `ENCRYPTION_KEY`
- **Pas de HSM**: Clé stockée en mémoire/fichier (pas de Hardware Security Module)

---

[← Scheduler](09-SCHEDULER.md) | [Suivant : Terminal WebSocket →](11-TERMINAL-WEBSOCKET.md)
