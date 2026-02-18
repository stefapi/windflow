# Authentification Multi-Provider

[← Base de données](03-DATABASE-SCHEMA.md) | [Suivant : Git Integration →](05-GIT-INTEGRATION.md)

## 🔐 Vue d'ensemble

Windflow-sample supporte **4 providers d'authentification** :
1. **Local** : Argon2id + sessions sécurisées
2. **LDAP/Active Directory** : Bind + search avec mapping de groupes
3. **OIDC/OAuth2** : Keycloak, Google, Azure AD, etc.
4. **MFA** : TOTP (Time-based One-Time Password) + codes de backup

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Auth Flow                          │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────┐    ┌──────────────┐    ┌───────────┐  │
│  │  Login  │───►│ Auth Provider│───►│  Session  │  │
│  │  Form   │    │              │    │  Cookie   │  │
│  └─────────┘    └──────────────┘    └───────────┘  │
│                      │                              │
│         ┌────────────┼────────────┐                │
│         ▼            ▼            ▼                │
│    ┌─────────┐  ┌─────────┐  ┌─────────┐          │
│    │  Local  │  │  LDAP   │  │  OIDC   │          │
│    │Argon2id │  │   AD    │  │ OAuth2  │          │
│    └─────────┘  └─────────┘  └─────────┘          │
│         │            │            │                │
│         └────────────┼────────────┘                │
│                      ▼                              │
│               ┌───────────┐                        │
│               │    MFA    │                        │
│               │   TOTP    │                        │
│               └───────────┘                        │
└─────────────────────────────────────────────────────┘
```

## 1. Hashing des mots de passe (Argon2id)

### Configuration

```typescript
// src/lib/server/auth.ts

// Paramètres Argon2id (correspondant à poetry.password)
const ARGON2_MEMORY_COST = 65536;  // 64 MB en kibibytes
const ARGON2_TIME_COST = 3;        // 3 itérations
const ARGON2_PARALLELISM = 1;      // Single-threaded
const ARGON2_HASH_LENGTH = 32;     // 256-bit output
const ARGON2_SALT_LENGTH = 16;     // 128-bit salt
```

### Fonction hashPassword

```typescript
export async function hashPassword(password: string): Promise<string> {
    // Sur vieux kernels (<3.17), poetry.password.hash() crashe
    // car il utilise getrandom() en interne.
    // Utiliser hash-wasm comme fallback (WASM pur, sans getrandom)
    if (usingFallback()) {
        const salt = secureRandomBytes(ARGON2_SALT_LENGTH);
        return argon2id({
            password,
            salt,
            iterations: ARGON2_TIME_COST,
            parallelism: ARGON2_PARALLELISM,
            memorySize: ARGON2_MEMORY_COST,
            hashLength: ARGON2_HASH_LENGTH,
            outputType: 'encoded'  // Format PHC: $argon2id$v=19$m=65536,t=3,p=1$...
        });
    }

    return Poetry.password.hash(password, {
        algorithm: 'argon2id',
        memoryCost: ARGON2_MEMORY_COST,
        timeCost: ARGON2_TIME_COST
    });
}
```

### Fonction verifyPassword

```typescript
export async function verifyPassword(
    password: string,
    hash: string
): Promise<boolean> {
    try {
        // Sur vieux kernels, utiliser hash-wasm
        if (usingFallback()) {
            return await argon2Verify({ password, hash });
        }

        return await Poetry.password.verify(password, hash);
    } catch {
        return false;
    }
}
```

**Avantages Argon2id:**
- Résistant aux attaques GPU (memory-hard)
- Résistant aux attaques de timing
- Résistant aux attaques side-channel
- Standard recommandé par l'OWASP

## 2. Gestion des sessions

### Génération de token

```typescript
function generateSessionToken(): string {
    // 32 bytes = 256 bits d'entropie
    return secureRandomBytes(32).toString('base64url');
}
```

### Création de session

```typescript
export async function createUserSession(
    userId: number,
    provider: string,  // 'local', 'ldap:AD', 'oidc:Keycloak', etc.
    cookies: Cookies
): Promise<Session> {
    // Nettoyer sessions expirées
    await deleteExpiredSessions();

    // Générer token sécurisé
    const sessionId = generateSessionToken();

    // Récupérer timeout depuis settings
    const settings = await getAuthSettings();
    const sessionTimeout = settings?.sessionTimeout || 86400; // 24h par défaut

    const expiresAt = new Date(Date.now() + sessionTimeout * 1000).toISOString();

    // Créer en DB
    const session = await dbCreateSession(sessionId, userId, provider, expiresAt);

    // Cookie HttpOnly sécurisé
    cookies.set('windflow_session', sessionId, {
        path: '/',
        httpOnly: true,                     // XSS protection
        secure: process.env.NODE_ENV === 'production', // HTTPS only en prod
        sameSite: 'strict',                 // CSRF protection
        maxAge: sessionTimeout
    });

    // Mettre à jour lastLogin
    await updateUser(userId, { lastLogin: new Date().toISOString() });

    return session;
}
```

### Validation de session

```typescript
export async function validateSession(
    cookies: Cookies
): Promise<AuthenticatedUser | null> {
    const sessionId = cookies.get('windflow_session');
    if (!sessionId) return null;

    const session = await dbGetSession(sessionId);
    if (!session) return null;

    // Vérifier expiration
    const expiresAt = new Date(session.expiresAt);
    if (expiresAt < new Date()) {
        await dbDeleteSession(sessionId);
        return null;
    }

    const user = await getUser(session.userId);
    if (!user || !user.isActive) return null;

    return await buildAuthenticatedUser(
        user,
        session.provider as 'local' | 'ldap' | 'oidc'
    );
}
```

### Destruction de session (logout)

```typescript
export async function destroySession(cookies: Cookies): Promise<void> {
    const sessionId = cookies.get('windflow_session');
    if (sessionId) {
        await dbDeleteSession(sessionId);
    }

    cookies.delete('windflow_session', { path: '/' });
}
```

## 3. Rate Limiting

### Configuration

```typescript
// src/lib/server/auth.ts

