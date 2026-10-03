# RUNBOOK — SPARK Lab (hora CDMX)

## 0. Setup (Sebas, 14:15)
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install omnigent && pip install -e .          # mismo venv: las tools importan pandas
omnigent setup                                     # credenciales del modelo (Anthropic o Databricks)
python tests/smoke_test.py                         # debe imprimir SMOKE TEST OK (sin red)
omnigent run lab.yaml -p "Say hello"               # go / no-go
```
`lab.yaml` usa el formato de archivo único de Omnigent: **sin** `spec_version` y con `executor: {harness: ...}` plano.

## 1. Datos (José, 14:15)
```bash
python -m sparklab.data --cycle J                  # descubrimiento: descarga + columnas derivadas
python -m sparklab.data --cycle I --seal           # hold-out: zip + SHA-256 al ledger. NO se procesa
python -m sparklab.ledger verify                   # cadena intacta
```
Si CDC falla: descargar los XPT a mano y usar `--raw-dir carpeta/`.
Pegar al chat del equipo los conteos que imprime el comando (filas, adultos, con HbA1c, en ayunas, diag).

## 2. Pizarrón (Brau, 14:15–15:00)
Llenar `expected`, `source` y `comparability` en `board/expectations.json` (proporción 0–1, con cita).
Valores de CDC derivados de NHANES conservan `"note": "pipeline check"`. **No tocar** `board/control_seeded.json`.

## 3. Loop en vivo (16:15–17:00)
```bash
omnigent run lab.yaml          # web UI: http://localhost:6767
```
Primer mensaje sugerido:
> Objective: find which discrepancy between self-reported diagnosis and HbA1c to investigate next among
> US adults. Run the SPARK loop. Stop and ask us before anything touches the hold-out.

Lo que debe verse: Skeptic atrapa E04 · gate de poder rechaza una celda chica · prereg con hash + commit.

## 4. Gates humanos, en cámara (17:00–17:20)
```bash
python -m sparklab.approve PR-xxxxxxxx --by Brau   # escribe los primeros 8 caracteres del hash
python -m sparklab.unseal                          # José: verifica hash, procesa una sola vez
```
Luego decirle al Supervisor: "approved and unsealed". El Experimenter corre `run_test(cycle="I")` una vez.

## 5. Cierre (17:20–18:00)
```bash
python -m sparklab.ledger verify
python -m sparklab.ledger show --type result
git add ledger prereg && git commit -m "run records"
```
`docs/RESULTS.md` desde `docs/RESULTS_TEMPLATE.md`, citando ids del ledger y calc_ids.
