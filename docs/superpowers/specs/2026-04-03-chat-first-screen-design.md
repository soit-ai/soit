# Chat First Screen Design

Date: 2026-04-03
Status: Proposed
Scope: Web chat first screen, top header, empty-thread welcome surface

## 1. Goal

Upgrade the SOIT chat first screen so it reads as a mature enterprise AI workspace rather than a generic AI chat shell.

The redesign should improve first-impression brand quality, clarify hierarchy, and make the composer the obvious primary action without changing the underlying chat runtime.

## 2. Context

The current chat landing experience already has the right structural ingredients:

- a persistent chat sidebar
- a top header with agent and model controls
- a centered empty-thread welcome state
- a composer with mode toggles
- suggestion cards for quick start prompts

But the first screen currently has several problems:

- the visual center of gravity sits too low on the page
- the welcome area consumes too much vertical space before the user reaches the real action
- the recommendation cards feel closer to a generic consumer AI prompt gallery than to an enterprise AI workspace
- the top header behaves more like a collection of controls than a stable work context bar
- decorative signals such as rotating logos, gradient text treatment, and colorful suggestion cards push the page toward a template-like AI assistant feel

Given the project design context, this is the wrong expression. SOIT should feel:

- professional
- clear
- forward-looking

And it should resemble a modern cloud workspace, not a generic AI chatbot shell.

## 3. Decisions Locked In

### 3.1 Priority

This redesign is `brand-first`.

### 3.2 Visual Reference

The desired visual reference is `Linear / Vercel`.

This means the page should feel:

- restrained
- precise
- high-signal
- quietly premium

It should not feel:

- playful
- candy-colored
- overly soft
- marketing-heavy

### 3.3 Scope Boundary

This pass should modify:

- the main first-screen content area
- the top header above the chat workspace

This pass should not materially redesign:

- the left conversation sidebar
- the message thread layout once the conversation has started
- chat runtime behavior
- thread persistence, agent switching, or model selection logic

### 3.4 Chosen Direction

The chosen first-screen concept is `Command Surface`.

The empty-thread state should feel like the user has already entered a serious AI workspace and is standing at the main command input, rather than arriving on a decorative assistant welcome page.

## 4. Chosen Approach

The redesign should be executed as a focused empty-state refinement rather than a whole-page rewrite.

Implementation order:

1. Reframe the top header as a work context bar
2. Compress and sharpen the welcome section
3. Promote the composer to the clear primary surface
4. Replace colorful suggestion cards with more task-oriented quick starts
5. Tune spacing, borders, and interaction polish

This approach was chosen because it delivers strong visual improvement while keeping risk low:

- it preserves current chat behavior
- it avoids touching the sidebar IA
- it limits regression scope to the page chrome and empty-thread surface

## 5. Design Principles

### 5.1 Input Is The Hero

On the first screen, the composer is the primary action and should be visually treated as the anchor of the page.

### 5.2 Context Before Tools

The top header should first explain where the user is and which agent/model context is active. Secondary tools should not compete with that understanding.

### 5.3 Brand Through Restraint

SOIT should feel premium because of typography, spacing, surface hierarchy, and control discipline, not because of rotating logos, colorful gradients, or decorative AI tropes.

### 5.4 Enterprise Prompts, Not Demo Prompts

Quick-start content should reflect realistic enterprise usage patterns and product value, not generic "look what AI can do" examples.

### 5.5 Empty State Should Teach Through Action

The first screen should help the user start working immediately. It should not require them to decode the layout before acting.

## 6. Information Architecture

### 6.1 Top Header

The top header should become a `context bar`.

Its content should be prioritized as:

1. current workspace context
2. agent selector
3. model selector
4. secondary actions

Expected outcomes:

- stronger relationship between selected agent and current thread title
- clearer grouping of agent/model controls
- lower visual weight for share and overflow actions

### 6.2 First-Screen Main Area

The empty-thread main area should be organized into three vertical zones:

1. compact identity and framing
2. primary command surface
3. quick-start tasks

This structure should be tighter than the current layout and vertically biased upward so the user sees the real action immediately.

## 7. Surface Design

### 7.1 Header Treatment

The header should move toward a quieter control-surface style:

- tighter spacing
- clearer grouping
- less button-like noise
- stronger alignment between title and selectors

The current separate feeling between title area and controls should be reduced.

### 7.2 Welcome Surface

The current welcome module should be substantially compressed.

Required changes:

