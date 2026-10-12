# VixenOne — Stitch Design Spec (single source)

Version: 12 Oct 2026 · Supersedes all earlier prompts in chat.

---

## 0. How to use Stitch (read first)

- One Stitch project only: **VixenOne**.
- **Method that works (learned):** never generate a content screen from a full prompt. **Duplicate the closest approved screen → edit the copy**, one section per edit, short prompts, no master block in edits.
- Full new-screen prompts lost styling 3 times (S1, S2). Duplicate-then-edit held styling every time.
- Delete superseded copies immediately. One approved screen per row below.
- Section 2 prompts = original content/data spec. Section 5 = what was actually approved (overrides section 2 where they differ).

### Tracker

| ID | Screen | Built from | Status |
| --- | --- | --- | --- |
| S0 | Design-system sheet | new | Approved |
| L1–L4 | App shell (expanded, evaluation, collapsed, drawer) | new | Approved |
| S1 | Sign in | new + styling edit | Approved |
| S2 | Evaluations list | older S2 + edits | Approved |
| S2-empty | Empty state | dup S2 | Pending check |
| S3 | Create evaluation | dup S2 | Approved |
| S3-error | File error | dup S3 | Pending check |
| S4 | Requirements review | dup S3 | Approved (sidebar fix) |
| S5 | Vendor comparison | dup S4 | Approved (icon fix) |
| S5-loading | Analysis in progress | dup S5 | Optional — not run |
| S6 | Finding drawer | dup S4 → re-run on dup S5 | Drawer content approved |
| S7 | Recommendation | dup S5 | Approved (scoring fix) |
| S7-insufficient | Insufficient info | dup S7 | Approved |
| S7-P | Print report | dup S7 | Approved (mandatory tag fix) |

---

## 1. MASTER BLOCK (paste at the top of every prompt)

```
DESIGN SYSTEM — apply exactly:
Restrained, modern enterprise SaaS (Linear / Stripe dashboard feel). Clean and decent, not flashy. No gradients, illustrations, glassmorphism, emoji or heavy shadows. Light theme. Desktop 1440px.
Font: Inter. Tabular numbers. Page title 24/600, section title 18/600, body 14/400, meta 12/500.
Colours: page #FFFFFF, surface #F8FAFC, border #E2E8F0, text #0F172A, muted text #64748B. Single accent indigo #4F46E5 (tint #EEF2FF for active backgrounds) — primary buttons, links, focus ring, active nav, active tab only. No other accent, no orange/brown.
Radius 8px. 1px borders instead of shadows. 4px spacing grid. Card padding 20px. Generous whitespace.
Finding status badges (filled pills, colour + text always): Compliant (green #15803D on #F0FDF4) · Partially compliant (amber #B45309 on #FFFBEB) · Non-compliant (red #B91C1C on #FEF2F2) · Not evidenced (slate #475569 on #F1F5F9) · Needs review (violet #7C3AED outline + flag icon) · Inferred (dashed slate border, italic text).
Risk badges with small line icon: Exclusion, Omission, Ambiguity, Contradiction, Unknown cost. Severity: High (red), Medium (amber), Low (slate).
Currency INR with Indian grouping (₹3,85,000). GST always shown separately.
Use only shadcn/ui-style components: Sidebar, Card, Table, Tabs, Badge, Button, Dialog, Sheet, Slider, Switch, Select, Input, Textarea, Tooltip, Progress, Alert, Separator, Accordion, Dropdown Menu, Avatar.

LAYOUT LOCK — never break (logged-in screens):
- Exactly two navigation zones: a HEADER BAR on top and a SIDEBAR below it on the left. Nothing else navigates.
- HEADER BAR: full viewport width, 56px, white, 1px bottom border, fixed. Left: square panel-toggle icon button (collapses sidebar), then "VixenOne" text wordmark with small indigo dot. Right edge: avatar with initials "PS" + "Priya Sharma" / "Facilities Manager", dropdown (Profile, Sign out). Nothing else in the header — no nav links, search or tabs.
- SIDEBAR: starts directly BELOW the header, runs full height to the bottom of the viewport, background #F8FAFC, 1px right border.
  Expanded 240px, top to bottom: (1) full-width primary button "+ New evaluation"; (2) nav item "Evaluations" (list icon), active = indigo text on #EEF2FF; (3) muted label "RECENT" + 3 single-line truncated items: "Housekeeping — Andheri East", "Security — Powai Campus", "Pantry & Cafeteria — BKC"; (4) pinned at bottom above a separator: "Settings" (gear icon), "Help" (question-mark-in-circle icon).
  Collapsed 64px: icons only, centred, tooltip on hover; "+" square indigo button; RECENT hidden.
- NO bottom navigation, NO second sidebar, NO right sidebar.
- NEVER show "Sign in", "Log in", "Sign up" or "Get started" on logged-in screens.
- Evaluation tabs (Requirements · Comparison · Recommendation) sit inside the page, below the evaluation title, indigo underline on active — never in header or sidebar.
- Content area = right of sidebar, below header. Sidebar expanded: content max 1200px, centred, 32px top padding. Sidebar collapsed: content fills full width with 40px side padding. Breadcrumb above page title when inside an evaluation.
- Drawers (Sheet) open from the right edge over a dimmed page, covering the header; temporary panels, not sidebars.
- No footer.

CONTENT LOCK — never break:
- Render ONLY the elements listed in the screen prompt, with the exact text and data given. Do not rename, add or remove rows, columns, buttons or labels.
- NEVER add: KPI/metric cards, stat tiles, insight cards, charts, sparklines, trend arrows, unlisted percentages, eyebrow labels, count pills, export/download icons, "Configure" buttons, unlisted filters, version numbers, taglines, marketing copy, decorative dots.
- Empty space is fine. Do not fill it.
- Two status families, never mixed:
  a) FINDING STATUS = filled pill badges (above). Only in matrices, findings, requirement-level views.
  b) EVALUATION / FILE STATUS = 8px dot + plain text, no pill: Draft (slate), Requirements review (indigo), Analysed (green), Stale (amber dot + refresh icon, "Stale — re-run needed"), Ready (green), Processing (indigo), Error (red).
- Tables: dates, status labels, numbers and action icons never truncate or wrap; the longest text column truncates instead. Last column fully visible inside the table border. Dates and meta in muted #64748B, never indigo.
- Button text in sentence case. Avatar shows initials, not an icon.
```

