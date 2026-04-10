#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

timestamp="$(date +%Y%m%dT%H%M%S)"
report_dir="$ROOT_DIR/backend/media/relatorios/legacy_import"
trailing_report="$report_dir/repair_trailing_preview_cycles_${timestamp}.json"
cycle_one_report="$report_dir/repair_incomplete_cycle_one_${timestamp}.json"

mkdir -p "$report_dir"

echo "[1/5] Aplicando migrações pendentes"
python manage.py migrate

echo "[2/5] Reorganizando ciclos com abril/2026 isolado no ciclo final"
pass=1
remaining=1
while [ "$remaining" -gt 0 ]; do
  current_report="${trailing_report%.json}_pass${pass}.json"
  echo "  - rodada ${pass}"
  python manage.py repair_trailing_preview_cycles --apply --report-json "$current_report"
  remaining="$(python manage.py shell -c "
from apps.contratos.trailing_preview_cycle_repair import repair_trailing_preview_cycles
print(repair_trailing_preview_cycles(apply=False)['remaining_candidates'])
" | tail -n 1 | tr -d '[:space:]')"
  if [ -z "$remaining" ]; then
    echo "Falha ao calcular remanescentes do trailing preview."
    exit 1
  fi
  echo "    remanescentes: $remaining"
  if [ "$remaining" -eq 0 ]; then
    trailing_report="$current_report"
    break
  fi
  pass=$((pass + 1))
  if [ "$pass" -gt 10 ]; then
    echo "Trailing preview ainda possui remanescentes após 10 rodadas."
    exit 1
  fi
done

echo "[3/5] Corrigindo ciclo 1 concluído sem 3 parcelas resolvidas"
pass=1
remaining=1
while [ "$remaining" -gt 0 ]; do
  current_report="${cycle_one_report%.json}_pass${pass}.json"
  echo "  - rodada ${pass}"
  python manage.py repair_incomplete_cycle_one --apply --report-json "$current_report"
  remaining="$(python manage.py shell -c "
from apps.contratos.incomplete_cycle_one_repair import repair_incomplete_cycle_one
print(repair_incomplete_cycle_one(apply=False)['remaining_invalid_completed_cycle_one'])
" | tail -n 1 | tr -d '[:space:]')"
  if [ -z "$remaining" ]; then
    echo "Falha ao calcular remanescentes do ciclo 1 incompleto."
    exit 1
  fi
  echo "    remanescentes: $remaining"
  if [ "$remaining" -eq 0 ]; then
    cycle_one_report="$current_report"
    break
  fi
  pass=$((pass + 1))
  if [ "$pass" -gt 10 ]; then
    echo "Ciclo 1 incompleto ainda possui remanescentes após 10 rodadas."
    exit 1
  fi
done

echo "[4/5] Conferência final da estrutura dos ciclos"
python manage.py shell -c "
from apps.contratos.trailing_preview_cycle_repair import repair_trailing_preview_cycles
from apps.contratos.incomplete_cycle_one_repair import repair_incomplete_cycle_one
print({
    'remaining_trailing_preview_candidates': repair_trailing_preview_cycles(apply=False)['remaining_candidates'],
    'remaining_invalid_completed_cycle_one': repair_incomplete_cycle_one(apply=False)['remaining_invalid_completed_cycle_one'],
})
"

echo "[5/5] Check final do Django"
python manage.py check

echo "Concluído."
echo "Trailing preview report: $trailing_report"
echo "Incomplete cycle one report: $cycle_one_report"
