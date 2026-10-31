export function formatScore(value: number): string {
	return value.toFixed(1);
}

export function formatPercent(value: number): string {
	return `${(value * 100).toFixed(1)}%`;
}

/** `part / total` as a percentage, or a dash when there is nothing to divide by. */
export function formatRate(part: number, total: number): string {
	return total > 0 ? formatPercent(part / total) : '—';
}

const count = new Intl.NumberFormat('en-US');

export function formatCount(value: number): string {
	return count.format(value);
}

const money = new Intl.NumberFormat('en-US', {
	style: 'currency',
	currency: 'USD',
	notation: 'compact',
	maximumFractionDigits: 1
});

export function formatMoney(value: number): string {
	return money.format(value);
}

const dateTime = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' });

export function formatDate(iso: string): string {
	return dateTime.format(new Date(iso));
}

/** `quality_drift` becomes `Quality drift`. */
export function humanize(value: string): string {
	const words = value.replace(/[_-]+/g, ' ').trim();
	return words.charAt(0).toUpperCase() + words.slice(1);
}

export type ScoreTone = 'good' | 'mixed' | 'poor';

export function scoreTone(score: number): ScoreTone {
	if (score >= 90) return 'good';
	if (score >= 60) return 'mixed';
	return 'poor';
}

export const TONE_TEXT: Record<ScoreTone, string> = {
	good: 'text-emerald-700',
	mixed: 'text-amber-700',
	poor: 'text-red-700'
};

export type Outcome = 'strict' | 'partial' | 'critical';

export const OUTCOME_LABELS: Record<Outcome, string> = {
	strict: 'Strict success',
	partial: 'Partial',
	critical: 'Critical failure'
};

export function outcomeOf(episode: { strict_success: boolean; critical_failure: boolean }): Outcome {
	if (episode.critical_failure) return 'critical';
	return episode.strict_success ? 'strict' : 'partial';
}