---

## 2. Screen prompts

### S1 — Sign in
```
[MASTER BLOCK]
Sign-in screen. The ONLY screen without header and sidebar — ignore the app shell here.
LOGIN LOCK: NO header, NO sidebar, NO split screen, NO hero image or illustration, NO side marketing panel.
Page background #F8FAFC. One white card 400px wide, centred horizontally and vertically, 1px #E2E8F0 border, 8px radius, 32px padding.
Card, top to bottom:
1. "VixenOne" wordmark with indigo dot, centred.
2. Muted 14px centred: "Evidence-backed vendor proposal evaluation."
3. Full-width secondary button "Continue with Google" with Google G icon.
4. Divider with centred "or".
5. Label "Email", input placeholder "you@company.com".
6. Label "Password" with right-aligned "Forgot password?" link; input with show/hide eye icon.
7. Full-width primary "Sign in".
16px below card, 400px wide: muted slate info box "Demo account: demo@vixenone.app".
Below that, muted 12px centred: "Prototype · AI Builder Cup 2026". Nothing else.
```

### S2 — Evaluations list
```
[MASTER BLOCK]
Evaluations list. Header + expanded sidebar; "Evaluations" active.
Content, in order, nothing else:
1. Header row: left = title "Evaluations" + muted subtitle "Compare vendor proposals against your requirements."; right = primary "+ New evaluation".
2. Toolbar, 24px below: search input 320px "Search evaluations"; select "Status: All". Nothing on the right.
3. Table, full content width, 1px border, 8px radius. Header row #F8FAFC, 12/500 muted, sentence case.
Columns: Name 40% · Category 18% · Vendors 7% (right-aligned number) · Status 22% · Updated 10% · ⋯ 3% (icon menu, fully visible).
Rows single line, 56px. Name truncates with ellipsis. No sublines, IDs or dots before names. Category and vendors plain text.
1. Housekeeping Services — Andheri East Office, FY 2026–27 | Facilities / Housekeeping | 3 | ● Analysed | 12 Oct 2026
2. Security Services — Powai Campus | Facilities / Security | 2 | ● Requirements review | 10 Oct 2026
3. Pantry & Cafeteria — BKC Office | Facilities / Housekeeping | 3 | ● Stale — re-run needed | 08 Oct 2026
4. Pest Control AMC — Thane Warehouse | Facilities / Housekeeping | 2 | ● Draft | 05 Oct 2026
Name = link style (#0F172A, underline on hover). Row hover #F8FAFC.
Below table, muted 12px: "4 evaluations". No pagination.
```