const RATE_LIMIT_MAX_ATTEMPTS = 5;           // 5 tentatives max
const RATE_LIMIT_WINDOW_MS = 15 * 60 * 1000; // 15 minutes
const RATE_LIMIT_LOCKOUT_MS = 15 * 60 * 1000; // 15 minutes de blocage
```

### Structure de données

```typescript
interface RateLimitEntry {
    attempts: number;
    lastAttempt: number;
    lockedUntil: number | null;
}

// Store in-memory (Map)
const rateLimitStore = new Map<string, RateLimitEntry>();

// Cleanup automatique toutes les 5 minutes
setInterval(() => {
    const now = Date.now();
    for (const [key, entry] of rateLimitStore) {
        if (now - entry.lastAttempt > RATE_LIMIT_WINDOW_MS) {
            rateLimitStore.delete(key);
        }
    }
}, 5 * 60 * 1000);
```

### Vérification de limitation

```typescript
export function isRateLimited(
    identifier: string  // username ou IP
): { limited: boolean; retryAfter?: number } {
    const entry = rateLimitStore.get(identifier);
    const now = Date.now();

    if (!entry) return { limited: false };

    // Vérifier si bloqué
    if (entry.lockedUntil && entry.lockedUntil > now) {
        return {
            limited: true,
            retryAfter: Math.ceil((entry.lockedUntil - now) / 1000)
        };
    }

    // Réinitialiser si hors fenêtre
    if (now - entry.lastAttempt > RATE_LIMIT_WINDOW_MS) {
        rateLimitStore.delete(identifier);
        return { limited: false };
    }

    return { limited: false };
}
```

### Enregistrement d'échec

```typescript
export function recordFailedAttempt(identifier: string): void {
    const now = Date.now();
    const entry = rateLimitStore.get(identifier);

    if (!entry || now - entry.lastAttempt > RATE_LIMIT_WINDOW_MS) {
        rateLimitStore.set(identifier, {
            attempts: 1,
            lastAttempt: now,
            lockedUntil: null
        });
        return;
    }

    entry.attempts++;
    entry.lastAttempt = now;

    if (entry.attempts >= RATE_LIMIT_MAX_ATTEMPTS) {
        entry.lockedUntil = now + RATE_LIMIT_LOCKOUT_MS;
    }
}
```

### Nettoyage sur succès

```typescript
export function clearRateLimit(identifier: string): void {
    rateLimitStore.delete(identifier);
}
```

## 4. Authentification Locale

### Flow complet

```typescript
export async function authenticateLocal(
    username: string,
    password: string
): Promise<LoginResult> {
    const user = await getUserByUsername(username);

    if (!user) {
        // Utiliser constant time pour prévenir timing attacks
        await hashPassword('dummy');
        return { success: false, error: 'Invalid username or password' };
    }

    if (!user.isActive) {
        return { success: false, error: 'Account is disabled' };
    }

    const validPassword = await verifyPassword(password, user.passwordHash);
    if (!validPassword) {
        return { success: false, error: 'Invalid username or password' };
    }

    // MFA requis?
    if (user.mfaEnabled) {
        return { success: true, requiresMfa: true };
    }

    return {
        success: true,
        user: await buildAuthenticatedUser(user, 'local')
    };
}
```

### API Route

```typescript
// routes/api/auth/login/+server.ts
import { authenticateLocal, createUserSession, isRateLimited, recordFailedAttempt, clearRateLimit } from '$lib/server/auth';

