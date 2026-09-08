# Optional shared gallery

Read only when the user requests a gallery or an existing task explicitly requires one. No gallery or preview server is created in the default headless loop. Scripts and assets below are relative to the skill root.

The default loop is bounded by an approved positive integer iteration count obtained before dispatch unless already supplied; never reconfirm an agreed count. Gallery generations map to those iterations, not extra authorization. Unsuccessful iterations count and substantive retuning starts a new one. Capture-only retries remain within the same image budget (16 review images per iteration unless overridden); record build-only repairs without hiding substantive changes as repairs. Stop at the count or early success/blocker and ask for approval before extending. A gallery or experimental evidence review never replaces the separate `run-as-code-reviewer` required for any PR.

## One shared gallery

Maintain ONE static `galleries.html` at the user-selected artifact root. Generations remain separate numbered folders for images and sidecars. Do not create a new HTML gallery per generation. Keep older artifacts intact.

The page has a generation list on the left. Selection on the right shows, in order:
1. Linked experiment task: ID, title, status, source link and embedded task body.
2. Incoming recommendations from the previous generation, plus applicable user feedback.
3. Recommendations for the next generation.
4. Image thumbnails, four per column, with click-to-expand and keyboard dismissal.

Use `scripts/build_gallery.py ROOT` after new evidence or reviews. It emits a self-contained HTML page with embedded data, so local-file Safari works without a server or fetch permissions. Refresh reloads updates and retains selection through the URL fragment. The file page remains manual-refresh and never probes local files through fetch. For requested automatic refresh, run the optional stdlib preview:

```sh
python3 scripts/serve_gallery.py ROOT --port 8765
```

Open its printed loopback URL. The server serves only the selected artifact root, rejects path/symlink escapes and directory listing, and polls a content hash of `galleries.html`. The page reloads only when that HTML actually changes; unchanged polling leaves selection and expanded images alone. Reload preserves the selected generation through the URL fragment. Continue rebuilding the gallery after task/evidence updates; this server does not rebuild it or alter Safari security settings.

Per generation, prefer `gallery.json` with optional `title`, `status`, `incoming`, `outgoing`, and `images` (relative image names or `{src, caption}` objects). Text is literal; do not place executable markup in it. Alternatively, put recommendations in `incoming.md` and `next-technique.md` (or `recommendations.md`). Without explicit incoming text, the builder uses the preceding generation's outgoing recommendations. Add `feedback.md` for batch feedback relevant to that generation. Without an explicit image list, the builder uses a preferred list from `settings.json`/`pass.json`, or all top-level images. Use explicit preferred lists to keep diagnostic/intermediate captures from burying the main evidence. Missing review text must say pending/unrecorded, never be invented. Reports and source sidecars stay beside images.

Allocate gallery metadata and embed the brief for every queued experiment as soon as its task exists, before captures finish; reserved slots show their honest pending brief rather than an invented hypothesis. Queued entries remain selectable with no images; include current status and dependencies in the task body. Do not wait for completion to publish the batch briefs. Tie each new/current generation to its durable experiment task. For the Backlog adapter, add optional metadata to `gallery.json`:

```json
{"experiment":{"id":"TASK-4","title":"Compare local slab extraction","status":"In Progress","task_file":"/absolute/project/backlog/tasks/task-4.md"}}
```

The builder derives **Generation E4** (or **Generation E1.19** for `TASK-1.19`) for both the list and selected heading. Keep physical numbered folders, ordering and URL identities unchanged; do not rename historical evidence. Historical entries without experiment metadata retain their existing title/numeric fallback. Supply `body` inline instead of reading `task_file` when preserving a frozen task snapshot; inline text takes precedence. A supplied `task_file` must be an absolute Markdown path and becomes a local source link. Without inline text, it must exist at build time. The task is embedded as literal text, never executable markup or a browser fetch. Rebuild to refresh task changes; the source task remains authoritative for status. Experiment identity does not expand the authorized generation budget or turn independently reviewed experiments into a reviewed integrated result.

Validate the gallery builder on actual output and a small fixture exercising no images, recommendation inheritance, special characters, explicit image ordering, task embedding, hierarchical task IDs and legacy title fallback. Check the page in the intended browser when possible. Do not add a web application framework for this simple index.