**S2-empty** (select S2 → edit)
```
[MASTER BLOCK]
Edit this screen: empty state. Remove toolbar, table and count. 120px below header row, centred: slate line icon (document stack), heading 18/600 "No evaluations yet", muted text "Upload a requirements document and 2–3 vendor proposals to get an evidence-backed comparison.", primary "+ New evaluation". Sidebar RECENT shows muted "No recent evaluations". Header row keeps title and subtitle only.
```

### S3 — Create evaluation
```
[MASTER BLOCK]
Create evaluation. Header + expanded sidebar; "Evaluations" active.
Content, in order, nothing else:
1. Breadcrumb "Evaluations / New evaluation". Title "New evaluation". Muted subtitle "Upload one requirements document and 2–3 vendor proposals."
2. Single column 880px, left-aligned. Three cards, 24px apart.
Card "Details": "Evaluation name" input "Housekeeping Services — Andheri East Office, FY 2026–27". Side by side: "Category" select "Facilities / Housekeeping"; "Location (optional)" input "Mumbai".
Card "Requirements document": muted helper "PDF or DOCX · max 10 MB · max 30 pages". File row: file icon · "Andheri_Housekeeping_RFP.pdf" · muted "14 pages · 2.1 MB" · right: ● Ready · × icon.
Card "Vendor proposals": muted helper "Add 2 or 3 vendors. PDF or DOCX · max 10 MB · max 30 pages each." Three rows, thin separators, each = "Vendor name" input (240px) + file area + state:
  1. "BrightNest Facility Services" · BrightNest_Proposal.pdf · "12 pages · 1.4 MB" · ● Ready · ×
  2. "Shubh Housekeeping Pvt Ltd" · Shubh_Proposal.docx · thin progress bar 60% · ● Processing… · ×
  3. "UrbanKleen Services" · compact dashed upload zone 48px: upload icon + "Drop file or browse"
  No "Add vendor" button.
3. Sticky bottom action bar in content area, white, 1px top border, right-aligned: "Cancel" secondary; "Extract requirements" primary DISABLED with tooltip "Waiting for all files to finish processing".
```

**S3-error** (select S3 → edit)
```
[MASTER BLOCK]
Edit this screen: Row 3 now has "UrbanKleen_Proposal.pdf" · "42 pages · 6.8 MB" · ● Error "Too long — max 30 pages". Red 12px helper below the row: "Upload a shorter version or only the relevant sections." Right of row: small secondary "Replace file" + ×. Row 2 now ● Ready. "Extract requirements" stays disabled, tooltip "Fix file errors to continue". Everything else unchanged.
```

