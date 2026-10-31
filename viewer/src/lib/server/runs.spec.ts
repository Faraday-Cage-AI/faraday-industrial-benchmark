import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import {
	appearanceKey,
	findTaskInRuns,
	getRun,
	indexRunAppearances,
	listRuns,
	runSlug
} from './runs.js';

let root: string;

function runFile(agent: string, score: number): string {
	return JSON.stringify({
		schema_version: 'faraday-industrial-run/3',
		benchmark_version: '0.6.0',
		agent,
		summary: {
			tasks: 1,
			families: 1,
			mean_score: score,
			strict_successes: score === 100 ? 1 : 0,
			critical_failures: 0,
			tool_calls: 3
		},
		family_summaries: {},
		capability_summaries: {},
		results: [
			{
				task: { id: 'faraday-quality-001', version: '0.2.3' },
				agent,
				score: { score, strict_success: score === 100, critical_failure: false },
				final_answer: {},
				trace: [],
				initial_state_hash: '',
				final_state_hash: '',
				applied_events: []
			}
		]
	});
}

beforeAll(async () => {
	root = await mkdtemp(path.join(tmpdir(), 'faraday-viewer-runs-'));
	await mkdir(path.join(root, 'runs', 'nested'), { recursive: true });
	await mkdir(path.join(root, 'reports'), { recursive: true });
	await writeFile(path.join(root, 'runs', 'nested', 'model.json'), runFile('model-a', 72));
	await writeFile(path.join(root, 'reports', 'oracle-run.json'), runFile('reference-oracle', 100));
	await writeFile(
		path.join(root, 'reports', 'qualification.json'),
		JSON.stringify({ schema_version: 'faraday-qualification/1' })
	);
	await writeFile(path.join(root, 'reports', 'broken.json'), '{ not json');
});

afterAll(async () => {
	await rm(root, { recursive: true, force: true });
});

describe('runSlug', () => {
	it('turns a relative path into a URL-safe slug', () => {
		expect(runSlug('reports/oracle-run.json')).toBe('reports--oracle-run');
		expect(runSlug('runs/nested/model.json')).toBe('runs--nested--model');
	});
});

describe('listRuns', () => {
	it('keeps run files, including nested ones, and skips other JSON', async () => {
		const runs = await listRuns(root);

		expect(runs.map((run) => run.slug).sort()).toEqual(['reports--oracle-run', 'runs--nested--model']);
	});
});

describe('getRun', () => {
	it('looks runs up by slug only', async () => {
		expect((await getRun('reports--oracle-run', root))?.run.agent).toBe('reference-oracle');
		expect(await getRun('reports--qualification', root)).toBeUndefined();
		expect(await getRun('../reports/oracle-run', root)).toBeUndefined();
	});
});

describe('indexRunAppearances', () => {
	it('groups run episodes by task ID and version', async () => {
		const index = await indexRunAppearances(root);

		expect([...index.keys()]).toEqual([appearanceKey('faraday-quality-001', '0.2.3')]);
		expect(index.get(appearanceKey('faraday-quality-001', '0.2.3'))).toHaveLength(2);
	});
});

describe('findTaskInRuns', () => {
	it('finds every run episode of one task version', async () => {
		const appearances = await findTaskInRuns('faraday-quality-001', '0.2.3', root);

		expect(appearances.map((item) => [item.agent, item.score]).sort()).toEqual([
			['model-a', 72],
			['reference-oracle', 100]
		]);
		expect(await findTaskInRuns('faraday-quality-001', '0.1.0', root)).toEqual([]);
	});
});
