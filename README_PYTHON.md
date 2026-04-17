# Python version

This folder contains a Python rewrite of the original C# WinForms tool.

It keeps the same overall strategy:

- interact with `ssReader.exe`
- read total page counts from process memory
- collect bmp pages from `%LOCALAPPDATA%\Tempuffer`
- convert them to png
- merge them into a pdf

Run it from the local conda environment instead of `base`:

```powershell
conda activate D:\Downloads\pdz-assistant-1.2\pdz-assistant-1.2\.conda-env
python .\python_version\main.py
```

Or use `run_python_version.bat`.
