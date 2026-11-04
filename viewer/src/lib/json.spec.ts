import { describe, expect, it } from 'vitest';
import { formatJson, tokenizeJson } from './json.js';

describe('tokenizeJson', () => {
	it('classifies keys, strings, numbers and literals without dropping text', () => {
		const source = formatJson({ id: 'LOT-1', count: -2.5e3, ok: true, note: null, tags: ['a: b'] });
		const tokens = tokenizeJson(source);

		expect(tokens.map((token) => token.text).join('')).toBe(source);
		for (const token of tokens) {
			expect(source.slice(token.start, token.start + token.text.length)).toBe(token.text);
		}
		expect(
			tokens.filter((token) => token.kind !== 'plain').map((token) => `${token.kind} ${token.text}`)
		).toEqual([
			'key "id"',
			'string "LOT-1"',
			'key "count"',
			'number -2500',
			'key "ok"',
			'literal true',
			'key "note"',
			'literal null',
			'key "tags"',
			'string "a: b"'
		]);
	});

	it('keeps escaped quotes inside one string token', () => {
		const tokens = tokenizeJson(JSON.stringify({ say: 'a "quoted" word' }));

		expect(tokens.filter((token) => token.kind === 'string').map((token) => token.text)).toEqual([
			'"a \\"quoted\\" word"'
		]);
	});
});
