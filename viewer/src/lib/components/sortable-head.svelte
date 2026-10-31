<script lang="ts">
	import ArrowDownIcon from '@lucide/svelte/icons/arrow-down';
	import ArrowUpIcon from '@lucide/svelte/icons/arrow-up';
	import ChevronsUpDownIcon from '@lucide/svelte/icons/chevrons-up-down';
	import * as Table from '#lib/components/ui/table/index.js';

	let {
		label,
		direction,
		onclick,
		class: className
	}: {
		label: string;
		direction: 'asc' | 'desc' | null;
		onclick: () => void;
		class?: string;
	} = $props();
</script>

<Table.Head
	class={className}
	aria-sort={direction === 'asc' ? 'ascending' : direction === 'desc' ? 'descending' : 'none'}
>
	<button
		type="button"
		class="hover:text-foreground focus-visible:ring-ring/50 -mx-1 inline-flex items-center gap-1 rounded px-1 outline-none focus-visible:ring-2"
		{onclick}
	>
		{label}
		{#if direction === 'asc'}
			<ArrowUpIcon class="size-3.5" aria-hidden="true" />
		{:else if direction === 'desc'}
			<ArrowDownIcon class="size-3.5" aria-hidden="true" />
		{:else}
			<ChevronsUpDownIcon class="size-3.5 opacity-40" aria-hidden="true" />
		{/if}
	</button>
</Table.Head>
