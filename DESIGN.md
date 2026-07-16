---
name: News Reader
description: A calm, high-density personal news command desk for reading, triage, research, review, market tracking, and auditable AI context.
colors:
  workspace-bg: "#f3f6fa"
  panel: "#ffffff"
  panel-soft: "#ffffffb8"
  panel-strong: "#ffffffeb"
  sidebar-material: "#e8eef7ad"
  border: "#7a899e38"
  hairline: "#54657e24"
  text: "#172033"
  muted: "#667085"
  icon-default: "#4b5563"
  signal-blue: "#2563eb"
  signal-blue-soft: "#2563eb1a"
  row-title: "#0f172a"
  row-title-important: "#a16207"
  row-title-bullish: "#b91c1c"
  row-title-bearish: "#047857"
  row-title-mixed: "#7c3aed"
  row-summary: "#475569"
  row-hover: "#f8fafcdb"
  row-selected: "#e2eafabd"
  queue-row: "#ffffff94"
  queue-row-read: "#f8fafc7a"
  queue-row-selected: "#e1ebfae6"
  detail-text: "#0f172a"
  detail-soft: "#334155"
  detail-card: "#f8fafcc7"
  detail-border: "#94a3b852"
  ready-green: "#065f46"
  pending-amber: "#b45309"
  failure-red: "#b91c1c"
  note-blue: "#1d4ed8"
  video-amber: "#92400e"
  dark-workspace: "#0b1220"
  dark-panel: "#111827"
  dark-text: "#e5e7eb"
  dark-muted: "#94a3b8"
  dark-detail-card: "#0f172a"
  dark-detail-border: "#334155"
typography:
  settings-title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "23px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  surface-title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "21px"
    fontWeight: 760
    lineHeight: 1.14
    letterSpacing: "-0.02em"
  app-title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "18px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.012em"
  detail-title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "19px"
    fontWeight: 740
    lineHeight: 1.32
    letterSpacing: "-0.012em"
  row-title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "16px"
    fontWeight: 700
    lineHeight: 1.32
    letterSpacing: "-0.006em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  row-summary:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.48
  navigation:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "13.25px"
    fontWeight: 660
    lineHeight: 1.18
  compact-label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.25
rounded:
  control: "12px"
  row: "14px"
  panel: "18px"
  pill: "999px"
spacing:
  xs: "4px"
  compact: "6px"
  sm: "8px"
  control: "10px"
  md: "12px"
  panel: "14px"
  lg: "16px"
  overlay: "18px"
  xl: "22px"
components:
  icon-button:
    backgroundColor: "#ffffff00"
    textColor: "{colors.icon-default}"
    rounded: "{rounded.pill}"
    size: "32px"
  topbar-control:
    backgroundColor: "{colors.panel-soft}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    height: "34px"
    padding: "0 12px"
  navigation-button:
    backgroundColor: "#ffffff00"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
  navigation-button-active:
    backgroundColor: "{colors.row-selected}"
    textColor: "{colors.signal-blue}"
    rounded: "{rounded.control}"
    padding: "8px 10px"
  news-row:
    backgroundColor: "{colors.queue-row}"
    textColor: "{colors.text}"
    rounded: "{rounded.row}"
    padding: "10px 12px"
  news-row-selected:
    backgroundColor: "{colors.queue-row-selected}"
    textColor: "{colors.row-title}"
    rounded: "{rounded.row}"
    padding: "10px 12px"
  input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
  status-chip:
    backgroundColor: "{colors.panel-soft}"
    textColor: "{colors.muted}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  detail-card:
    backgroundColor: "{colors.detail-card}"
    textColor: "{colors.detail-text}"
    rounded: "{rounded.row}"
    padding: "12px 14px"
  settings-panel:
    backgroundColor: "{colors.panel-strong}"
    textColor: "{colors.text}"
    rounded: "{rounded.panel}"
    padding: "18px 18px 20px"
---

# Design System: News Reader

## 1. Overview

**Creative North Star: "The Quiet Command Desk / 安静的指挥台"**

News Reader is a personal, high-frequency news workstation for reading, triage, daily briefings, notes, reminders, tracked topics, market views, versioned reviews, and AI-assisted research. It is built for recurring expert work: the interface should disappear into the task, preserve the user's mental map, and make a large amount of state understandable without becoming chaotic.

