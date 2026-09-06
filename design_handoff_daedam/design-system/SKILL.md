---
name: daedam-design
description: Use this skill to generate well-branded interfaces and assets for 대담 (Daedam, AI 음성 모의면접), either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the readme.md file within this skill, and explore the other available files.
If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.
If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

Ground rules that are easy to get wrong:
- Token names live in tokens/*.css. Light screens: warm paper `--color-bg #F5F3EF`, ink `#16233A`, amber accent `--color-accent #B8802E`, positive green `#3A7A68`. Sub-pixel sizes stay (13.5px is 13.5px).
- Amber only for things the user must look at; green for in-range / connected / the candidate's voice. No red anywhere.
- Light screens: one soft card shadow (`--shadow-card`), no hover color on buttons, radii 4/3/2 only.
- The **stage** (면접, 문턱 띠, 리서치, 분석 중, 리포트 머리, 랜딩 데모) is a separate world: `--stage-bg` radial night, a still keylight from above, the matte glass sphere (`components/stage/Avatar.jsx`) with amber light when the interviewer speaks and mint when listening. Shadows and gradients are allowed there. The question sits directly under the sphere, Pretendard 25/600/-.02em, paper `#F4EFE6`.
- Logo is symbol C3 (`assets/logo/`): one circle split vertically, ink left (interviewer), amber right (candidate). Never the old square mark.
- Icons are line SVGs from `components/core/Icons.jsx` (1.5px stroke) — no text glyphs (→ ✓ ▲ ▶).
- One font (Pretendard Variable). Numbers always `tabular-nums`.
- Korean copy in plain 존댓말; no emoji, no exclamation marks. State facts; when a value can't be measured, say so instead of showing 0.
- Audio-rate values (sphere light, waveform) go ref → style, never React state.
