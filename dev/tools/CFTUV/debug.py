import bpy
import colorsys
from mathutils import Vector

try:
    from .constants import GP_DEBUG_PREFIX
    from .model import FrameRole, LoopKind, PatchGraph, PatchType
except ImportError:
    from constants import GP_DEBUG_PREFIX
    from model import FrameRole, LoopKind, PatchGraph, PatchType


_GP_STYLES = {
    'Loops_Boundary': (1.0, 0.95, 0.95, 0.95),
    'Loops_Holes': (0.2, 0.35, 0.85, 0.95),
    'Overlay_Centers': (1.0, 1.0, 1.0, 1.0),
}

# Цвета chains по frame role — рисуются на одном слое Loops_Chains
_CHAIN_COLORS = {
    FrameRole.H_FRAME: (1.0, 0.85, 0.0, 1.0),     # жёлтый
    FrameRole.V_FRAME: (0.0, 0.85, 0.85, 1.0),     # бирюзовый
    FrameRole.FREE: (0.55, 0.55, 0.55, 0.7),        # серый
}

_BASIS_COLORS = {
    'U': (1.0, 0.15, 0.15, 1.0),
    'V': (0.15, 1.0, 0.15, 1.0),
    'N': (0.2, 0.2, 1.0, 1.0),
}

_LABEL_COLLECTION_NAME = GP_DEBUG_PREFIX + 'Labels'
_LABEL_PREFIX = GP_DEBUG_PREFIX + 'L_'
_LABEL_SCALE = 0.20
_LABEL_LIFT = 0.025
_GP_OBJECT_TYPES = {'GPENCIL', 'GREASEPENCIL'}
_GP_V3_RADIUS_PER_PIXEL = 0.00075


def _enum_value(value):
    return value.value if hasattr(value, 'value') else value


def _get_gp_debug_name(source_obj):
    return GP_DEBUG_PREFIX + source_obj.name


def is_gp_debug_object(obj):
    return obj is not None and getattr(obj, 'type', None) in _GP_OBJECT_TYPES


def _grease_pencil_collections():
    collections = []
    gp_v3 = getattr(bpy.data, 'grease_pencils_v3', None)
    if gp_v3 is not None:
        collections.append(gp_v3)
    gp_legacy = getattr(bpy.data, 'grease_pencils', None)
    if gp_legacy is not None and gp_legacy not in collections:
        collections.append(gp_legacy)
    return collections


def _grease_pencil_object_collection():
    collections = _grease_pencil_collections()
    return collections[0] if collections else None


def gp_layer_name(layer):
    return getattr(layer, 'info', getattr(layer, 'name', ''))


def get_gp_layer(gp_data, layer_name):
    layers = getattr(gp_data, 'layers', None)
    if layers is None:
        return None
    for layer in layers:
        if gp_layer_name(layer) == layer_name:
            return layer
    return None


def _clear_gp_layer(layer):
    if hasattr(layer, 'clear'):
        layer.clear()
        return

    frames = getattr(layer, 'frames', None)
    if frames is None:
        return
    while len(frames) > 0:
        frame = frames[-1]
        frame_number = getattr(frame, 'frame_number', None)
        if frame_number is None:
            break
        frames.remove(frame_number)


def _lift_point(point, normal, offset=0.01):
    if normal.length <= 1e-8:
        return point.copy()
    return point + normal.normalized() * offset


def _lift_points(points, normal, offset=0.01):
    return [_lift_point(point, normal, offset) for point in points]


def _chain_replay_length(chain):
    points = list(chain.vert_cos)
    if len(points) < 2:
        return 0.0
    total = 0.0
    for index in range(len(points) - 1):
        total += (points[index + 1] - points[index]).length
    if chain.is_closed:
        total += (points[0] - points[-1]).length
    return total


def _loop_enabled(loop, settings_dict):
    loop_kind = _enum_value(loop.kind)
    if loop_kind == LoopKind.HOLE.value:
        return settings_dict.get('loops_holes', True)
    return settings_dict.get('loops_boundary', True)