Apple's design philosophy is applied here as a method, not as visual imitation. Purpose keeps the current reading or research task dominant. Agency gives the user direct navigation, reversible actions, visible state, and clear exits. Responsibility keeps imports, generated summaries, translations, chat context, errors, and external research auditable. Familiarity uses standard web and platform conventions. Flexibility adapts structure across desktop, tablet, mobile, keyboard, pointer, touch, light mode, and dark mode. Simplicity removes unnecessary competition. Craft and restrained delight appear through precise typography, responsive feedback, and durable details rather than decoration.

At the interface level, every screen must express **Hierarchy, Harmony, and Consistency**. Content and the current task receive the highest visual priority. Navigation, controls, and status occupy distinct functional layers. The same state or action must retain the same meaning across the feed, detail panel, daily briefing, tracked topics, market workbench, reviews, chat, and settings.

The current product has three adaptive structures:

- **Desktop command desk:** collection and source navigation on the left, the active list or workbench in the center, and contextual reading or research on the right. The current implementation uses `minmax(206px, 232px) minmax(420px, 36vw) minmax(460px, 1fr)` with a `12px` gap.
- **Compact desktop and tablet (`≤1180px`):** the workspace becomes one column, collection groups form a compact matrix, and the detail surface becomes a bottom drawer.
- **Mobile (`≤768px`):** the feed becomes the primary full-height surface, the detail view becomes a full-screen horizontal transition, collections move to a three-item bottom navigation, and secondary filters move to sheets. A local `≤640px` breakpoint stacks dense editor grids.

The frontmatter records implementation tokens that exist today. The rules below are the normative contract for new work and for planned cleanup. Existing legacy exceptions — broad decorative gradients, blur on ordinary content panels, scattered literal status colors, and fallback-only variables such as `--success` or `--text-secondary` — must be migrated rather than copied. Hidden scrollbars are an intentional density choice in this personal workstation; any horizontally scrollable control region must provide another visible overflow cue.

**Key Characteristics:**

- Stable, content-first three-zone workflow on desktop.
- Compact system typography optimized for Chinese and English scanning.
- Cool neutral surfaces with Signal Blue reserved for focus, selection, and primary action.
- Explicit state grammar for reading, research, review, market, and AI workflows.
- Functional material and elevation only where they clarify control or spatial hierarchy.
- Structured grouping for advanced rules, filters, settings, and research actions without hiding controls the user considers important.
- Responsive structure rather than merely shrinking the desktop interface.

**The Purpose-before-Chrome Rule.** Every element must improve reading, triage, research, review, recovery, or return-to-context. If removing it does not reduce comprehension or control, remove it.

**The Stable Mental Map Rule.** Keep collection, active work, and context in predictable places. Preserve selection, scroll anchors, filter scope, and return paths when the user moves between modes.

**The Agency Rule.** The user must be able to leave a mode, cancel an edit, recover from a failed action, and understand what changed. Destructive or bulk actions need confirmation, undo, or another proportionate recovery path.

**The Responsibility Rule.** Clearly distinguish source material, user-authored notes, generated content, external research, pending work, stale output, and failures. AI must never appear more certain or better sourced than its context supports.

## 2. Colors

The implemented palette is a cool blue-gray workspace with translucent structural layers, Signal Blue for interaction, and semantic colors for workflow status. Apple-like restraint means color communicates hierarchy and state; it does not decorate empty space.

### Primary

- **Signal Blue** (`#2563eb`): focus rings, active navigation, selected controls, primary actions, unread indicators, and links. Its rarity gives it authority.
- **Signal Blue Soft** (`#2563eb1a`): selected or active tonal surfaces. Combine with text, shape, or outline so selection does not depend on color alone.
- **Selected Row** (`#e2eafabd`) and **Selected Queue Row** (`#e1ebfae6`): current collection and current item surfaces in light mode.

### Secondary

- **Ready Green** (`#065f46`): complete, available, configured, or successfully generated.
- **Pending Amber** (`#b45309`): queued, pending, stale, due, waiting, or caution.
- **Failure Red** (`#b91c1c`): failed, destructive, urgent, or unavailable.

### Tertiary

- **Bullish Red** (`#b91c1c`), **Bearish Green** (`#047857`), and **Mixed Violet** (`#7c3aed`): market direction only. They are not generic success or failure colors in market contexts.
- **Note Blue** (`#1d4ed8`): user-authored notes, idea previews, and archived research context.
- **Video Amber** (`#92400e`): video and non-standard media identification.
- Review outcomes and lifecycle events may use green, red, gray, cyan, violet, amber, or pink only when paired with an explicit label such as “成立”, “未成立”, “不可判断”, “进展”, or “修订”.