export async function POST({ request, cookies, getClientAddress }) {
    const { username, password } = await request.json();

    // Rate limiting par username et IP
    const clientIP = getClientAddress();
    const rateLimit = isRateLimited(username) || isRateLimited(clientIP);

    if (rateLimit.limited) {
        return json({
            error: `Too many failed attempts. Try again in ${rateLimit.retryAfter} seconds.`
        }, { status: 429 });
    }

    const result = await authenticateLocal(username, password);

    if (!result.success) {
        recordFailedAttempt(username);
        recordFailedAttempt(clientIP);
        return json({ error: result.error }, { status: 401 });
    }

    if (result.requiresMfa) {
        // Stocker temporairement user ID pour vérification MFA
        // (peut utiliser cookie signé ou store temporaire)
        return json({ requiresMfa: true });
    }

    // Succès - créer session
    clearRateLimit(username);
    clearRateLimit(clientIP);

    await createUserSession(result.user!.id, 'local', cookies);

    return json({ user: result.user });
}
```

## 5. LDAP / Active Directory

### Configuration

```sql
-- drizzle/0000_initial_schema.sql
CREATE TABLE ldap_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    server_url TEXT NOT NULL,           -- ldap://host:389 ou ldaps://host:636
    bind_dn TEXT,                       -- cn=admin,dc=example,dc=com
    bind_password TEXT,                 -- CHIFFRÉ avec encryption.ts
    base_dn TEXT NOT NULL,              -- ou=users,dc=example,dc=com
    user_filter TEXT NOT NULL,          -- (uid={{username}})
    username_attribute TEXT DEFAULT 'uid',
    email_attribute TEXT DEFAULT 'mail',
    display_name_attribute TEXT DEFAULT 'cn',
    group_base_dn TEXT,                 -- ou=groups,dc=example,dc=com
    group_filter TEXT,                  -- (member={{user_dn}})
    admin_group TEXT,                   -- docker-admins
    role_mappings TEXT,                 -- JSON: [{"groupDn": "...", "roleId": 1}]
    tls_enabled INTEGER DEFAULT 0,
    tls_ca TEXT,                        -- Certificat CA PEM
    created_at TEXT DEFAULT (datetime('now'))
);
```

### Fonction d'authentification

```typescript
export async function authenticateLdap(
    username: string,
    password: string,
    configId?: number
): Promise<LoginResult & { providerName?: string }> {
    // Récupérer configs LDAP actives
    const configs = configId
        ? [await getLdapConfig(configId)].filter(Boolean) as LdapConfig[]
        : await getEnabledLdapConfigs();

    if (configs.length === 0) {
        return { success: false, error: 'No LDAP configuration available' };
    }

    // Essayer chaque config
    for (const config of configs) {
        const result = await tryLdapAuth(username, password, config);
        if (result.success) {
            return { ...result, providerName: config.name };
        }
    }

    return { success: false, error: 'Invalid username or password' };
}
```

### Flow LDAP

```typescript
async function tryLdapAuth(
    username: string,
    password: string,
    config: LdapConfig
): Promise<LoginResult> {
    const client = new LdapClient({
        url: config.serverUrl,
        tlsOptions: config.tlsEnabled ? {
            rejectUnauthorized: !config.tlsCa,
            ca: config.tlsCa ? [config.tlsCa] : undefined
        } : undefined
    });

    try {
        // 1. Bind avec service account pour rechercher l'utilisateur
        if (config.bindDn && config.bindPassword) {
            await client.bind(config.bindDn, config.bindPassword);
        }

        // 2. Rechercher l'utilisateur
        const filter = config.userFilter.replace('{{username}}', username);
        const { searchEntries } = await client.search(config.baseDn, {
            scope: 'sub',
            filter: filter,
            sizeLimit: 1,
            attributes: [
                'dn',
                config.usernameAttribute,
                config.emailAttribute,
                config.displayNameAttribute
            ]
        });

        if (searchEntries.length === 0) {
            await client.unbind();
            return { success: false, error: 'User not found' };
        }

        const userEntry = searchEntries[0];
        const userDn = userEntry.dn;

        await client.unbind();

        // 3. Bind en tant qu'utilisateur (authentification)
        const userClient = new LdapClient({
            url: config.serverUrl,
            tlsOptions: config.tlsEnabled ? {
                rejectUnauthorized: !config.tlsCa,
                ca: config.tlsCa ? [config.tlsCa] : undefined
            } : undefined
        });

        try {
            await userClient.bind(userDn, password);
            await userClient.unbind();
        } catch (bindError) {
            return { success: false, error: 'Invalid username or password' };
        }

        // 4. Extraire attributs utilisateur
        const ldapUsername = getAttributeValue(userEntry, config.usernameAttribute) || username;
        const email = getAttributeValue(userEntry, config.emailAttribute);
        const displayName = getAttributeValue(userEntry, config.displayNameAttribute);

        // 5. Vérifier appartenance groupe admin
        let shouldBeAdmin = false;
        if (config.adminGroup) {
            shouldBeAdmin = await checkLdapGroupMembership(
                config,
                userDn,
                config.adminGroup
            );
        }

        const authProvider = `ldap:${config.name}`;

        // 6. Créer ou mettre à jour l'utilisateur local
        let user = await getUserByUsername(ldapUsername);
        if (!user) {
            user = await createUser({
                username: ldapUsername,
                email: email || undefined,
                displayName: displayName || undefined,
                passwordHash: '', // Pas de mot de passe local pour LDAP
                authProvider
            });
        } else {
            await updateUser(user.id, {
                email: email || undefined,
                displayName: displayName || undefined,
                authProvider
            });
            user = (await getUser(user.id))!;
        }

        // 7. Gérer rôle Admin
        const adminRole = await getRoleByName('Admin');
        if (adminRole) {
            const hasAdminRole = await userHasAdminRole(user.id);
            if (shouldBeAdmin && !hasAdminRole) {
                await assignUserRole(user.id, adminRole.id, null);
            }
        }

        // 8. Mapper rôles depuis groupes LDAP (Enterprise)
        const roleMappings = typeof config.roleMappings === 'string'
            ? JSON.parse(config.roleMappings)
            : config.roleMappings;

        if (roleMappings && await isEnterprise()) {
            for (const mapping of roleMappings) {
                const isInGroup = await checkLdapGroupMembership(
                    config,
                    userDn,
                    mapping.groupDn
                );
                if (isInGroup) {
                    await assignUserRole(user.id, mapping.roleId, undefined);
                }
            }
        }

        if (!user.isActive) {
            return { success: false, error: 'Account is disabled' };
        }

        if (user.mfaEnabled) {
            return { success: true, requiresMfa: true };
        }

        return {
            success: true,
            user: await buildAuthenticatedUser(user, 'ldap')
        };
    } catch (error: any) {
        console.error('[LDAP] Authentication error:', error.message);
        return { success: false, error: 'LDAP authentication failed' };
    }
}
```

### Vérification appartenance groupe

```typescript
async function checkLdapGroupMembership(
    config: LdapConfig,
    userDn: string,
    groupDnOrName: string
): Promise<boolean> {
    const client = new LdapClient({ url: config.serverUrl });

    try {
        if (config.bindDn && config.bindPassword) {
            await client.bind(config.bindDn, config.bindPassword);
        }

        // Détecter si DN complet ou juste nom
        const isFullDn = groupDnOrName.includes('=') && groupDnOrName.includes(',');

        let searchBase: string;
        let groupFilter: string;

        if (config.groupFilter) {
            // Filtre personnalisé
            searchBase = config.groupBaseDn || groupDnOrName;
            groupFilter = config.groupFilter
                .replace('{{username}}', userDn)
                .replace('{{user_dn}}', userDn)
                .replace('{{group}}', groupDnOrName);
        } else if (isFullDn) {
            // DN complet
            searchBase = groupDnOrName;
            groupFilter = `(member=${userDn})`;
        } else {
            // Nom de groupe seulement
            if (!config.groupBaseDn) {
                await client.unbind();
                return false;
            }
            searchBase = config.groupBaseDn;
            groupFilter = `(&(cn=${groupDnOrName})(member=${userDn}))`;
        }

        const { searchEntries } = await client.search(searchBase, {
            scope: isFullDn && !config.groupFilter ? 'base' : 'sub',
            filter: groupFilter,
            sizeLimit: 1
        });

        await client.unbind();
        return searchEntries.length > 0;
    } catch (error) {
        console.error('[LDAP] Group membership check failed:', error);
        try { await client.unbind(); } catch {}
        return false;
    }
}
```

## 6. OIDC / OAuth2

### Configuration

```sql
-- drizzle/0000_initial_schema.sql
CREATE TABLE oidc_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                 -- Keycloak, Azure AD, Google
    enabled INTEGER DEFAULT 1,
    issuer_url TEXT NOT NULL,           -- https://auth.example.com/realms/myrealm
    client_id TEXT NOT NULL,
    client_secret TEXT NOT NULL,        -- CHIFFRÉ
    redirect_uri TEXT NOT NULL,         -- https://Windflow-sample.example.com/api/auth/oidc/callback
    scopes TEXT DEFAULT 'openid profile email',
    username_claim TEXT DEFAULT 'preferred_username',
    email_claim TEXT DEFAULT 'email',
    display_name_claim TEXT DEFAULT 'name',
    admin_claim TEXT,                   -- roles
    admin_value TEXT,                   -- admin,docker-admin (comma-separated)
    role_mappings TEXT,                 -- JSON: [{"claimValue": "...", "roleId": 1}]
    role_mappings_claim TEXT DEFAULT 'groups',
    created_at TEXT DEFAULT (datetime('now'))
);
```

### Flow OIDC

```typescript
// 1. Générer URL d'autorisation
export async function buildOidcAuthorizationUrl(
    configId: number,
    redirectUrl: string = '/'
): Promise<{ url: string; state: string } | { error: string }> {
    const config = await getOidcConfig(configId);
    if (!config || !config.enabled) {
        return { error: 'OIDC configuration not found' };
    }

    try {
        const discovery = await getOidcDiscovery(config.issuerUrl);

        // Générer state, nonce, PKCE
        const state = secureRandomBytes(32).toString('base64url');
        const nonce = secureRandomBytes(16).toString('base64url');
        const { codeVerifier, codeChallenge } = generatePkce();

        // Stocker state (expire 10 min)
        oidcStateStore.set(state, {
            configId,
            codeVerifier,
            nonce,
            redirectUrl,
            expiresAt: Date.now() + 600000
        });

        // Construire URL
        const params = new URLSearchParams({
            response_type: 'code',
            client_id: config.clientId,
            redirect_uri: config.redirectUri,
            scope: config.scopes || 'openid profile email',
            state,
            nonce,
            code_challenge: codeChallenge,
            code_challenge_method: 'S256'
        });

        const authUrl = `${discovery.authorization_endpoint}?${params.toString()}`;
        return { url: authUrl, state };
    } catch (error: any) {
        return { error: error.message || 'Failed to initialize SSO' };
    }
}

