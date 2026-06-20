#!/usr/bin/env python3
"""Apply Ada Email UI patches to a vendored open-webui tree."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if old not in text:
        raise SystemExit(f"patch failed ({label}): anchor not found")
    return text.replace(old, new, 1)


def patch_stores(path: Path) -> None:
    text = path.read_text()
    anchor = "export const showArtifacts = writable(false);"
    insert = anchor + "\nexport const showAdaInbox = writable(false);"
    if "showAdaInbox" not in text:
        text = replace_once(text, anchor, insert, label="stores")
        path.write_text(text)


def patch_settings(path: Path) -> None:
    text = path.read_text()
    if "AdaEmail" not in text:
        text = replace_once(
            text,
            "import Tools from './Settings/Tools.svelte';",
            "import Tools from './Settings/Tools.svelte';\n\timport AdaEmail from './Settings/AdaEmail.svelte';\n\timport AdaAgentModels from './Settings/AdaAgentModels.svelte';",
            label="settings-import",
        )
        text = replace_once(
            text,
            "\t\t\t'db'\n\t\t].includes(tabFromPath)",
            "\t\t\t'db',\n\t\t\t'ada-email',\n\t\t\t'ada-agent'\n\t\t].includes(tabFromPath)",
            label="settings-tab-list",
        )
        tab_button = """
\t\t<button
\t\t\tid="ada-email"
\t\t\tclass="px-0.5 py-1 min-w-fit rounded-lg flex-1 md:flex-none flex text-left transition {selectedTab ===
\t\t\t'ada-email'
\t\t\t\t? ''
\t\t\t\t: ' text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
\t\t\ton:click={() => {
\t\t\t\tgoto('/admin/settings/ada-email');
\t\t\t}}
\t\t>
\t\t\t<div class=" self-center mr-2">
\t\t\t\t<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-4 h-4">
\t\t\t\t\t<path d="M1.5 8.67v8.58a3 3 0 0 0 3 3h15a3 3 0 0 0 3-3V8.67l-8.928 5.493a3 3 0 0 1-3.144 0L1.5 8.67Z" />
\t\t\t\t\t<path d="M22.5 6.908V6.75a3 3 0 0 0-3-3h-15a3 3 0 0 0-3 3v.158l9.714 5.978a1.5 1.5 0 0 0 1.572 0L22.5 6.908Z" />
\t\t\t\t</svg>
\t\t\t</div>
\t\t\t<div class=" self-center">{$i18n.t('Ada Email')}</div>
\t\t</button>

\t\t<button
\t\t\tid="ada-agent"
\t\t\tclass="px-0.5 py-1 min-w-fit rounded-lg flex-1 md:flex-none flex text-left transition {selectedTab ===
\t\t\t'ada-agent'
\t\t\t\t? ''
\t\t\t\t: ' text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
\t\t\ton:click={() => {
\t\t\t\tgoto('/admin/settings/ada-agent');
\t\t\t}}
\t\t>
\t\t\t<div class=" self-center mr-2">
\t\t\t\t<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-4 h-4">
\t\t\t\t\t<path fill-rule="evenodd" d="M14.615 1.595a.75.75 0 0 1 .359.852L12.982 9.75h7.268a.75.75 0 0 1 .548 1.262l-10.5 11.25a.75.75 0 0 1-1.272-.71l1.992-7.302H3.75a.75.75 0 0 1-.548-1.262l10.5-11.25a.75.75 0 0 1 .913-.143Z" clip-rule="evenodd" />
\t\t\t\t</svg>
\t\t\t</div>
\t\t\t<div class=" self-center">{$i18n.t('Ada Agent Models')}</div>
\t\t</button>

