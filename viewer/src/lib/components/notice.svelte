<script lang="ts">
	import CircleAlertIcon from '@lucide/svelte/icons/circle-alert';
	import InfoIcon from '@lucide/svelte/icons/info';
	import TriangleAlertIcon from '@lucide/svelte/icons/triangle-alert';
	import type { Snippet } from 'svelte';
	import { cn } from '#lib/utils.js';

	type Tone = 'info' | 'warning' | 'error';

	let {
		tone = 'info',
		title,
		children,
		class: className
	}: {
		tone?: Tone;
		title: string;
		children?: Snippet;
		class?: string;
	} = $props();

	const TONES: Record<Tone, { class: string; icon: typeof InfoIcon }> = {
		info: { class: 'border-sky-200 bg-sky-50 text-sky-950', icon: InfoIcon },
		warning: { class: 'border-amber-200 bg-amber-50 text-amber-950', icon: TriangleAlertIcon },
		error: { class: 'border-red-200 bg-red-50 text-red-950', icon: CircleAlertIcon }
	};

	const Icon = $derived(TONES[tone].icon);
</script>

<div class={cn('flex gap-3 rounded-lg border p-4 text-sm', TONES[tone].class, className)}>
	<Icon class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
	<div class="flex min-w-0 flex-col gap-1.5">
		<p class="font-medium">{title}</p>
		{#if children}
			<div class="flex flex-col gap-1.5 opacity-90">{@render children()}</div>
		{/if}
	</div>
</div>