def _chain_enabled(chain, settings_dict):
    role = _enum_value(chain.frame_role)
    key = {
        FrameRole.H_FRAME.value: 'frame_h',
        FrameRole.V_FRAME.value: 'frame_v',
        FrameRole.FREE.value: 'frame_free',
    }.get(role)
    return settings_dict.get(key, True) if key else True


def _get_or_create_gp_object(source_obj):
    gp_name = _get_gp_debug_name(source_obj)

    if gp_name in bpy.data.objects:
        gp_obj = bpy.data.objects[gp_name]
        if is_gp_debug_object(gp_obj):
            return gp_obj
        bpy.data.objects.remove(gp_obj, do_unlink=True)

    gp_collection = _grease_pencil_object_collection()
    if gp_collection is None:
        raise RuntimeError("Grease Pencil data-block collection is unavailable in this Blender version")

    gp_data = gp_collection.new(gp_name)
    gp_obj = bpy.data.objects.new(gp_name, gp_data)
    bpy.context.scene.collection.objects.link(gp_obj)
    gp_obj.matrix_world = source_obj.matrix_world.copy()
    if hasattr(gp_data, 'stroke_depth_order'):
        gp_data.stroke_depth_order = '3D'
    if hasattr(gp_data, 'stroke_thickness_space'):
        gp_data.stroke_thickness_space = 'SCREENSPACE'
    return gp_obj


def _ensure_gp_layer(gp_data, layer_name, color_rgba):
    mat_name = f'CFTUV_{layer_name}'
    if mat_name in bpy.data.materials:
        mat = bpy.data.materials[mat_name]
    else:
        mat = bpy.data.materials.new(mat_name)
        bpy.data.materials.create_gpencil_data(mat)

    mat.grease_pencil.color = color_rgba[:4]
    mat.grease_pencil.show_fill = False

    mat_idx = None
    for index, slot in enumerate(gp_data.materials):
        if slot and slot.name == mat_name:
            mat_idx = index
            break
    if mat_idx is None:
        gp_data.materials.append(mat)
        mat_idx = len(gp_data.materials) - 1

    layer = get_gp_layer(gp_data, layer_name)
    if layer is not None:
        _clear_gp_layer(layer)
    else:
        layer = gp_data.layers.new(layer_name, set_active=False)

    frame = layer.frames[0] if layer.frames else layer.frames.new(0)
    return frame, mat_idx


def _new_gp_stroke(frame, point_count):
    if hasattr(frame, 'strokes') and hasattr(frame.strokes, 'new'):
        stroke = frame.strokes.new()
        stroke.points.add(point_count)
        return stroke

    drawing = getattr(frame, 'drawing', None)
    if drawing is None:
        raise RuntimeError("Grease Pencil frame has no drawing/strokes API")
    drawing.add_strokes(sizes=[point_count])
    return drawing.strokes[-1]


def _set_gp_stroke_style(stroke, line_width, cyclic):
    if hasattr(stroke, 'line_width'):
        stroke.line_width = line_width
    if hasattr(stroke, 'use_cyclic'):
        stroke.use_cyclic = cyclic
    elif hasattr(stroke, 'cyclic'):
        stroke.cyclic = cyclic


def _set_gp_stroke_point(point, location, line_width):
    coords = (location.x, location.y, location.z)
    if hasattr(point, 'co'):
        point.co = coords
    elif hasattr(point, 'position'):
        point.position = coords

    if hasattr(point, 'strength'):
        point.strength = 1.0
    elif hasattr(point, 'opacity'):
        point.opacity = 1.0

    if hasattr(point, 'pressure'):
        point.pressure = 1.0
    if hasattr(point, 'radius'):
        point.radius = max(0.0005, line_width * _GP_V3_RADIUS_PER_PIXEL)


def _add_gp_stroke(frame, points, mat_idx, line_width=4, cyclic=False):
    if len(points) < 2:
        return
    stroke = _new_gp_stroke(frame, len(points))
    stroke.material_index = mat_idx
    _set_gp_stroke_style(stroke, line_width, cyclic)
    for index, point in enumerate(points):
        _set_gp_stroke_point(stroke.points[index], point, line_width)


