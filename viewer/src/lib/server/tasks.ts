import { readdir } from 'node:fs/promises';
import path from 'node:path';
import type { Task, TaskSetListing } from '#lib/types.js';
import { fileCache } from './file-cache.js';
import { REPO_ROOT } from './repo.js';

export interface TaskSet {
	name: string;
	/** Path relative to the repository root. */
	path: string;
	tasks: Task[];
}

type RawTask = Partial<Task> & Pick<Task, 'id' | 'family' | 'title' | 'prompt'>;

// Mirrors the defaults in `IncidentTask.from_dict`.
function normalizeTask(raw: RawTask): Task {
	return {
		...raw,
		version: raw.version ?? '0.6.0',
		difficulty: raw.difficulty ?? 'medium',
		systems: raw.systems ?? [],
		max_tool_calls: raw.max_tool_calls ?? 30,
		horizon_minutes: raw.horizon_minutes ?? 60,
		tags: raw.tags ?? [],
		controlled_plan_actions: raw.controlled_plan_actions ?? []
	};
}

// Like `load_tasks`, a task file holds either a list of tasks or a single task.
const readTaskFile = fileCache((text) => {
	const payload: unknown = JSON.parse(text);
	const records = Array.isArray(payload) ? payload : [payload];
	return records.map((record) => normalizeTask(record as RawTask));
});

/** Every `data/<set>/tasks.json`, with the public suite first. */
export async function listTaskSets(root = REPO_ROOT): Promise<TaskSet[]> {
	const dataDirectory = path.join(root, 'data');
	let entries;
	try {
		entries = await readdir(dataDirectory, { withFileTypes: true });
	} catch {
		return [];
	}
	const sets = await Promise.all(
		entries
			.filter((entry) => entry.isDirectory())
			.map(async (entry): Promise<TaskSet | null> => {
				const file = path.join(dataDirectory, entry.name, 'tasks.json');
				try {
					const { value } = await readTaskFile(file);
					return { name: entry.name, path: path.relative(root, file), tasks: value };
				} catch (error) {
					if ((error as NodeJS.ErrnoException).code !== 'ENOENT') {
						console.warn(`Skipping unreadable task file ${file}:`, error);
					}
					return null;
				}
			})
	);
	return sets
		.filter((set): set is TaskSet => set !== null)
		.sort(
			(a, b) =>
				Number(b.name === 'public') - Number(a.name === 'public') || a.name.localeCompare(b.name)
		);
}

export async function getTaskSet(name: string, root = REPO_ROOT): Promise<TaskSet | undefined> {
	return (await listTaskSets(root)).find((set) => set.name === name);
}

export function summarizeTaskSet(set: TaskSet): TaskSetListing {
	const unique = (values: string[]) => [...new Set(values)].sort();
	return {
		name: set.name,
		path: set.path,
		tasks: set.tasks.length,
		families: unique(set.tasks.map((task) => task.family)),
		versions: unique(set.tasks.map((task) => task.version)),
		difficulties: unique(set.tasks.map((task) => task.difficulty))
	};
}

/**
 * Finds the task a run episode came from. Runs record a task's ID and version but not
 * its seed or task file, and the same ID appears in several versioned task sets.
 */
export async function findTask(
	id: string,
	version: string,
	root = REPO_ROOT
): Promise<{ set: TaskSet; task: Task } | undefined> {
	for (const set of await listTaskSets(root)) {
		const task = set.tasks.find((item) => item.id === id && item.version === version);
		if (task) return { set, task };
	}
	return undefined;
}
