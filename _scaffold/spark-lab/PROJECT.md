# SPARK Lab — Documento del proyecto

Hack-Nation 7th Global AI Hackathon · Reto 03 "Agentic Scientific Discovery" (Databricks / Omnigent) · 3 de octubre de 2026
Equipo: Braulio (pitch, pizarrón, videos, gate humano) · José (datos, estadística, resultados) · Sebas (Omnigent, tools, repo)

## 1. Tesis en una frase
**SPARK es el método científico para el régimen de observación abundante y atención escasa.** No cambia la lógica de la ciencia (abducción, falsación, replicación); cambia el procedimiento, los roles y los defaults, como lo hicieron Bacon con los instrumentos, Fisher con la estadística, Platt con la biología rápida y el pre-registro con la crisis de replicación.

## 2. Campo científico
**Epidemiología de salud pública basada en encuestas nacionales** (ciencia de re-análisis: conocimiento nuevo a partir de datos observacionales que ya existen).
Caso v1: **diabetes no diagnosticada en adultos de EE. UU.** (NHANES). Se eligió porque es la única condición donde la encuesta tiene tres fuentes de verdad independientes (auto-reporte, HbA1c, glucosa en ayunas); donde se contradicen hay una sorpresa medida.
Fuera de alcance en v1: laboratorio húmedo, simulación, matemáticas, claims causales o clínicos.
Roadmap: hipertensión y obesidad en la misma encuesta → otras encuestas nacionales → farmacovigilancia (FAERS) → bases biomédicas.

## 3. La pregunta
Hay adultos que dicen no tener diagnóstico de diabetes y cuya HbA1c es ≥ 6.5 %. ¿Quiénes son y por qué? Rivales con predicción numérica:
- **H_access** — acceso a salud: los no asegurados tienen razón de prevalencia ≥ 1.5 (nulo 1.0).
- **H_recent_onset** — onset reciente: ≥ 60 % de la celda tiene HbA1c en [6.5, 7.0) (nulo 0.5).
- **H_measurement_error** — error de medición / mal reporte (rival obligatoria; piso declarado).
Decisión al final del loop: qué discrepancia investigar, qué evidencia falta y qué subgrupo amerita re-medición confirmatoria. Nunca "a quién tamizar".

## 4. El método: el loop SPARK
| Paso | Qué pasa | Quién |
|---|---|---|
| **S**urprise | Contrastar el pizarrón (expectativas con cita) con los datos; detectar contradicciones datos-vs-datos | Scout (agente) · humano con observación vivida |
| **P**ropose | 2–3 hipótesis rivales con predicciones numéricas no traslapadas, pre-registradas | Experimenter |
| **A**ttack | Chequeo de definiciones, poder, confusores, sensibilidad a umbrales, error de medición | Skeptic |
| **R**un | ≥ 2 tests, elegido por discriminación × poder / miradas al hold-out; aprobación humana; ejecución | Experimenter + humano |
| **K**eep/Kill | Réplica en el hold-out sellado (una sola vez); veredicto apoyada / incompatible / inconclusa; decisión y siguiente test | Experimenter + Supervisor |

Las cinco leyes: empieza en la sorpresa · varias hipótesis, pre-registradas · refuta antes de gastar · asigna por información por costo · nada existe hasta que replica. Meta-reglas: la memoria es el resultado (el ledger, negativos incluidos) · los humanos gobiernan (objetivo, relevancia, juicio, aprobación).

## 5. Datos
- **Descubrimiento:** NHANES 2017–2018 (sufijo `_J`): DEMO, DIQ, GHB, HIQ, HUQ, BMX, GLU.
- **Hold-out sellado:** NHANES 2015–2016 (`_I`). Zip con SHA-256 registrado en el ledger; nadie lo carga hasta `approve` + `unseal`.
- Biomarcador primario: HbA1c (muestra MEC completa, peso `WTMEC2YR`). Glucosa en ayunas solo como sensibilidad (`WTSAF2YR`).
- Filtros: ≥ 20 años, sin embarazo, código 3 (borderline) aparte, 7/9 excluidos.
- Varianza: linearización de Taylor con estratos `SDMVSTRA` y PSU `SDMVPSU`, IC con t.

