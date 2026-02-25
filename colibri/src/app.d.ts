// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces

import type { AuthenticatedUser } from '$lib/server/auth';

// Build-time constants injected by Vite
declare const __BUILD_DATE__: string | null;
declare const __BUILD_COMMIT__: string | null;

declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			user: AuthenticatedUser | null;
			authEnabled: boolean;
		}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