### Neutral

- **Workspace Blue-Gray** (`#f3f6fa`): light-mode app background.
- **Panel White** (`#ffffff`): primary readable content surface.
- **Soft Panel** (`#ffffffb8`) and **Strong Panel** (`#ffffffeb`): structural material values used by current controls and raised surfaces.
- **Sidebar Material** (`#e8eef7ad`): implemented navigation and contextual panel tint.
- **Ink** (`#172033`) and **Row Title Ink** (`#0f172a`): primary UI and content text.
- **Muted Slate** (`#667085`): secondary labels and metadata; it must still meet WCAG AA where it carries required information.
- **Row Summary Slate** (`#475569`) and **Detail Soft Slate** (`#334155`): summaries and long-form secondary copy.
- **Hairline** (`#54657e24`) and **Detail Border** (`#94a3b852`): separation without card-wall heaviness.
- **Dark Workspace** (`#0b1220`), **Dark Panel** (`#111827`), **Dark Text** (`#e5e7eb`), and **Dark Muted** (`#94a3b8`): dark-mode structural roles.

**The Functional Material Rule.** Translucency, blur, and background sampling belong to navigation, toolbars, popovers, overlays, drawers, and other controls that float above content. Ordinary reading rows, detail prose, notes, AI output, tracked timelines, and review history use stable tonal or solid surfaces. Do not extend the current broad blur and gradient treatment to new content surfaces.

**The State Color Rule.** Every semantic color must answer one of these questions: what is selected, what changed, what is the status, what market direction is expressed, or what action is available?

**The Blue Rarity Rule.** Signal Blue marks the current point of interaction. If several major zones are blue at once, hierarchy has failed.

**The Direction Label Rule.** Market red, green, and violet always appear with text, an icon, a pattern, or another redundant cue. Color alone never carries bullish, bearish, mixed, review, or error meaning.

**The Dual-theme Rule.** Every new color must define and visually verify light and dark behavior. Avoid translucent mixes whose meaning or contrast changes unpredictably between themes.

## 3. Typography

**Display Font:** None. News Reader does not use display typography.

**Body Font:** System sans (`-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`).

**Label/Mono Font:** System sans; no separate monospaced role is established.

**Character:** Platform-native, compact, calm, and highly legible. One system family creates familiarity and lets hierarchy come from placement, size, weight, and state instead of font novelty.

### Hierarchy

- **Settings Title** (`23px`, 700, `1.2`): the largest administrative heading; never used as marketing display type.
- **Surface Title** (`21px`, 760, `1.14`): available for a visible workbench title. The current feed header is visually hidden, so do not reserve empty height for it.
- **App Title** (`18px`, 700, `1.2`): persistent desktop product identity.
- **Detail Title** (`19px`, 740, `1.32`): selected story, daily briefing, idea, tracked topic, review, or right-panel title.
- **Row Title** (`16px`, 700, `1.32`): primary item title; read rows may reduce weight and contrast but remain legible.
- **Body** (`14px`, 400, `1.5`): forms, normal interface copy, AI context, and reading content baseline.
- **Row Summary** (`13px`, 400, `1.48`): list preview and compact timeline summary.
- **Navigation** (`13.25px`, 660, `1.18`): collection navigation and primary compact commands.
- **Compact Label** (`12px`, 600, `1.25`): filters, metadata, controls, and state chips.
- **Micro Metadata** (`11px`–`11.5px`): source/time lines, date counts, and short badges only. Never use it for instructions, error recovery, form help, or required status.

The detail reader currently supports small (`0.93`), medium (`1`), and large (`1.16`) font scales. Preserve this user control and apply it consistently to summary, AI points, conclusion, article body, original content, notes, and chat text.

**The Product Scale Rule.** Do not introduce display fonts, fluid hero type, oversized headings, or dramatic editorial typography. This is a workstation, not a magazine or landing page.

**The Chinese Readability Rule.** Do not shrink body, summaries, instructions, or recovery copy below `13px`. Use hierarchy, grouping, and layout when density becomes too high.

**The Wide Detail Surface Rule.** Do not impose a fixed `65–75ch` line-length cap. Reading content may use the available detail width; preserve readability through the user-controlled font scale, line height, paragraph rhythm, and section hierarchy.