### S4 — Requirements review
```
[MASTER BLOCK]
Requirements review. Header + expanded sidebar; "Evaluations" active; RECENT "Housekeeping — Andheri East" in indigo text.
Content, in order, nothing else:
1. Breadcrumb "Evaluations / Housekeeping Services — Andheri East Office". Title "Housekeeping Services — Andheri East Office, FY 2026–27". Muted meta "Mumbai · Monthly contract · 18 requirements (6 mandatory)".
2. Tabs: Requirements (active) · Comparison · Recommendation.
3. Card with horizontal stepper: Extract ✓ · Analyse BrightNest ✓ · Analyse Shubh ✓ · Analyse UrbanKleen ✓ · Score ✓ · Recommend ✓. Green checks, thin connector lines.
4. Amber alert: "Requirements were edited after analysis. Results are stale — re-run analysis to update."
5. Row: section title "Requirements" + muted "18 requirements · 6 mandatory"; right: "+ Add requirement" secondary, "Re-run analysis" primary.
6. Table. Columns: ID 7% · Requirement 33% · Category 11% · Mandatory 9% (switch) · Acceptance condition 22% · Source 12% · actions 6% (edit, delete icons).
REQ-01 | Minimum 12 housekeeping staff on site, Mon–Sat, 8 am–8 pm | Staffing | on | ≥12 staff per shift | RFP p.3 §2.1
REQ-02 | Washroom cleaning every 2 hours with checklist | Service | on | Every ≤2 h, checklist provided | RFP p.3 §2.3
REQ-03 | Washroom consumables included in monthly fee | Commercial | on | Priced within base fee | RFP p.5 §4.1
REQ-04 | Quarterly deep cleaning of carpets and upholstery | Service | off | 4 per year | RFP p.4 §2.6
REQ-05 | On-site supervisor during all shifts | Staffing | on | Supervisor per shift | RFP p.3 §2.2
REQ-06 | Ad-hoc cleaning response within 2 hours | SLA | off | Response ≤2 h stated | RFP p.4 §3.1
REQ-07 | Monthly pest control | Service | off | 12 treatments per year | RFP p.4 §2.8
REQ-08 | Police verification and PF/ESIC compliance | Compliance | on | Certificates provided | RFP p.6 §5.2
REQ-04 shown in inline edit mode: inputs inside cells, small "Save" primary + "Cancel" ghost in actions cell.
Source cell = muted text with small document icon.
Below table, muted 12px: "Showing 8 of 18 requirements".
```

### S5 — Vendor comparison
```
[MASTER BLOCK]
Vendor comparison. Header + expanded sidebar; "Evaluations" active; RECENT "Housekeeping — Andheri East" in indigo text.
Content, in order, nothing else:
1. Breadcrumb, title, meta exactly as: "Evaluations / Housekeeping Services — Andheri East Office" · "Housekeeping Services — Andheri East Office, FY 2026–27" · "Mumbai · Monthly contract · 18 requirements (6 mandatory)".
2. Tabs: Requirements · Comparison (active) · Recommendation.
3. Three vendor cards in a row, equal width:
- BrightNest Facility Services · muted tag "Lowest quote" · Score 64/100 · red text "1 mandatory failure" · ₹3,85,000/month + GST · Unknown cost badge "2 unknown costs"
- Shubh Housekeeping Pvt Ltd · muted tag "Strongest coverage" · Score 86/100 · green text "0 mandatory failures" · ₹4,60,000/month + GST · muted "0 unknown costs"
- UrbanKleen Services · Score 58/100 · green text "0 mandatory failures" · ₹4,10,000/month + GST · Unknown cost badge "1 unknown cost" · Needs review badge "1 needs review"
4. Filter row: "Vendor: All", "Status: All", "Risk type: All" selects; switch "Mandatory only". Nothing else.
5. Section title "Compliance matrix". Table, sticky first column. Columns: Requirement 40% · BrightNest 20% · Shubh 20% · UrbanKleen 20%.
Requirement cell = ID + short text; small muted "Mandatory" tag where marked. Vendor cells = finding status pill + small risk icon if listed; cells clickable (hover outline, pointer).
REQ-01 (Mandatory) Min 12 staff on site | Compliant | Compliant | Needs review (Ambiguity, Contradiction icons)
REQ-02 (Mandatory) Washroom cleaning every 2 h | Compliant | Compliant | Partially compliant
REQ-03 (Mandatory) Consumables included | Non-compliant (Exclusion icon) | Compliant | Not evidenced
REQ-04 Quarterly deep cleaning | Non-compliant (Exclusion icon) | Compliant | Partially compliant
REQ-05 (Mandatory) Supervisor all shifts | Compliant | Compliant | Compliant
REQ-06 Ad-hoc response ≤2 h | Not evidenced | Compliant | Not evidenced
REQ-07 Monthly pest control | Partially compliant (Unknown cost icon) | Compliant | Compliant
REQ-08 (Mandatory) Police verification, PF/ESIC | Compliant | Compliant | Compliant
6. Section title "Cost comparison". Table. Columns: Item 25% · BrightNest 25% · Shubh 25% · UrbanKleen 25%. Numbers right-aligned.
Monthly base | ₹3,85,000 | ₹4,60,000 | ₹4,10,000
GST 18% | ₹69,300 | ₹82,800 | ₹73,800
Monthly total | ₹4,54,300 | ₹5,42,800 | ₹4,83,800 (bold row)
Included | Staffing, supervisor | Staffing, 24×7 supervisor, consumables, deep cleaning, pest control | Staffing, pest control
Excluded | Consumables, deep cleaning | — | —
Optional | — | — | Deep cleaning ₹18,000/quarter
Unknown cost | Unknown cost badge: Pest control "on request"; consumables at actuals | — | Unknown cost badge: Weekend coverage
```

