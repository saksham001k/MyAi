# Project uploads and editing

Open **Project files · Upload and edit**. Upload UTF-8 source or text files, or a folder. Files are copied into `data/workbench/files` in your MyAi workspace. Your original project stays unchanged. Uploads persist across restarts and conversations; selected files are shared project context, not private to one chat.

Select files to include with a Chat or Code message. Limits: 100 files, 60 KB per file, 12 selected files and 12,000 context characters. Large folders should be reduced to relevant source files first. Binary images, video, PDF and Office documents are not parsed in this version. Folder uploads stop at the first unsupported file; earlier successful uploads remain. Existing filenames are not overwritten. `.git`, `.env` and environment variants are excluded; remove other credentials before uploading.

To edit:

1. Load your coding model and select **Code**. For larger tasks use 8192 context if memory allows.
2. Select relevant files, enable **propose file changes for review**, and describe one focused change. You can also ask it to create new files.
3. Review the generated diff in Project files. Click **Apply changes** to write the uploaded copies.
4. Download the changed files. **Undo changes** restores the previous contents and removes files created by that proposal, provided they have not since changed.

The conversation records a change ID. Paste it into **Open saved change** to reopen a review after restarting. Proposals and backups are stored in `data/workbench/changes`. A malformed model answer is reported without modifying files. A small local model may need smaller tasks or a stronger coding model; it is not equivalent to Codex's reasoning quality.

The model receives selected file contents as text and produces a structured proposal. This is not an autonomous terminal agent: there is no command execution, test execution, Git push, arbitrary disk access, or automatic editing of originals. Changes are bounded to the project workspace and must be applied through the review UI. File freshness is checked before Apply/Undo. Writes replace individual files atomically with rollback on ordinary I/O errors; power loss during a multi-file apply is not a transactional filesystem operation.
