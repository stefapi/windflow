<script lang="ts">
	import { Activity } from 'lucide-svelte';

	interface Props {
		today: number;
		total: number;
	}

	let { today, total }: Props = $props();
</script>

{#if total > 0}
	<div class="flex items-center justify-between text-xs pt-1 border-t border-border/50">
		<span class="flex items-center gap-1 text-muted-foreground">
			<Activity class="w-3 h-3" /> Events
		</span>
		<span class="font-medium">
			{today} today <span class="text-muted-foreground">/ {total} total</span>
		</span>
	</div>
{/if}
