# Lessons Tab Redesign — W3Schools-style

## Goal
Replace the flat scrollable card list in MAYA's Lessons tab with a two-pane
"course" layout: sidebar chapter nav + focused reading pane, modeled on
w3schools' tutorial UX.

## Data model changes
`lessons.json` lesson objects gain a 4th field:
```json
{"id": "l1", "title": "...", "what": "...", "example": "...", "action": "...", "learned": false}
```
- `validate_and_fix("lessons", ...)`: add `l.setdefault("example", "")` —
  backward compatible, old files without it just get an empty example block.
- `LES_SCHEMA` constant updated to include `example`.
- `lessons_instruction` default text updated: ask agy for richer content per
  field (longer explanation, a concrete example, a one-line actionable
  takeaway) instead of one-liners.

## Aggregation, not single-date
`LessonsTab` stops subclassing `JsonTab` (which only ever loads the
currently-selected date's file). Becomes its own `ctk.CTkFrame`.

- `_load_all()`: iterate `list_history_dates()` oldest→newest, `load_json`
  each `content/<date>/lessons.json`, run through `validate_and_fix`, flatten
  into one ordered list of `(date, lesson_dict)`. Skip dates with no/invalid
  lessons file.
- Chapters numbered continuously 1..N across the full flattened list (not
  reset per day).

## Layout
- **Left**: scrollable sidebar. Per date, a non-interactive date-header label
  followed by that day's chapter rows (number + title, checkmark if
  learned). Today's group rendered first (most recent date first, matching
  existing `list_history_dates()` sort).
- **Right**: reading pane for the selected chapter —
  - Title heading + "Chapter N" badge
  - "What" explanation block (paragraph style)
  - "Example" box — distinct styled block (monospace/code-like background),
    only rendered if non-empty
  - "Action" callout — reuse existing yolk-highlight style
  - Mark Learned toggle button
  - Edit button (opens existing `EditDialog`, extended with the new
    `example` field)
  - Prev / Next buttons at the bottom, step through the flattened chapter
    list sequentially (crosses date boundaries transparently)

## Header bar
Keep `TabHeader` with "Generate with agy", "Edit instruction" buttons. Add a
"Refresh" button that re-runs `_load_all()` (re-scans all date folders).

## Generate semantics (unchanged target, same as today)
"Generate with agy" still builds a prompt targeting **only** the current
date's `lessons.json` (via existing `build_prompt`/`path_for`) and overwrites
just that day's batch. Other days' files are never touched — history
accumulates naturally as the user generates new days.

## Progress tracking
Stat chips (Total / Learned / Mastery%) and the progress bar aggregate across
**all** chapters in the flattened list, not just the current date's 10.

## Refresh/polling
- Full re-scan (`_load_all()`) on tab build, on "Refresh" click, and when the
  MAYA-logo full-refresh fires (`on_date_change` hook already exists for
  this — repurpose it to call `_load_all()` instead of just reloading one
  date).
- Light poll (existing 900ms interval) watches only the *current date's*
  file mtime, like before — if it changes (e.g. agy just finished writing),
  re-run `_load_all()`. Re-scanning all N date folders every 900ms is not
  worth the I/O.

## Dropped
- Manual reorder (drag up/down arrows) — removed. Chronological/date order
  is now meaningful; arbitrary reordering doesn't fit a cumulative course
  structure.
- Per-lesson reorder buttons (`reorder_buttons` usage in lesson cards) go
  away with the old card layout.

## Kept
- Edit dialog (now with 4 fields instead of 3)
- Mark-learned toggle + persisted `learned` bool per lesson
- "Generate with agy" / "Edit instruction" buttons
- Existing `EditDialog`, `card_frame`, icon helpers — reused, not replaced
