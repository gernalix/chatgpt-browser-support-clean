# On-demand browser support

 Browser transport, targeted page/composer helpers and launch-safety checks for
 explicitly requested browser support. The original package and command names
 are retained for compatibility. No task lifecycle or external authority is
 provided by this repository.

 Global supervision, account/project discovery, automatic rollover/recovery,
 registration/resume and the historical installer are permanently retired.
 Their entrypoints reject unconditionally. Keep those guards in place; do not
 restore retired units or execute historical checkpoints. Service templates
 are inert source files and are not installed by this package.

 The `doctor` command is an explicitly requested connectivity diagnostic; it
 never claims or resumes a task. Real browser operations require a separately
 authorized session. Profiles, endpoints, chat/session data and checkpoints
 belong in private runtime storage outside this repository.

 Install the package dependencies in your chosen Python environment. Offline
 checks use fake browser objects and temporary storage, without launching a
 browser or contacting ChatGPT:

 ```bash
 PYTHONPATH=src python3 -B -m unittest discover -s tests -v
 ```
 