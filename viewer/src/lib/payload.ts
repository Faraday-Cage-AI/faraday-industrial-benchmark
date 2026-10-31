type Primitive = string | number | boolean | null;

export interface Field {
	key: string;
	value: string;
}

export interface PayloadView {
	/** Who sent a message-like event. */
	sender?: string;
	/** Free text, shown as sentences. */
	prose: Field[];
	/** Values that fit on one line. */
	fields: Field[];
	/** Objects whose values all fit on one line, such as `facts`. */
	groups: { key: string; fields: Field[] }[];
	/** Anything deeper, shown as JSON. */
	nested: { key: string; value: unknown }[];
}

const PROSE_KEYS = new Set(['subject', 'body', 'message', 'note', 'finding', 'reason']);

function isPrimitive(value: unknown): value is Primitive {
	return (
		value === null ||
		typeof value === 'string' ||
		typeof value === 'number' ||
		typeof value === 'boolean'
	);
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isFlat(value: unknown): boolean {
	return (
		isPrimitive(value) ||
		(Array.isArray(value) && value.every(isPrimitive)) ||
		(isRecord(value) && Object.keys(value).length === 0)
	);
}

/** Strings stay as they are, lists of plain values are joined, and everything else becomes JSON. */
export function formatValue(value: unknown): string {
	if (typeof value === 'string') return value;
	if (Array.isArray(value) && value.length > 0 && value.every(isPrimitive)) {
		return value.map(formatValue).join(', ');
	}
	return JSON.stringify(value) ?? String(value);
}

export function toFields(record: Record<string, unknown>): Field[] {
	return Object.entries(record).map(([key, value]) => ({ key, value: formatValue(value) }));
}

/** Sorts an event payload's entries by how they read best: as text, as a field list, or as JSON. */
export function describePayload(payload: Record<string, unknown>): PayloadView {
	const view: PayloadView = { prose: [], fields: [], groups: [], nested: [] };
	for (const [key, value] of Object.entries(payload)) {
		if (key === 'sender' && typeof value === 'string') view.sender = value;
		else if (PROSE_KEYS.has(key) && typeof value === 'string') view.prose.push({ key, value });
		else if (isFlat(value)) view.fields.push({ key, value: formatValue(value) });
		else if (isRecord(value) && Object.values(value).every(isFlat)) {
			view.groups.push({ key, fields: toFields(value) });
		} else view.nested.push({ key, value });
	}
	return view;
}