def _ensure_gp_material(gp_data, mat_name, color_rgba):
    """Создаёт или находит GP material и возвращает его индекс в gp_data."""
    if mat_name in bpy.data.materials:
        mat = bpy.data.materials[mat_name]
    else:
        mat = bpy.data.materials.new(mat_name)
        bpy.data.materials.create_gpencil_data(mat)
    mat.grease_pencil.color = color_rgba[:4]
    mat.grease_pencil.show_fill = False

    for index, slot in enumerate(gp_data.materials):
        if slot and slot.name == mat_name:
            return index
    gp_data.materials.append(mat)
    return len(gp_data.materials) - 1


def _ensure_gp_fill_material(gp_data, mat_name, color_rgba):
    if mat_name in bpy.data.materials:
        mat = bpy.data.materials[mat_name]
    else:
        mat = bpy.data.materials.new(mat_name)
    if not mat.grease_pencil:
        bpy.data.materials.create_gpencil_data(mat)
    mat.grease_pencil.color = color_rgba[:4]
    mat.grease_pencil.show_fill = True
    mat.grease_pencil.fill_color = color_rgba[:4]
    mat.grease_pencil.show_stroke = False

    for index, slot in enumerate(gp_data.materials):
        if slot and slot.name == mat_name:
            return index
    gp_data.materials.append(mat)
    return len(gp_data.materials) - 1


def _get_or_create_label_collection():
    """Возвращает коллекцию для text labels, создаёт если нет."""
    if _LABEL_COLLECTION_NAME in bpy.data.collections:
        return bpy.data.collections[_LABEL_COLLECTION_NAME]
    col = bpy.data.collections.new(_LABEL_COLLECTION_NAME)
    bpy.context.scene.collection.children.link(col)
    return col


def _clear_labels():
    """Удаляет все text label objects и коллекцию."""
    if _LABEL_COLLECTION_NAME in bpy.data.collections:
        col = bpy.data.collections[_LABEL_COLLECTION_NAME]
        for obj in list(col.objects):
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data and data.users == 0:
                bpy.data.curves.remove(data)
        bpy.data.collections.remove(col)
    # Зачищаем осиротевшие label объекты
    for obj in list(bpy.data.objects):
        if obj.name.startswith(_LABEL_PREFIX):
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data and data.users == 0:
                bpy.data.curves.remove(data)


def _chain_midpoint(chain):
    """Точка на середине chain по длине."""
    points = list(chain.vert_cos)
    if not points:
        return Vector((0, 0, 0))
    if len(points) == 1:
        return points[0].copy()
    # Считаем суммарную длину
    seg_lengths = []
    total = 0.0
    for i in range(len(points) - 1):
        seg_len = (points[i + 1] - points[i]).length
        seg_lengths.append(seg_len)
        total += seg_len
    if total < 1e-8:
        return points[0].copy()
    half = total * 0.5
    accum = 0.0
    for i, seg_len in enumerate(seg_lengths):
        if accum + seg_len >= half:
            t = (half - accum) / seg_len if seg_len > 1e-8 else 0.0
            return points[i].lerp(points[i + 1], t)
        accum += seg_len
    return points[-1].copy()


