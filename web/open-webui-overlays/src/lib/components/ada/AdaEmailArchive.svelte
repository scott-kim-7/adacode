<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import {
		emailAttachmentUrl,
		emailRawUrl,
		getEmailMessage,
		listAccounts,
		markInboxRead,
		markInboxReadBulk,
		searchEmails,
		type EmailAccount,
		type EmailMessageDetail,
		type EmailMessageListItem
	} from '$lib/apis/ada';

	const i18n = getContext('i18n');
	let items: EmailMessageListItem[] = [];
	let accounts: EmailAccount[] = [];
	let selectedMessageId = '';
	let detail: EmailMessageDetail | null = null;
	let selectedInboxIds: Set<number> = new Set();
	let q = '';
	let loading = false;
	let agentError = '';

	async function load() {
		loading = true;
		agentError = '';
		try {
			const [searchBody, accountsBody] = await Promise.all([
				searchEmails({ q, limit: 50, offset: 0 }),
				listAccounts()
			]);
			items = searchBody.data ?? [];
			accounts = accountsBody.data ?? [];
		} catch (err) {
			agentError = String(err);
			items = [];
		} finally {
			loading = false;
		}
	}

	async function openMessage(messageId: string) {
		selectedMessageId = messageId;
		agentError = '';
		try {
			detail = await getEmailMessage(messageId);
		} catch (err) {
			agentError = String(err);
			detail = null;
		}
	}

	function toggleSelect(inboxId: number | null | undefined) {
		if (!inboxId) return;
		if (selectedInboxIds.has(inboxId)) selectedInboxIds.delete(inboxId);
		else selectedInboxIds.add(inboxId);
		selectedInboxIds = new Set(selectedInboxIds);
	}

	async function markSelectedRead() {
		const ids = Array.from(selectedInboxIds);
		if (!ids.length) return;
		try {
			await markInboxReadBulk({ inbox_ids: ids });
			selectedInboxIds = new Set();
			await load();
		} catch (err) {
			agentError = String(err);
		}
	}

	async function markCurrentRead() {
		if (!detail?.inbox_id) return;
		try {
			await markInboxRead(detail.inbox_id);
			await load();
			detail = await getEmailMessage(detail.message_id);
		} catch (err) {
			agentError = String(err);
		}
	}

	onMount(load);
</script>

<div class="grid grid-cols-1 lg:grid-cols-2 gap-3 h-full p-3 min-h-0">
	<div class="border rounded-lg p-3 space-y-2 overflow-y-auto min-h-0">
		<div class="flex gap-2">
			<input
				class="flex-1 rounded border px-2 py-1 text-sm dark:bg-gray-900"
				bind:value={q}
				placeholder={$i18n.t('Search emails')}
			/>
			<button class="px-3 py-1 text-xs border rounded" on:click={load}>{$i18n.t('Search')}</button>
		</div>
		<div class="flex gap-2">
			<button
				class="px-3 py-1 text-xs border rounded"
				on:click={markSelectedRead}
				disabled={selectedInboxIds.size === 0}
			>
				{$i18n.t('Mark selected as read')}
			</button>
		</div>
		{#if agentError}
			<p class="text-xs text-red-600">{$i18n.t('Agent unreachable')}: {agentError}</p>
		{:else if loading}
			<div class="text-xs text-gray-500">{$i18n.t('Loading...')}</div>
		{:else if accounts.length === 0}
			<div class="text-xs text-gray-500">{$i18n.t('Connect Gmail in Admin → Ada Email to import mail.')}</div>
		{:else if items.length === 0}
			<div class="text-xs text-gray-500">{$i18n.t('No archived messages yet. Recent mail is imported after Gmail connect; wait for Heartbeat or run it from Ada Email settings.')}</div>
		{/if}
		{#each items as item}
			<div
				class="rounded border p-2 text-xs cursor-pointer {selectedMessageId === item.message_id
					? 'border-gray-400 dark:border-gray-600'
					: ''}"
				on:click={() => openMessage(item.message_id)}
			>
				<div class="flex justify-between gap-2">
					<div class="font-medium min-w-0 truncate">{item.subject || item.message_id}</div>
					{#if item.inbox_id}
						<input
							type="checkbox"
							checked={selectedInboxIds.has(item.inbox_id)}
							on:click|stopPropagation={() => toggleSelect(item.inbox_id)}
						/>
					{/if}
				</div>
				<div class="text-gray-500">{item.from_address}</div>
				<div class="text-gray-500">{item.received_at}</div>
				{#if item.summary_status}
					<div class="text-gray-400">{item.summary_status}</div>
				{/if}
			</div>
		{/each}
	</div>

	<div class="border rounded-lg p-3 space-y-2 overflow-y-auto min-h-0">
		{#if detail}
			<div class="text-sm font-medium">{detail.subject}</div>
			<div class="text-xs text-gray-500">{detail.from_address}</div>
			<div class="text-xs">{detail.summary_status}: {detail.summary_text || '-'}</div>
			<div class="flex gap-2 flex-wrap">
				{#if detail.inbox_id}
					<button class="px-3 py-1 text-xs border rounded" on:click={markCurrentRead}>
						{$i18n.t('Mark as read')}
					</button>
				{/if}
				<a class="px-3 py-1 text-xs border rounded" href={emailRawUrl(detail.message_id)}>
					{$i18n.t('Download .eml')}
				</a>
			</div>
			<pre class="text-xs whitespace-pre-wrap">{detail.body_text}</pre>
			{#if detail.attachments?.length}
				<div class="text-xs font-medium">{$i18n.t('Attachments')}</div>
				{#each detail.attachments as a}
					<div class="text-xs flex justify-between gap-2">
						<span>{a.filename}</span>
						<a href={emailAttachmentUrl(a.id)}>{$i18n.t('Download')}</a>
					</div>
				{/each}
			{/if}
		{:else}
			<div class="text-xs text-gray-500">{$i18n.t('Select a message')}</div>
		{/if}
	</div>
</div>
