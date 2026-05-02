from mathutils import Vector


WORLD_UP = Vector((0.0, 0.0, 1.0))

# Patch classification thresholds
FLOOR_THRESHOLD = 0.9
WALL_THRESHOLD = 0.3

# BAND structural classification
BAND_CAP_SIMILARITY_MIN = 0.97
BAND_DIRECTIONAL_CONSISTENCY_MIN = 0.80
BAND_HARD_SIDE_SIMILARITY_MIN = 0.80
BAND_DIRECTION_BACKTRACK_RATIO = 0.02
BAND_DIRECTION_MIN_SAMPLES = 16
TUBE_SEAM_LENGTH_DOMINANCE_MIN = 1.10

# Boundary chain neighbor types
NB_MESH_BORDER = -1
NB_SEAM_SELF = -2

# Frame classification
FRAME_ALIGNMENT_THRESHOLD_H = 0.04
FRAME_ALIGNMENT_THRESHOLD_V = 0.04
FRAME_COMPOUND_LENGTH_THRESHOLD = 0.02
# Backward-compatible alias for code paths that still expect one generic threshold.
FRAME_ALIGNMENT_THRESHOLD = FRAME_ALIGNMENT_THRESHOLD_V

# Corner detection
CORNER_ANGLE_THRESHOLD_DEG = 37.0

# ============================================================
# Sawtooth → H/V promotion (fallback после strict FREE)
# ============================================================
# Цель: FREE-chain у которой polyline «шумит» зубьями вдоль прямой оси,
# но хорда и главная ось идут вдоль U или V patch-базиса, получает
# шанс быть промотированной в H_FRAME / V_FRAME.
#
# Тест КОМПОЗИТНЫЙ — все четыре сигнала должны пройти одновременно,
# чтобы гладкая дуга / S-кривая не проскочили как «зубья».
SAWTOOTH_CHORD_AXIS_ALIGNMENT_MIN = 0.93
# |chord · axis| / |chord| ≥ 0.93 → хорда в конусе ~21° от оси patch.
# Диагональ 45° (≈0.707) отсекается.

SAWTOOTH_PCA_EIGENVALUE_RATIO_MIN = 8.0
# Отношение λ1 / λ2 для 2D-проекции точек в (U,V). ≥ 8 → polyline
# «сильно вытянут» по одной оси, это линия с шумом, не дуга.

SAWTOOTH_MIN_DIRECTION_REVERSALS = 3
# Минимум смен знака производной перпендикулярной-к-хорде компоненты.
# Чистая прямая = 0, дуга = 1, S-кривая = 2, 2 зубца = 3, 3 зубца = 5.
# Этот сигнал ловит И cross-chord sawtooth (зубья по обе стороны хорды),
# И same-side crenellation (декоративные канавки «вглубь стены»), чего
# простой zero-crossing счёт не делает.

# Debug
GP_DEBUG_PREFIX = "CFTUV_Debug_"

# ============================================================
# Scoring weights — задокументированы в Phase 3.5
# Подобраны эмпирически на production мешах (архитектурные ассеты).
# Изменение любого веса влияет на порядок scaffold placement.
# ============================================================

# --- Root patch certainty scoring ---
# Определяет приоритет patch как root для quilt.
# Сумма весов = 1.0 (+ semantic bonus сверху).
ROOT_WEIGHT_AREA = 0.30          # Крупные patches — более стабильный seed
ROOT_WEIGHT_FRAME = 0.30         # Patches с H+V frame — надёжный scaffold каркас
ROOT_WEIGHT_FREE_RATIO = 0.20    # Меньше FREE chains = более предсказуемый layout
ROOT_WEIGHT_HOLES = 0.10         # Patches без holes — проще для conformal
ROOT_WEIGHT_BASE = 0.10          # Базовый score для любого valid patch

# --- Attachment candidate scoring ---
# Определяет силу связи patch→patch через seam.
# Сумма весов = 1.0 (минус penalties).
ATTACH_WEIGHT_SEAM = 0.25       # Длина shared seam нормализованная по max
ATTACH_WEIGHT_PAIR = 0.40       # Сила лучшей chain pair через seam (доминирует)
ATTACH_WEIGHT_TARGET = 0.20     # Root certainty целевого patch
ATTACH_WEIGHT_OWNER = 0.15      # Root certainty текущего patch