- remove the rotating model logo treatment
- remove decorative gradient-heavy emphasis
- keep a short SOIT identity statement
- keep one short explanatory line
- retain capability tags, but make them read like work domains rather than marketing badges

The welcome surface should feel like a workspace preface, not a hero section.

### 7.3 Composer Surface

The composer should become the dominant first-screen element.

Required changes:

- move it visually higher in the empty state
- strengthen its shape, hierarchy, and affordance
- preserve current controls for deep thinking, web search, code mode, attachment, and send
- reduce tutorial-like helper noise in the default state
- maintain the compliance / hint line, but at a lower visual priority

The desired effect is a command console feel, not a chat toy feel.

### 7.4 Quick-Start Suggestions

Suggestion cards should shift from colorful inspirational prompts to task-oriented enterprise quick starts.

Required changes:

- remove the current candy-gradient card language
- use lower-saturation surfaces with stronger type hierarchy
- keep click-to-fill or click-to-send efficiency
- rewrite prompts so they feel aligned with SOIT use cases

Example direction:

- summarize or analyze a document
- generate an agent prompt or instruction set
- research a topic with web search
- explain or draft code for an engineering task

## 8. Copy Direction

### 8.1 Welcome Copy

The first-screen copy should become more workbench-oriented and less assistant-greeting-oriented.

It should emphasize:

- SOIT as a workspace for structured AI work
- directness
- confidence
- low-friction start

It should avoid:

- overly warm assistant language
- vague "help and creativity" positioning
- generic AI companion phrasing

### 8.2 Capability Labels

Capability labels should read as concise operating domains, for example:

- Knowledge Retrieval
- Code Collaboration
- Multi-Model Reasoning

Exact phrasing can remain localized, but the tone should stay operational and clear.

### 8.3 Suggestion Copy

Suggestion copy should represent realistic first actions for platform users and builders.

The suggestions should feel useful enough that a real user might click one immediately.

## 9. Motion and Interaction

The redesign should reduce decorative motion.

Required interaction posture:

- subtle hover response on cards and controls
- crisp focus states
- no ambient animation that exists only to signal "AI"
- reduced-motion safe behavior by default

If animation remains, it should serve clarity or responsiveness rather than spectacle.

## 10. Accessibility and Responsiveness

The redesigned first screen must preserve or improve:

- WCAG AA contrast
- visible focus states on all header and composer controls
- keyboard access for the primary empty-thread flow
- readable hierarchy at narrower desktop widths

Responsive intent:

- desktop remains the primary optimized target
- the header should collapse gracefully without making agent/model context unreadable
- the composer must stay dominant without causing control overflow

## 11. Implementation Boundaries

### 11.1 Files Expected To Change

- `web/app/routes/chat/index.tsx`
- `web/app/components/ui/chat/thread.tsx`
- `web/app/i18n/zh-CN/chat.ts`

Optional follow-up file if needed:

- corresponding non-Chinese chat locale files, if parity is required immediately

### 11.2 Files Explicitly Out Of Scope

- `web/app/routes/chat/ui/box-sidebar.tsx`
- chat services and runtime adapters
- thread persistence logic
- assistant message rendering

## 12. Risks and Controls

### 12.1 Risk: Brand Upgrade Still Looks Like Generic AI Chat

If the redesign keeps too much of the current welcome-page grammar, the result will still feel template-like.

Mitigation:

- remove rotating model branding
- remove high-saturation prompt cards
- use stronger typographic restraint

### 12.2 Risk: The Page Becomes Too Severe

If the page becomes too stripped down, users may lose the sense that SOIT is an AI-native product.

Mitigation:

- retain a compact identity statement
- preserve capability labels
- keep quick-start tasks visible

### 12.3 Risk: Header Refactor Hurts Existing Habits

Reordering header controls may create short-term friction for returning users.

Mitigation:

- keep existing actions and selectors
- change hierarchy and grouping before changing behavior
- avoid relocating controls into hidden menus unless necessary

## 13. Verification Strategy

Implementation based on this design should verify:

- empty-thread screen renders correctly with no active thread
- existing conversation state still renders normally once messages exist
- quick-start tasks still trigger the expected prompt behavior
- agent selection still changes context correctly
- model selection still works
- share and overflow actions still function
- no text overflow in Chinese labels
- no layout breakage across standard desktop widths

## 14. Success Criteria

The redesign is successful when:

- the first screen looks unmistakably more like a modern enterprise AI workspace
- the composer is the most obvious action within one visual scan
- the page no longer reads as a generic AI chat template
- the header feels like a stable context bar rather than a control pile
- recommendation content feels useful, not decorative
