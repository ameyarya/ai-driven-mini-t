# Workspace layout

`ai-driven-mini-t` is the single working directory for this project. Active source
files are no longer duplicated in its parent `Code` folder.

| Location | Purpose | Published to GitHub? |
| --- | --- | --- |
| Root Python files and dashboard | Current runtime and tests | Yes |
| `docs/` | Status, prompts, ideas, performance results | Yes |
| `experiments/` | Reproducible detector evaluation tools | Yes |
| `simulation/` | MuJoCo scene, localhost:8002 playground and simulation tests | Yes |
| `.sim-venv/`, `playground-data/simulation/`, `playground-data/shots/` | Local simulator environment, recordings, attempt ledgers and private test output | No |
| `.tank_update.key`, `tank_camera.yml` | Existing signing key and machine-specific camera configuration | No |
| `.detector-venv/`, `tools/`, `weights/` | Local detector environment, binaries, model weights | No |
| `vision-output/`, `detector-output/`, `images/`, `*.log` | Private captures, experiments, photos, and logs | No |
| `*-backup-*/` | Original hardware backups | No |
| `local-notes/` | Full working rover plan and its earlier backup | No |
| `local-archive/workspace-cleanup-2026-10-02/` | Original duplicate sources, legacy tank/truck experiments, prompt/idea originals, configuration backups, migration manifest | No |

## Start from the repo

```sh
cd ~/Documents/Github/ai-driven-mini-t
python3 server_tank.py
```

The server starts the detector worker when needed. The relocated detector
Python environment retains the installed dependencies and repaired entry points.

For the local camera relay, when it is not already running:

```sh
cd ~/Documents/Github/ai-driven-mini-t
./tools/mediamtx/mediamtx tank_camera.yml
```

The Mac still needs Ollama running and the DJI Mimo livestream publishing.
Camera/motor settings were preserved; cleanup does not start an autonomous goal.

## Preservation record

The cleanup inventoried and verified 27,228 file, directory, and symlink entries
before repairing environment/configuration paths. No inventoried content was
deleted. Relocation-sensitive configuration originals and original symlink
values were saved before repair. Active logs may continue growing; their
pre-move byte prefixes were verified. Original signing-key permissions were
preserved. Historical frame JSON logs retain their original absolute path
strings; resolve those filenames within the new `vision-output/` folder.

The private `migration-manifest.json` records original/destination paths,
file sizes and SHA-256 hashes, and symlink targets. Legacy hardware scripts are
archived as historical experiments rather than included in automatic test discovery.

## Local fine-tuning files

- `.training-venv/`: ignored isolated MLX training/inference environment.
- `tools/qwen3-vl-4b-mlx/`: ignored 4-bit base model and tokenizer.
- `playground-data/planner-training/`: ignored data splits, manifests, adapter
  checkpoints, training logs and held-out evaluation outputs.
- `rover_mlx_planner_server.py`: tracked local adapter inference service, port 8767.
- `docs/FINE_TUNING.md`: published experiment setup, results and limits.

Run training and model evaluation sequentially on the 16 GB Mac.
