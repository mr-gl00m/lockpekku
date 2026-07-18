# Lockpekku
---
<p align="center">
  <img src="https://github.com/mr-gl00m/lockpekku/blob/main/resources/lockpekku.png" alt="Lockpekku Logo" width="100"/>

Leftover processes are bugs in the tree. Lockpekku pecks them out.
---

A folder move that fails with "being used by another process" comes from one of four lock vectors. Lockpekku detects the three attributable ones (an executable running from inside the tree, a working directory inside the tree, a command line naming a path inside it) and checks the fourth (raw handles from Explorer windows, the preview pane, the search indexer, or elevated processes) through Windows delete-sharing access. The probe does not rename the selected tree.

## Run

```
uv venv
uv pip install -r requirements.txt
python main.py
```

## Use

Set the root, hit Scan or leave Live on (rescans every 2.5 s, keeps your checkboxes). Check rows and Kill Selected, or Kill All Listed to clear everything. Probe Move takes a non-mutating snapshot of incompatible handles across the selected tree; if it finds one while the table is empty, the usual fix is closing the Explorer window sitting in the folder. Copy Report puts the scan on the clipboard as a markdown table.

Killing a process another user or an elevated context owns reports "denied": rerun Lockpekku elevated. Note the scan itself also sees more when elevated; unelevated, an elevated process's paths are invisible.
