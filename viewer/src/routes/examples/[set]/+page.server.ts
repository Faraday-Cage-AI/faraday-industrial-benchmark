import { error } from '@sveltejs/kit';
import { appearanceKey, indexRunAppearances } from '#lib/server/runs.js';
import { getTaskSet, summarizeTaskSet } from '#lib/server/tasks.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params }) => {
	const set = await getTaskSet(params.set);
	if (!set) error(404, `No task set named "${params.set}" under data/.`);
	const appearances = await indexRunAppearances();

	return {
		summary: summarizeTaskSet(set),
		episodes: set.tasks.map((task) => ({
			id: task.id,
			version: task.version,
			title: task.title,
			family: task.family,
			difficulty: task.difficulty,
			tags: task.tags,
			systems: task.systems.length,
			max_tool_calls: task.max_tool_calls,
			horizon_minutes: task.horizon_minutes,
			runs: appearances.get(appearanceKey(task.id, task.version))?.length ?? 0
		}))
	};
};
