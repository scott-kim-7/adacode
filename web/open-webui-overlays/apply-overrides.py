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
            "import Tools from './Settings/Tools.svelte';\n\timport AdaEmail from './Settings/AdaEmail.svelte';",
            label="settings-import",
        )
        text = replace_once(
            text,
            "\t\t\t'db'\n\t\t].includes(tabFromPath)",
            "\t\t\t'db',\n\t\t\t'ada-email'\n\t\t].includes(tabFromPath)",
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
\t\t\tid="db"
"""
        text = replace_once(text, '\t\t<button\n\t\t\tid="db"', tab_button, label="settings-tab-button")
        text = replace_once(
            text,
            "\t\t{:else if selectedTab === 'pipelines'}",
            "\t\t{:else if selectedTab === 'ada-email'}\n\t\t\t<AdaEmail />\n\t\t{:else if selectedTab === 'pipelines'}",
            label="settings-tab-content",
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
            "FROM --platform=$BUILDPLATFORM node:22-alpine3.20 AS build\nARG BUILD_HASH\nARG PUBLIC_ADA_AGENT_BASE_URL=http://host.docker.internal:8082",
            label="dockerfile-arg",
        )
        text = replace_once(
            text,
            "ENV APP_BUILD_HASH=${BUILD_HASH}\nRUN npm run build",
            "ENV APP_BUILD_HASH=${BUILD_HASH}\nENV PUBLIC_ADA_AGENT_BASE_URL=${PUBLIC_ADA_AGENT_BASE_URL}\nENV PUBLIC_ADA_AGENT_PORT=8082\nRUN npm run build",
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
    patch_dockerfile(root / "Dockerfile")
    copy_backend_overlay(root, overlay)
    patch_main(root / "backend/open_webui/main.py")
    merge_i18n(
        root / "src/lib/i18n/locales/en-US/translation.json",
        overlay / "i18n-additions.json",
    )
    print("Ada overrides applied.")


if __name__ == "__main__":
    main()
