# CFTUV Regression Checklist

Минимальный ручной checklist для regression-проверки после runtime и analysis изменений.

Использование:

1. Сначала прочитать:
   - `docs/cftuv_architecture_v2.0.md`
   - `docs/cftuv_entity_model_and_control_plan.md`
   - при runtime-задаче `docs/cftuv_runtime_notes.md`
2. Открыть regression mesh.
3. Запустить `Save Regression Snapshot`.
4. Проверить, что snapshot содержит две секции:
   - `PatchGraph Snapshot`
   - `Scaffold Snapshot`
5. Сохранить snapshot baseline или сравнить с предыдущим.
6. Отметить expected / unexpected behavior по пунктам ниже.

## Baseline Mesh Set

- [ ] Simple wall
- [ ] Wall with hole-attached patches
- [ ] Floor caps
- [ ] Closed ring house
- [ ] Mixed wall/floor
- [ ] Bevel-heavy wall
- [ ] Isolated curved wall strip
- [ ] Curved wall strip with neighbors
- [ ] Capless cylinder
- [ ] Cylinder with caps and opening

## Per-Mesh Checklist

Для каждого mesh фиксировать:

- [ ] Patch count не изменился без ожидаемой причины
- [ ] Chain count не изменился без ожидаемой причины
- [ ] Corner count не изменился без ожидаемой причины
- [ ] Quilt count не изменился без ожидаемой причины
- [ ] `PatchGraph Snapshot` читается компактно и без явной потери topology context
- [ ] Unsupported patch ids ожидаемы
- [ ] Invalid closure count ожидаем
- [ ] Closure seam residuals не деградировали
- [ ] Row / column scatter не деградировал
- [ ] Conformal fallback patch count ожидаем
- [ ] `H_FRAME / V_FRAME / FREE` распределение выглядит ожидаемо
- [ ] `Run` / `Junction` summary в snapshot выглядит ожидаемо
- [ ] Build order не показывает suspicious drift
- [ ] Pinned / unpinned summary ожидаема
- [ ] Scaffold Analyze / Debug не показывает очевидно ложный split или merge
- [ ] Debug visualization совпадает со snapshot

## Notes Template

```text
Mesh:
Snapshot file:
Expected patch/quilt counts:
Expected chain/corner counts:
Expected unsupported patches:
Expected closure behavior:
Expected row/column behavior:
Expected conformal fallback:
Expected frame rows/columns:
Observed deviations:
Decision: OK / Investigate
```
