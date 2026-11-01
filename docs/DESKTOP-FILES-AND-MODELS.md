# Add local models and create Desktop HTML files

Restart MyAi after installing these changes. Earthma can remain running.

## Add a downloaded model

Open Settings > Add models. Paste the full path of a downloaded `.gguf` file
and click Add local model. You can copy a path from Windows File Explorer using
Copy as path; surrounding quotation marks are accepted. An optional publisher
SHA-256 can verify the copy against the publisher's checksum.

The app copies the file into its models directory in the background and shows
progress. The source is kept, and a model with the same name is never overwritten.
After completion it appears in the installed model list and request routing.
The GGUF header alone does not prove runtime compatibility or model quality.
Existing catalog downloads remain under Settings > Models & performance.

## Create an HTML app on Desktop

Send an explicit request such as:

> Build me a calculator HTML file on my Desktop.

MyAi routes this to a file task. Plain basic calculator requests use a tested
built-in template and need no model inference. Other HTML requests select an
installed coding model to generate the document. The app saves the result to the Windows
Desktop location (including a redirected Desktop). The task displays the full
saved path and offers Download HTML file. Existing files are kept; a unique suffix
is used if the requested name already exists. An optional simple name such as
`clock.html` is supported. The task list and a local report preserve the result.

Requests asking how to make a file continue to receive explanations. Unsupported
file types and destinations are not included in this first increment. Desktop
HTML creation does not edit a selected project or execute system commands.

Truncated output, missing closing HTML, an explanation without a document, and
separate script/style references cause a visible failure rather than a success
claim. Structural checks do not prove the generated app works: open it and test
the requested behavior. The task reports that browser behavior was not tested
automatically. Cancellation prevents publication if requested before saving;
already saved files are retained. These tasks do not yet save a shared project
handoff automatically.

The multi-model scheduler and automatic parallel work remain separate upcoming
features.

## Validation on this PC

The exact calculator request was tested through the composer. The browser checks
covered addition, subtraction, multiplication, division, decimal precision,
left-to-right chained operations, operator replacement, mouse buttons, backspace,
division by zero and recovery, repeated decimal input, and change of sign. All
14 checks passed, with no JavaScript errors. These checks were performed during
development; future generated HTML apps do not automatically receive those tests.

The first real 3B model attempt saved HTML but produced an incomplete calculator
interface. This motivated the basic calculator template. It is not evidence that
all model-generated applications work correctly. The Settings browser checks
used a synthetic GGUF header fixture in an isolated app to test copying and
duplicate handling; it was not loaded for inference or imported into the user's
installed models.
