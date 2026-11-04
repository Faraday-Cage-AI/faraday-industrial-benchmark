export type JsonTokenKind = 'key' | 'string' | 'number' | 'literal' | 'plain';

export interface JsonToken {
	kind: JsonTokenKind;
	text: string;
	/** Offset of the token's first character in the source. */
	start: number;
}

// A string followed by a colon is an object key.
const TOKEN = /("(?:[^"\\]|\\.)*")(\s*:)?|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\b(?:true|false|null)\b/g;

export function formatJson(value: unknown): string {
	return JSON.stringify(value, null, 2) ?? String(value);
}

/** Splits JSON text into tokens for coloring. Text between tokens is `plain`. */
export function tokenizeJson(source: string): JsonToken[] {
	const tokens: JsonToken[] = [];
	let last = 0;
	for (const match of source.matchAll(TOKEN)) {
		const [text, quoted, colon] = match;
		const start = match.index;
		if (start > last) tokens.push({ kind: 'plain', text: source.slice(last, start), start: last });
		if (quoted === undefined) {
			tokens.push({ kind: /^[a-z]/.test(text) ? 'literal' : 'number', text, start });
		} else if (colon === undefined) {
			tokens.push({ kind: 'string', text: quoted, start });
		} else {
			tokens.push(
				{ kind: 'key', text: quoted, start },
				{ kind: 'plain', text: colon, start: start + quoted.length }
			);
		}
		last = start + text.length;
	}
	if (last < source.length) tokens.push({ kind: 'plain', text: source.slice(last), start: last });
	return tokens;
}
