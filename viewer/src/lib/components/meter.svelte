<script lang="ts">
	import type { ScoreTone } from '#lib/format.js';
	import { cn } from '#lib/utils.js';

	let {
		value,
		label,
		tone,
		class: className
	}: {
		/** Between 0 and 1. */
		value: number;
		label: string;
		tone?: ScoreTone;
		class?: string;
	} = $props();

	const FILLS: Record<ScoreTone, string> = {
		good: 'bg-emerald-500',
		mixed: 'bg-amber-500',
		poor: 'bg-red-500'
	};

	const percent = $derived(Math.round(Math.min(1, Math.max(0, value)) * 1000) / 10);
</script>

<div
	class={cn('bg-muted h-1.5 w-full overflow-hidden rounded-full', className)}
	role="meter"
	aria-label={label}
	aria-valuemin={0}
	aria-valuemax={100}
	aria-valuenow={percent}
>
	<div class={['h-full rounded-full', tone ? FILLS[tone] : 'bg-primary']} style:width="{percent}%"></div>
</div>
