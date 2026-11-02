# chatgpt-rdc-supervisor

Read project-capsule.yaml and the linked existing references. Use isolated task
worktrees and the installed Git single writer; preserve every valid work item.

src/chatgpt_rdc_supervisor/browser.py owns bounded browser channel/page/composer operations; safety.py enforces launch checks; storage/model/checkpoint modules hold private operation context. cli.py exposes requested diagnostics/helpers while retired supervision, discovery, registration/resume and installers reject. Tests use fake browser objects and temporary storage.

- No browser credentials, profile/session data, private conversations or endpoints with secrets in Git/output.
- Real operations require a separately authorized session and must preserve ownership/launch-safety boundaries.
- No implicit task claiming, Pn/Batch creation or retired lifecycle writes.
- Do not launch/control a real browser, inspect accounts/projects or contact ChatGPT during capsule verification.
- Global supervision, rollover/recovery, lifecycle registration/resume and historical installers remain permanently retired.
- The systemd templates are inert source files, not a requested installation.

Run the declared fixture checks inside the isolated environment. Do not use
real credentials, data, browser sessions, notifications or services as fixtures.
Source integration is distinct from installation or live consumer acceptance.