// 2. Callback OIDC
export async function handleOidcCallback(
    code: string,
    state: string
): Promise<LoginResult & { redirectUrl?: string }> {
    // Valider state
    const stateData = oidcStateStore.get(state);
    if (!stateData) {
        return { success: false, error: 'Invalid or expired state' };
    }

    oidcStateStore.delete(state);

    if (stateData.expiresAt < Date.now()) {
        return { success: false, error: 'SSO session expired' };
    }

    const config = await getOidcConfig(stateData.configId);
    if (!config) {
        return { success: false, error: 'OIDC configuration not found' };
    }

    try {
        const discovery = await getOidcDiscovery(config.issuerUrl);

        // Échanger code contre tokens
        const tokenResponse = await fetch(discovery.token_endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({
                grant_type: 'authorization_code',
                code,
                redirect_uri: config.redirectUri,
                client_id: config.clientId,
                client_secret: config.clientSecret,
                code_verifier: stateData.codeVerifier
            })
        });

        if (!tokenResponse.ok) {
            return { success: false, error: 'Failed to exchange code' };
        }

        const tokens = await tokenResponse.json();

        // Décoder ID token
        let claims: Record<string, any> = {};

        if (tokens.id_token) {
            const idTokenParts = tokens.id_token.split('.');
            if (idTokenParts.length === 3) {
                claims = JSON.parse(
                    Buffer.from(idTokenParts[1], 'base64url').toString()
                );
            }
        }

        // Fetch userinfo si disponible
        if (discovery.userinfo_endpoint && tokens.access_token) {
            const userinfoResponse = await fetch(discovery.userinfo_endpoint, {
                headers: { 'Authorization': `Bearer ${tokens.access_token}` }
            });
            if (userinfoResponse.ok) {
                const userinfo = await userinfoResponse.json();
                claims = { ...claims, ...userinfo };
            }
        }

        // Valider nonce
        if (claims.nonce && claims.nonce !== stateData.nonce) {
            return { success: false, error: 'Invalid nonce' };
        }

        // Extraire infos utilisateur
        const username = claims[config.usernameClaim] 
                      || claims.preferred_username 
                      || claims.sub;
        const email = claims[config.emailClaim] || claims.email;
        const displayName = claims[config.displayNameClaim] || claims.name;

        if (!username) {
            return { success: false, error: 'Username claim not found' };
        }

        // Vérifier admin
        let shouldBeAdmin = false;
        if (config.adminClaim && config.adminValue) {
            const adminClaimValue = claims[config.adminClaim];
            const adminValues = config.adminValue.split(',').map(v => v.trim());
            
            if (Array.isArray(adminClaimValue)) {
                shouldBeAdmin = adminClaimValue.some(v => adminValues.includes(v));
            } else {
                shouldBeAdmin = adminValues.includes(adminClaimValue);
            }
        }

        const authProvider = `oidc:${config.name}`;

        // Créer ou MAJ utilisateur
        let user = await getUserByUsername(username);
        if (!user) {
            user = await createUser({
                username,
                email: email || undefined,
                displayName: displayName || undefined,
                passwordHash: '',
                authProvider
            });
        } else {
            await updateUser(user.id, {
                email: email || undefined,
                displayName: displayName || undefined,
                authProvider
            });
            user = (await getUser(user.id))!;
        }

        // Gérer rôle Admin
        const adminRole = await getRoleByName('Admin');
        if (adminRole && shouldBeAdmin) {
            const hasAdminRole = await userHasAdminRole(user.id);
            if (!hasAdminRole) {
                await assignUserRole(user.id, adminRole.id, null);
            }
        }

        // Mapper rôles depuis claims
        if (config.roleMappings) {
            const roleMappings = typeof config.roleMappings === 'string'
                ? JSON.parse(config.roleMappings)
                : config.roleMappings;

            const roleMappingsClaim = config.roleMappingsClaim || 'groups';
            const claimValue = claims[roleMappingsClaim];

            if (Array.isArray(roleMappings) && claimValue) {
                const claimValues = Array.isArray(claimValue) 
                    ? claimValue 
                    : [claimValue];

                for (const mapping of roleMappings) {
                    if (mapping.claimValue 
                        && mapping.roleId 
                        && claimValues.includes(mapping.claimValue)) {
                        await assignUserRole(user.id, mapping.roleId, null);
                    }
                }
            }
        }

        if (!user.isActive) {
            return { success: false, error: 'Account is disabled' };
        }

        // OIDC bypass MFA (authentifié via IdP)
        return {
            success: true,
            user: await buildAuthenticatedUser(user, 'oidc'),
            redirectUrl: stateData.redirectUrl,
            providerName: config.name
        };
    } catch (error: any) {
        console.error('[OIDC] Callback error:', error.message);
        return { success: false, error: 'SSO authentication failed' };
    }
}
```

## 7. MFA (TOTP) avec codes de backup

### Structure MfaData

```typescript
interface MfaData {
    secret: string;           // Secret TOTP (base32)
    backupCodes: string[];    // Codes de backup hashés (non utilisés)
}
```

### Génération du setup MFA

```typescript
export async function generateMfaSetup(userId: number): Promise<{
    secret: string;
    qrDataUrl: string;
} | null> {
    const user = await getUser(userId);
    if (!user) return null;

    // Issuer avec hostname
    const hostname = process.env.WINDFLOW_HOSTNAME || os.hostname();
    const issuer = `Windflow-sample (${hostname})`;

    // Créer secret TOTP
    const totpSecret = new OTPAuth.Secret({ size: 20 });
    const totp = new OTPAuth.TOTP({
        issuer,
        label: user.username,
        algorithm: 'SHA1',
        digits: 6,
        period: 30,
        secret: totpSecret
    });

    const secretBase32 = totp.secret.base32;
    const otpauthUrl = totp.toString();

    // Générer QR code
    const qrDataUrl = await QRCode.toDataURL(otpauthUrl, {
        width: 200,
        margin: 2
    });

    // Stocker temporairement (pas encore activé)
    const mfaData: MfaData = { secret: secretBase32, backupCodes: [] };
    await updateUser(userId, { mfaSecret: JSON.stringify(mfaData) });

    return { secret: secretBase32, qrDataUrl };
}
```

### Activation MFA avec vérification

```typescript
export async function verifyAndEnableMfa(
    userId: number,
    token: string
): Promise<{ success: false } | { success: true; backupCodes: string[] }> {
    const user = await getUser(userId);
    if (!user || !user.mfaSecret) return { success: false };

    const mfaData = parseMfaData(user.mfaSecret);
    if (!mfaData) return { success: false };

    const totp = new OTPAuth.TOTP({
        issuer: 'Windflow-sample',
        label: user.username,
        algorithm: 'SHA1',
        digits: 6,
        period: 30,
        secret: OTPAuth.Secret.fromBase32(mfaData.secret)
    });

    const delta = totp.validate({ token, window: 1 });
    if (delta === null) return { success: false };

    // Générer codes de backup
    const plainBackupCodes = generateBackupCodes();
    const hashedBackupCodes = await Promise.all(
        plainBackupCodes.map(hashBackupCode)
    );

    // Activer MFA
    const updatedMfaData: MfaData = {
        secret: mfaData.secret,
        backupCodes: hashedBackupCodes
    };
    await updateUser(userId, {
        mfaEnabled: true,
        mfaSecret: JSON.stringify(updatedMfaData)
    });

    // Retourner codes en clair (affichés une seule fois)
    return { success: true, backupCodes: plainBackupCodes };
}
```

### Vérification MFA (TOTP ou backup code)

```typescript
export async function verifyMfaToken(
    userId: number,
    token: string
): Promise<boolean> {
    const user = await getUser(userId);
    if (!user || !user.mfaEnabled || !user.mfaSecret) return false;

    const mfaData = parseMfaData(user.mfaSecret);
    if (!mfaData) return false;

    // 1. Essayer TOTP
    const totp = new OTPAuth.TOTP({
        issuer: 'Windflow-sample',
        label: user.username,
        algorithm: 'SHA1',
        digits: 6,
        period: 30,
        secret: OTPAuth.Secret.fromBase32(mfaData.secret)
    });

    const delta = totp.validate({ token, window: 1 });
    if (delta !== null) return true;

    // 2. Essayer backup code
    if (mfaData.backupCodes && mfaData.backupCodes.length > 0) {
        const hashedInput = await hashBackupCode(token);
        const codeIndex = mfaData.backupCodes.indexOf(hashedInput);

        if (codeIndex !== -1) {
            // Retirer code utilisé
            const updatedBackupCodes = [...mfaData.backupCodes];
            updatedBackupCodes.splice(codeIndex, 1);

            const updatedMfaData: MfaData = {
                secret: mfaData.secret,
                backupCodes: updatedBackupCodes
            };
            await updateUser(userId, {
                mfaSecret: JSON.stringify(updatedMfaData)
            });

            return true;
        }
    }

    return false;
}
```

### Génération des codes de backup

```typescript
function generateBackupCodes(): string[] {
    const codes: string[] = [];
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // Sans 0,O,1,I
    
    for (let i = 0; i < 10; i++) {
        let code = '';
        for (let j = 0; j < 8; j++) {
            code += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        codes.push(code);
    }
    
    return codes;
}

async function hashBackupCode(code: string): Promise<string> {
    // Normaliser: majuscules, sans espaces/tirets
    const normalized = code.toUpperCase().replace(/[\s-]/g, '');
    const hasher = new Poetry.CryptoHasher('sha256');
    hasher.update(normalized);
    return hasher.digest('hex');
}
```

## 8. Permissions et RBAC

### Structure des permissions

```typescript
interface Permissions {
    containers: string[];      // ['view', 'start', 'stop', 'create', 'delete', 'exec']
    images: string[];         // ['view', 'pull', 'push', 'delete']
    volumes: string[];        // ['view', 'create', 'delete']
    networks: string[];       // ['view', 'create', 'delete']
    stacks: string[];         // ['view', 'deploy', 'delete']
    environments: string[];   // ['view', 'manage']
    registries: string[];     // ['view', 'manage']
    notifications: string[];  // ['view', 'manage']
    configsets: string[];     // ['view', 'manage']
    settings: string[];       // ['view', 'manage']
    users: string[];          // ['view', 'manage']
    git: string[];            // ['view', 'manage']
    license: string[];        // ['view', 'manage']
    audit_logs: string[];     // ['view']
    activity: string[];       // ['view']
    schedules: string[];      // ['view', 'manage']
}
```

### Vérification de permission

```typescript
export async function checkPermission(
    user: AuthenticatedUser,
    resource: keyof Permissions,
    action: string,
    environmentId?: number
): Promise<boolean> {
    // Free edition: tous les utilisateurs ont accès complet
    if (!(await isEnterprise())) return true;

    // Admins: accès complet
    if (await userHasAdminRole(user.id)) return true;

    // Permissions spécifiques à l'environnement
    if (environmentId !== undefined) {
        const permissions = await getUserPermissionsForEnvironment(
            user.id,
            environmentId
        );
        return permissions[resource]?.includes(action) ?? false;
    }

    // Permissions globales
    return user.permissions[resource]?.includes(action) ?? false;
}
```

### Middleware de permission

```typescript
// routes/api/containers/[id]/start/+server.ts
import { checkPermission } from '$lib/server/auth';

export async function POST({ params, locals }) {
    const user = locals.user;
    if (!user) {
        return json({ error: 'Unauthorized' }, { status: 401 });
    }

    const envId = Number(params.envId);
    const hasPermission = await checkPermission(
        user,
        'containers',
        'start',
        envId
    );

    if (!hasPermission) {
        return json({ error: 'Permission denied' }, { status: 403 });
    }

    // Démarrer le conteneur...
    return json({ success: true });
}
```

## 9. Sécurité

### Mesures de sécurité implémentées

1. **Hashing robuste**
   - Argon2id (memory-hard, résistant GPU)
   - Fallback hash-wasm pour vieux kernels
   - Salt unique par mot de passe

2. **Sessions sécurisées**
   - Tokens cryptographiques (256 bits)
   - Cookies HttpOnly (XSS protection)
   - Secure flag en production (HTTPS only)
   - SameSite=Strict (CSRF protection)

3. **Rate limiting**
   - 5 tentatives max en 15 minutes
   - Blocage 15 minutes après 5 échecs
   - Par username ET par IP

4. **Protection timing attacks**
   - Constant-time password verification
   - Dummy hash sur username invalide

5. **MFA**
   - TOTP standard (RFC 6238)
   - Codes de backup hashés SHA-256
   - QR code pour setup facile

6. **LDAP sécurisé**
   - TLS optionnel
   - Validation certificat CA
   - Bind de service séparé

7. **OIDC sécurisé**
   - PKCE (code_challenge)
   - State pour CSRF protection
   - Nonce validation
   - Discovery automatique

### Recommandations production

```bash
# 1. Variables d'environnement
NODE_ENV=production
ENCRYPTION_KEY=<generated-key>
ORIGIN=https://Windflow-sample.example.com

# 2. HTTPS obligatoire
# Utiliser reverse proxy (Nginx, Traefik)

# 3. Session timeout
# Configurer dans Settings > Auth (défaut: 24h)

# 4. Activer authentification
# Settings > Auth > Enable Authentication

# 5. MFA recommandée pour admins
# User Profile > Security > Enable MFA

# 6. Rate limiting
# Déjà activé par défaut (in-memory)
# Pour multi-instance: utiliser Redis

# 7. Audit logs
# Enterprise: logs d'authentification automatiques
```

---

[← Base de données](03-DATABASE-SCHEMA.md) | [Suivant : Git Integration →](05-GIT-INTEGRATION.md)
