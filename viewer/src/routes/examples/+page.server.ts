import { listTaskSets, summarizeTaskSet } from '#lib/server/tasks.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	return { sets: (await listTaskSets()).map(summarizeTaskSet) };
};
