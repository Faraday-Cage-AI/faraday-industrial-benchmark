<script lang="ts">
	import type { Snippet } from 'svelte';
	import * as Card from '#lib/components/ui/card/index.js';
	import { cn } from '#lib/utils.js';

	let {
		label,
		value,
		detail,
		valueClass,
		children
	}: {
		label: string;
		value: string;
		detail?: string;
		valueClass?: string;
		children?: Snippet;
	} = $props();
</script>

<Card.Root size="sm">
	<Card.Content class="gap-1">
		<p class="text-muted-foreground text-xs font-medium">{label}</p>
		<p class={cn('text-2xl font-semibold tracking-tight tabular-nums', valueClass)}>{value}</p>
		{#if detail}
			<p class="text-muted-foreground text-xs">{detail}</p>
		{/if}
		{@render children?.()}
	</Card.Content>
</Card.Root>