# --- Chain pair strength ---
# Определяет силу связи между двумя chains через seam.
PAIR_WEIGHT_FRAME_CONT = 0.40   # Совпадение frame role (H→H, V→V) — основной сигнал
PAIR_WEIGHT_ENDPOINT = 0.25     # Качество endpoint bridge (shared corners/verts)
PAIR_WEIGHT_CORNER = 0.10       # Сила corner anchors
PAIR_WEIGHT_SEMANTIC = 0.10     # Совпадение semantic key
PAIR_WEIGHT_EP_STRENGTH = 0.10  # Endpoint strength отдельных chains
PAIR_WEIGHT_LOOP = 0.05         # Совпадение loop kind (OUTER↔OUTER, HOLE↔HOLE)

# --- Chain frontier thresholds ---
# Контролируют когда frontier builder останавливается.
FRONTIER_PROPAGATE_THRESHOLD = 0.45  # Score выше → уверенно propagate через seam
FRONTIER_WEAK_THRESHOLD = 0.25       # Score ниже → skip (слишком слабая связь)
FRONTIER_MINIMUM_SCORE = 0.30        # Минимальный score для placement chain в frontier

# --- Continuous scoring factors (P5) ---
SCORE_FREE_LENGTH_SCALE = 0.1
SCORE_FREE_LENGTH_CAP = 0.15
SCORE_DOWNSTREAM_SCALE = 0.05
SCORE_DOWNSTREAM_CAP = 0.20
SCORE_ISOLATED_HV_PENALTY = 0.40
SCORE_HV_ADJ_FULL_BONUS = 0.35
SCORE_HV_ADJ_ISOLATED_PENALTY = 1.80
SCORE_BRIDGE_FIRST_PATCH_PENALTY = 1.10
SCORE_BRIDGE_CROSS_PATCH_PENALTY = 0.85
SCORE_FREE_STRIP_CONNECTOR = 0.10
SCORE_FREE_FRAME_NEIGHBOR = 0.05

# --- P7 skeleton graph tolerances (S2) ---
SKELETON_ROW_SPREAD_TOLERANCE = 0.01
SKELETON_COL_SPREAD_TOLERANCE = 0.01
SKELETON_SIBLING_LENGTH_TOLERANCE = 0.001
SKELETON_SIBLING_WEIGHT = 5.0
SKELETON_GAUGE_WEIGHT = 1_000_000.0
SKELETON_MAX_RESIDUAL_WARN = 0.01
SKELETON_MAX_CYCLE_RESIDUAL_APPLY = 0.25
USE_SKELETON_SOLVE = True
# --- Closure cut heuristic weights ---
# Определяют score каждого seam edge как кандидата на UV cut.
# Высокий score = edge лучше подходит как разрыв (rigid endpoints, clean cut).
# Сумма весов = 1.10 (clamp01 на выходе).
CLOSURE_CUT_WEIGHT_FRAME_CONT = 0.22    # Совпадение frame role через seam
CLOSURE_CUT_WEIGHT_ENDPOINT_BRIDGE = 0.17  # Качество endpoint bridge
CLOSURE_CUT_WEIGHT_ENDPOINT_STR = 0.11  # Сила endpoint anchors
CLOSURE_CUT_WEIGHT_SEAM_NORM = 0.09     # Длина shared seam нормализованная
CLOSURE_CUT_WEIGHT_FIXED_RATIO = 0.15   # Доля fixed (H/V anchored) endpoints
CLOSURE_CUT_WEIGHT_SAME_AXIS = 0.15     # Доля same-axis endpoint neighbours
CLOSURE_CUT_WEIGHT_FREE_TOUCH = 0.13    # Инверсия доли FREE-touched endpoints
CLOSURE_CUT_WEIGHT_DIHEDRAL = 0.08      # Dihedral convexity: concave → prefer cut
