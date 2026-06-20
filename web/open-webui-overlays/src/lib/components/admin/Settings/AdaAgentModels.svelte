<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import {
		getAgentModels,
		putAgentModels,
		testAgentModels,
		type AgentModelsConfig
	} from '$lib/apis/ada';

	const i18n = getContext('i18n');

	let ready = false;
	let saving = false;
	let testingChat = false;
	let testingTask = false;

	let chatBaseUrl = 'http://127.0.0.1:8089/v1';
	let chatModelId = 'mlx-coder';
	let taskBaseUrl = 'http://127.0.0.1:8089/v1';
	let taskModelId = 'mlx-coder';
	let taskMaxTokens = 512;

	function applyConfig(cfg: AgentModelsConfig) {
		chatBaseUrl = cfg.chat.base_url;
		chatModelId = cfg.chat.model_id;
		taskBaseUrl = cfg.task.base_url;
		taskModelId = cfg.task.model_id;
		taskMaxTokens = cfg.task.max_tokens ?? 512;
	}

	onMount(async () => {
		try {
			applyConfig(await getAgentModels());
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			ready = true;
		}
	});

	async function save() {
		saving = true;
		try {
			const cfg = await putAgentModels({
				chat: {
					base_url: chatBaseUrl.trim(),
					model_id: chatModelId.trim(),
					api_key: 'local'
				},
				task: {
					base_url: taskBaseUrl.trim(),
					model_id: taskModelId.trim(),
					api_key: 'local',
					max_tokens: Number(taskMaxTokens) || 512
				},
				tool: 'chat'
			});
			applyConfig(cfg);
			toast.success($i18n.t('Agent models saved'));
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			saving = false;
		}
	}

	async function testProfile(profile: 'chat' | 'task') {
		if (profile === 'chat') testingChat = true;
		else testingTask = true;
		try {
			await testAgentModels(profile);
			toast.success($i18n.t('Connection OK'));
		} catch (e) {
			toast.error(`${e}`);
		} finally {
			if (profile === 'chat') testingChat = false;
			else testingTask = false;
		}
	}
</script>

<div class="flex flex-col gap-4">
	<div>
		<div class="text-lg font-medium">{$i18n.t('Ada Agent Models')}</div>
		<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
			{$i18n.t('Chat and task LLM endpoints (saved to Agent agent.yaml via admin proxy).')}
		</div>
	</div>

	{#if !ready}
		<Spinner className="size-5" />
	{:else}
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<div class="flex flex-col gap-2 p-3 rounded-lg border border-gray-100 dark:border-gray-850">
				<div class="text-sm font-medium">{$i18n.t('Chat model (heavy)')}</div>
				<label class="text-xs">{$i18n.t('Base URL')}</label>
				<input class="w-full rounded-lg px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900" bind:value={chatBaseUrl} />
				<label class="text-xs">{$i18n.t('Model id')}</label>
				<input class="w-full rounded-lg px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900" bind:value={chatModelId} />
				<button
					class="mt-1 px-3 py-1.5 text-sm rounded-lg bg-gray-100 dark:bg-gray-800"
					disabled={testingChat}
					on:click={() => testProfile('chat')}
				>
					{testingChat ? $i18n.t('Testing...') : $i18n.t('Test connection')}
				</button>
			</div>

			<div class="flex flex-col gap-2 p-3 rounded-lg border border-gray-100 dark:border-gray-850">
				<div class="text-sm font-medium">{$i18n.t('Task model (light)')}</div>
				<label class="text-xs">{$i18n.t('Base URL')}</label>
				<input class="w-full rounded-lg px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900" bind:value={taskBaseUrl} />
				<label class="text-xs">{$i18n.t('Model id')}</label>
				<input class="w-full rounded-lg px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900" bind:value={taskModelId} />
				<label class="text-xs">{$i18n.t('Max tokens')}</label>
				<input
					type="number"
					min="1"
					class="w-full rounded-lg px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900"
					bind:value={taskMaxTokens}
				/>
				<button
					class="mt-1 px-3 py-1.5 text-sm rounded-lg bg-gray-100 dark:bg-gray-800"
					disabled={testingTask}
					on:click={() => testProfile('task')}
				>
					{testingTask ? $i18n.t('Testing...') : $i18n.t('Test connection')}
				</button>
			</div>
		</div>

		<button
			class="px-4 py-2 text-sm rounded-lg bg-black text-white dark:bg-white dark:text-black disabled:opacity-50"
			disabled={saving}
			on:click={save}
		>
			{saving ? $i18n.t('Saving...') : $i18n.t('Save models')}
		</button>
	{/if}
</div>
