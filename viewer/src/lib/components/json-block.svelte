<script lang="ts">
	import { formatJson, tokenizeJson, type JsonTokenKind } from '#lib/json.js';
	import { cn } from '#lib/utils.js';

	let { value, class: className }: { value: unknown; class?: string } = $props();

	const COLORS: Record<JsonTokenKind, string> = {
		key: 'text-sky-800',
		string: 'text-emerald-800',
		number: 'text-amber-700',
		literal: 'text-violet-700',
		plain: 'text-muted-foreground'
	};

	const tokens = $derived(tokenizeJson(formatJson(value)));
</script>

<pre
	class={cn(
		'bg-muted/50 overflow-auto rounded-md border p-3 font-mono text-xs leading-relaxed wrap-break-word whitespace-pre-wrap',
		className
	)}><code>{#each tokens as token (token.start)}<span class={COLORS[token.kind]}>{token.text}</span>{/each}</code></pre>
