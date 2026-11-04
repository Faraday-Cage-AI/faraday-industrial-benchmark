import { readdir } from 'node:fs/promises';
import path from 'node:path';
import type { Run, RunListing, TaskAppearance } from '#lib/types.js';
import { fileCache } from './file-cache.js';
import { REPO_ROOT } from './repo.js';

const RUN_SCHEMA_PREFIX = 'faraday-industrial-run/';
const RUN_DIRECTORIES = ['runs', 'reports'];
const MAX_DEPTH = 3;

const readRunFile = fileCache((text): Run | null => {
	try {
		const value: unknown = JSON.parse(text);
		return isRun(value) ? value : null;
	} catch {
		return null;
	}
});

function isRun(value: unknown): value is Run {
	if (typeof value !== 'object' || value === null) return false;
	const candidate = value as Partial<Run>;
	return (
		typeof candidate.schema_version === 'string' &&
		candidate.schema_version.startsWith(RUN_SCHEMA_PREFIX) &&
		Array.isArray(candidate.results)
	);
}

/** Turns `reports/oracle-run.json` into the URL-safe `reports--oracle-run`. */
export function runSlug(relativePath: string): string {
	return relativePath
		.replace(/\.json$/i, '')
		.split(/[\\/]/)
		.join('--');
}

async function findJsonFiles(directory: string, depth: number): Promise<string[]> {
	let entries;
	try {
		entries = await readdir(directory, { withFileTypes: true });
	} catch {
		return [];
	}
	const nested = await Promise.all(
		entries.map(async (entry) => {
			const full = path.join(directory, entry.name);
			if (entry.isDirectory()) return depth > 0 ? findJsonFiles(full, depth - 1) : [];
			return entry.isFile() && entry.name.endsWith('.json') ? [full] : [];
		})
	);
	return nested.flat();
}

/** Every run file under `runs/` and `reports/`, newest first. Other JSON files are skipped. */
export async function listRuns(root = REPO_ROOT): Promise<RunListing[]> {
	const files = (
		await Promise.all(
			RUN_DIRECTORIES.map((directory) => findJsonFiles(path.join(root, directory), MAX_DEPTH))
		)
	).flat();
	const listings = await Promise.all(
		files.map(async (file): Promise<RunListing | null> => {
			const loaded = await readRunFile(file).catch(() => null);
			if (!loaded?.value) return null;
			const { value: run, modified } = loaded;
			const relative = path.relative(root, file);
			return {
				slug: runSlug(relative),
				path: relative,
				agent: run.agent,
				benchmark_version: run.benchmark_version,
				schema_version: run.schema_version,
				modified: modified.toISOString(),
				summary: run.summary
			};
		})
	);
	return listings
		.filter((listing): listing is RunListing => listing !== null)
		.sort((a, b) => b.modified.localeCompare(a.modified) || a.path.localeCompare(b.path));
}

export async function getRun(
	slug: string,
	root = REPO_ROOT
): Promise<{ listing: RunListing; run: Run } | undefined> {
	const listing = (await listRuns(root)).find((item) => item.slug === slug);
	if (!listing) return undefined;
	const { value: run } = await readRunFile(path.join(root, listing.path));
	return run ? { listing, run } : undefined;
}

export function appearanceKey(taskId: string, version: string): string {
	return `${taskId}@${version}`;
}

/** Every saved run episode, grouped by `appearanceKey` and ordered like `listRuns`. */
export async function indexRunAppearances(
	root = REPO_ROOT
): Promise<Map<string, TaskAppearance[]>> {
	const index = new Map<string, TaskAppearance[]>();
	for (const listing of await listRuns(root)) {
		const loaded = await readRunFile(path.join(root, listing.path)).catch(() => null);
		for (const result of loaded?.value?.results ?? []) {
			const key = appearanceKey(result.task.id, result.task.version);
			const appearances = index.get(key) ?? [];
			appearances.push({
				slug: listing.slug,
				agent: listing.agent,
				path: listing.path,
				score: result.score.score,
				strict_success: result.score.strict_success,
				critical_failure: result.score.critical_failure
			});
			index.set(key, appearances);
		}
	}
	return index;
}

/** Every saved run episode of one task version. */
export async function findTaskInRuns(
	taskId: string,
	version: string,
	root = REPO_ROOT
): Promise<TaskAppearance[]> {
	return (await indexRunAppearances(root)).get(appearanceKey(taskId, version)) ?? [];
}
