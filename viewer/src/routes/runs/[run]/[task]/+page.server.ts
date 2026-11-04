import { error } from '@sveltejs/kit';
import { getRun } from '#lib/server/runs.js';
import { replayEpisode } from '#lib/server/scenarios.js';
import { findTask } from '#lib/server/tasks.js';
import type { ReplayResult } from '#lib/types.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params }) => {
	const found = await getRun(params.run);
	if (!found) error(404, `No run file matches "${params.run}".`);
	const { listing, run } = found;
	const index = run.results.findIndex((result) => result.task.id === params.task);
	if (index === -1) error(404, `${listing.path} has no episode "${params.task}".`);
	const result = run.results[index];

	const source = await findTask(result.task.id, result.task.version);
	// Streamed, so the page renders before the Python helper finishes.
	const replay: Promise<ReplayResult> = source
		? replayEpisode(listing.path, source.set.path, result.task)
		: Promise.resolve({
				ok: false,
				message: `No task file under data/ contains ${result.task.id} version ${result.task.version}.`
			});

	return {
		listing,
		result,
		taskSet: source?.set.name ?? null,
		previous: run.results[index - 1]?.task.id ?? null,
		next: run.results[index + 1]?.task.id ?? null,
		replay
	};
};