**S5-loading** (select S5 → edit)
```
[MASTER BLOCK]
Edit this screen: analysis in progress. Replace vendor cards, filters, matrix and cost table with grey skeleton blocks of the same sizes. Above them, a card with stepper: Extract ✓ · Analyse BrightNest ✓ · Analyse Shubh (indigo, spinner, muted "Reading proposal — page 9 of 16") · Analyse UrbanKleen (pending, slate) · Score (pending) · Recommend (pending). Progress bar 45% below the stepper. Breadcrumb, title, meta, tabs unchanged.
```

### S6 — Finding detail drawer (select S5 → edit)
```
[MASTER BLOCK]
Edit this screen: open a right-side drawer (Sheet) 520px, covering header, page behind dimmed 40% slate.
Drawer header: "REQ-03 · BrightNest Facility Services", close X. Below: muted "Mandatory" tag + Non-compliant pill.
Sections separated by thin separators:
1. "Requirement": "Supply of washroom consumables included in monthly fee." Muted "Acceptance: priced within base fee."
2. "Finding": "The proposal explicitly excludes washroom consumables and bills them at actuals, so the monthly fee does not cover them." Small solid slate badge "Fact — directly quoted".
3. "Evidence": quote block, 3px red left border, #F8FAFC background: "Washroom consumables (tissue, hand wash, air freshener) are not included and will be billed at actuals." — "not included" highlighted soft amber. Below: document icon + muted "BrightNest_Proposal.pdf · Page 4 · §3.2 Exclusions".
4. "Confidence": "High" + small bar.
5. "Related risks": Exclusion (High), Unknown cost (High).
6. "Clarification question": textarea prefilled "Please provide a fixed monthly rate for washroom consumables, or confirm a cap on billing at actuals." Small primary "Save" + ghost "Copy".
Drawer footer, 1px top border: left "Mark as needs review" secondary; right "‹ Previous" "Next ›" ghost.
Clicked matrix cell (REQ-03 × BrightNest) shows indigo outline behind the overlay.
```

### S7 — Recommendation
```
[MASTER BLOCK]
Recommendation. Header + expanded sidebar; "Evaluations" active; RECENT "Housekeeping — Andheri East" in indigo text.
Content, in order, nothing else:
1. Breadcrumb, title, meta as S5.
2. Tabs: Requirements · Comparison · Recommendation (active). On the right end of the tabs row: secondary button "Print / Save as PDF" with printer icon.
3. Card "Summary": callout, 3px indigo left border, bold: "Recommended next step: proceed with Shubh Housekeeping Pvt Ltd, subject to clarifications." Body: "Vendor B best meets requirements with no mandatory gaps. Vendor A is ₹75,000/month cheaper on base price but excludes consumables and deep cleaning, and its pest-control cost is unknown. Clarify Vendor A's consumables rate and Vendor C's staffing commitment before deciding."
4. Card "Mandatory failures", title in red: row "BrightNest Facility Services — REQ-03 Washroom consumables" + Non-compliant pill. Muted note: "Mandatory failures are shown regardless of total score."
5. Three vendor cards in a row, each with headings Strengths / Weaknesses / Unresolved (short bullets):
BrightNest — Lowest base price ₹3,85,000; police verification provided / Consumables excluded; deep cleaning excluded / Pest-control cost unknown; ad-hoc response time not stated
Shubh — All 6 mandatory met; 24×7 supervisor; 2-hour response SLA / Highest base price ₹4,60,000 / None
UrbanKleen — Pest control included / No SLA stated / Staffing "adequate manpower as required"; weekend coverage contradictory
6. Card "Scoring breakdown". Table: Criterion 30% · Weight 25% (slider + % value) · BrightNest 15% · Shubh 15% · UrbanKleen 15% (score, muted contribution below).
Rows: Mandatory compliance 35% · Service coverage 20% · Cost comparability 20% · SLA / operational 15% · Unresolved risks 10%. Bold total row: 64 · 86 · 58.
Below table: muted "Weights total 100%" left; primary "Recalculate" right.
7. Card "Clarification questions": accordion per vendor with count — BrightNest (2) open, Shubh (0), UrbanKleen (2) closed. BrightNest items, each editable text + copy icon: "Please provide a fixed monthly rate for washroom consumables, or confirm a cap on billing at actuals." · "Please quote a fixed monthly price for pest control." Secondary "Copy all" at card top right.
8. Muted card "Limitations": "Covers only the uploaded documents." · "Inferred findings are marked — verify before deciding." · "Scores depend on the weights above."
```

