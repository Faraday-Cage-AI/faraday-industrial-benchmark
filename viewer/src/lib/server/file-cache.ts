import { readFile, stat } from 'node:fs/promises';

export interface CachedFile<T> {
	value: T;
	modified: Date;
}

/** Parses a file once and reuses the result until its size or modification time changes. */
export function fileCache<T>(parse: (text: string) => T): (file: string) => Promise<CachedFile<T>> {
	const entries = new Map<string, { stamp: string; entry: CachedFile<T> }>();
	return async (file) => {
		const info = await stat(file);
		const stamp = `${info.mtimeMs}:${info.size}`;
		const hit = entries.get(file);
		if (hit?.stamp === stamp) return hit.entry;
		const entry = { value: parse(await readFile(file, 'utf8')), modified: info.mtime };
		entries.set(file, { stamp, entry });
		return entry;
	};
}