\t\t<button
\t\t\tid="db"
"""
        text = replace_once(text, '\t\t<button\n\t\t\tid="db"', tab_button, label="settings-tab-button")
        text = replace_once(
            text,
            "\t\t{:else if selectedTab === 'pipelines'}",
            "\t\t{:else if selectedTab === 'ada-email'}\n\t\t\t<AdaEmail />\n\t\t{:else if selectedTab === 'ada-agent'}\n\t\t\t<AdaAgentModels />\n\t\t{:else if selectedTab === 'pipelines'}",
            label="settings-tab-content",
        )
        path.write_text(text)
    elif "AdaAgentModels" not in text:
        text = replace_once(
            text,
            "import AdaEmail from './Settings/AdaEmail.svelte';",
            "import AdaEmail from './Settings/AdaEmail.svelte';\n\timport AdaAgentModels from './Settings/AdaAgentModels.svelte';",
            label="settings-import-agent-models",
        )
        if "'ada-agent'" not in text:
            text = replace_once(
                text,
                "\t\t\t'ada-email'\n\t\t].includes(tabFromPath)",
                "\t\t\t'ada-email',\n\t\t\t'ada-agent'\n\t\t].includes(tabFromPath)",
                label="settings-tab-list-agent",
            )
        if "id=\"ada-agent\"" not in text:
            agent_tab = """
\t\t<button
\t\t\tid="ada-agent"
\t\t\tclass="px-0.5 py-1 min-w-fit rounded-lg flex-1 md:flex-none flex text-left transition {selectedTab ===
\t\t\t'ada-agent'
\t\t\t\t? ''
\t\t\t\t: ' text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'}"
\t\t\ton:click={() => {
\t\t\t\tgoto('/admin/settings/ada-agent');
\t\t\t}}
\t\t>
\t\t\t<div class=" self-center mr-2">
\t\t\t\t<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-4 h-4">
\t\t\t\t\t<path fill-rule="evenodd" d="M14.615 1.595a.75.75 0 0 1 .359.852L12.982 9.75h7.268a.75.75 0 0 1 .548 1.262l-10.5 11.25a.75.75 0 0 1-1.272-.71l1.992-7.302H3.75a.75.75 0 0 1-.548-1.262l10.5-11.25a.75.75 0 0 1 .913-.143Z" clip-rule="evenodd" />
\t\t\t\t</svg>
\t\t\t</div>
\t\t\t<div class=" self-center">{$i18n.t('Ada Agent Models')}</div>
\t\t</button>

"""
            text = replace_once(
                text,
                "\t\t\t<div class=\" self-center\">{$i18n.t('Ada Email')}</div>\n\t\t</button>\n\n\t\t<button\n\t\t\tid=\"db\"",
                "\t\t\t<div class=\" self-center\">{$i18n.t('Ada Email')}</div>\n\t\t</button>\n" + agent_tab + "\t\t<button\n\t\t\tid=\"db\"",
                label="settings-tab-button-agent",
            )
        if "selectedTab === 'ada-agent'" not in text:
            text = replace_once(
                text,
                "\t\t{:else if selectedTab === 'ada-email'}\n\t\t\t<AdaEmail />\n\t\t{:else if selectedTab === 'pipelines'}",
                "\t\t{:else if selectedTab === 'ada-email'}\n\t\t\t<AdaEmail />\n\t\t{:else if selectedTab === 'ada-agent'}\n\t\t\t<AdaAgentModels />\n\t\t{:else if selectedTab === 'pipelines'}",
                label="settings-tab-content-agent",
            )
        path.write_text(text)


def patch_navbar(path: Path) -> None:
    text = path.read_text()
    if "showAdaInbox" not in text:
        text = replace_once(
            text,
            "\t\tshowControls,\n\t\tshowSidebar,",
            "\t\tshowControls,\n\t\tshowAdaInbox,\n\t\tshowArtifacts,\n\t\tshowEmbeds,\n\t\tshowOverview,\n\t\tshowCallOverlay,\n\t\tshowSidebar,",
            label="navbar-imports",
        )
        text = replace_once(
            text,
            "import Knobs from '../icons/Knobs.svelte';",
            "import Knobs from '../icons/Knobs.svelte';\n\timport AdaInboxIcon from '$lib/components/ada/icons/AdaInboxIcon.svelte';",
            label="navbar-icon-import",
        )
        inbox_btn = """
