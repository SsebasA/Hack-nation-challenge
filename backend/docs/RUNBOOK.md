# RUNBOOK — SPARK Lab (hora CDMX)

> **En este repo:** todo vive en `backend/`. Corre cada comando desde `backend/`, con el venv de la raíz
> (`source ../.venv/bin/activate`, Python 3.13). Instalación: `pip install -e backend/` desde la raíz.
> Antes de la corrida real: `omnigent stop` (un daemon viejo, p. ej. del ensayo en `/tmp/spark-rehearsal`,
> haría que las tools escriban en otro ledger). Omnigent no pasa `SPARKLAB_ROOT` a las tools; el ensayo usa su
> propio venv. Si la descarga de CDC falla por SSL: `open "/Applications/Python 3.13/Install Certificates.command"`.

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

## 2b. UI web (opcional, en paralelo al loop)
La UI de `frontend/` habla con `python -m sparklab.api` (puerto 8787), que lee el laboratorio (pizarrón, ledger,
calcs, protocolos) y la sesión `spark_lab` de Omnigent (mensajes, tool calls, estado de sub-agentes) y expone los
gates humanos. No calcula nada: todo número lleva su `calc_id`.
```bash
omnigent stop && source .venv/bin/activate && omnigent start   # Omnigent DEBE correr desde este venv (importa sparklab.tools)
pip install -e "backend/[api]"                 # desde la raíz; añade fastapi/uvicorn/httpx (ya vienen con omnigent)
cd backend && python -m sparklab.api           # http://127.0.0.1:8787  (docs en /docs)
cd ../frontend && npm install && npm run dev   # http://localhost:3000
```
Desde la UI (todo queda en el ledger con `origin: human` y firmado con tu nombre):
- **Objetivo / "Start the lab"**: sube `lab.yaml` como agente a Omnigent, liga la sesión al host local, le manda el
  objetivo al Supervisor y registra un `plan_update`. Equivale a `omnigent run lab.yaml -p "..."`.
- **Pick**: tras S (solo el Scout) el Supervisor se detiene y la UI pide elegir la discrepancia; manda "Pursue E0x" y registra una `note`.
- **Approve / Unseal**: mismo roce que el CLI: tecleas los 8 primeros caracteres del SHA-256 (del protocolo / del zip
  sellado, según el ledger) y firmas. Un prefijo incorrecto no escribe nada. Los CLIs siguen funcionando igual.
- **"Approved and unsealed"**: botón que avisa al Supervisor para la única corrida en el hold-out. **Decision**: `decision`.
- **Chat**: mensajes libres al Supervisor (pestaña Activity → Chat).
Notas:
- Sin API arriba la UI reproduce el guion mock (MOCK DATA). `?mode=mock` fuerza el guion; `?mode=live` fuerza la API.
- La API empareja la sesión por etiqueta `spark.study` (las que arranca la UI) o por workspace (= carpeta del estudio;
  el estudio raíz acepta también la raíz del repo). Fijar una con `SPARK_OMNIGENT_SESSION=<id>`. Nunca se engancha a
  sesiones de otro checkout. Variables: `SPARK_API_PORT`, `SPARK_OMNIGENT_URL`, `SPARKLAB_ROOT`, `SPARKLAB_STUDIES_DIR`.
- **Varios estudios**: `New study` crea `backend/studies/<id>/` (ledger, board copiado, prereg; datos y zip sellado
  enlazados del laboratorio raíz, con su propia entrada `seal`). El runner de Omnigent es compartido: sus tools
  trabajan sobre el **estudio activo** (`backend/studies/ACTIVE`), que fija la UI al arrancar la sesión o
  `python -m sparklab.studies use <id>`. Los CLIs (`approve`, `unseal`, `ledger`) también siguen ese puntero salvo
  que `SPARKLAB_ROOT` esté definido. Un solo estudio con agentes a la vez.
- Prueba: `python tests/test_bridge.py` (laboratorio sintético en un directorio temporal, nunca el ledger real).
- **Ensayo rápido sin LLM** (UI completa en ~2 min, datos sintéticos en `/tmp/spark-ui-rehearsal`):
  `python tests/rehearsal.py` (tú das los gates en la UI) o `--auto-gates` (sin intervención).
- **Modo rápido con agentes reales** (mismos gates y reglas; máx. 3 anomalías, 3 ataques, debate de 1 ronda):
  `SPARK_LAB_MODE=fast SPARK_FAST_MODEL=<modelo> python -m sparklab.api`, luego **New study** → Start the lab.
  Por CLI: `python -m sparklab.fastlab --model <modelo>` y `omnigent run lab.fast.yaml` (generado, no se edita).

## 3. Loop en vivo (16:15–17:00)
```bash
omnigent run lab.yaml          # web UI: http://localhost:6767
```
Primer mensaje sugerido:
> Objective: find which discrepancy between self-reported diagnosis and HbA1c to investigate next among
> US adults. Run the SPARK loop. Stop and ask us before anything touches the hold-out.

Lo que debe verse: al inicio de A el Skeptic atrapa E04 (si elegiste E04, la UI pide elegir otra) · gate de poder rechaza una celda chica · prereg con hash + commit.

## 4. Gates humanos, en cámara (17:00–17:20)
```bash
python -m sparklab.approve PR-xxxxxxxx --by Brau   # escribe los primeros 8 caracteres del hash
python -m sparklab.unseal                          # José: verifica hash, procesa una sola vez
```
O lo mismo desde la UI web (paso Run: tecleas el prefijo del hash y firmas). Luego decirle al Supervisor:
"approved and unsealed" (botón en la UI o en el chat). El Experimenter corre `run_test(cycle="I")` una vez.

## 5. Cierre (17:20–18:00)
```bash
python -m sparklab.ledger verify
python -m sparklab.ledger show --type result
git add ledger prereg && git commit -m "run records"
```
`docs/RESULTS.md` desde `docs/RESULTS_TEMPLATE.md`, citando ids del ledger y calc_ids.
