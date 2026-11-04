import { error } from '@sveltejs/kit';
import { getRun } from '#lib/server/runs.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params }) => {
	const found = await getRun(params.run);
	if (!found) error(404, `No run file matches "${params.run}".`);
	const { listing, run } = found;

	// The run page lists episodes only, so traces and criteria stay on the server.
	return {
		listing,
		families: Object.entries(run.family_summaries).map(([name, summary]) => ({ name, ...summary })),
		capabilities: Object.entries(run.capability_summaries).map(([name, summary]) => ({
			name,
			...summary
		})),
		episodes: run.results.map(({ task, score }) => ({
			id: task.id,
			version: task.version,
			title: task.title,
			family: task.family,
			difficulty: task.difficulty,
			score: score.score,
			strict_success: score.strict_success,
			critical_failure: score.critical_failure,
			criteria_passed: score.criteria.filter((criterion) => criterion.passed).length,
			criteria_total: score.criteria.length,
			tool_calls: score.tool_calls,
			max_tool_calls: task.max_tool_calls,
			elapsed_minutes: score.elapsed_minutes,
			horizon_minutes: task.horizon_minutes,
			violations: score.violations.length
		}))
	};
};
