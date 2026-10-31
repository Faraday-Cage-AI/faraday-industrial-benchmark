<script lang="ts">
	import CircleAlertIcon from '@lucide/svelte/icons/circle-alert';
	import CircleCheckIcon from '@lucide/svelte/icons/circle-check';
	import CircleXIcon from '@lucide/svelte/icons/circle-x';
	import { Badge } from '#lib/components/ui/badge/index.js';
	import { OUTCOME_LABELS, type Outcome } from '#lib/format.js';

	let { outcome }: { outcome: Outcome } = $props();

	const STYLES: Record<Outcome, { class: string; icon: typeof CircleCheckIcon; title: string }> = {
		strict: {
			class: 'border-emerald-600/20 bg-emerald-50 text-emerald-700',
			icon: CircleCheckIcon,
			title:
				'Every criterion passed, economics earned full points, nothing critical went wrong, and the agent submitted a final answer.'
		},
		partial: {
			class: 'border-amber-600/25 bg-amber-50 text-amber-800',
			icon: CircleAlertIcon,
			title:
				'Not a strict success: a criterion failed, economics fell short of full points, or the final answer is missing.'
		},
		critical: {
			class: 'border-red-600/20 bg-red-50 text-red-700',
			icon: CircleXIcon,
			title: 'A critical violation set the score to 0.'
		}
	};

	const style = $derived(STYLES[outcome]);
	const Icon = $derived(style.icon);
</script>

<Badge variant="outline" class={style.class} title={style.title}>
	<Icon data-icon="inline-start" aria-hidden="true" />
	{OUTCOME_LABELS[outcome]}
</Badge>