def _create_chain_labels(graph, source_obj):
    """Создаёт text label в midpoint каждого chain: P{id}C{idx}."""
    _clear_labels()
    col = _get_or_create_label_collection()
    world_matrix = source_obj.matrix_world

    for patch_id in sorted(graph.nodes.keys()):
        node = graph.nodes[patch_id]
        normal = node.normal
        for loop_index, loop in enumerate(node.boundary_loops):
            chain_records = loop.iter_oriented_chain_records()
            if not chain_records:
                chain_records = tuple(
                    (graph.get_chain_use(patch_id, loop_index, chain_index), chain)
                    for chain_index, chain in enumerate(loop.chains)
                )

            for chain_use, chain in chain_records:
                if chain_use is None:
                    continue
                chain_idx = chain_use.chain_index
                if len(chain.vert_cos) < 1:
                    continue
                mid = _chain_midpoint(chain)
                pos = _lift_point(mid, normal, _LABEL_LIFT)
                pos = world_matrix @ pos

                label_text = f"P{patch_id}C{chain_idx}"
                obj_name = f"{_LABEL_PREFIX}{patch_id}_{chain_idx}"

                curve_data = bpy.data.curves.new(obj_name, type='FONT')
                curve_data.body = label_text
                curve_data.size = _LABEL_SCALE
                curve_data.align_x = 'CENTER'
                curve_data.align_y = 'CENTER'

                role = chain.frame_role if isinstance(chain.frame_role, FrameRole) else FrameRole(chain.frame_role)
                color = _CHAIN_COLORS.get(role, _CHAIN_COLORS[FrameRole.FREE])

                mat_name = f'CFTUV_Label_{role.value}'
                if mat_name in bpy.data.materials:
                    mat = bpy.data.materials[mat_name]
                else:
                    mat = bpy.data.materials.new(mat_name)
                mat.diffuse_color = color[:4]

                curve_data.materials.clear()
                curve_data.materials.append(mat)

                text_obj = bpy.data.objects.new(obj_name, curve_data)
                text_obj.location = pos
                col.objects.link(text_obj)


def clear_visualization(source_obj):
    _clear_labels()

    gp_name = _get_gp_debug_name(source_obj)
    if gp_name in bpy.data.objects:
        obj = bpy.data.objects[gp_name]
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in _grease_pencil_collections():
        if gp_name in collection:
            collection.remove(collection[gp_name])

    mesh_name = GP_DEBUG_PREFIX + 'Mesh_' + source_obj.name
    if mesh_name in bpy.data.objects:
        obj = bpy.data.objects[mesh_name]
        mesh_data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh_data and mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data)

    for mat in list(bpy.data.materials):
        if (
            mat.name.startswith('CFTUV_P')
            or mat.name.startswith('CFTUV_Axis_')
            or mat.name.startswith('CFTUV_Chain_')
            or mat.name.startswith('CFTUV_DebugPatch_')
            or mat.name.startswith('CFTUV_Loops_')
            or mat.name.startswith('CFTUV_Overlay_')
            or mat.name.startswith('CFTUV_Frontier_')
            or mat.name.startswith('CFTUV_Label_')
        ) and mat.users == 0:
            bpy.data.materials.remove(mat)


def _create_patch_mesh(graph: PatchGraph, source_obj):
    mesh_name = GP_DEBUG_PREFIX + 'Mesh_' + source_obj.name

    if mesh_name in bpy.data.objects:
        old_obj = bpy.data.objects[mesh_name]
        old_data = old_obj.data
        bpy.data.objects.remove(old_obj, do_unlink=True)
        if old_data and old_data.users == 0:
            bpy.data.meshes.remove(old_data)

    all_verts = []
    all_faces = []
    face_mat_indices = []
    golden_ratio = 0.618033988749895
    materials = []

    patch_ids = sorted(graph.nodes.keys())
    for draw_index, patch_id in enumerate(patch_ids):
        node = graph.nodes[patch_id]
        offset = len(all_verts)

        for vert in node.mesh_verts:
            all_verts.append(vert)

        for tri in node.mesh_tris:
            all_faces.append(tuple(index + offset for index in tri))
            face_mat_indices.append(draw_index)

        hue = (draw_index * golden_ratio) % 1.0
        patch_type = _enum_value(node.patch_type)
        if patch_type == PatchType.WALL.value:
            sat, val, alpha = 0.8, 0.9, 0.4
        else:
            sat, val, alpha = 0.5, 0.6, 0.3
        r, g, b = colorsys.hsv_to_rgb(hue, sat, val)

        mat_name = f'CFTUV_P{draw_index:03d}'
        if mat_name in bpy.data.materials:
            mat = bpy.data.materials[mat_name]
        else:
            mat = bpy.data.materials.new(mat_name)
        mat.diffuse_color = (r, g, b, alpha)
        mat.use_nodes = False
        materials.append(mat)

    mesh_data = bpy.data.meshes.new(mesh_name)
    mesh_data.from_pydata([vert[:] for vert in all_verts], [], all_faces)
    mesh_data.update()

    for mat in materials:
        mesh_data.materials.append(mat)

    for face_index, mat_index in enumerate(face_mat_indices):
        if face_index < len(mesh_data.polygons):
            mesh_data.polygons[face_index].material_index = mat_index

    mesh_obj = bpy.data.objects.new(mesh_name, mesh_data)
    mesh_obj.matrix_world = source_obj.matrix_world.copy()
    bpy.context.scene.collection.objects.link(mesh_obj)
    mesh_obj.show_transparent = True
    mesh_obj.display_type = 'SOLID'
    mesh_obj.color = (1, 1, 1, 0.5)
    mesh_obj.hide_viewport = True
    mesh_obj.hide_render = True