**The Native Rhythm Rule.** Use modest negative tracking only on compact titles. Body, Chinese copy, labels, and metadata retain natural spacing. Apply `text-wrap: balance` to short headings and `text-wrap: pretty` to prose where supported.

## 4. Elevation

News Reader uses tonal layering first and physical elevation second. A shadow means that a surface is temporarily or spatially above the workspace. A blur means that a functional control layer floats over changing content. Neither is general decoration.

### Shadow Vocabulary

- **Subtle Structural Shadow** (`0 1px 2px rgba(15, 23, 42, 0.05), 0 4px 10px rgba(15, 23, 42, 0.05)`): currently used on major desktop panels. Prefer hairlines and tonal separation when equivalent.
- **Soft Lift** (`0 8px 14px rgba(31, 41, 55, 0.06)`): limited floating or transitional surface.
- **Popover Lift** (`0 14px 28px rgba(15, 23, 42, 0.14)`): display preferences and compact popovers.
- **Settings Lift** (`0 20px 48px rgba(15, 23, 42, 0.16)`): blocking settings overlay.
- **Mobile Drawer Lift** (`0 -8px 26px rgba(15, 23, 42, 0.14–0.16)`): bottom sheets and tablet detail drawer.
- **Mobile Navigation Edge** (`0 -2px 12px rgba(2, 6, 23, 0.08)`): fixed bottom navigation separation.

Most implemented state transitions last `160ms`; press feedback uses `120ms`; drawer transitions use `200ms`. Continue using short ease-out or standard ease curves for selection, disclosure, hover, focus, and drawer movement. The `2s` reading-anchor flash is state feedback, not page choreography.

**The Flat Content Rule.** News rows, detail prose, AI cards, note cards, market items, tracked timelines, daily sections, and review history remain flat at rest. Use borders, spacing, or tonal contrast instead of decorative shadows.

**The Control-layer Rule.** Top bars, sticky toolbars, popovers, settings, filter sheets, and drawers may use blur or elevation when it clarifies that they float above content. Avoid stacking several translucent layers over each other.

**The Motion-as-State Rule.** Motion communicates cause and effect: selection, press, expansion, loading, return-to-anchor, sheet entry, or detail entry. No orchestrated page-load sequences, bounce, elastic movement, or ornamental reveals.

**The Reduced-motion Rule.** Every new animation must include a `prefers-reduced-motion` alternative. The current stylesheet lacks a global reduced-motion treatment; treat that as migration work, not as permission to omit it.

## 5. Components

Components should feel familiar enough that an experienced user can act without decoding them. Each interactive component needs default, hover, focus-visible, active, disabled, loading, and error behavior where applicable.

### Buttons

- **Icon button:** `32px` circular control with a `16px` glyph on desktop. A visible focus ring uses Signal Blue. Icon-only controls require an accessible name and tooltip. Important persistent actions remain directly reachable and are organized into semantic groups instead of an overflow menu.
- **Topbar control:** `34px` high, `12px` radius, quiet translucent fill, compact label, and `0.96` press scale.
- **Text action:** `8px 12px` padding and `12px` radius. The primary action is determined by task hierarchy, not by adding more saturated color.
- **Mobile target:** use the largest practical target that preserves separation. Compact controls below `44×44px` are intentional when a universal enlargement would create overlap; flag actual collision, clipping, or mis-tap risk rather than size alone.
- **Destructive action:** requires a clear label and proportionate confirmation or recovery. Destructive styling appears only when the action is imminent.

### Chips

- Chips are compact pills for filters, source/media kinds, workflow status, review outcomes, and market direction.
- A selected filter, pending task, failed task, user note, generated summary, bullish direction, and review outcome are different semantic roles; do not reuse one color treatment merely because the shape is the same.
- Labels remain visible when meaning would otherwise require color or icon memory.

### Cards / Containers

- **Control radius:** `12px`; **row radius:** `14px`; **panel radius:** `18px`; pills use `999px`.
- Cards exist only for real grouping: an editable note, generated AI block, reminder collection, settings group, or discrete review event. A normal list item does not become a floating card.
- Avoid nested cards. Prefer dividers, section headings, structured grouping, and stable background layers.
- Content cards use solid or low-translucency tonal surfaces and no resting shadow.

### Inputs / Fields

- Inputs use a stable panel/workspace mix, `12px` radius, `13px`–`14px` type, and a visible Signal Blue focus treatment.
- Labels, current values, helper text, errors, and associated actions stay spatially grouped.
- Placeholders meet the same practical contrast threshold as other necessary text and never replace persistent labels in complex forms.
- Native controls and standard browser behavior are preferred over invented affordances.

