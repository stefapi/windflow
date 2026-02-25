import type { PageServerLoad } from './$types';
import { getScannerSettings } from '$lib/server/scanner';

export const load: PageServerLoad = async () => {
	const { scanner } = await getScannerSettings();
	return {
		scannerEnabled: scanner !== 'none'
	};
};