**S7-insufficient** (select S7 → edit)
```
[MASTER BLOCK]
Edit this screen: replace the Summary callout with amber 3px left border, warning icon, bold "Insufficient information to recommend". Body: "2 of 3 vendors have unverified mandatory requirements. Resolve the clarification questions before deciding." Secondary button "Go to clarification questions". Everything else unchanged.
```

### S7-P — Print report (new screen)
```
[MASTER BLOCK]
Print version of the report. Ignore the app shell: NO header, NO sidebar, NO tabs, NO sliders, NO buttons. A4 portrait, white.
Top: "VixenOne · Vendor evaluation report"; title "Housekeeping Services — Andheri East Office, FY 2026–27"; muted "Generated 12 Oct 2026 · Prepared for Priya Sharma".
Sections in order: Summary · Mandatory failures · Compliance summary (same 8×3 matrix, outlined pills with text, must read in greyscale) · Cost comparison · Scoring breakdown (weights as plain numbers) · Vendor strengths / weaknesses · Clarification questions numbered per vendor · Limitations.
Footer: muted "Page 1 of 4". 11pt body, compact spacing, thin borders, no colour fills larger than badges.
```

---

## 3. Review checklist (every screen)

- Header full width; sidebar below it; sidebar runs to the bottom.
- No KPI cards, insight cards, extra columns or buttons.
- Finding status = pills; evaluation/file status = dot + text.
- No truncated dates/status; last column visible.
- Indian number format; GST separate.
- Only indigo as accent.

## 4. Assumptions
- ASSUMED: Requirement counts other than 18 (S2 sub-lines) are illustrative.

- ASSUMED: Stitch lets you select a screen and edit it in place.
- ASSUMED: Scores 64 / 86 / 58 are illustrative, not engine output.
- ASSUMED: Priya Sharma and demo@vixenone.app are placeholders.
- ASSUMED: File page/size counts are illustrative.

---

## 5. Approved decisions (override section 2)

### Layout & style
- Tables: uppercase 12px muted headers, light grey header row, 1px row separators. Pagination allowed on list tables.
- S2 Name cell: two lines — semibold name + muted sub-line "Location · N requirements" (Draft: "Thane · Not extracted yet"). No RFP IDs.
- S3 action buttons sit in page flow under the last card in design; **sticky in build**.
- Sidebar background stopping short in Stitch frames = static-frame quirk. **Build: full height.**
- Help icon renders as empty circle in Stitch = glyph bug. **Build: question-mark-in-circle.**

### Risk icons (fixed mapping)
| Risk | Icon |
| --- | --- |
| Exclusion | ban (circle with slash) |
| Ambiguity | help-circle |
| Unknown cost | rupee with question mark (or receipt) |
| Contradiction | arrows-left-right (not yet shown in Stitch) |
| Omission | circle-minus (not yet shown in Stitch) |

### Scoring logic (S7, S7-P) — CERTAIN
- Each vendor cell = criterion score **out of 100**, with **points = score × weight** below.
- Total = sum of points, rounded. Weight applied **once**.