## 6. Reglas duras (código, no prompt)
1. Ningún número existe si no salió de una tool.
2. Toda hipótesis se etiqueta por origen (human | agent:nombre).
3. `register_prereg` congela el protocolo con hash SHA-256 y hace `git commit` antes de cualquier `run_test`.
4. El hold-out solo se toca con `run_test` + `prereg` + `approval` humana con el mismo hash + `unseal` verificado. Cada mirada se cuenta.
5. `approve` y `unseal` son comandos de terminal para humanos; los agentes no los tienen.
6. Gate de poder: celda sin ponderar < 30 no entra a confirmatorio.
7. Tres veredictos: apoyada / incompatible / inconclusa. "p ≥ 0.05" no es muerte.
8. Sin claims causales ni clínicos; análisis por raza/etnia requieren revisión humana antes de publicarse.

## 7. Arquitectura
```
Humanos (objetivo, observación vivida, approve, unseal)
   │
Omnigent: Supervisor ──> Scout ──> Skeptic ──> Experimenter
   │                     (tools de sparklab: read_board, compute_surprise, estimate,
   │                      check_power, check_definitions, register_prereg, run_test, ledger)
   ├── board/expectations.json (+ control sembrado)
   ├── data/processed/nhanes_J (descubrimiento) · data/sealed/nhanes_I.zip (hold-out)
   └── ledger/ledger.jsonl (anomaly, attack, hypothesis, prereg, approval, unseal, result, decision, plan_update)
```
Archivos: `lab.yaml` (agentes) · `sparklab/` (config, data, stats, ledger, tools, approve, unseal) · `board/` · `ledger/` · `docs/` · `tests/smoke_test.py`.

## 8. Plan de hoy (hora CDMX)
| Hora | Sebas | José | Brau |
|---|---|---|---|
| 14:15–15:00 | venv + omnigent + `pip install -e .`; go/no-go `omnigent run lab.yaml -p "Say hello"` | `python -m sparklab.data --cycle J`; `--cycle I --seal`; conteos al chat | Corregir cifras y citas del pizarrón; video de equipo (60 s) |
| 15:00–16:15 | ajustar `lab.yaml` y auth; prueba de tools | validar números a mano; sección 2 del runbook | deck (6 slides); shot list |
| 16:15–17:00 | al teclado: `omnigent run lab.yaml` | valida cada número | graba pantalla |
| 17:00–17:20 | — | `python -m sparklab.unseal` en cámara | `python -m sparklab.approve <id> --by Brau` en cámara |
| 17:20–18:00 | README, `docs/AGENTS.md`, export ledger | `docs/RESULTS.md` con ids del ledger | micro-baseline 20 min; edita demo 2 min; deck PDF |
| 18:00 | **Entrega** | | |

## 9. Entregables
Repo público · `lab.yaml` + `docs/AGENTS.md` (especificaciones y gates) · demo de 2 min · video de equipo · deck PDF · `docs/RESULTS.md` (evidencia citada, código y resultados, mejora medida, siguiente experimento) · `ledger/ledger.jsonl` (run records).

## 10. Métricas (honestas)
- Minutos-humano por veredicto auditable (todo contado: curar pizarrón, revisar citas, aprobar).
- Micro-baseline manual de 20 min (interno, declarado).
- Control sembrado atrapado (sí/no) · celda rechazada por poder (n) · miradas al hold-out (1).
- Se reporta el número que salga; sin multiplicadores con conteos diminutos.

## 11. Limitaciones y v2
Descriptivo, no causal · baseline interno n=1 · priors de CDC son "pipeline check" (derivados de NHANES) · 1 loop = evidencia del método, no validación · IC del PR con SEs independientes (aprox.).
v2: placebo (permutación) y spike-in · estabilidad entre corridas · Skeptic en otro modelo (harness distinto en Omnigent) · priors de ciclos no traslapados · playbook de lecciones (mejora recursiva con gates humanos) · más ciclos y condiciones.

## 12. Frases para el pitch
- "Every time the economics of observation changed, the scientific method changed. It just changed again."
- "SPARK is the scientific method for abundant observation and scarce attention. Same logic of science; new procedure, new roles, new defaults."
- "Agents compute surprise; they can't tell which surprise matters. Relevance, lived observation, judgment and consent are human by design."
- "Nothing touches the hold-out without a pre-registration, a hash, a human approval and a verified seal."
- "Omnigent is the operating system of the method: sub-agents are the roles, policies and tool guards are the gates, the session is the lab notebook."