### Feedback and Recovery

- Pending, ready, and failed feedback stays inside the row, editor, evidence card, or detail surface that initiated the operation. Do not send right-panel form errors to the center-list footer.
- A failed optimistic personal action restores the previous state and names the unsaved action beside the affected row or open detail, with a direct retry. Automatic read tracking does not create repetitive row alerts.
- Editors preserve the user's current input on failure, keep the primary action available for another attempt, and use a local `role="alert"`; pending and confirmed messages use a local `role="status"`.
- When the resulting content change is already visible, that change is the primary success feedback. Do not add permanent success chips or duplicate background-task labels.
- User-facing feedback explains the failed task and next action. Raw internal error codes are replaced with a stable recovery message unless the server already returned useful human-readable detail.

### Navigation

- Desktop navigation is grouped into **阅读**, **个人队列**, **研究**, and **市场**, followed by source filtering. Every collection remains directly visible; semantic grouping and spacing reduce competition rather than hiding destinations.
- Navigation labels occupy the leading column while short counts use a quieter trailing badge. Exactly one current collection uses a quiet blue selected surface, a visible text label, and `aria-current="page"`.
- At `≤1180px`, the four collection groups form a compact matrix inside the single-column workspace before detail opens as a drawer; the breakpoint must prevent three-column horizontal overflow.
- Mobile keeps three persistent bottom destinations and contextual sheets for the remaining collections, sources, display preferences, and secondary actions. The active secondary destination replaces the generic “更多” label with its actual collection name, and sheet grouping mirrors desktop information architecture.
- Navigation changes preserve the reading anchor and selection context where possible.

### News Row

- A row carries source, time, unread state, title, summary, personal flags, note preview, reminder, and market tags in a stable order. Source and time retain separate text roles but read as one adjacent `来源 · 时间` provenance cluster; the cluster compresses before it competes with actions.
- The article row header uses a `minmax(0, 1fr)` provenance column and a compact trailing actions column. Important, read later, and favorite remain directly visible, while personal context no longer competes with provenance for the same horizontal space.
- The title and summary are the primary scan targets. Inline actions remain secondary; on pointer devices they strengthen on hover, focus-within, or selection, while touch devices keep them discoverable. Do not add a “More” menu or stricter content truncation to create space.
- User-note state and preview appear after the summary as one lightweight annotation group. Reminder and market tags follow in one wrapping context strip; do not create nested cards for each state.
- The read-later button is the sole row-level expression of its background detail task: neutral before queuing, amber while fetching, green when detail is ready, and red when fetching fails. Its accessible label and tooltip name the exact state; do not repeat that state as a per-row text chip.
- Read/unread uses more than one cue: unread dot plus title weight/contrast. The transparent read dot keeps provenance aligned. Selection uses tonal background plus outline/ring, including when the item is already read.
- Optimistic personal-state changes require rollback plus a local “未保存，已恢复原状态” message and retry action.

### Toolbars and Filters

- A toolbar exposes all actions relevant to the current collection or detail mode. Every current detail action is important and remains directly visible or reachable without a “More” menu.
- Establish hierarchy through semantic groups, stable ordering, compact internal spacing, larger inter-group spacing, and whole-group wrapping rather than hiding actions.
- The center feed toolbar keeps three stable layers: current-view filters and creation controls, reading and ordering controls, then bulk and maintenance controls. Context changes which controls apply, not their semantic placement.
- On mobile, center-toolbar groups remain in one direct horizontal sequence. Reset to the leading edge when the collection changes and use dynamic edge fades to reveal overflow position.
- Horizontal scrolling toolbars on mobile must provide affordance that more actions exist; never rely solely on an invisible scrollbar.

### Detail Panel

- The detail panel is the contextual reading and research surface. Its order is title, provenance and metadata, current status, primary actions, personal state, generated context, source content, and deeper research.
- Empty detail space should help the user resume or understand the next action without competing with the feed.
- On compact desktop it is a bottom drawer; on mobile it keeps the current full-screen transition and edge-swipe return behavior. Preserve list position and selected state; do not add a persistent back bar or browser-history integration solely for navigation parity.
- Detail font scaling is user-controlled and persistent.

### Daily, Tracking, Market, and Reviews

