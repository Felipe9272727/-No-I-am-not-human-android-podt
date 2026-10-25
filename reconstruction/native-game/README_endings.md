# Gameplay ending selection

`endings.cpp` implements the recovered ten-candidate order and predicates. It uses production thresholds of four innocent kills, two used povistkas, and three FEMA calls. It evaluates every candidate and selects the highest priority, preserving candidate order on ties. Super is not part of this selection. Death/Cult/Mushroom visit-index helpers preserve the recovered mappings and reject unsupported indices.

Evidence status and unresolved source-hash limitations are recorded in `reconstruction/reverse-endings/verified_spec.json`.
