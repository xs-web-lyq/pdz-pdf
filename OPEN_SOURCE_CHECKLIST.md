# Open Source Checklist

Use this checklist before pushing `pdz-pdf` to a public GitHub repository.

## 1. Confirm Rights

- confirm whether the upstream project `PettterWang/pdz-assistant` has a license
- confirm whether your Python rewrite can be publicly redistributed
- confirm whether `Gemini.ico`, screenshots, demo gifs, or bundled assets can be published

## 2. Clean the Repository

- keep source code, scripts, and documentation
- exclude logs, cache folders, build outputs, packaged runtimes, and generated binaries
- review untracked files before `git add .`

## 3. Prepare GitHub Metadata

- repository name: `pdz-pdf`
- description: `Convert PDZ reading output from ssReader into PDF with a Python desktop tool for Windows.`
- topics: `pdz`, `pdf`, `ssreader`, `python`, `windows`, `desktop-tool`

## 4. Choose a License Carefully

- if upstream licensing is clear and compatible, choose a normal open source license
- if upstream licensing is unclear, do not add an MIT or Apache license yet
- if needed, publish first as source-visible with attribution after rights are confirmed

## 5. Push to GitHub

Run these commands in the `pdz-pdf` repository root after creating an empty GitHub repository:

```powershell
git branch -M main
git remote add origin https://github.com/<your-name>/pdz-pdf.git
git add .
git commit -m "Initial open source release"
git push -u origin main
```

## 6. Keep Attribution Visible

Make sure the repository README includes:

- original project name
- original project URL
- a short note that this project is a Python rewrite or adaptation