def apply_layer_visibility(gp_data, dbg_settings):
    mapping = {
        'Patches_WALL': dbg_settings.get('patches_wall', True),
        'Patches_FLOOR': dbg_settings.get('patches_floor', True),
        'Patches_SLOPE': dbg_settings.get('patches_slope', True),
        'Loops_Chains': dbg_settings.get('loops_chains', True),
        'Loops_Boundary': dbg_settings.get('loops_boundary', True),
        'Loops_Holes': dbg_settings.get('loops_holes', True),
        'Overlay_Basis': dbg_settings.get('overlay_basis', True),
        'Overlay_Centers': dbg_settings.get('overlay_centers', True),
        'Frontier_Path': dbg_settings.get('frontier_path', True),
    }
    for layer_name, visible in mapping.items():
        layer = get_gp_layer(gp_data, layer_name)
        if layer is not None:
            layer.hide = not visible

    # Labels collection visibility
    labels_visible = dbg_settings.get('overlay_labels', True)
    if _LABEL_COLLECTION_NAME in bpy.data.collections:
        bpy.data.collections[_LABEL_COLLECTION_NAME].hide_viewport = not labels_visible


def create_visualization(graph: PatchGraph, source_obj, settings_dict=None):
    settings_dict = settings_dict or {}

    gp_obj = _get_or_create_gp_object(source_obj)
    gp_data = gp_obj.data
    _create_patch_mesh(graph, source_obj)

    frames_and_mats = {}
    for style_name, color in _GP_STYLES.items():
        frame, mat_idx = _ensure_gp_layer(gp_data, style_name, color)
        frames_and_mats[style_name] = (frame, mat_idx)

    # Loops_Chains — единый слой, материалы по frame role
    chains_layer_name = 'Loops_Chains'
    chains_layer = get_gp_layer(gp_data, chains_layer_name)
    if chains_layer is not None:
        _clear_gp_layer(chains_layer)
    else:
        chains_layer = gp_data.layers.new(chains_layer_name, set_active=False)
    chains_frame = chains_layer.frames[0] if chains_layer.frames else chains_layer.frames.new(0)
    chain_mat_indices = {}
    for role, color in _CHAIN_COLORS.items():
        mat_name = f'CFTUV_Chain_{role.value}'
        chain_mat_indices[role] = _ensure_gp_material(gp_data, mat_name, color)

    basis_layer_name = 'Overlay_Basis'
    basis_layer = get_gp_layer(gp_data, basis_layer_name)
    if basis_layer is not None:
        _clear_gp_layer(basis_layer)
    else:
        basis_layer = gp_data.layers.new(basis_layer_name, set_active=False)
    basis_frame = basis_layer.frames[0] if basis_layer.frames else basis_layer.frames.new(0)

    basis_mats = {}
    for axis_key, color in _BASIS_COLORS.items():
        mat_name = f'CFTUV_Axis_{axis_key}'
        if mat_name in bpy.data.materials:
            mat = bpy.data.materials[mat_name]
        else:
            mat = bpy.data.materials.new(mat_name)
        if not mat.grease_pencil:
            bpy.data.materials.create_gpencil_data(mat)
        mat.grease_pencil.color = color[:4]
        mat.grease_pencil.show_fill = False

        mat_idx = None
        for index, slot in enumerate(gp_data.materials):
            if slot and slot.name == mat_name:
                mat_idx = index
                break
        if mat_idx is None:
            gp_data.materials.append(mat)
            mat_idx = len(gp_data.materials) - 1
        basis_mats[axis_key] = mat_idx

    patch_layers = {}
    for patch_type in (PatchType.WALL.value, PatchType.FLOOR.value, PatchType.SLOPE.value):
        layer_name = f'Patches_{patch_type}'
        layer = get_gp_layer(gp_data, layer_name)
        if layer is not None:
            _clear_gp_layer(layer)
        else:
            layer = gp_data.layers.new(layer_name, set_active=False)
        patch_layers[patch_type] = layer.frames[0] if layer.frames else layer.frames.new(0)

    patch_mat_indices = {}
    golden_ratio = 0.618033988749895
    for draw_index, patch_id in enumerate(sorted(graph.nodes.keys())):
        node = graph.nodes[patch_id]
        patch_type = _enum_value(node.patch_type)
        hue = (draw_index * golden_ratio) % 1.0
        if patch_type == PatchType.WALL.value:
            sat, val = 0.8, 0.9
        elif patch_type == PatchType.SLOPE.value:
            sat, val = 0.7, 0.75
        else:
            sat, val = 0.5, 0.6
        r, g, b = colorsys.hsv_to_rgb(hue, sat, val)

        mat_name = f'CFTUV_DebugPatch_{patch_id:03d}'
        patch_mat_indices[patch_id] = _ensure_gp_fill_material(
            gp_data,
            mat_name,
            (r, g, b, 1.0),
        )

    centers_frame, centers_mat = frames_and_mats['Overlay_Centers']

    for patch_id in sorted(graph.nodes.keys()):
        node = graph.nodes[patch_id]

        centroid = _lift_point(node.centroid, node.normal, 0.012)
        axis_len = 0.15
        center_size = 0.045

        _add_gp_stroke(basis_frame, [centroid, centroid + node.basis_u * axis_len], basis_mats['U'], line_width=8)
        _add_gp_stroke(basis_frame, [centroid, centroid + node.basis_v * axis_len], basis_mats['V'], line_width=8)
        _add_gp_stroke(basis_frame, [centroid, centroid + node.normal * axis_len * 0.6], basis_mats['N'], line_width=6)
        _add_gp_stroke(centers_frame, [centroid - node.basis_u * center_size, centroid + node.basis_u * center_size], centers_mat, line_width=5)
        _add_gp_stroke(centers_frame, [centroid - node.basis_v * center_size, centroid + node.basis_v * center_size], centers_mat, line_width=5)

        patch_type = _enum_value(node.patch_type)
        patch_frame = patch_layers.get(patch_type, patch_layers[PatchType.WALL.value])
        patch_mat = patch_mat_indices[patch_id]
        for tri in node.mesh_tris:
            if len(tri) < 3:
                continue
            stroke = _new_gp_stroke(patch_frame, len(tri))
            stroke.material_index = patch_mat
            _set_gp_stroke_style(stroke, 1, True)
            for point_index, vert_index in enumerate(tri):
                point = node.mesh_verts[vert_index]
                _set_gp_stroke_point(stroke.points[point_index], point, 1)

        for loop_index, boundary_loop in enumerate(node.boundary_loops):
            loop_points = _lift_points(boundary_loop.vert_cos + [boundary_loop.vert_cos[0]], node.normal, 0.014)
            if len(loop_points) >= 2:
                if _enum_value(boundary_loop.kind) == LoopKind.HOLE.value:
                    frame, mat_idx = frames_and_mats['Loops_Holes']
                    _add_gp_stroke(frame, loop_points, mat_idx, line_width=5)
                else:
                    frame, mat_idx = frames_and_mats['Loops_Boundary']
                    _add_gp_stroke(frame, loop_points, mat_idx, line_width=5)

            chain_records = boundary_loop.iter_oriented_chain_records()
            if not chain_records:
                chain_records = tuple(
                    (graph.get_chain_use(patch_id, loop_index, chain_index), chain)
                    for chain_index, chain in enumerate(boundary_loop.chains)
                )

            for _chain_use, chain in chain_records:
                if _chain_use is None:
                    continue
                raw_points = chain.vert_cos + [chain.vert_cos[0]] if chain.is_closed else chain.vert_cos
                lifted_points = _lift_points(raw_points, node.normal, 0.016)
                if len(lifted_points) < 2:
                    continue

                role = chain.frame_role if isinstance(chain.frame_role, FrameRole) else FrameRole(chain.frame_role)
                line_width = 6 if role in (FrameRole.H_FRAME, FrameRole.V_FRAME) else 3
                mat_idx = chain_mat_indices.get(role, chain_mat_indices[FrameRole.FREE])
                _add_gp_stroke(chains_frame, lifted_points, mat_idx, line_width=line_width)

    _create_chain_labels(graph, source_obj)

    apply_layer_visibility(gp_data, settings_dict)
    return gp_obj