\t\t\t\t\t<Tooltip content={$i18n.t('Ada Inbox')}>
\t\t\t\t\t\t<button
\t\t\t\t\t\t\tclass=" flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
\t\t\t\t\t\t\ton:click={async () => {
\t\t\t\t\t\t\tawait showArtifacts.set(false);
\t\t\t\t\t\t\tawait showEmbeds.set(false);
\t\t\t\t\t\t\tawait showOverview.set(false);
\t\t\t\t\t\t\tawait showCallOverlay.set(false);
\t\t\t\t\t\t\tawait showAdaInbox.set(true);
\t\t\t\t\t\t\tawait showControls.set(true);
\t\t\t\t\t\t}}
\t\t\t\t\t\t\taria-label={$i18n.t('Ada Inbox')}
\t\t\t\t\t\t>
\t\t\t\t\t\t\t<div class=" m-auto self-center">
\t\t\t\t\t\t\t\t<AdaInboxIcon className=" size-5" strokeWidth="1.5" />
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t</button>
\t\t\t\t\t</Tooltip>

\t\t\t\t\t{#if $user?.role === 'admin' || ($user?.permissions.chat?.controls ?? true)}
"""
        text = replace_once(
            text,
            "\t\t\t\t\t{#if $user?.role === 'admin' || ($user?.permissions.chat?.controls ?? true)}",
            inbox_btn,
            label="navbar-inbox-button",
        )
        controls_click_old = "\t\t\t\t\t\t\ton:click={async () => {\n\t\t\t\t\t\t\t\tawait showControls.set(!$showControls);\n\t\t\t\t\t\t\t}}"
        controls_click_new = "\t\t\t\t\t\t\ton:click={async () => {\n\t\t\t\t\t\t\t\tif (!$showControls) {\n\t\t\t\t\t\t\t\t\tawait showAdaInbox.set(false);\n\t\t\t\t\t\t\t\t\tawait showArtifacts.set(false);\n\t\t\t\t\t\t\t\t\tawait showEmbeds.set(false);\n\t\t\t\t\t\t\t\t\tawait showOverview.set(false);\n\t\t\t\t\t\t\t\t\tawait showCallOverlay.set(false);\n\t\t\t\t\t\t\t\t}\n\t\t\t\t\t\t\t\tawait showControls.set(!$showControls);\n\t\t\t\t\t\t\t}}"
        if controls_click_old in text:
            text = replace_once(text, controls_click_old, controls_click_new, label="navbar-controls-click")
    archive_btn = """
\t\t\t\t\t{#if $user?.role === 'admin'}
\t\t\t\t\t\t<Tooltip content={$i18n.t('Email Archive')} interactive={true}>
\t\t\t\t\t\t\t<button
\t\t\t\t\t\t\t\ttype="button"
\t\t\t\t\t\t\t\tclass=" flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
\t\t\t\t\t\t\t\taria-label={$i18n.t('Email Archive')}
\t\t\t\t\t\t\t\ton:click={async () => {
\t\t\t\t\t\t\t\tawait showAdaInbox.set(false);
\t\t\t\t\t\t\t\tawait showArtifacts.set(false);
\t\t\t\t\t\t\t\tawait showEmbeds.set(false);
\t\t\t\t\t\t\t\tawait showOverview.set(false);
\t\t\t\t\t\t\t\tawait showCallOverlay.set(false);
\t\t\t\t\t\t\t\tawait showControls.set(false);
\t\t\t\t\t\t\t\tgoto('/ada/email');
\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t>
\t\t\t\t\t\t\t\t<div class=" m-auto self-center">
\t\t\t\t\t\t\t\t\t<AdaMailIcon className=" size-5" strokeWidth="1.5" />
\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t</button>
\t\t\t\t\t\t</Tooltip>
\t\t\t\t\t{/if}

"""
    old_archive_btn = """
\t\t\t\t\t{#if $user?.role === 'admin'}
\t\t\t\t\t\t<Tooltip content={$i18n.t('Email Archive')}>
\t\t\t\t\t\t\t<a
\t\t\t\t\t\t\t\thref="/ada/email"
\t\t\t\t\t\t\t\tclass=" flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
\t\t\t\t\t\t\t\taria-label={$i18n.t('Email Archive')}
\t\t\t\t\t\t\t>
\t\t\t\t\t\t\t\t<div class=" m-auto self-center">
\t\t\t\t\t\t\t\t\t<AdaMailIcon className=" size-5" strokeWidth="1.5" />
\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t</a>
\t\t\t\t\t\t</Tooltip>
\t\t\t\t\t{/if}

"""
    if "goto('/ada/email')" in text:
        pass
    elif old_archive_btn.strip() in text:
        text = text.replace(old_archive_btn, archive_btn, 1)
    elif 'href="/ada/email"' not in text and "AdaInboxIcon" in text:
        if "AdaMailIcon" not in text:
            text = replace_once(
                text,
                "import AdaInboxIcon from '$lib/components/ada/icons/AdaInboxIcon.svelte';",
                "import AdaInboxIcon from '$lib/components/ada/icons/AdaInboxIcon.svelte';\n\timport AdaMailIcon from '$lib/components/ada/AdaMailIcon.svelte';",
                label="navbar-archive-icon-import",
            )
        text = replace_once(
            text,
            "\t\t\t\t\t<Tooltip content={$i18n.t('Ada Inbox')}>",
            archive_btn + "\t\t\t\t\t<Tooltip content={$i18n.t('Ada Inbox')}>",
            label="navbar-archive-button",
        )
    path.write_text(text)


def patch_chat_controls(path: Path) -> None:
    text = path.read_text()
    if "AdaInboxPanel" not in text:
        text = replace_once(
            text,
            "\t\tshowArtifacts,\n\t\tshowEmbeds",
            "\t\tshowArtifacts,\n\t\tshowEmbeds,\n\t\tshowAdaInbox",
            label="chatcontrols-import-store",
        )
        text = replace_once(
            text,
            "import Embeds from './ChatControls/Embeds.svelte';",
            "import Embeds from './ChatControls/Embeds.svelte';\n\timport AdaInboxPanel from '$lib/components/ada/AdaInboxPanel.svelte';",
            label="chatcontrols-import-panel",
        )
        text = replace_once(
            text,
            "\t\tshowEmbeds.set(false);\n\n\t\tif ($showCallOverlay)",
            "\t\tshowEmbeds.set(false);\n\t\tshowAdaInbox.set(false);\n\n\t\tif ($showCallOverlay)",
            label="chatcontrols-close",
        )
        text = replace_once(
            text,
            "class=\" {$showCallOverlay || $showOverview || $showArtifacts || $showEmbeds",
            "class=\" {$showCallOverlay || $showOverview || $showArtifacts || $showEmbeds || $showAdaInbox",
            label="chatcontrols-mobile-class",
        )
        text = replace_once(
            text,
            "\t\t\t\t{:else if $showOverview}\n\t\t\t\t\t{#await import('./Overview.svelte') then { default: Overview }}\n\t\t\t\t\t\t<Overview\n\t\t\t\t\t\t\t{history}\n\t\t\t\t\t\t\tonNodeClick={(e) => {\n\t\t\t\t\t\t\t\tconst node = e.node;\n\t\t\t\t\t\t\t\tshowMessage(node.data.message, true);\n\t\t\t\t\t\t\t}}\n\t\t\t\t\t\t\tonClose={() => {\n\t\t\t\t\t\t\t\tshowControls.set(false);\n\t\t\t\t\t\t\t}}\n\t\t\t\t\t\t/>\n\t\t\t\t\t{/await}\n\t\t\t\t{:else}",
            "\t\t\t\t{:else if $showOverview}\n\t\t\t\t\t{#await import('./Overview.svelte') then { default: Overview }}\n\t\t\t\t\t\t<Overview\n\t\t\t\t\t\t\t{history}\n\t\t\t\t\t\t\tonNodeClick={(e) => {\n\t\t\t\t\t\t\t\tconst node = e.node;\n\t\t\t\t\t\t\t\tshowMessage(node.data.message, true);\n\t\t\t\t\t\t\t}}\n\t\t\t\t\t\t\tonClose={() => {\n\t\t\t\t\t\t\t\tshowControls.set(false);\n\t\t\t\t\t\t\t}}\n\t\t\t\t\t\t/>\n\t\t\t\t\t{/await}\n\t\t\t\t{:else if $showAdaInbox}\n\t\t\t\t\t<AdaInboxPanel />\n\t\t\t\t{:else}",
            label="chatcontrols-mobile-branch",
        )
        text = replace_once(
            text,
            "class=\"w-full {($showOverview || $showArtifacts || $showEmbeds) && !$showCallOverlay",
            "class=\"w-full {($showOverview || $showArtifacts || $showEmbeds || $showAdaInbox) && !$showCallOverlay",
            label="chatcontrols-desktop-class",
        )
        text = replace_once(
            text,
            "\t\t\t\t\t{:else if $showOverview}\n\t\t\t\t\t\t{#await import('./Overview.svelte') then { default: Overview }}\n\t\t\t\t\t\t\t<Overview\n\t\t\t\t\t\t\t\t{history}\n\t\t\t\t\t\t\t\tonNodeClick={(e) => {\n\t\t\t\t\t\t\t\t\tconst node = e.node;\n\t\t\t\t\t\t\t\t\tif (node?.data?.message?.favorite) {\n\t\t\t\t\t\t\t\t\t\thistory.messages[node.data.message.id].favorite = true;\n\t\t\t\t\t\t\t\t\t} else {\n\t\t\t\t\t\t\t\t\t\thistory.messages[node.data.message.id].favorite = null;\n\t\t\t\t\t\t\t\t\t}\n\n\t\t\t\t\t\t\t\t\tshowMessage(node.data.message, true);\n\t\t\t\t\t\t\t\t}}\n\t\t\t\t\t\t\t\tonClose={() => {\n\t\t\t\t\t\t\t\t\tshowControls.set(false);\n\t\t\t\t\t\t\t\t}}\n\t\t\t\t\t\t\t/>\n\t\t\t\t\t\t{/await}\n\t\t\t\t\t{:else}",
            "\t\t\t\t\t{:else if $showOverview}\n\t\t\t\t\t\t{#await import('./Overview.svelte') then { default: Overview }}\n\t\t\t\t\t\t\t<Overview\n\t\t\t\t\t\t\t\t{history}\n\t\t\t\t\t\t\t\tonNodeClick={(e) => {\n\t\t\t\t\t\t\t\t\tconst node = e.node;\n\t\t\t\t\t\t\t\t\tif (node?.data?.message?.favorite) {\n\t\t\t\t\t\t\t\t\t\thistory.messages[node.data.message.id].favorite = true;\n\t\t\t\t\t\t\t\t\t} else {\n\t\t\t\t\t\t\t\t\t\thistory.messages[node.data.message.id].favorite = null;\n\t\t\t\t\t\t\t\t\t}\n\n\t\t\t\t\t\t\t\t\tshowMessage(node.data.message, true);\n\t\t\t\t\t\t\t\t}}\n\t\t\t\t\t\t\t\tonClose={() => {\n\t\t\t\t\t\t\t\t\tshowControls.set(false);\n\t\t\t\t\t\t\t\t}}\n\t\t\t\t\t\t\t/>\n\t\t\t\t\t\t{/await}\n\t\t\t\t\t{:else if $showAdaInbox}\n\t\t\t\t\t\t<AdaInboxPanel />\n\t\t\t\t\t{:else}",
            label="chatcontrols-desktop-branch",
        )
        path.write_text(text)


def patch_chat(path: Path) -> None:
    text = path.read_text()
    if "showAdaInbox" not in text:
        text = replace_once(
            text,
            "\t\tshowEmbeds\n\t} from '$lib/stores';",
            "\t\tshowEmbeds,\n\t\tshowAdaInbox\n\t} from '$lib/stores';",
            label="chat-import",
        )
        text = replace_once(
            text,
            "\t\t\t\tshowEmbeds.set(false);\n\t\t\t}\n\t\t});",
            "\t\t\t\tshowEmbeds.set(false);\n\t\t\t\tshowAdaInbox.set(false);\n\t\t\t}\n\t\t});",
            label="chat-subscribe",
        )
        text = replace_once(
            text,
            "\t\tawait showArtifacts.set(false);\n\n\t\tif ($page.url.pathname.includes('/c/'))",
            "\t\tawait showArtifacts.set(false);\n\t\tawait showAdaInbox.set(false);\n\n\t\tif ($page.url.pathname.includes('/c/'))",
            label="chat-init",
        )
        path.write_text(text)


def patch_openai(path: Path) -> None:
	text = path.read_text()
	marker = "    headers, cookies = await get_headers_and_cookies(\n        request, url, key, api_config, metadata, user=user\n    )\n"
	phase2_block = """
    # Ada Agent forwarding (Phase 2)
    import json as _json
    _ada_meta = metadata if isinstance(metadata, dict) else {}
    headers["X-Ada-Request-Kind"] = "task" if _ada_meta.get("task") else "chat"
    _ada_allow = (
        "features", "files", "chat_id", "message_id",
        "tool_ids", "tool_servers", "collection_names",
        "task", "task_body", "filter_ids",
    )
    _ada_filtered = {k: _ada_meta[k] for k in _ada_allow if k in _ada_meta}
    if _ada_filtered:
        headers["X-OpenWebUI-Metadata"] = _json.dumps(_ada_filtered, ensure_ascii=False)[:65536]
    if headers.get("Authorization"):
        headers["X-Ada-Owui-Authorization"] = headers["Authorization"]

"""
	if "X-Ada-Request-Kind" in text and "features" in text and '_ada_allow = (' in text:
		return
	if "X-Ada-Request-Kind" in text:
		# Upgrade Phase 1 patch to Phase 2 allowlist
		start = text.find("    # Ada Agent forwarding")
		end = text.find("\n\n", start)
		if start != -1 and end != -1:
			text = text[:start] + phase2_block.strip() + "\n" + text[end + 2 :]
			path.write_text(text)
		return
	insert = marker + phase2_block
	text = replace_once(text, marker, insert, label="openai-ada-headers")
	path.write_text(text)


def patch_middleware_features(path: Path) -> None:
	text = path.read_text()
	if "Ada Phase 2 — preserve features" in text:
		return
	anchor = "    metadata = {\n        **metadata,\n        \"tool_ids\": tool_ids,\n        \"files\": files,\n    }"
	insert = """    # Ada Phase 2 — preserve features for Agent metadata header
    if features:
        metadata = {**metadata, "features": features}

""" + anchor
	text = replace_once(text, anchor, insert, label="middleware-features")
	path.write_text(text)


def patch_middleware_agent_handles_context(path: Path) -> None:
	text = path.read_text()
	if "_ada_agent_handles_context" in text:
		return

	log_anchor = "log = logging.getLogger(__name__)\n"
	helper = log_anchor + """

def _ada_agent_handles_context() -> bool:
    return os.environ.get("ADA_AGENT_HANDLES_CONTEXT", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


"""
	text = replace_once(text, log_anchor, helper, label="middleware-ada-helper")

	memory_old = (
		'        if "memory" in features and features["memory"]:\n'
		"            form_data = await chat_memory_handler("
	)
	memory_new = (
		'        if "memory" in features and features["memory"] and not _ada_agent_handles_context():\n'
		"            form_data = await chat_memory_handler("
	)
	text = replace_once(text, memory_old, memory_new, label="middleware-skip-memory")

	web_old = (
		'        if "web_search" in features and features["web_search"]:\n'
		"            form_data = await chat_web_search_handler("
	)
	web_new = (
		'        if "web_search" in features and features["web_search"] and not _ada_agent_handles_context():\n'
		"            form_data = await chat_web_search_handler("
	)
	text = replace_once(text, web_old, web_new, label="middleware-skip-web")

	files_old = """    try:
        form_data, flags = await chat_completion_files_handler(
            request, form_data, extra_params, user
        )
        sources.extend(flags.get("sources", []))
    except Exception as e:
        log.exception(e)

    # If context is not empty, insert it into the messages
    if len(sources) > 0:"""

	files_new = """    if not _ada_agent_handles_context():
        try:
            form_data, flags = await chat_completion_files_handler(
                request, form_data, extra_params, user
            )
            sources.extend(flags.get("sources", []))
        except Exception as e:
            log.exception(e)

    # If context is not empty, insert it into the messages
    if len(sources) > 0 and not _ada_agent_handles_context():"""

	text = replace_once(text, files_old, files_new, label="middleware-skip-files")

	tool_anchor = "                tool_call_retries = 0\n\n                while ("
	tool_insert = """                tool_call_retries = 0

                if _ada_agent_handles_context() and metadata.get("params", {}).get(
                    "function_calling"
                ) == "native" and not metadata.get("tool_servers"):
                    tool_calls.clear()

                while ("""
	text = replace_once(text, tool_anchor, tool_insert, label="middleware-skip-agent-tools")
	path.write_text(text)


def patch_middleware_mcp_tool_skip(path: Path) -> None:
	text = path.read_text()
	old = """                if _ada_agent_handles_context() and metadata.get("params", {}).get(
                    "function_calling"
                ) == "native" and not metadata.get("tool_servers") and not any(
                    str(tid).startswith("server:mcp:")
                    for tid in (metadata.get("tool_ids") or [])
                ):
                    tool_calls.clear()"""
	new = """                if _ada_agent_handles_context() and metadata.get("params", {}).get(
                    "function_calling"
                ) == "native" and not metadata.get("tool_servers"):
                    tool_calls.clear()"""
	if old in text:
		text = text.replace(old, new)
		path.write_text(text)


def patch_main(path: Path) -> None:
	text = path.read_text()
	if "\n    ada,\n" not in text:
		text = replace_once(
			text,
			"    utils,\n    scim,\n)",
			"    utils,\n    scim,\n    ada,\n)",
			label="main-import-ada",
		)
	if 'prefix="/api/v1/ada"' not in text:
		text = replace_once(
			text,
			'app.include_router(configs.router, prefix="/api/v1/configs", tags=["configs"])',
			'app.include_router(configs.router, prefix="/api/v1/configs", tags=["configs"])\n\napp.include_router(ada.router, prefix="/api/v1/ada", tags=["ada"])',
			label="main-router-ada",
		)
	path.write_text(text)


def copy_backend_overlay(root: Path, overlay: Path) -> None:
    src = overlay / "backend/open_webui/routers/ada.py"
    dest = root / "backend/open_webui/routers/ada.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(src.read_text())


def patch_dockerfile(path: Path) -> None:
    text = path.read_text()
    if "PUBLIC_ADA_AGENT_BASE_URL" not in text:
        text = replace_once(
            text,
            "FROM --platform=$BUILDPLATFORM node:22-alpine3.20 AS build\nARG BUILD_HASH",
            "FROM --platform=$BUILDPLATFORM node:22-alpine3.20 AS build\nARG BUILD_HASH\nARG PUBLIC_ADA_AGENT_BASE_URL=http://host.docker.internal:9082",
            label="dockerfile-arg",
        )
        text = replace_once(
            text,
            "ENV APP_BUILD_HASH=${BUILD_HASH}\nRUN npm run build",
            "ENV APP_BUILD_HASH=${BUILD_HASH}\nENV PUBLIC_ADA_AGENT_BASE_URL=${PUBLIC_ADA_AGENT_BASE_URL}\nENV PUBLIC_ADA_AGENT_PORT=9082\nRUN npm run build",
            label="dockerfile-env",
        )
    if '\nENV NODE_OPTIONS="--max-old-space-size=' not in text:
        if "# ENV NODE_OPTIONS=\"--max-old-space-size=4096\"" in text:
            text = replace_once(
                text,
                "# ENV NODE_OPTIONS=\"--max-old-space-size=4096\"\n",
                'ENV NODE_OPTIONS="--max-old-space-size=8192"\n',
                label="dockerfile-node-heap",
            )
        else:
            text = replace_once(
                text,
                "ENV PUBLIC_ADA_AGENT_BASE_URL=${PUBLIC_ADA_AGENT_BASE_URL}\nRUN npm run build",
                'ENV PUBLIC_ADA_AGENT_BASE_URL=${PUBLIC_ADA_AGENT_BASE_URL}\nENV NODE_OPTIONS="--max-old-space-size=8192"\nRUN npm run build',
                label="dockerfile-node-heap-fallback",
            )
    path.write_text(text)


def merge_i18n(target: Path, additions: Path) -> None:
    base = json.loads(target.read_text())
    extra = json.loads(additions.read_text())
    base.update(extra)
    target.write_text(json.dumps(base, ensure_ascii=False, indent='\t') + '\n')


def patch_config_default_features(path: Path) -> None:
	text = path.read_text()
	if "Ada default ENABLE_WEB_SEARCH" in text:
		return
	old = 'os.getenv("ENABLE_WEB_SEARCH", "False").lower() == "true",'
	new = 'os.getenv("ENABLE_WEB_SEARCH", "True").lower() == "true",  # Ada default ENABLE_WEB_SEARCH'
	if old not in text:
		raise SystemExit("patch failed (config-default-features): anchor not found")
	path.write_text(text.replace(old, new, 1))


def patch_chat_default_features(path: Path) -> None:
	text = path.read_text()
	if "Ada default features ON" in text:
		return
	text = replace_once(
		text,
		"\tlet webSearchEnabled = false;\n\tlet codeInterpreterEnabled = false;",
		"\t// Ada default features ON\n\tlet webSearchEnabled = true;\n\tlet codeInterpreterEnabled = true;",
		label="chat-default-features-init",
	)
	for old, new in (
		(
			"\t\twebSearchEnabled = false;\n\t\timageGenerationEnabled = false;",
			"\t\twebSearchEnabled = true;\n\t\timageGenerationEnabled = false;",
		),
		(
			"\t\twebSearchEnabled = false;\n\t\timageGenerationEnabled = false;\n\t\tcodeInterpreterEnabled = false;",
			"\t\twebSearchEnabled = true;\n\t\timageGenerationEnabled = false;\n\t\tcodeInterpreterEnabled = true;",
		),
		(
			"\t\t\twebSearchEnabled = false;\n\t\t\timageGenerationEnabled = false;\n\t\t\tcodeInterpreterEnabled = false;",
			"\t\t\twebSearchEnabled = true;\n\t\t\timageGenerationEnabled = false;\n\t\t\tcodeInterpreterEnabled = true;",
		),
	):
		if old in text:
			text = text.replace(old, new)
	text = text.replace(
		"\t\twebSearchEnabled = true;\n\t\timageGenerationEnabled = false;\n\t\tcodeInterpreterEnabled = false;",
		"\t\twebSearchEnabled = true;\n\t\timageGenerationEnabled = false;\n\t\tcodeInterpreterEnabled = true;",
	)
	path.write_text(text)


def patch_message_input_default_features(path: Path) -> None:
	text = path.read_text()
	if "Ada default features ON" in text:
		return
	text = replace_once(
		text,
		"\texport let webSearchEnabled = false;\n\texport let codeInterpreterEnabled = false;",
		"\t// Ada default features ON\n\texport let webSearchEnabled = true;\n\texport let codeInterpreterEnabled = true;",
		label="message-input-default-features",
	)
	path.write_text(text)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: apply-overrides.py <open-webui-root> <overlay-root>")
    root = Path(sys.argv[1])
    overlay = Path(sys.argv[2])
    patch_stores(root / "src/lib/stores/index.ts")
    patch_settings(root / "src/lib/components/admin/Settings.svelte")
    patch_navbar(root / "src/lib/components/chat/Navbar.svelte")
    patch_chat_controls(root / "src/lib/components/chat/ChatControls.svelte")
    patch_chat(root / "src/lib/components/chat/Chat.svelte")
    patch_chat_default_features(root / "src/lib/components/chat/Chat.svelte")
    patch_message_input_default_features(root / "src/lib/components/chat/MessageInput.svelte")
    patch_config_default_features(root / "backend/open_webui/config.py")
    patch_dockerfile(root / "Dockerfile")
    patch_openai(root / "backend/open_webui/routers/openai.py")
    patch_middleware_features(root / "backend/open_webui/utils/middleware.py")
    patch_middleware_agent_handles_context(root / "backend/open_webui/utils/middleware.py")
    patch_middleware_mcp_tool_skip(root / "backend/open_webui/utils/middleware.py")
    copy_backend_overlay(root, overlay)
    patch_main(root / "backend/open_webui/main.py")
    merge_i18n(
        root / "src/lib/i18n/locales/en-US/translation.json",
        overlay / "i18n-additions.json",
    )
    print("Ada overrides applied.")


if __name__ == "__main__":
    main()
