import { REPO_ROOT } from '#lib/server/repo.js';
import { listRuns } from '#lib/server/runs.js';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	return { runs: await listRuns(), repoRoot: REPO_ROOT };
};