- Daily briefings retain section hierarchy and source traceability without magazine-style presentation.
- Tracked topics keep their important weights, scoring, exclusions, and matching parameters visible, but divide them into clear sections with stable alignment and stronger labels.
- Tracking editors use flat semantic sections rather than nested cards. Keyword rules keep persistent labels and nearby help; numeric parameters use a label-to-value comparison grid with two columns when space permits and one column below 640px. Save actions remain visible at the bottom of the editor scroll context, without hiding any parameter.
- Tracking and review editors keep validation, pending, and failure feedback inside the active right-panel form. Inputs survive failed saves, duplicate submission is blocked while pending, and review-detail load failures expose retry in the detail timeline.
- Market workbench content keeps user-authored ideas, generated summaries, direction labels, and source news visually distinct.
- Versioned reviews show current judgment, outcome, evidence, revision history, reminder state, and retracking actions in one scrollable context. Timeline color never replaces event labels.

### Chat / AI Context

- Chat lives inside detail as a research mode, not as an independent chatbot product.
- Always show the current provider/model and whether context comes from full detail, summary/metadata, or external search.
- Pending, streaming/working, generated, stale, failed, empty, archived, and retry states need explicit copy.
- User messages, assistant output, user notes, article text, and external research use distinct roles and remain traceable.

### Settings Overlay

- Settings is a true blocking overlay and may use the strongest elevation vocabulary.
- Service, model, and release-note sections use familiar navigation with visible labels; cryptic single-letter icons are supplemental, not sufficient by themselves.
- Configuration surfaces show current value, proposed value, service health, save status, and failure recovery together.

## 6. Do's and Don'ts

### Do:

- **Do** preserve the command-desk mental model and left-to-right desktop flow.
- **Do** make the active content or task visually dominant while navigation and chrome recede.
- **Do** use the system font stack, familiar controls, direct manipulation, clear feedback, and visible exits.
- **Do** use Signal Blue (`#2563eb`) only for focus, selection, links, unread state, and meaningful primary actions.
- **Do** maintain a redundant, consistent grammar for read/unread, important, read later, favorite, reminder, note, tracked, pinned, generated, stale, failed, review, and market states.
- **Do** preserve user context: selection, scroll anchor, collection, source filter, detail mode, and draft state.
- **Do** expose loading, empty, pending, failed, stale, retry, and recovery states in plain Chinese.
- **Do** identify AI provider, model, context scope, source boundary, external-search use, and failure mode.
- **Do** design for keyboard, pointer, touch, screen readers, light/dark themes, reduced motion, and WCAG AA contrast from the start.
- **Do** use semantic grouping and stable layout for tracking rules, review workflows, market controls, filters, and settings without hiding important controls.
- **Do** verify desktop, compact desktop/tablet, and mobile whenever navigation, layout, typography, or a persistent control changes.

### Don't:

- **Don't** make News Reader look or behave like a marketing landing page, magazine site, showcase UI, or generic SaaS dashboard.
- **Don't** use hero-style visual drama, oversized typography, display fonts, decorative gradients, glassmorphism as a default, ornamental motion, or low-density card walls.
- **Don't** imitate Apple through excessive blur, floating glass cards, large rounded rectangles, or decorative hardware metaphors. Apply Apple principles through hierarchy, harmony, consistency, agency, familiarity, flexibility, and craft.
- **Don't** add blur or translucency to ordinary content merely because the topbar, popover, or drawer uses material.
- **Don't** use decorative effects that reduce scan speed or make core state harder to trust.
- **Don't** give every advanced control the same visual weight; use grouping, headings, spacing, and order while keeping important controls reachable.
- **Don't** use an icon vocabulary that requires guessing. Pair unfamiliar or consequential icons with labels, tooltips, or contextual text.
- **Don't** remove every cue that a horizontally scrollable region continues beyond the viewport; hidden scrollbars require an alternative such as an edge fade.
- **Don't** rely on red, green, blue, violet, opacity, or animation alone to communicate meaning.
- **Don't** add full-page choreography, bounce, elastic motion, or content that starts invisible and depends on animation to appear.
- **Don't** use repeated uppercase eyebrows, numbered section scaffolding, side-stripe accents, gradient text, or one-off component styles.
- **Don't** flatten errors into vague failures or hide retry and recovery actions.
- **Don't** make AI features opaque, imply knowledge beyond the available context, hide search usage, or blur news facts, user notes, generated summaries, and external research.
- **Don't** copy legacy literal colors, undefined fallback variables, broad panel gradients, or content-layer blur into new components; migrate them into the documented token and state system.
