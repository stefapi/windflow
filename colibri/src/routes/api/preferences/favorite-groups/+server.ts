import { json, type RequestHandler } from '@sveltejs/kit';
import { getUserPreference, setUserPreference } from '$lib/server/db';
import { authorize } from '$lib/server/authorize';

const LOGS_FAVORITE_GROUPS_KEY = 'logs_favorite_groups';

// Favorite groups are stored as an array of { name: string, containers: string[] }
// Per environment, so environmentId is required

export interface FavoriteGroup {
	name: string;
	containers: string[]; // Container names (not IDs, since IDs change on recreate)
}

export const GET: RequestHandler = async ({ url, cookies }) => {
	const auth = await authorize(cookies);

	try {
		const envId = url.searchParams.get('env');
		if (!envId) {
			return json({ error: 'Environment ID is required' }, { status: 400 });
		}

		const environmentId = parseInt(envId);
		if (isNaN(environmentId)) {
			return json({ error: 'Invalid environment ID' }, { status: 400 });
		}

		// userId is null for free edition (shared prefs), set for enterprise
		const userId = auth.user?.id ?? null;

		const groups = await getUserPreference<FavoriteGroup[]>({
			userId,
			environmentId,
			key: LOGS_FAVORITE_GROUPS_KEY
		});

		return json({ groups: groups ?? [] });
	} catch (error) {
		console.error('Failed to get favorite groups:', error);
		return json({ error: 'Failed to get favorite groups' }, { status: 500 });
	}
};

export const POST: RequestHandler = async ({ request, cookies }) => {
	const auth = await authorize(cookies);

	try {
		const body = await request.json();
		const { environmentId, action, name, containers, newName } = body;

		if (!environmentId || typeof environmentId !== 'number') {
			return json({ error: 'Environment ID is required' }, { status: 400 });
		}

		if (!action || !['add', 'remove', 'update', 'reorder'].includes(action)) {
			return json({ error: 'Action must be "add", "remove", "update", or "reorder"' }, { status: 400 });
		}

		// userId is null for free edition (shared prefs), set for enterprise
		const userId = auth.user?.id ?? null;

		// Get current groups
		const currentGroups = await getUserPreference<FavoriteGroup[]>({
			userId,
			environmentId,
			key: LOGS_FAVORITE_GROUPS_KEY
		}) ?? [];

		let newGroups: FavoriteGroup[];

		if (action === 'add') {
			// Add a new group
			if (!name || typeof name !== 'string') {
				return json({ error: 'Group name is required' }, { status: 400 });
			}
			if (!Array.isArray(containers) || containers.length === 0) {
				return json({ error: 'Containers array is required and must not be empty' }, { status: 400 });
			}

			// Check for duplicate name
			if (currentGroups.some(g => g.name === name)) {
				return json({ error: 'A group with this name already exists' }, { status: 400 });
			}

			newGroups = [...currentGroups, { name, containers }];
		} else if (action === 'remove') {
			// Remove a group by name
			if (!name || typeof name !== 'string') {
				return json({ error: 'Group name is required' }, { status: 400 });
			}

			newGroups = currentGroups.filter(g => g.name !== name);
		} else if (action === 'update') {
			// Update a group (rename or change containers)
			if (!name || typeof name !== 'string') {
				return json({ error: 'Group name is required' }, { status: 400 });
			}

			const groupIndex = currentGroups.findIndex(g => g.name === name);
			if (groupIndex === -1) {
				return json({ error: 'Group not found' }, { status: 404 });
			}

			// Check for duplicate name if renaming
			if (newName && newName !== name && currentGroups.some(g => g.name === newName)) {
				return json({ error: 'A group with this name already exists' }, { status: 400 });
			}

			newGroups = [...currentGroups];
			newGroups[groupIndex] = {
				name: newName || name,
				containers: Array.isArray(containers) ? containers : currentGroups[groupIndex].containers
			};
		} else {
			// Reorder: replace entire array
			if (!Array.isArray(body.groups)) {
				return json({ error: 'groups array is required for reorder action' }, { status: 400 });
			}
			newGroups = body.groups;
		}

		// Save updated groups
		await setUserPreference(
			{ userId, environmentId, key: LOGS_FAVORITE_GROUPS_KEY },
			newGroups
		);

		return json({ groups: newGroups });
	} catch (error) {
		console.error('Failed to update favorite groups:', error);
		return json({ error: 'Failed to update favorite groups' }, { status: 500 });
	}
};
