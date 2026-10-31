import { error } from '@sveltejs/kit';
import { findTaskInRuns } from '#lib/server/runs.js';
import { loadScenario } from '#lib/server/scenarios.js';
import { getTaskSet } from '#lib/server/tasks.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params }) => {
	const set = await getTaskSet(params.set);
	if (!set) error(404, `No task set named "${params.set}" under data/.`);
	const index = set.tasks.findIndex((task) => task.id === params.task);
	if (index === -1) error(404, `${set.path} has no episode "${params.task}".`);
	const task = set.tasks[index];

	// Start the Python helper before reading runs; the page streams its result.
	const scenario = loadScenario(set.path, task);

	return {
		set: { name: set.name, path: set.path },
		task,
		previous: set.tasks[index - 1]?.id ?? null,
		next: set.tasks[index + 1]?.id ?? null,
		appearances: await findTaskInRuns(task.id, task.version),
		scenario
	};
};
