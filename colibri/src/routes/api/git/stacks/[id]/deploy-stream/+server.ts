import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getGitStack } from '$lib/server/db';
import { deployGitStackWithProgress } from '$lib/server/git';
import { authorize } from '$lib/server/authorize';

export const POST: RequestHandler = async ({ params, cookies }) => {
	const auth = await authorize(cookies);

	const id = parseInt(params.id);
	const gitStack = await getGitStack(id);

	if (!gitStack) {
		return new Response(JSON.stringify({ error: 'Git stack not found' }), {
			status: 404,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	// Permission check with environment context
	if (auth.authEnabled && !await auth.can('stacks', 'start', gitStack.environmentId || undefined)) {
		return new Response(JSON.stringify({ error: 'Permission denied' }), {
			status: 403,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	// Create a readable stream for SSE
	const stream = new ReadableStream({
		async start(controller) {
			const encoder = new TextEncoder();

			const sendEvent = (data: any) => {
				controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
			};

			try {
				await deployGitStackWithProgress(id, sendEvent);
			} catch (error: any) {
				sendEvent({ status: 'error', error: error.message || 'Unknown error' });
			} finally {
				controller.close();
			}
		}
	});

	return new Response(stream, {
		headers: {
			'Content-Type': 'text/event-stream',
			'Cache-Control': 'no-cache',
			'Connection': 'keep-alive'
		}
	});
};
