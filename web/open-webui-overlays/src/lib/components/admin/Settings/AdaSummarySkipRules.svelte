<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	import type { SummarySkipCondition, SummarySkipMatch, SummarySkipRule, SummarySkipRuleLogic } from '$lib/apis/ada';

	export let rules: SummarySkipRule[] = [];
	export let disabled = false;

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher<{ save: void }>();

	const matchOptions: Array<{ value: SummarySkipMatch; label: string }> = [
		{ value: 'sender_contains', label: 'From contains' },
		{ value: 'sender_domain', label: 'From domain is' },
		{ value: 'subject_contains', label: 'Subject contains' },
		{ value: 'header_present', label: 'Has header' },
		{ value: 'from_noreply', label: 'From is no-reply address' }
	];

	const logicOptions: Array<{ value: SummarySkipRuleLogic; label: string }> = [
		{ value: 'any', label: 'Match any condition (OR)' },
		{ value: 'all', label: 'Match all conditions (AND)' }
	];

	function newId(): string {
		return `rule-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
	}

	function newCondition(match: SummarySkipMatch = 'sender_contains'): SummarySkipCondition {
		return {
			match,
			pattern: match === 'header_present' || match === 'from_noreply' ? undefined : '',
			header: match === 'header_present' ? 'List-Id' : undefined
		};
	}

	function newRule(): SummarySkipRule {
		return {
			id: newId(),
			name: 'New rule',
			enabled: true,
			logic: 'any',
			conditions: [newCondition()]
		};
	}

	function addRule() {
		rules = [...rules, newRule()];
	}

	function addPreset(match: SummarySkipMatch) {
		let rule = newRule();
		rule.conditions = [newCondition(match)];
		if (match === 'from_noreply') rule = { ...rule, name: 'No-reply senders' };
		if (match === 'header_present') rule = { ...rule, name: 'Mailing list' };
		if (match === 'sender_contains') rule = { ...rule, name: 'Custom rule' };
		rules = [...rules, rule];
	}

	function addCondition(ruleIndex: number) {
		const copy = [...rules];
		copy[ruleIndex] = {
			...copy[ruleIndex],
			conditions: [...copy[ruleIndex].conditions, newCondition()]
		};
		rules = copy;
	}

	function removeCondition(ruleIndex: number, condIndex: number) {
		const copy = [...rules];
		const conditions = copy[ruleIndex].conditions.filter((_, i) => i !== condIndex);
		if (!conditions.length) return;
		copy[ruleIndex] = { ...copy[ruleIndex], conditions };
		rules = copy;
	}

	function move(index: number, dir: -1 | 1) {
		const next = index + dir;
		if (next < 0 || next >= rules.length) return;
		const copy = [...rules];
		const [item] = copy.splice(index, 1);
		copy.splice(next, 0, item);
		rules = copy;
	}

	function remove(index: number) {
		rules = rules.filter((_, i) => i !== index);
	}

	function emitSave() {
		dispatch('save');
	}
</script>

<div class="rounded-lg border border-gray-100 dark:border-gray-800 p-3 space-y-2">
	<div class="text-sm font-medium">{$i18n.t('Summary skip rules')}</div>
	<div class="text-xs text-gray-500">{$i18n.t('Skip LLM summary and Ada Inbox for matching mail. Archive is kept.')}</div>
	<div class="flex gap-2 flex-wrap">
		<button type="button" class="text-xs border rounded px-2 py-1" on:click={addRule} disabled={disabled}>
			{$i18n.t('Add rule')}
		</button>
		<button type="button" class="text-xs border rounded px-2 py-1" on:click={() => addPreset('from_noreply')} disabled={disabled}>
			{$i18n.t('Preset: No-reply')}
		</button>
		<button type="button" class="text-xs border rounded px-2 py-1" on:click={() => addPreset('header_present')} disabled={disabled}>
			{$i18n.t('Preset: Mailing list')}
		</button>
		<button type="button" class="text-xs border rounded px-2 py-1" on:click={() => addPreset('sender_contains')} disabled={disabled}>
			{$i18n.t('Preset: Custom rule')}
		</button>
	</div>

	{#if rules.length === 0}
		<div class="text-xs text-gray-500">{$i18n.t('No rules yet')}</div>
	{/if}

	{#each rules as rule, idx}
		<div class="rounded border border-gray-100 dark:border-gray-800 p-2 space-y-2">
			<div class="flex items-center gap-2 flex-wrap">
				<input type="checkbox" bind:checked={rule.enabled} disabled={disabled} />
				<input class="flex-1 min-w-[8rem] rounded px-2 py-1 text-xs border dark:bg-gray-900" bind:value={rule.name} disabled={disabled} />
				<button type="button" class="text-xs underline" on:click={() => move(idx, -1)} disabled={disabled || idx === 0}>{$i18n.t('Move up')}</button>
				<button type="button" class="text-xs underline" on:click={() => move(idx, 1)} disabled={disabled || idx === rules.length - 1}>{$i18n.t('Move down')}</button>
				<button type="button" class="text-xs underline text-red-600" on:click={() => remove(idx)} disabled={disabled}>{$i18n.t('Delete rule')}</button>
			</div>
			<div class="text-xs text-gray-500">{$i18n.t('Conditions')}</div>
			<select class="rounded px-2 py-1 text-xs border dark:bg-gray-900 w-full md:w-auto" bind:value={rule.logic} disabled={disabled}>
				{#each logicOptions as option}
					<option value={option.value}>{$i18n.t(option.label)}</option>
				{/each}
			</select>
			{#each rule.conditions as cond, condIdx}
				<div class="grid grid-cols-1 md:grid-cols-3 gap-2 items-center">
					<select class="rounded px-2 py-1 text-xs border dark:bg-gray-900" bind:value={cond.match} disabled={disabled}>
						{#each matchOptions as option}
							<option value={option.value}>{$i18n.t(option.label)}</option>
						{/each}
					</select>
					{#if cond.match === 'header_present'}
						<input class="rounded px-2 py-1 text-xs border dark:bg-gray-900" bind:value={cond.header} placeholder={$i18n.t('Header name')} disabled={disabled} />
					{:else if cond.match !== 'from_noreply'}
						<input class="rounded px-2 py-1 text-xs border dark:bg-gray-900" bind:value={cond.pattern} placeholder={$i18n.t('Pattern')} disabled={disabled} />
					{:else}
						<div class="text-xs text-gray-500">—</div>
					{/if}
					<button
						type="button"
						class="text-xs underline text-red-600 justify-self-start"
						on:click={() => removeCondition(idx, condIdx)}
						disabled={disabled || rule.conditions.length <= 1}
					>
						{$i18n.t('Remove condition')}
					</button>
				</div>
			{/each}
			<button type="button" class="text-xs border rounded px-2 py-1" on:click={() => addCondition(idx)} disabled={disabled}>
				{$i18n.t('Add condition')}
			</button>
		</div>
	{/each}

	<div class="flex justify-end">
		<button type="button" class="px-3 py-1.5 text-xs border rounded-lg disabled:opacity-50" on:click={emitSave} disabled={disabled}>
			{$i18n.t('Save summary skip rules')}
		</button>
	</div>
</div>