def _prepare_patch_fill_materials(graph, gp_data):
    """Создаёт fill-материалы для каждого patch (как в Patches_ слоях)."""
    golden_ratio = 0.618033988749895
    patch_mat_indices = {}
    for draw_index, patch_id in enumerate(sorted(graph.nodes.keys())):
        node = graph.nodes[patch_id]
        patch_type = _enum_value(node.patch_type)
        hue = (draw_index * golden_ratio) % 1.0
        if patch_type == PatchType.WALL.value:
            sat, val = 0.8, 0.9
        elif patch_type == PatchType.SLOPE.value:
            sat, val = 0.7, 0.75
        else:
            sat, val = 0.5, 0.6
        r, g, b = colorsys.hsv_to_rgb(hue, sat, val)

        mat_name = f'CFTUV_FrontierPatch_{patch_id:03d}'
        if mat_name in bpy.data.materials:
            mat = bpy.data.materials[mat_name]
        else:
            mat = bpy.data.materials.new(mat_name)
        if not mat.grease_pencil:
            bpy.data.materials.create_gpencil_data(mat)
        mat.grease_pencil.color = (r, g, b, 0.6)
        mat.grease_pencil.show_fill = True
        mat.grease_pencil.fill_color = (r, g, b, 0.6)
        mat.grease_pencil.show_stroke = False

        mat_idx = None
        for slot_index, slot in enumerate(gp_data.materials):
            if slot and slot.name == mat_name:
                mat_idx = slot_index
                break
        if mat_idx is None:
            gp_data.materials.append(mat)
            mat_idx = len(gp_data.materials) - 1
        patch_mat_indices[patch_id] = mat_idx
    return patch_mat_indices


