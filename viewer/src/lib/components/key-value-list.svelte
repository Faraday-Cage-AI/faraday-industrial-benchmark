<script lang="ts">
	import type { Field } from '#lib/payload.js';
	import { cn } from '#lib/utils.js';

	let { fields, class: className }: { fields: Field[]; class?: string } = $props();
</script>

<dl class={cn('grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1 text-xs', className)}>
	{#each fields as field (field.key)}
		<dt class="text-muted-foreground font-mono">{field.key}</dt>
		<dd class="wrap-break-word whitespace-pre-line">{field.value}</dd>
	{/each}
</dl>
