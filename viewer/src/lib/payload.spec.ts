import { describe, expect, it } from 'vitest';
import { describePayload, formatValue } from './payload.js';

describe('formatValue', () => {
	it('keeps strings, joins lists of plain values, and writes everything else as JSON', () => {
		expect(formatValue('LOT-1')).toBe('LOT-1');
		expect(formatValue(['LOT-1', 'LOT-2'])).toBe('LOT-1, LOT-2');
		expect(formatValue(24000)).toBe('24000');
		expect(formatValue(true)).toBe('true');
		expect(formatValue(null)).toBe('null');
		expect(formatValue([])).toBe('[]');
		expect(formatValue({ a: 1 })).toBe('{"a":1}');
	});
});

describe('describePayload', () => {
	it('shows a message as prose with its sender', () => {
		const view = describePayload({ sender: 'shipping', subject: 'Cutoff', body: 'Lots ship soon.' });

		expect(view.sender).toBe('shipping');
		expect(view.prose).toEqual([
			{ key: 'subject', value: 'Cutoff' },
			{ key: 'body', value: 'Lots ship soon.' }
		]);
		expect(view.fields).toEqual([]);
	});

	it('lists flat values, groups flat objects, and keeps deeper values as JSON', () => {
		const sections = { orders: [{ order_id: 'SO-1', packs: 3 }] };
		const view = describePayload({
			file_id: 'CRM',
			version: 2,
			lot_ids: ['A', 'B'],
			facts: { datum: 'A', finish: 'Ra 1.6 um' },
			sections,
			message: 'Revision C is authoritative.'
		});

		expect(view.fields).toEqual([
			{ key: 'file_id', value: 'CRM' },
			{ key: 'version', value: '2' },
			{ key: 'lot_ids', value: 'A, B' }
		]);
		expect(view.groups).toEqual([
			{
				key: 'facts',
				fields: [
					{ key: 'datum', value: 'A' },
					{ key: 'finish', value: 'Ra 1.6 um' }
				]
			}
		]);
		expect(view.nested).toEqual([{ key: 'sections', value: sections }]);
		expect(view.prose).toEqual([{ key: 'message', value: 'Revision C is authoritative.' }]);
	});
});