def _draw_patch_fill(gp_frame, node, mat_idx):
    """Рисует fill triangles patch'а на GP frame."""
    for tri in node.mesh_tris:
        if len(tri) < 3:
            continue
        stroke = _new_gp_stroke(gp_frame, len(tri))
        stroke.material_index = mat_idx
        _set_gp_stroke_style(stroke, 1, True)
        for point_index, vert_index in enumerate(tri):
            point = node.mesh_verts[vert_index]
            _set_gp_stroke_point(stroke.points[point_index], point, 1)


def create_frontier_visualization(graph: PatchGraph, scaffold_map, source_obj, settings_dict=None):
    """Анимированная визуализация scaffold build — покадровый replay frontier.

    Каждый кадр аккумулятивный: frame N показывает chains шагов 0..N.
    Цвета как в Loops_Chains: жёлтый (H), бирюзовый (V), серый (FREE).
    Когда все chains patch'а размещены — появляется fill заливка.
    Самый длинный chain = 1 секунда (fps из сцены), остальные шаги
    пропорционально короче. Playback через timeline.
    """
    settings_dict = settings_dict or {}
    gp_name = _get_gp_debug_name(source_obj)
    gp_obj = bpy.data.objects.get(gp_name)
    if not is_gp_debug_object(gp_obj):
        return
    gp_data = gp_obj.data

    layer_name = 'Frontier_Path'
    layer = get_gp_layer(gp_data, layer_name)
    if layer is not None:
        _clear_gp_layer(layer)
    else:
        layer = gp_data.layers.new(layer_name, set_active=False)

    # Материалы: chains по role + patch fills
    chain_mat_indices = {}
    for role, color in _CHAIN_COLORS.items():
        mat_name = f'CFTUV_Frontier_{role.value}'
        chain_mat_indices[role] = _ensure_gp_material(gp_data, mat_name, color)

    patch_fill_mats = _prepare_patch_fill_materials(graph, gp_data)

    # Собираем все шаги из всех quilts в единый timeline
    all_steps = []
    for quilt in scaffold_map.quilts:
        build_order = getattr(quilt, 'build_order', [])
        for ref in build_order:
            all_steps.append(ref)

    if not all_steps:
        apply_layer_visibility(gp_data, settings_dict)
        return

    # Считаем сколько chains у каждого patch в build_order
    patch_total_chains = {}
    for ref in all_steps:
        pid = ref[0]
        patch_total_chains[pid] = patch_total_chains.get(pid, 0) + 1

    fps = bpy.context.scene.render.fps
    max_step_frames = max(1, round(fps))
    total_steps = len(all_steps)
    step_frames = []
    step_lengths = []
    for ref in all_steps:
        node = graph.nodes.get(ref[0])
        if node is None or ref[1] < 0 or ref[1] >= len(node.boundary_loops):
            step_lengths.append(0.0)
            continue
        loop = node.boundary_loops[ref[1]]
        if ref[2] < 0 or ref[2] >= len(loop.chains):
            step_lengths.append(0.0)
            continue
        step_lengths.append(_chain_replay_length(loop.chains[ref[2]]))

    max_step_length = max(step_lengths, default=0.0)
    if max_step_length <= 1e-8:
        step_frames = [max_step_frames] * total_steps
    else:
        for length in step_lengths:
            ratio = length / max_step_length
            step_frames.append(max(1, round(max_step_frames * ratio)))

    # Каждый GP frame аккумулятивный: chains 0..step + fill для завершённых patches
    frame_cursor = 0
    for step_index in range(total_steps):
        frame_number = frame_cursor
        gp_frame = layer.frames.new(frame_number)

        # Счётчик размещённых chains на текущий шаг
        patch_placed = {}

        for draw_index in range(step_index + 1):
            ref = all_steps[draw_index]
            patch_id, loop_idx, chain_idx = ref
            patch_placed[patch_id] = patch_placed.get(patch_id, 0) + 1

            node = graph.nodes.get(patch_id)
            if node is None:
                continue
            if loop_idx < 0 or loop_idx >= len(node.boundary_loops):
                continue
            loop = node.boundary_loops[loop_idx]
            if chain_idx < 0 or chain_idx >= len(loop.chains):
                continue
            chain = loop.chains[chain_idx]

            role = chain.frame_role if isinstance(chain.frame_role, FrameRole) else FrameRole(chain.frame_role)
            mat_idx = chain_mat_indices.get(role, chain_mat_indices[FrameRole.FREE])
            line_width = 10 if draw_index == step_index else 6

            raw_points = chain.vert_cos + [chain.vert_cos[0]] if chain.is_closed else chain.vert_cos
            lifted_points = _lift_points(raw_points, node.normal, 0.020)
            if len(lifted_points) >= 2:
                _add_gp_stroke(gp_frame, lifted_points, mat_idx, line_width=line_width)

        # Рисуем fill для patches у которых все chains размещены
        for pid, placed_count in patch_placed.items():
            if placed_count >= patch_total_chains.get(pid, 999):
                node = graph.nodes.get(pid)
                if node is not None and pid in patch_fill_mats:
                    _draw_patch_fill(gp_frame, node, patch_fill_mats[pid])
        frame_cursor += step_frames[step_index]

    # Настраиваем timeline
    scene = bpy.context.scene
    scene.frame_start = 0
    scene.frame_end = max(0, frame_cursor - 1)
    scene.frame_current = 0

    apply_layer_visibility(gp_data, settings_dict)


__all__ = [
    'apply_layer_visibility',
    'create_visualization',
    'clear_visualization',
    'create_frontier_visualization',
    'get_gp_layer',
    'gp_layer_name',
    'is_gp_debug_object',
]