| Criterion | Weight | BrightNest | Shubh | UrbanKleen |
| --- | --- | --- | --- | --- |
| Mandatory compliance | 35% | 83 → 29.1 | 100 → 35.0 | 67 → 23.4 |
| Service coverage | 20% | 65 → 13.0 | 90 → 18.0 | 70 → 14.0 |
| Cost comparability | 20% | 55 → 11.0 | 70 → 14.0 | 60 → 12.0 |
| SLA / operational | 15% | 50 → 7.5 | 80 → 12.0 | 20 → 3.0 |
| Unresolved risks | 10% | 35 → 3.5 | 70 → 7.0 | 55 → 5.5 |
| **Total** | 100% | **64** | **86** | **58** |

### Clarification questions (full demo set)
- BrightNest: (1) fixed monthly rate for consumables or cap on actuals; (2) fixed monthly price for pest control.
- Shubh: none.
- UrbanKleen: (1) exact staff deployed per shift; (2) whether Sunday and holiday coverage is included.

### Mandatory tags (5 of the 8 sample rows)
REQ-01, REQ-02, REQ-03, REQ-05, REQ-08 carry the "Mandatory" tag everywhere: matrix, print summary, requirements table. The 6th mandatory requirement is among the 10 rows not shown.

---

## 6. Additions (approved 12 Oct, after first freeze)

| ID | Screen | Status | Build notes |
| --- | --- | --- | --- |
| L0 | Public landing page | Approved | Hero preview must show 3 vendors (Stitch shows BrightNest only) |
| S1 | Auth — Sign in tab | Derived | S1 card + tabs row "Sign in (active) · Sign up" |
| S1b | Auth — Sign up tab | Approved | Google; Full name; Work email; Password (≥8 hint); Role select; Create account |
| S2 | Evaluations list + KPI tiles | Approved (replaces old S2) | Row separators on every row |

### Landing (L0)
- Sticky header: wordmark · How it works · Features · Showcase · Who it's for · FAQ · "Sign in" link · "Sign up" button. Links smooth-scroll; active section highlighted. Signed-in visitor sees "Open app".
- Sections: Hero → How it works (3 steps) → Features (6) → Showcase carousel (S4, S5, S6, S7 screenshots) → Who it's for carousel (3 roles) → Principle band (dark) → FAQ (5) → CTA → footer.
- No testimonials, no client logos, no pricing (decision: no invented reviews).
- Motion: fade/slide on scroll, carousel transitions, smooth scroll, subtle hover; honour reduced-motion.
- Hero preview rows: REQ-01 C/C/Needs review · REQ-02 C/C/Partial · REQ-03 Non-compliant/C/Not evidenced · REQ-07 Partial/C/C.

### FAQ answers
1. Which documents can I upload? — PDF or Word, up to 10 MB and 30 pages each: one requirements document and 2–3 vendor proposals.
2. Does VixenOne choose the vendor for me? — No. It shows evidence, risks, cost and scores, and suggests a next step — or says when there isn't enough information to recommend.
3. How are scores calculated? — Five weighted criteria: mandatory compliance, service coverage, cost comparability, SLA, unresolved risks. You can change the weights. Mandatory failures are always shown separately.
4. Can I edit the extracted requirements? — Yes. Edit, add or remove them before analysis. Edits after analysis mark results stale until you re-run.
5. Can I share the results? — Yes. Print or save the report as PDF, and copy the clarification questions to send to vendors.

### Auth
- One page, two tabs; routes /sign-in and /sign-up. Landing "Sign up" → /sign-up; "Sign in" → /sign-in.
- Sign-up creates Firebase user, then PUT /me (name, role). Google sign-up → default role Facilities manager (ASSUMED).
- Backend: users table in Postgres; /me read-or-create; PUT /me.

### KPI tiles (S2)
| Tile | Rule (computed, never typed) | Demo |
| --- | --- | --- |
| Evaluations | count all | 4 |
| Needs action | status = Requirements review or Stale | 2 |
| Analysed | status = Analysed | 1 |
| Open clarifications | unanswered clarification questions across evaluations | 4 |
- Clicking a tile filters the table. No trends, no percentages.