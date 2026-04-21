# pdz-pdf (Python Version)

For the GitHub-facing repository homepage, see `README.md`.

This folder contains a Python rewrite of the original `pdz-assistant` tool.

It keeps the same overall workflow:

- interact with `ssReader.exe`
- read total page counts from process memory
- collect bmp pages from `%LOCALAPPDATA%\Temp\buffer`
- convert them to png
- merge them into a pdf

## What This Project Does

This project is intended for converting PDZ reading output into PDF files by coordinating with the local `ssReader.exe` process and collecting rendered page images.

Recommended repository names for open source publishing:

- `pdz-pdf`
- `pdz-to-pdf`
- `ssreader-pdz-to-pdf`

`pdz-pdf` is the most concise and the easiest for GitHub users to search.

Suggested GitHub description:

`Convert PDZ reading output from ssReader into PDF with a portable Python desktop tool.`

Suggested GitHub topics:

- `pdz`
- `pdf`
- `ssreader`
- `python`
- `windows`
- `desktop-tool`

## Local Run

Run it from the local conda environment instead of `base`:

```powershell
conda activate D:\Downloads\pdz-assistant-1.2\pdz-assistant-1.2\.conda-env
python .\main.py
```

Or use `run_python_version.bat`.

## Open Source Notes

Before publishing this repository, it is recommended to check the following:

- remove or ignore build outputs, logs, caches, and temporary packaging artifacts
- confirm whether bundled icons, screenshots, and demo assets are allowed to be redistributed
- confirm whether the upstream project license or author permission allows republishing modified or ported versions

No explicit `LICENSE` file was found in the current Python repository snapshot, so it is better to confirm the licensing situation before publishing this as a public open source repository.

## Project Origin

This Python version references the original project idea and workflow from:

- Original project: `PettterWang/pdz-assistant`
- Source URL: `https://github.com/PettterWang/pdz-assistant`

If you publish this project publicly, keep a visible attribution section in the repository README and describe which parts were rewritten, adapted, or newly added in the Python version.
