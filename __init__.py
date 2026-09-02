bl_info = {
    "name": "HD2 Mass LUT / Texture ID Swap",
    "author": "Uskummel",
    "version": (1, 2, 5),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > ID_Swap",
    "description": "Apply preset or per-slot custom Armor/Helmet LUTs across many archives",
    "doc_url": "https://github.com/USKUMMEL/Helldivers-2-Mass-LUTs-Swap-Blender-Addon",
    "category": "Import-Export",
}

"""
Standalone HD2 LUT / Texture ID Swap addon.

The addon never replaces Units, meshes, rigging, decal sheets, masks, normal
maps, or Materials.  It overrides each destination LUT Texture ID with a
selected source Texture payload.  The patch writer aliases identical payloads,
so many destination LUT IDs store the source LUT data only once.
"""

import base64
import copy
import hashlib
import importlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import time

import bpy
import bpy.utils.previews
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator, Panel, PropertyGroup, UIList


DATA_CACHE = {}
CUSTOM_SLOT_CACHE = {}
PRIVATE_ARCHIVES = {}
PRIVATE_PAYLOADS = {}
SUPPORT_ICONS = None
EMBEDDED_SUPPORT_ICONS = {
    "paypal": "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACcElEQVR42m2SS0jUURSHv3Pvf2Z0NB8VihGaKWGWRe0iclYVQpsC3RREFLqLFpGbYJhFgUgLd0W0iSCaoo1B0UZdVUQUkUKGCkH2GBojbcYZ597TYpx85G91uXC+e853rrA68bghkfDsHYhhoqdxWQcYMIuoe8lE/31QAdFSSbAGMIoBPF7OECq/AB7EgiqY0EU6Blt4zzV6kpaHPY4ifVXG8ACI7sBlHPn5PIvfHYupPPm0spQ9gYjycPxfB6sBAglPLB4AO0Et+XRA9oel8DNE6qPStq2Dp0vHIeFJql0HiAsAs6F6kAb8EhTyggcyOcEGjs7OKKl0FwDjyDoHE0VAOGjChMpxOU9l1CCqVG5yxA47mhpDfP/yoSRsLSDWLowB1rRSEKir9XSfEkwg1G4NiEQDUl8mKDePUBXAkVgvEQC7C6eezdWemhowJs3879v8/HYFzcY41/yraKy4ypUO6vYsm/UHkLChqkIJlzv8wgh923tXHlApFZckCrF4wPRc8WxtnMKfY7Q3v6OqMsDaKYYmIyS1smh+uVhViOsGE5RyZzbGg9xZhiZb1twn1RIfCVZ233Z9C8ZcwtgMkYUh3iQy/8FuTZ+ltqGFudlh+lpeA3D7cyvqOgICewSVTpQaFqPCnhsZKHwlsDmqNr1iYSGGCc6QmS8gwUFuzTxGxOJdIyJiwOzGloXB3wO6QOpQOYdzh0iln1FT3UrY1pPLjKNaQMx+kJOIHMXwwuC9Zyl7lfH+QVRGseFq8HcxZoaCn2L4/B2yuSf07biM6k0iFWWovkX1Od59WpmzO2mXv3TRbPtAL/sG69bI2yB/AR6y8SXyg7NRAAAAAElFTkSuQmCC",
    "kofi": "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAACSElEQVR42qWTT0tUcRSGn/O7d+6d8Ro6Uu3cZYlUqCAmQYkbK3KpVvYBWvQBohZJi7YFRos+gP9aCCVYG4M2LYxSMxEtCApaVOrkaHPv3Ps7LUZzdGrVWR7OX97nhfJQFVQN/wpVg6qUp9w9zSIKaONU2CqOnMPao6Uqs6xFfbYk8mZfLVKeaBpfr5Oa9AMc97JJO6DbwwVsIYEkHtFc4fpiX+3qTo9w+7aBQU60URO74TTVfnO8vmUBu+8B42erDJvhrER+17sZcjCI9I6r87hPksbJ/KiTDfqr8luRg3r6Z7uAMYCyFtrI1gSet7E5tnih+lLvuDoC0PY83/xN02/PZpPkXnPKEU8w2/8poEVFEHJF5cZ8lLz66ToHKbTMdFfPugChNT027eihVKRZz6P4Yhq+fC5dUF9PqrOLu+8j6nzDUEtKz7w2msvRA5QGqGgDisQqKJCfmMAuzJceP36S2s4uFnKWBOXaEZeMICHSAPBXzdMDA0gQIEFAMHAVVbjfkmK4w+fhhyLfI0hLGQeiuoKgKUcQlEz7Kfybt0oXtLcDyssfMPypwNx6QnU2pfGWruwOMDx1o+TOch75WoCMWEzHaQBsaPmlwqOPRebWLIczRmwhEcdJPQF2ZWyazI/a2qA/s7EV+a54aks6ijGEVtmMwRMbSW3gFVc3x5Yu7shYBpJ1w2k94DcX1/aCJIBrMKamyiQb4awbl4FUgXK2aggxV/ajnBQSNIlHpALlSjPROBW2Gtfp1iQ+tsdM5/0KM/G/dv4N4zQouRknkjEAAAAASUVORK5CYII=",
}
# Keep the destination's Pattern Mask and ID Mask Array: they describe that
# armor's own regions.  Pattern LUT (2) remains opt-in via the UI option.
ARMORLUT_CHANNELS = (9, 10)


class LUTSwapError(Exception):
    """A recoverable preflight or write error."""


def support_icon_value(name):
    if SUPPORT_ICONS is None or name not in SUPPORT_ICONS:
        return 0
    return SUPPORT_ICONS[name].icon_id


def armor_swap_support_is_visible(context):
    """Return true while the enabled Armor/Helmet swap add-on owns the support UI."""
    try:
        for addon in context.preferences.addons:
            module_name = str(getattr(addon, "module", "")).replace("-", "_").casefold()
            if "hd2_mass_id_swap" in module_name or "hd2_armor_multi_swap" in module_name:
                return True
    except (AttributeError, TypeError):
        pass

    # Fallback for legacy installs whose Preferences module ID is unusual.
    return hasattr(bpy.types, "HD2MS_PT_MainPanel")


def is_sdk_module(module):
    return module is not None and all(
        hasattr(module, attribute)
        for attribute in (
            "Global_TocManager",
            "MaterialID",
            "TexID",
            "UnitID",
            "StreamToc",
            "MemoryStream",
            "StingrayMaterial",
        )
    )


def get_sdk():
    """Find the active HD2SDK Community Edition module."""
    for module_name in ("HD2SDK", "HD2SDK-CommunityEdition"):
        module = sys.modules.get(module_name)
        if is_sdk_module(module):
            return module
        try:
            module = importlib.import_module(module_name)
        except (ImportError, ValueError):
            continue
        if is_sdk_module(module):
            return module

    try:
        import addon_utils
        for module in addon_utils.modules():
            if is_sdk_module(module):
                return module
            if getattr(module, "bl_info", {}).get("name") == "Helldivers 2 SDK: Community Edition":
                loaded = importlib.import_module(module.__name__)
                if is_sdk_module(loaded):
                    return loaded
    except (ImportError, AttributeError, ValueError):
        pass
    return None


def data_filename(mode):
    return "helmet_detailed.json" if mode == "HELMET" else "armor_detailed.json"


def mode_label(mode):
    return "Helmet" if mode == "HELMET" else "Armor"


def is_unknown_helmet(mode, name):
    return mode == "HELMET" and str(name).strip().casefold() == "unknown helmet"


def parse_hex_id(value, description):
    try:
        text = str(value).strip().lower()
        if text.startswith("0x"):
            text = text[2:]
        return int(text, 16)
    except (TypeError, ValueError) as error:
        raise LUTSwapError(f"Invalid {description}: {value!r}") from error


def load_dataset(mode):
    """Load and validate the bundled armor or helmet semantic map."""
    cached = DATA_CACHE.get(mode)
    if cached is not None:
        return cached

    path = os.path.join(os.path.dirname(__file__), data_filename(mode))
    try:
        with open(path, "r", encoding="utf-8") as data_file:
            raw = json.load(data_file)
    except (OSError, json.JSONDecodeError) as error:
        raise LUTSwapError(f"Could not read {os.path.basename(path)}: {error}") from error
    if not isinstance(raw, dict):
        raise LUTSwapError(f"{os.path.basename(path)} must contain armor classes.")

    entries = {}
    categories = {"light": [], "medium": [], "heavy": []}
    for armor_class, archives in raw.items():
        if not isinstance(archives, dict):
            continue
        normalized_class = str(armor_class).lower()
        for archive_id, archive in archives.items():
            archive_id = str(archive_id).lower()
            if not isinstance(archive, dict):
                continue
            if archive_id in entries:
                raise LUTSwapError(f"{data_filename(mode)} contains duplicate archive {archive_id}.")
            name = str(archive.get("name") or archive_id)
            entry = dict(archive)
            entry["_armor_class"] = normalized_class
            entries[archive_id] = entry
            if normalized_class in categories:
                categories[normalized_class].append((archive_id, name))

    for archives in categories.values():
        archives.sort(key=lambda item: (item[1].casefold(), item[0]))
    if not entries:
        raise LUTSwapError(f"No archive entries were found in {os.path.basename(path)}.")
    DATA_CACHE[mode] = (entries, categories)
    return DATA_CACHE[mode]


def flatten_archive_rows(archive):
    """Return each semantic Unit / LUT row from a detailed JSON archive record."""
    rows = []
    for body, slots in archive.items():
        if body in {"name", "_armor_class"} or not isinstance(slots, dict):
            continue
        for region, layers in slots.items():
            if not isinstance(layers, dict):
                continue
            for layer, values in layers.items():
                if not isinstance(values, list):
                    continue
                for ordinal, value in enumerate(values):
                    if not isinstance(value, dict):
                        continue
                    try:
                        unit_id = int(str(value.get("unit_id_dec", "")).strip())
                    except ValueError:
                        unit_id = parse_hex_id(value.get("unit_id_hex"), "Unit ID")
                    rows.append(
                        {
                            "key": (str(body).lower(), str(region).lower(), str(layer).lower(), ordinal),
                            "body": str(body).lower(),
                            "region": str(region).lower(),
                            "layer": str(layer).lower(),
                            "ordinal": ordinal,
                            "unit_id": unit_id,
                            "material_lut": parse_hex_id(value.get("material_lut", "0"), "material_lut"),
                            "pattern_lut": parse_hex_id(value.get("pattern_lut", "0"), "pattern_lut"),
                        }
                    )
    return rows


def source_props(mode):
    if mode == "HELMET":
        return "hd2_lut_helmet_source_id", "hd2_lut_helmet_source_name"
    return "hd2_lut_armor_source_id", "hd2_lut_armor_source_name"


def dds_source_props(mode):
    if mode == "HELMET":
        return "hd2_lut_helmet_source_kind", "hd2_lut_helmet_source_dds", "hd2_lut_helmet_source_dds_id"
    return "hd2_lut_armor_source_kind", "hd2_lut_armor_source_dds", "hd2_lut_armor_source_dds_id"


def is_dds_source(scene, mode):
    return getattr(scene, dds_source_props(mode)[0]) == "DDS"


def make_dds_texture_entry(sdk, source_slot):
    """Build one standard game-LUT Texture payload from a DDS or image file."""
    filepath = str(source_slot.dds_path).strip()
    if not filepath or not os.path.isfile(filepath):
        raise LUTSwapError("Choose a valid LUT texture file first.")
    try:
        texture = None
        if os.path.splitext(filepath)[1].lower() == ".dds":
            with open(filepath, "rb") as source_file:
                texture = sdk.StingrayTexture()
                texture.FromDDS(source_file.read())
                texture.ParseDDSHeader()
        # Armor LUT shaders expect the same layout used by the game's LUTs:
        # 23x8 half-float RGBA with a complete mip chain.  A DDS with another
        # format can be written into a patch but is ignored/falls back at run
        # time, so normalize it before serialization.
        if not (
            texture is not None and texture.Width == 23 and texture.Height == 8
            and texture.Format == "R16G16B16A16_FLOAT" and texture.NumMipMaps == 5
        ):
            texconv = str(getattr(sdk, "Global_texconvpath", ""))
            if not texconv or not os.path.isfile(texconv):
                raise LUTSwapError("HD2SDK texconv.exe is required to convert this LUT DDS.")
            with tempfile.TemporaryDirectory(prefix="hd2_lut_") as temp_dir:
                result = subprocess.run(
                    [texconv, "-y", "-dx10", "-f", "R16G16B16A16_FLOAT", "-m", "0", "-o", temp_dir, filepath],
                    capture_output=True, text=True, check=False,
                )
                base_name = os.path.splitext(os.path.basename(filepath))[0]
                converted = next(
                    (
                        os.path.join(temp_dir, name)
                        for name in os.listdir(temp_dir)
                        if os.path.isfile(os.path.join(temp_dir, name))
                        and os.path.splitext(name)[0].casefold() == base_name.casefold()
                        and os.path.splitext(name)[1].casefold() == ".dds"
                    ),
                    "",
                )
                if result.returncode or not os.path.isfile(converted):
                    raise LUTSwapError(f"Could not convert LUT DDS: {result.stderr or result.stdout}")
                with open(converted, "rb") as converted_file:
                    texture = sdk.StingrayTexture()
                    texture.FromDDS(converted_file.read())
                    texture.ParseDDSHeader()
        if not (
            texture.Width == 23 and texture.Height == 8
            and texture.Format == "R16G16B16A16_FLOAT" and texture.NumMipMaps == 5
        ):
            raise LUTSwapError(
                "A LUT texture must be 23 x 8 pixels. Resize the source image to 23 x 8 before importing."
            )
        toc = sdk.MemoryStream(IOMode="write")
        gpu = sdk.MemoryStream(IOMode="write")
        stream = sdk.MemoryStream(IOMode="write")
        texture.Serialize(toc, gpu, stream)
    except Exception as error:
        raise LUTSwapError(f"Could not import LUT texture: {error}") from error
    texture_id = int(str(source_slot.dds_id or "0") or "0")
    if not texture_id:
        texture_id = int(sdk.RandomHash16())
        source_slot.dds_id = str(texture_id)
    entry = sdk.TocEntry()
    entry.FileID = texture_id
    entry.TypeID = sdk.TexID
    entry.IsCreated = True
    entry.SetData(toc.Data, gpu.Data, stream.Data, True)
    return texture_id, entry, os.path.basename(filepath)


def destination_props(mode):
    if mode == "HELMET":
        return "hd2_lut_helmet_destinations", "hd2_lut_helmet_destination_index", "hd2_lut_helmet_destination_filter"
    return "hd2_lut_armor_destinations", "hd2_lut_armor_destination_index", "hd2_lut_armor_destination_filter"


def slot_props(mode):
    if mode == "HELMET":
        return "hd2_lut_helmet_source_slots", "hd2_lut_helmet_source_slot_index"
    return "hd2_lut_armor_source_slots", "hd2_lut_armor_source_slot_index"


def custom_slot_props(mode):
    if mode == "HELMET":
        return "hd2_lut_helmet_custom_slots", "hd2_lut_helmet_custom_slot_index"
    return "hd2_lut_armor_custom_slots", "hd2_lut_armor_custom_slot_index"


def custom_group_props(mode, body_mode):
    prefix = "helmet" if mode == "HELMET" else "armor"
    suffix = "overall_groups" if body_mode == "OVERALL" else "body_groups"
    return f"hd2_lut_{prefix}_custom_{suffix}"


def managed_props(mode):
    if mode == "HELMET":
        return "hd2_lut_helmet_generated_patch_path", "hd2_lut_helmet_generated_material_ids"
    return "hd2_lut_armor_generated_patch_path", "hd2_lut_armor_generated_material_ids"


def managed_texture_props(mode):
    if mode == "HELMET":
        return "hd2_lut_helmet_generated_patch_path", "hd2_lut_helmet_generated_texture_ids"
    return "hd2_lut_armor_generated_patch_path", "hd2_lut_armor_generated_texture_ids"


def active_mode(scene):
    return scene.hd2_lut_mode


def active_destinations(scene, mode=None):
    mode = mode or active_mode(scene)
    return getattr(scene, destination_props(mode)[0])


def active_source_slots(scene, mode=None):
    mode = mode or active_mode(scene)
    return getattr(scene, slot_props(mode)[0])


def active_custom_slots(scene, mode=None):
    mode = mode or active_mode(scene)
    return getattr(scene, custom_slot_props(mode)[0])


def active_custom_groups(scene, mode, body_mode=None):
    body_mode = body_mode or scene.hd2_lut_custom_body_mode
    return getattr(scene, custom_group_props(mode, body_mode))


def get_source_archive(scene, mode=None):
    mode = mode or active_mode(scene)
    id_prop, name_prop = source_props(mode)
    return str(getattr(scene, id_prop)).lower(), str(getattr(scene, name_prop))


def set_source_archive(scene, mode, archive_id, archive_name):
    id_prop, name_prop = source_props(mode)
    setattr(scene, id_prop, str(archive_id).lower())
    setattr(scene, name_prop, str(archive_name))


def source_slot_key(item):
    return (
        str(item.body).lower(),
        str(item.region).lower(),
        str(item.layer).lower(),
        int(item.ordinal),
    )


def custom_group_key(item):
    return str(item.body).lower(), str(item.region).lower()


def format_semantic_key(key):
    body, region, layer, ordinal = key
    suffix = "" if ordinal == 0 else f" #{ordinal + 1}"
    return f"{body} / {region} / {layer}{suffix}"


def clear_source_slots(scene, mode):
    active_source_slots(scene, mode).clear()
    setattr(scene, slot_props(mode)[1], 0)


def clear_slot_dds_id(source_slot, context):
    """A manually changed file path must receive a fresh generated Texture ID."""
    source_slot.dds_id = ""
    if context is not None:
        context.scene.hd2_lut_analysis = ""


def custom_slot_catalog(mode):
    """All semantic LUT slots that occur anywhere in the selected JSON map."""
    cached = CUSTOM_SLOT_CACHE.get(mode)
    if cached is not None:
        return cached
    details, _ = load_dataset(mode)
    union = set()
    maximum = 0
    for archive in details.values():
        keys = {row["key"] for row in flatten_archive_rows(archive) if row["material_lut"]}
        union.update(keys)
        maximum = max(maximum, len(keys))
    CUSTOM_SLOT_CACHE[mode] = (tuple(sorted(union)), maximum)
    return CUSTOM_SLOT_CACHE[mode]


def ensure_custom_slots(scene, mode):
    """Create the fixed custom-LUT preset list once, preserving chosen DDS files."""
    expected, _ = custom_slot_catalog(mode)
    slots = active_custom_slots(scene, mode)
    if {source_slot_key(item) for item in slots} == set(expected) and len(slots) == len(expected):
        return
    previous = {
        source_slot_key(item): (str(item.dds_path), str(item.dds_id), bool(item.enabled))
        for item in slots
    }
    slots.clear()
    for key in expected:
        item = slots.add()
        item.body, item.region, item.layer, item.ordinal = key
        item.label = format_semantic_key(key)
        item.enabled = True
        prior = previous.get(key)
        if prior:
            item.dds_path, item.dds_id, item.enabled = prior


def group_key_for_slot(key, body_mode):
    body, region, _, _ = key
    return ("overall", region) if body_mode == "OVERALL" else (body, region)


def format_custom_group_key(key):
    body, region = key
    if body == "overall":
        return f"{region.replace('_', ' ').title()}  (Overall)"
    return f"{body.replace('_', ' ').title()} / {region.replace('_', ' ').title()}"


def ensure_custom_groups(scene, mode, body_mode):
    """Create stable group controls while preserving the user's DDS choices."""
    keys, _ = custom_slot_catalog(mode)
    expected = tuple(sorted({group_key_for_slot(key, body_mode) for key in keys}))
    groups = active_custom_groups(scene, mode, body_mode)
    if {custom_group_key(item) for item in groups} == set(expected) and len(groups) == len(expected):
        return
    previous = {
        custom_group_key(item): (str(item.dds_path), str(item.dds_id), bool(item.enabled), bool(item.expanded))
        for item in groups
    }
    groups.clear()
    for key in expected:
        item = groups.add()
        item.body, item.region = key
        item.label = format_custom_group_key(key)
        item.enabled = True
        prior = previous.get(key)
        if prior:
            item.dds_path, item.dds_id, item.enabled, item.expanded = prior


def ensure_custom_presets(scene, mode):
    ensure_custom_slots(scene, mode)
    ensure_custom_groups(scene, mode, "OVERALL")
    ensure_custom_groups(scene, mode, "BODY")


def on_lut_mode_changed(scene, context):
    """Populate a new scene before the Custom LUT panel is drawn."""
    mode = str(scene.hd2_lut_mode)
    if is_dds_source(scene, mode):
        ensure_custom_presets(scene, mode)


def on_lut_source_kind_changed(scene, context):
    """The callback is shared by Armor and Helmet source-kind properties."""
    for mode in ("ARMOR", "HELMET"):
        if is_dds_source(scene, mode):
            ensure_custom_presets(scene, mode)


def initialize_custom_slots_after_register():
    """Run after Blender lifts its add-on registration data restriction."""
    for scene in bpy.data.scenes:
        ensure_custom_presets(scene, "ARMOR")
        ensure_custom_presets(scene, "HELMET")
    return None


def populate_source_slots(scene, mode):
    source_id, source_name = get_source_archive(scene, mode)
    clear_source_slots(scene, mode)
    if not source_id:
        return
    details, _ = load_dataset(mode)
    archive = details.get(source_id)
    if archive is None:
        raise LUTSwapError(f"Source archive {source_name or source_id} is absent from {data_filename(mode)}.")

    slots = active_source_slots(scene, mode)
    for row in flatten_archive_rows(archive):
        if row["material_lut"] == 0:
            continue
        item = slots.add()
        item.body = row["body"]
        item.region = row["region"]
        item.layer = row["layer"]
        item.ordinal = row["ordinal"]
        item.unit_id = str(row["unit_id"])
        item.material_lut = f"{row['material_lut']:016x}"
        item.pattern_lut = f"{row['pattern_lut']:016x}"
        item.label = f"{format_semantic_key(row['key'])}  -  {item.material_lut}"
        item.enabled = True


def contains_destination(items, archive_id):
    wanted = str(archive_id).lower()
    return any(str(item.archive_id).lower() == wanted for item in items)


def archive_read_path(sdk, archive_id):
    """Resolve a package path without filling HD2SDK's visible archive list."""
    archive_id = str(archive_id).lower()
    for archive in getattr(sdk.Global_TocManager, "SearchArchives", []):
        if str(getattr(archive, "Name", "")).lower() == archive_id:
            return str(archive.Path)
    game_path = str(getattr(sdk, "Global_gamepath", "") or "")
    if not game_path:
        raise LUTSwapError("HD2SDK has no valid Helldivers 2 data folder.")
    return os.path.join(game_path, archive_id)


def hydrate_toc_data(archive, entry):
    """Hydrate one private TOC payload, never Unit GPU or stream data."""
    expected_size = int(getattr(entry, "TocDataSize", 0))
    if expected_size == len(getattr(entry, "TocData", b"")) and expected_size:
        return entry
    start = int(getattr(entry, "TocDataOffset", 0))
    end = start + expected_size
    data = archive.TocFile.Data
    if expected_size <= 0 or start < 0 or end > len(data):
        raise LUTSwapError(f"Could not read TOC bytes for resource {entry.FileID}.")
    entry.TocData = bytearray(data[start:end])
    # Unit entries naturally own GPU/stream payloads, but this tool only reads
    # their Material ID table from TocData.  Materials used by armor LUTs have
    # no such payload in the current game data.
    entry.GpuData = bytearray()
    entry.StreamData = bytearray()
    return entry


def get_private_archive(sdk, archive_id):
    """Read only a package TOC; selected armor archives stay out of HD2SDK UI."""
    path = archive_read_path(sdk, archive_id)
    cache_key = os.path.normcase(os.path.abspath(path))
    cached = PRIVATE_ARCHIVES.get(cache_key)
    if cached is not None:
        return cached

    archive = sdk.StreamToc()
    try:
        is_slim = bool(hasattr(sdk, "is_slim_version") and sdk.is_slim_version())
        if is_slim and hasattr(sdk, "get_package_toc"):
            # get_package_toc intentionally stops after the entry table.  We
            # need the small Unit and Material TOC payloads too, but never
            # their GPU/stream companion packages.  The slim module can
            # reconstruct just this one main package without touching SDK UI.
            slim_module = getattr(sdk, "slim_m", None)
            if slim_module is not None and hasattr(slim_module, "reconstruct_package_from_bundles"):
                toc_data = slim_module.reconstruct_package_from_bundles(path)
            else:
                toc_data = sdk.get_package_toc(path)
            if not toc_data:
                raise LUTSwapError(f"Archive file was not found: {archive_id}")
            archive.UpdatePath(path)
            archive.TocFile = sdk.MemoryStream(toc_data)
            archive.GpuFile = sdk.MemoryStream()
            archive.StreamFile = sdk.MemoryStream()
            if not archive.Serialize(SerializeData=False):
                raise LUTSwapError(f"Could not parse archive TOC: {archive_id}")
        elif not archive.FromFile(path, SerializeData=False):
            raise LUTSwapError(f"Could not parse archive TOC: {archive_id}")
    except LUTSwapError:
        raise
    except Exception as error:
        raise LUTSwapError(f"Could not read archive {archive_id}: {error}") from error

    PRIVATE_ARCHIVES[cache_key] = archive
    return archive


def get_private_entry(archive, type_id, file_id):
    entry = archive.TocDict.get(int(type_id), {}).get(int(file_id))
    return hydrate_toc_data(archive, entry) if entry is not None else None


def hydrate_resource_payload(sdk, archive, entry):
    """Read one complete resource without making its archive visible in HD2SDK."""
    if entry is None:
        return None
    cache_key = os.path.normcase(os.path.abspath(str(archive.Path)))
    payloads = PRIVATE_PAYLOADS.get(cache_key)
    if payloads is None:
        payloads = sdk.load_package(str(archive.Path))
        PRIVATE_PAYLOADS[cache_key] = payloads
    toc_data, gpu_data, stream_data = payloads

    def slice_payload(data, offset, size, label):
        if not size:
            return bytearray()
        end = int(offset) + int(size)
        if int(offset) < 0 or end > len(data):
            raise LUTSwapError(f"Could not read {label} payload for resource {entry.FileID}.")
        return bytearray(data[int(offset):end])

    entry.TocData = slice_payload(toc_data, entry.TocDataOffset, entry.TocDataSize, "TOC")
    entry.GpuData = slice_payload(gpu_data, entry.GpuResourceOffset, entry.GpuResourceSize, "GPU")
    entry.StreamData = slice_payload(stream_data, entry.StreamOffset, entry.StreamSize, "stream")
    return entry


def find_private_resource(sdk, file_id, type_id, preferred_archive=None):
    """Find a resource through HD2SDK's index without loading it into the SDK UI."""
    candidates = []
    if preferred_archive is not None:
        candidates.append(preferred_archive)
    for search_archive in getattr(sdk.Global_TocManager, "SearchArchives", []):
        if search_archive.HasEntry(file_id, type_id):
            candidates.append(get_private_archive(sdk, search_archive.Name))
    seen = set()
    for archive in candidates:
        path = os.path.normcase(os.path.abspath(str(archive.Path)))
        if path in seen:
            continue
        seen.add(path)
        entry = archive.TocDict.get(int(type_id), {}).get(int(file_id))
        if entry is not None:
            return archive, hydrate_resource_payload(sdk, archive, entry)
    return None, None


def read_unit_material_ids(sdk, archive, unit_id):
    """Read Unit.MaterialIDs directly from TOC bytes, without importing its mesh."""
    entry = get_private_entry(archive, sdk.UnitID, unit_id)
    if entry is None:
        raise LUTSwapError(f"Unit {unit_id} was not found in archive {archive.Name}.")
    data = entry.TocData
    # Current Unit layout: uint32 MaterialsOffset at byte 112, then a count,
    # section IDs, and uint64 Material IDs.
    if len(data) < 116:
        raise LUTSwapError(f"Unit {unit_id} has no readable material table.")
    offset = struct.unpack_from("<I", data, 112)[0]
    if offset <= 0 or offset + 4 > len(data):
        raise LUTSwapError(f"Unit {unit_id} has an invalid material table offset.")
    count = struct.unpack_from("<I", data, offset)[0]
    ids_offset = offset + 4 + count * 4
    end = ids_offset + count * 8
    if count > 256 or end > len(data):
        raise LUTSwapError(f"Unit {unit_id} has an invalid material ID list.")
    return list(struct.unpack_from(f"<{count}Q", data, ids_offset)) if count else []


def parse_material(sdk, entry):
    if not getattr(entry, "TocData", None):
        raise LUTSwapError(f"Material {entry.FileID} has no readable TOC data.")
    material = sdk.StingrayMaterial()
    try:
        material.Serialize(sdk.MemoryStream(entry.TocData))
    except Exception as error:
        raise LUTSwapError(f"Could not parse Material {entry.FileID}: {error}") from error
    return material


def serialize_material(sdk, material, material_id):
    stream = sdk.MemoryStream(IOMode="write")
    try:
        material.Serialize(stream)
    except Exception as error:
        raise LUTSwapError(f"Could not serialize Material {material_id}: {error}") from error
    return stream.Data


def material_lut_indices(sdk, archive, material_id, expected_lut):
    entry = get_private_entry(archive, sdk.MaterialID, material_id)
    if entry is None:
        raise LUTSwapError(f"Material {material_id} was not found in archive {archive.Name}.")
    material = parse_material(sdk, entry)
    indices = [index for index, texture_id in enumerate(material.TexIDs) if int(texture_id) == int(expected_lut)]
    return entry, indices


def current_patch_material(sdk, material_id):
    patch = getattr(sdk.Global_TocManager, "ActivePatch", None)
    if patch is None:
        return None
    return patch.TocDict.get(int(sdk.MaterialID), {}).get(int(material_id))


def current_patch_texture(sdk, texture_id):
    patch = getattr(sdk.Global_TocManager, "ActivePatch", None)
    if patch is None:
        return None
    return patch.TocDict.get(int(sdk.TexID), {}).get(int(texture_id))


def derive_source_lut_id(sdk, source_archive, source_item):
    """Use a patched source Material's current LUT when one exists."""
    baseline_lut = parse_hex_id(source_item.material_lut, "source material_lut")
    candidates = []
    for material_id in read_unit_material_ids(sdk, source_archive, int(source_item.unit_id)):
        try:
            entry, indices = material_lut_indices(sdk, source_archive, material_id, baseline_lut)
        except LUTSwapError:
            # A Unit can also reference shared Materials stored in another
            # package.  They are irrelevant unless they contain this exact
            # source LUT, so the JSON baseline remains the safe fallback.
            continue
        if not indices:
            continue
        patched_entry = current_patch_material(sdk, material_id)
        material = parse_material(sdk, patched_entry if patched_entry is not None else entry)
        candidates.extend(int(material.TexIDs[index]) for index in indices)
    if not candidates:
        return baseline_lut
    if len(set(candidates)) != 1:
        raise LUTSwapError(
            f"Source slot {source_item.label} resolves to multiple current LUT IDs. Select a more specific slot."
        )
    return candidates[0]


def derive_source_lut_channels(sdk, source_archive, source_item):
    """Read the complete LUT-material binding set from one semantic source slot."""
    baseline_lut = parse_hex_id(source_item.material_lut, "source material_lut")
    candidates = []
    for material_id in read_unit_material_ids(sdk, source_archive, int(source_item.unit_id)):
        try:
            entry, indices = material_lut_indices(sdk, source_archive, material_id, baseline_lut)
        except LUTSwapError:
            continue
        if not indices:
            continue
        material = parse_material(sdk, entry)
        # The paired LUT bindings must follow the source.  Zero is meaningful
        # and must be copied, not treated as absent.
        if len(material.TexIDs) > 10 and indices[0] == 10:
            candidates.append(tuple(int(material.TexIDs[index]) for index in ARMORLUT_CHANNELS))
    if not candidates:
        return None
    if len(set(candidates)) != 1:
        raise LUTSwapError(
            f"Source slot {source_item.label} resolves to multiple LUT-material bindings. "
            "Select a more specific slot."
        )
    return dict(zip(ARMORLUT_CHANNELS, candidates[0]))


def selected_source_items(scene, mode):
    return [item for item in active_source_slots(scene, mode) if item.enabled]


def source_lut_groups(scene, mode):
    """Group semantic rows by the actual source Primary LUT ID for the UI."""
    groups = {}
    for item in active_source_slots(scene, mode):
        groups.setdefault(str(item.material_lut).lower(), []).append(item)
    return sorted(groups.items(), key=lambda item: item[0])


def source_group_summary(items):
    semantics = []
    for item in items:
        text = f"{item.body}/{item.region}/{item.layer}"
        if text not in semantics:
            semantics.append(text)
    preview = ", ".join(semantics[:3])
    if len(semantics) > 3:
        preview += f" +{len(semantics) - 3}"
    return preview


def resolve_source_slot(source_items, target_key):
    """Only a matching semantic slot may replace a destination LUT."""
    exact = {source_slot_key(item): item for item in source_items}
    return exact.get(target_key)


def add_texture_override(overrides, conflicts, target_lut, source_lut, origin):
    """Map one existing game LUT ID to one source payload deterministically."""
    key = int(target_lut)
    existing = overrides.get(key)
    if existing is None:
        overrides[key] = {"source_lut": int(source_lut), "origins": [origin]}
        return
    existing["origins"].append(origin)
    if existing["source_lut"] != int(source_lut):
        conflicts.append((key, existing["source_lut"], int(source_lut), origin))


def build_custom_slot_sources(sdk, scene, mode):
    """Resolve child DDS overrides first, then their expanded/collapsed group DDS."""
    ensure_custom_presets(scene, mode)
    body_mode = scene.hd2_lut_custom_body_mode
    groups = active_custom_groups(scene, mode, body_mode)
    group_by_key = {custom_group_key(item): (index, item) for index, item in enumerate(groups)}
    sources = {}
    texture_entries = {}
    source_labels = {}
    loaded_owners = {}

    def load_owner(owner_key, owner):
        loaded = loaded_owners.get(owner_key)
        if loaded is None:
            texture_id, entry, filename = make_dds_texture_entry(sdk, owner)
            loaded = texture_id, entry, filename
            loaded_owners[owner_key] = loaded
            texture_entries[texture_id] = entry
        return loaded

    for slot_index, slot in enumerate(active_custom_slots(scene, mode)):
        if not slot.enabled:
            continue
        slot_key = source_slot_key(slot)
        if str(slot.dds_path).strip():
            texture_id, _, filename = load_owner(("slot", slot_index), slot)
        else:
            group_index, group = group_by_key[group_key_for_slot(slot_key, body_mode)]
            if not group.enabled or not str(group.dds_path).strip():
                continue
            texture_id, _, filename = load_owner(("group", group_index), group)
        sources[slot_key] = texture_id
        source_labels[slot_key] = filename
    return sources, texture_entries, source_labels


def build_mapping_plan(sdk, scene, mode):
    source_id, source_name = get_source_archive(scene, mode)
    dds_mode = is_dds_source(scene, mode)
    if not dds_mode and not source_id:
        raise LUTSwapError(f"Choose a {mode_label(mode)} preset first.")
    destinations = list(active_destinations(scene, mode))
    if not destinations:
        raise LUTSwapError(f"Add at least one destination {mode_label(mode)} archive.")
    if dds_mode:
        resolved_sources, source_texture_entries, custom_source_labels = build_custom_slot_sources(
            sdk, scene, mode
        )
        if not resolved_sources:
            raise LUTSwapError("Import a custom LUT DDS into at least one slot.")
        source_name = "Custom LUTs per slot"
    else:
        source_items = selected_source_items(scene, mode)
    if not dds_mode and not source_items:
        raise LUTSwapError("Select at least one source LUT slot.")

    details, _ = load_dataset(mode)
    if not dds_mode and source_id not in details:
        raise LUTSwapError(f"Source archive {source_name or source_id} is absent from {data_filename(mode)}.")
    if not dds_mode:
        source_texture_entries = {}
        source_archive = get_private_archive(sdk, source_id)
        # The detailed JSON already contains the concrete global Texture IDs.
        # Resolving them through Unit -> Material made the old implementation
        # slow and, more importantly, led it to patch Material references.  LUT
        # ID swap only needs these source Texture IDs and their payloads.
        resolved_sources = {
            source_slot_key(item): parse_hex_id(item.material_lut, "source material_lut")
            for item in source_items
        }

    overrides = {}
    conflicts = []
    unmatched = []
    destination_rows = 0
    skipped_zero = 0
    matched_source_keys = set()

    for destination in destinations:
        archive_id = str(destination.archive_id).lower()
        archive_info = details.get(archive_id)
        if archive_info is None:
            raise LUTSwapError(
                f"Destination archive {destination.name or archive_id} is absent from {data_filename(mode)}."
            )
        for target in flatten_archive_rows(archive_info):
            target_lut = target["material_lut"]
            if target_lut == 0:
                skipped_zero += 1
                continue
            if dds_mode:
                source_lut = resolved_sources.get(target["key"])
                source_item = None
                if source_lut is None:
                    continue
                matched_source_keys.add(target["key"])
            else:
                source_item = resolve_source_slot(source_items, target["key"])
                if source_item is None:
                    unmatched.append((destination.name or archive_id, target["key"]))
                    continue
                matched_source_keys.add(source_slot_key(source_item))
                source_lut = resolved_sources[source_slot_key(source_item)]
            if source_lut == 0:
                continue

            origin = (
                destination.name or archive_id,
                format_semantic_key(target["key"]),
                custom_source_labels[target["key"]] if dds_mode else source_item.label,
            )
            add_texture_override(overrides, conflicts, target_lut, source_lut, origin)
            destination_rows += 1

    if dds_mode:
        # Imported custom slots that do not exist on any selected destination
        # produce no entry by design; they do not borrow another slot.
        unmatched = [
            ("destination list", key)
            for key in resolved_sources
            if key not in matched_source_keys
        ]

    if conflicts and not scene.hd2_lut_allow_shared_ids:
        _, first_source, second_source, origin = conflicts[0]
        raise LUTSwapError(
            "A shared destination LUT Texture ID is requested with different source payloads "
            f"({first_source:016x} vs {second_source:016x}) at {origin[0]} / {origin[1]}. "
            "Deselect one source slot or enable Allow shared LUT IDs."
        )
    # JSON traversal is deterministic.  When explicitly allowed, retain the
    # first source requested for a globally shared destination Texture ID.
    if conflicts:
        for key, first_source, _, _ in conflicts:
            overrides[key]["source_lut"] = first_source

    # Resolve each unique source payload once.  apply_plan clones it under all
    # destination LUT IDs; the content-addressed writer stores equal payloads
    # at the same TOC/GPU/stream offsets.
    for texture_id in sorted({change["source_lut"] for change in overrides.values() if change["source_lut"]}):
        if texture_id in source_texture_entries:
            continue
        _, texture_entry = find_private_resource(sdk, texture_id, sdk.TexID, source_archive)
        if texture_entry is not None:
            source_texture_entries[texture_id] = clone_resource_entry(texture_entry)
            continue
        # A custom source texture may exist only in the active patch.
        patch_entry = current_patch_texture(sdk, texture_id)
        if patch_entry is None:
            raise LUTSwapError(
                f"Could not locate LUT Texture {texture_id:016x} in the game archives."
            )
        source_texture_entries[texture_id] = clone_resource_entry(patch_entry)

    return {
        "mode": mode,
        "source_name": source_name or source_id,
        "source_id": source_id,
        "destination_count": len(destinations),
        "overrides": overrides,
        "source_texture_entries": source_texture_entries,
        "unmatched": unmatched,
        "conflict_count": len(conflicts),
        "destination_rows": destination_rows,
        "skipped_zero": skipped_zero,
        "source_lut_count": len({change["source_lut"] for change in overrides.values() if change["source_lut"]}),
    }


def format_plan(plan):
    message = (
        f"READY - {plan['source_name']} to {plan['destination_count']} destination archive(s): "
        f"{len(plan['overrides'])} destination LUT Texture ID override(s), "
        f"{plan['source_lut_count']} unique source payload(s)."
    )
    if plan["unmatched"]:
        message += f" {len(plan['unmatched'])} imported slot(s) are absent from the destinations and were ignored."
    if plan["conflict_count"]:
        message += f" {plan['conflict_count']} shared-Texture conflict(s): first mapping kept."
    return message


def clone_resource_entry(entry):
    """Copy a resource byte-for-byte; never call the SDK save path."""
    clone = copy.copy(entry)
    clone.TocData = bytearray(entry.TocData)
    clone.GpuData = bytearray(getattr(entry, "GpuData", b""))
    clone.StreamData = bytearray(getattr(entry, "StreamData", b""))
    clone.TocData_OLD = bytearray()
    clone.GpuData_OLD = bytearray()
    clone.StreamData_OLD = bytearray()
    clone.LoadedData = None
    clone.IsLoaded = False
    clone.IsSelected = False
    clone.IsModified = True
    return clone


def clone_material_entry(entry):
    return clone_resource_entry(entry)


def parse_id_csv(value):
    return {int(part) for part in str(value or "").split(",") if part.isdigit()}


def remove_previous_managed_materials(scene, patch, mode, material_type_id):
    """Undo only Material entries generated by this mode in this Blender scene."""
    path_prop, ids_prop = managed_props(mode)
    if str(getattr(scene, path_prop)) != str(patch.Path):
        return 0
    materials = patch.TocDict.get(int(material_type_id), {})
    removed = 0
    for material_id in parse_id_csv(getattr(scene, ids_prop)):
        if materials.pop(material_id, None) is not None:
            removed += 1
    if removed:
        patch.UpdateTypes()
    return removed


def remember_managed_materials(scene, patch, mode, material_ids):
    path_prop, ids_prop = managed_props(mode)
    setattr(scene, path_prop, str(patch.Path))
    setattr(scene, ids_prop, ",".join(str(value) for value in sorted(material_ids)))


def remove_previous_managed_textures(scene, patch, mode, texture_type_id):
    """Remove stale LUT aliases from this mode when the destination list shrinks."""
    path_prop, ids_prop = managed_texture_props(mode)
    if str(getattr(scene, path_prop)) != str(patch.Path):
        return 0
    textures = patch.TocDict.get(int(texture_type_id), {})
    removed = 0
    for texture_id in parse_id_csv(getattr(scene, ids_prop)):
        if textures.pop(texture_id, None) is not None:
            removed += 1
    if removed:
        patch.UpdateTypes()
    return removed


def remember_managed_textures(scene, patch, mode, texture_ids):
    path_prop, ids_prop = managed_texture_props(mode)
    setattr(scene, path_prop, str(patch.Path))
    setattr(scene, ids_prop, ",".join(str(value) for value in sorted(texture_ids)))


def remove_legacy_dds_redirects(sdk, scene, patch, plan):
    """Remove <= 1.0.8 DDS redirects even when the .blend tracking state was lost."""
    if not is_dds_source(scene, plan["mode"]):
        return 0, 0
    if len(plan["source_texture_entries"]) != 1:
        return 0, 0

    source_entry = next(iter(plan["source_texture_entries"].values()))
    source_payload = (source_entry.TocData, source_entry.GpuData, source_entry.StreamData)
    target_ids = {int(value) for value in plan["overrides"]}
    textures = patch.TocDict.get(int(sdk.TexID), {})
    legacy_texture_ids = {
        int(texture_id)
        for texture_id, entry in textures.items()
        if int(texture_id) not in target_ids
        and payloads_equal(
            (entry.TocData, entry.GpuData, entry.StreamData), source_payload
        )
    }
    if not legacy_texture_ids:
        return 0, 0

    materials = patch.TocDict.get(int(sdk.MaterialID), {})
    legacy_material_ids = set()
    for material_id, entry in materials.items():
        try:
            material = parse_material(sdk, entry)
        except LUTSwapError:
            continue
        if legacy_texture_ids.intersection(int(value) for value in material.TexIDs):
            legacy_material_ids.add(int(material_id))

    for material_id in legacy_material_ids:
        materials.pop(material_id, None)
    for texture_id in legacy_texture_ids:
        textures.pop(texture_id, None)
    if legacy_material_ids or legacy_texture_ids:
        patch.UpdateTypes()
    return len(legacy_material_ids), len(legacy_texture_ids)


def ensure_active_patch(sdk):
    manager = sdk.Global_TocManager
    if manager.ActivePatch is not None:
        return manager.ActivePatch
    if manager.ActiveArchive is None:
        base_path = os.path.join(str(sdk.Global_gamepath), str(sdk.BaseArchiveHexID))
        manager.LoadArchive(base_path, SetActive=True)
    manager.CreatePatchFromActive("LUT Texture Swap")
    return manager.ActivePatch


def coalesce_loaded_patch_payloads(patch):
    """
    A previously written deduplicated patch is read by HD2SDK into separate
    bytearrays for each alias.  Entries with equal on-disk ranges are known to
    share immutable payloads, so make them share one buffer again before the
    content-addressed writer hashes the patch.
    """
    toc_file = getattr(patch, "TocFile", None)
    if toc_file is None or not toc_file.IsReading():
        return 0
    loaded_entry_objects = {id(entry) for entry in getattr(patch, "TocEntries", ())}
    canonical = {}
    merged = 0
    for entries in patch.TocDict.values():
        for entry in entries.values():
            if id(entry) not in loaded_entry_objects or getattr(entry, "IsModified", False):
                continue
            key = (
                int(entry.TocDataOffset),
                len(entry.TocData),
                int(entry.GpuResourceOffset),
                len(entry.GpuData),
                int(entry.StreamOffset),
                len(entry.StreamData),
            )
            original = canonical.get(key)
            if original is None:
                canonical[key] = entry
                continue
            entry.TocData = original.TocData
            entry.GpuData = original.GpuData
            entry.StreamData = original.StreamData
            entry.TocData_OLD = original.TocData_OLD
            entry.GpuData_OLD = original.GpuData_OLD
            entry.StreamData_OLD = original.StreamData_OLD
            merged += 1
    return merged


def payload_digest(entry, cache):
    payload = (
        entry.TocData if entry.TocData is not None else b"",
        entry.GpuData if entry.GpuData is not None else b"",
        entry.StreamData if entry.StreamData is not None else b"",
    )
    identity = tuple((id(data), len(data)) for data in payload)
    cached = cache.get(identity)
    if cached is not None:
        return cached
    digest = hashlib.sha256()
    for data in payload:
        digest.update(len(data).to_bytes(8, "little"))
        digest.update(data)
    result = (digest.digest(), payload)
    cache[identity] = result
    return result


def payloads_equal(left, right):
    return all(
        left_data is right_data or (len(left_data) == len(right_data) and left_data == right_data)
        for left_data, right_data in zip(left, right)
    )


def validate_patch_offsets(patch):
    toc_size = len(patch.TocFile.Data)
    gpu_size = len(patch.GpuFile.Data)
    stream_size = len(patch.StreamFile.Data)
    for entries in patch.TocDict.values():
        for entry in entries.values():
            if int(entry.TocDataOffset) + len(entry.TocData) > toc_size:
                raise LUTSwapError(f"TOC payload for resource {entry.FileID} is out of bounds.")
            if int(entry.GpuResourceOffset) + len(entry.GpuData) > gpu_size:
                raise LUTSwapError(f"GPU payload for resource {entry.FileID} is out of bounds.")
            if int(entry.StreamOffset) + len(entry.StreamData) > stream_size:
                raise LUTSwapError(f"Stream payload for resource {entry.FileID} is out of bounds.")
            if entry.GpuData and int(entry.GpuResourceOffset) % 64:
                raise LUTSwapError(f"GPU payload for resource {entry.FileID} is not 64-byte aligned.")
            if entry.StreamData and int(entry.StreamOffset) % 64:
                raise LUTSwapError(f"Stream payload for resource {entry.FileID} is not 64-byte aligned.")


def atomic_write(path, data):
    temporary_path = path + ".hd2lut.tmp"
    try:
        with open(temporary_path, "w+b") as output:
            output.write(data)
        os.replace(temporary_path, path)
    except Exception:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
        raise


def write_deduplicated_patch(patch, sdk):
    """
    Preserve pre-existing aliases and store equal Unit/Texture payloads once.
    HD2SDK's ordinary writer emits every alias payload again.
    """
    patch.TocFile = sdk.MemoryStream(IOMode="write")
    patch.GpuFile = sdk.MemoryStream(IOMode="write")
    patch.StreamFile = sdk.MemoryStream(IOMode="write")
    patch.Serialize(SerializeData=False)

    canonical_entries = {}
    digest_cache = {}
    unique_payloads = 0
    for entries in patch.TocDict.values():
        for entry in entries.values():
            digest, payload = payload_digest(entry, digest_cache)
            bucket = canonical_entries.setdefault(digest, [])
            canonical = next(
                (
                    candidate
                    for candidate, candidate_payload in bucket
                    if payloads_equal(candidate_payload, payload)
                ),
                None,
            )
            if canonical is None:
                entry.SerializeData(patch.TocFile, patch.GpuFile, patch.StreamFile)
                bucket.append((entry, payload))
                unique_payloads += 1
            else:
                entry.TocDataOffset = canonical.TocDataOffset
                entry.GpuResourceOffset = canonical.GpuResourceOffset
                entry.StreamOffset = canonical.StreamOffset

    toc_entry_start = 72 + len(patch.TocTypes) * 32
    patch.TocFile.seek(toc_entry_start)
    index = 1
    for toc_type in patch.TocTypes:
        for entry in patch.TocDict[toc_type.TypeID].values():
            entry.Serialize(patch.TocFile, index)
            index += 1

    entry_count = sum(len(entries) for entries in patch.TocDict.values())
    minimum_toc_size = 256 * entry_count
    if len(patch.TocFile.Data) < minimum_toc_size:
        patch.TocFile.Data.extend(bytearray(minimum_toc_size - len(patch.TocFile.Data)))
    validate_patch_offsets(patch)
    atomic_write(patch.Path, patch.TocFile.Data)
    atomic_write(patch.Path + ".gpu_resources", patch.GpuFile.Data)
    atomic_write(patch.Path + ".stream", patch.StreamFile.Data)
    return unique_payloads


def apply_plan(sdk, scene, plan):
    """Alias source Texture payloads under the LUT IDs used by vanilla Materials."""
    patch = ensure_active_patch(sdk)
    coalesce_loaded_patch_payloads(patch)
    detected_materials, detected_textures = remove_legacy_dds_redirects(
        sdk, scene, patch, plan
    )
    # Migration from <= 1.0.8: remove only the Material entries recorded by
    # this Blender scene.  Materials are no longer part of the LUT patch.
    tracked_materials = remove_previous_managed_materials(
        scene, patch, plan["mode"], sdk.MaterialID
    )
    removed_legacy_materials = detected_materials + tracked_materials
    remove_previous_managed_textures(scene, patch, plan["mode"], sdk.TexID)

    target_texture_ids = set()
    for target_lut, change in sorted(plan["overrides"].items()):
        source_lut = int(change["source_lut"])
        source_entry = plan["source_texture_entries"][source_lut]
        replacement = clone_resource_entry(source_entry)
        replacement.FileID = int(target_lut)
        replacement.TypeID = int(sdk.TexID)
        replacement.IsCreated = True
        patch.AddEntry(replacement, override=True, ReloadUI=False)
        target_texture_ids.add(int(target_lut))

    # Remove the one explicitly tracked by <= 1.0.8 as a final fallback.  The
    # payload-signature migration above also works after Blender was restarted.
    _, _, legacy_dds_id_prop = dds_source_props(plan["mode"])
    legacy_dds_text = str(getattr(scene, legacy_dds_id_prop) or "")
    if legacy_dds_text.isdigit():
        legacy_dds_id = int(legacy_dds_text)
        if legacy_dds_id not in target_texture_ids:
            patch.TocDict.get(int(sdk.TexID), {}).pop(legacy_dds_id, None)

    patch.UpdateTypes()
    payloads = write_deduplicated_patch(patch, sdk)
    remember_managed_materials(scene, patch, plan["mode"], set())
    remember_managed_textures(scene, patch, plan["mode"], target_texture_ids)
    # Match the working Armor/Helmet ID Swap addon's post-write flow.
    if hasattr(sdk, "LoadEntryLists"):
        sdk.LoadEntryLists()
    return (
        patch, payloads, target_texture_ids,
        removed_legacy_materials, detected_textures,
    )


class HD2LUT_SourceSlotItem(PropertyGroup):
    body: StringProperty()
    region: StringProperty()
    layer: StringProperty()
    ordinal: IntProperty()
    unit_id: StringProperty()
    material_lut: StringProperty()
    pattern_lut: StringProperty()
    label: StringProperty()
    enabled: BoolProperty(default=True)
    dds_path: StringProperty(default="", update=clear_slot_dds_id)
    dds_id: StringProperty(default="")


class HD2LUT_CustomGroupItem(PropertyGroup):
    body: StringProperty()
    region: StringProperty()
    label: StringProperty()
    enabled: BoolProperty(default=True)
    expanded: BoolProperty(default=False)
    dds_path: StringProperty(default="", update=clear_slot_dds_id)
    dds_id: StringProperty(default="")


class HD2LUT_ArchiveItem(PropertyGroup):
    archive_id: StringProperty()
    name: StringProperty()


class HD2LUT_UL_SourceSlots(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.label, icon='IMAGE_DATA')


class HD2LUT_UL_Destinations(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.name, icon='FILE_FOLDER')
        remove = row.operator("hd2_lut.remove_destination", text="", icon='X')
        remove.index = index

    def filter_items(self, context, data, propname):
        mode = active_mode(context.scene)
        query = str(getattr(context.scene, destination_props(mode)[2])).strip().casefold()
        if not query:
            return [], []
        items = getattr(data, propname)
        flags = [
            self.bitflag_filter_item
            if query in f"{item.name} {item.archive_id}".casefold()
            else 0
            for item in items
        ]
        return flags, []


class HD2LUT_OT_SetSourceArchive(Operator):
    bl_idname = "hd2_lut.set_source_archive"
    bl_label = "Use Source LUT Archive"
    bl_description = "Use this archive as the semantic LUT source"

    archive_id: StringProperty(options={'HIDDEN'})
    archive_name: StringProperty(options={'HIDDEN'})
    mode: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        mode = self.mode or active_mode(context.scene)
        if is_unknown_helmet(mode, self.archive_name):
            self.report({'INFO'}, "Unknown Helmet entries are excluded from Helmet mode")
            return {'CANCELLED'}
        try:
            set_source_archive(context.scene, mode, self.archive_id, self.archive_name)
            populate_source_slots(context.scene, mode)
        except LUTSwapError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        context.scene.hd2_lut_analysis = ""
        self.report({'INFO'}, f"Selected source: {self.archive_name}")
        return {'FINISHED'}


class HD2LUT_OT_ClearSource(Operator):
    bl_idname = "hd2_lut.clear_source"
    bl_label = "Clear Source LUT Archive"

    def execute(self, context):
        mode = active_mode(context.scene)
        set_source_archive(context.scene, mode, "", "")
        clear_source_slots(context.scene, mode)
        context.scene.hd2_lut_analysis = ""
        return {'FINISHED'}


class HD2LUT_OT_SetAllSourceSlots(Operator):
    bl_idname = "hd2_lut.set_all_source_slots"
    bl_label = "Select Source LUT Slots"

    enabled: BoolProperty(default=True, options={'HIDDEN'})

    def execute(self, context):
        for item in active_source_slots(context.scene):
            item.enabled = self.enabled
        context.scene.hd2_lut_analysis = ""
        return {'FINISHED'}


class HD2LUT_OT_SetSourceGroup(Operator):
    bl_idname = "hd2_lut.set_source_group"
    bl_label = "Toggle Source LUT Group"
    bl_description = "Enable or disable every semantic slot using this source LUT"

    material_lut: StringProperty(options={'HIDDEN'})
    enabled: BoolProperty(default=True, options={'HIDDEN'})
    mode: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        mode = self.mode or active_mode(context.scene)
        wanted = str(self.material_lut).lower()
        for item in active_source_slots(context.scene, mode):
            if str(item.material_lut).lower() == wanted:
                item.enabled = self.enabled
        context.scene.hd2_lut_analysis = ""
        return {'FINISHED'}


class HD2LUT_OT_AddDestinationArchive(Operator):
    bl_idname = "hd2_lut.add_destination_archive"
    bl_label = "Add Destination Archive"
    bl_description = "Add this archive without closing the search window"

    archive_id: StringProperty(options={'HIDDEN'})
    archive_name: StringProperty(options={'HIDDEN'})
    mode: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        mode = self.mode or active_mode(context.scene)
        if is_unknown_helmet(mode, self.archive_name):
            self.report({'INFO'}, "Unknown Helmet entries are excluded from Helmet mode")
            return {'CANCELLED'}
        destinations = active_destinations(context.scene, mode)
        if contains_destination(destinations, self.archive_id):
            self.report({'INFO'}, "Archive is already in the destination list")
            return {'CANCELLED'}
        item = destinations.add()
        item.archive_id = str(self.archive_id).lower()
        item.name = str(self.archive_name)
        context.scene.hd2_lut_analysis = ""
        self.report({'INFO'}, f"Added destination: {self.archive_name}")
        return {'FINISHED'}


class HD2LUT_OT_AddDestinationClass(Operator):
    bl_idname = "hd2_lut.add_destination_class"
    bl_label = "Add Destination Class"
    bl_description = "Add every known Light, Medium, or Heavy entry for this mode"

    armor_class: StringProperty(options={'HIDDEN'})
    mode: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        mode = self.mode or active_mode(context.scene)
        try:
            _, categories = load_dataset(mode)
        except LUTSwapError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        destinations = active_destinations(context.scene, mode)
        added = 0
        for archive_id, archive_name in categories.get(self.armor_class, []):
            if is_unknown_helmet(mode, archive_name) or contains_destination(destinations, archive_id):
                continue
            item = destinations.add()
            item.archive_id = archive_id
            item.name = archive_name
            added += 1
        context.scene.hd2_lut_analysis = ""
        self.report({'INFO'}, f"Added {added} {self.armor_class} destination archive(s)")
        return {'FINISHED'}


class HD2LUT_OT_RemoveDestination(Operator):
    bl_idname = "hd2_lut.remove_destination"
    bl_label = "Remove Destination"

    index: IntProperty(options={'HIDDEN'})

    def execute(self, context):
        destinations = active_destinations(context.scene)
        if 0 <= self.index < len(destinations):
            destinations.remove(self.index)
            context.scene.hd2_lut_analysis = ""
        return {'FINISHED'}


class HD2LUT_OT_ClearDestinations(Operator):
    bl_idname = "hd2_lut.clear_destinations"
    bl_label = "Clear Destination Archives"

    def execute(self, context):
        active_destinations(context.scene).clear()
        context.scene.hd2_lut_analysis = ""
        return {'FINISHED'}


class HD2LUT_OT_BrowseArchives(Operator):
    bl_idname = "hd2_lut.browse_archives"
    bl_label = "Search LUT Archives"
    bl_description = "Live-search the bundled armor or helmet JSON"

    search_query: StringProperty(name="Search", default="", options={'TEXTEDIT_UPDATE'})
    source_mode: BoolProperty(default=False, options={'HIDDEN'})
    mode: StringProperty(options={'HIDDEN'})

    def invoke(self, context, event):
        self.search_query = ""
        self.mode = self.mode or active_mode(context.scene)
        return context.window_manager.invoke_popup(self, width=680)

    def execute(self, context):
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        mode = self.mode or active_mode(context.scene)
        layout.prop(self, "search_query", icon='VIEWZOOM')
        try:
            details, _ = load_dataset(mode)
        except LUTSwapError as error:
            layout.label(text=str(error), icon='ERROR')
            return

        query = self.search_query.strip().casefold()
        matches = [
            (archive_id, str(info.get("name") or archive_id), str(info.get("_armor_class") or ""))
            for archive_id, info in details.items()
            if not is_unknown_helmet(mode, str(info.get("name") or archive_id))
            and (
                not query
                or query in archive_id.casefold()
                or query in str(info.get("name") or "").casefold()
            )
        ]
        matches.sort(key=lambda item: (item[1].casefold(), item[0]))
        if not matches:
            layout.label(text="No archive found.", icon='INFO')
            return
        if len(matches) > 80:
            layout.label(text=f"Showing first 80 of {len(matches)} results; refine the search.", icon='INFO')
        for archive_id, archive_name, armor_class in matches[:80]:
            row = layout.row(align=True)
            row.label(text=f"{archive_name}  [{armor_class}]", icon='FILE_FOLDER')
            if self.source_mode:
                operator = row.operator("hd2_lut.set_source_archive", text="Use", icon='CHECKMARK')
            else:
                operator = row.operator("hd2_lut.add_destination_archive", text="Add", icon='ADD')
            operator.archive_id = archive_id
            operator.archive_name = archive_name
            operator.mode = mode


class HD2LUT_OT_SelectDDS(Operator, ImportHelper):
    bl_idname = "hd2_lut.select_dds"
    bl_label = "Select LUT Texture"
    filename_ext = ".dds"
    filter_glob: StringProperty(
        default="*.dds;*.png;*.tga;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff",
        options={'HIDDEN'},
    )
    mode: StringProperty(options={'HIDDEN'})
    slot_index: IntProperty(options={'HIDDEN'}, default=-1)
    target_kind: StringProperty(options={'HIDDEN'}, default="SLOT")

    def execute(self, context):
        mode = self.mode or active_mode(context.scene)
        if self.target_kind == "GROUP":
            items = active_custom_groups(context.scene, mode)
        else:
            items = active_custom_slots(context.scene, mode)
        if not 0 <= self.slot_index < len(items):
            self.report({'ERROR'}, "The selected custom LUT item no longer exists")
            return {'CANCELLED'}
        items[self.slot_index].dds_path = self.filepath
        items[self.slot_index].dds_id = ""
        items[self.slot_index].enabled = True
        context.scene.hd2_lut_analysis = ""
        return {'FINISHED'}


class HD2LUT_OT_ToggleCustomGroup(Operator):
    bl_idname = "hd2_lut.toggle_custom_group"
    bl_label = "Expand Custom LUT Group"

    mode: StringProperty(options={'HIDDEN'})
    group_index: IntProperty(options={'HIDDEN'}, default=-1)

    def execute(self, context):
        mode = self.mode or active_mode(context.scene)
        groups = active_custom_groups(context.scene, mode)
        if 0 <= self.group_index < len(groups):
            groups[self.group_index].expanded = not groups[self.group_index].expanded
        return {'FINISHED'}


class HD2LUT_OT_GeneratePatch(Operator):
    bl_idname = "hd2_lut.generate_patch"
    bl_label = "Generate & Write LUT Patch"
    bl_description = "Override destination LUT Texture IDs; Materials, meshes, masks and decals remain unchanged"

    def execute(self, context):
        started = time.perf_counter()
        sdk = get_sdk()
        if sdk is None:
            self.report({'ERROR'}, "HD2SDK is not enabled or could not be imported")
            return {'CANCELLED'}
        mode = active_mode(context.scene)
        PRIVATE_ARCHIVES.clear()
        PRIVATE_PAYLOADS.clear()
        try:
            plan = build_mapping_plan(sdk, context.scene, mode)
            (
                patch, payloads, target_texture_ids,
                removed_legacy_materials, removed_legacy_textures,
            ) = apply_plan(sdk, context.scene, plan)
        except (LUTSwapError, OSError, RuntimeError, ValueError) as error:
            context.scene.hd2_lut_analysis = f"BLOCKED - {error}"
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        finally:
            PRIVATE_ARCHIVES.clear()
            PRIVATE_PAYLOADS.clear()

        elapsed = time.perf_counter() - started
        context.scene.hd2_lut_analysis = format_plan(plan)
        self.report(
            {'INFO'},
            f"Wrote {len(target_texture_ids)} LUT Texture ID override(s) using "
            f"{plan['source_lut_count']} source payload(s); {payloads} total stored patch payload(s) "
            f"in {elapsed:.1f}s. Removed {removed_legacy_materials} legacy Material override(s) "
            f"and {removed_legacy_textures} legacy DDS redirect(s).",
        )
        return {'FINISHED'}


class HD2LUT_OT_OpenSupportLink(Operator):
    bl_idname = "hd2_lut.open_support_link"
    bl_label = "Open Support Link"
    bl_description = "Open the creator's support page in your web browser"

    url: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        bpy.ops.wm.url_open(url=self.url)
        return {'FINISHED'}


class HD2LUT_PT_MainPanel(Panel):
    bl_label = "HD2 LUT / Texture ID Swap"
    bl_idname = "HD2LUT_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ID_Swap'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        if not armor_swap_support_is_visible(context):
            support_box = layout.box()
            support_box.label(text="Created by Uskummel", icon='USER')
            support_box.label(text="If this saved your time:", icon='FUND')
            support_row = support_box.row(align=True)
            paypal = support_row.operator(
                "hd2_lut.open_support_link",
                text="Buy me a coffee (PayPal)",
                icon_value=support_icon_value("paypal"),
            )
            paypal.url = "http://paypal.me/uskummel"
            kofi = support_row.operator(
                "hd2_lut.open_support_link",
                text="Buy me a coffee (Ko-fi)",
                icon_value=support_icon_value("kofi"),
            )
            kofi.url = "https://ko-fi.com/uskummel"

        sdk = get_sdk()
        if sdk is None:
            layout.label(text="Enable HD2SDK first.", icon='ERROR')
            return

        mode_row = layout.row(align=True)
        mode_row.prop(scene, "hd2_lut_mode", expand=True)
        mode = active_mode(scene)
        label = mode_label(mode)
        source_id, source_name = get_source_archive(scene, mode)
        slots_prop, slots_index_prop = slot_props(mode)
        destinations_prop, destinations_index_prop, filter_prop = destination_props(mode)

        source_box = layout.box()
        source_kind, _, _ = dds_source_props(mode)
        source_box.prop(scene, source_kind, expand=True)
        source_box.label(
            text=(f"1. {label} custom LUT slots" if is_dds_source(scene, mode)
                  else f"1. Source {label} LUT archive"),
            icon='IMAGE_DATA',
        )
        if is_dds_source(scene, mode):
            body_mode = scene.hd2_lut_custom_body_mode
            source_box.prop(scene, "hd2_lut_custom_body_mode", expand=True)
            groups = active_custom_groups(scene, mode, body_mode)
            slots = active_custom_slots(scene, mode)
            if not groups:
                source_box.label(text="Preparing custom slot list…", icon='TIME')
            for group_index, group in enumerate(groups):
                group_row = source_box.row(align=True)
                toggle = group_row.operator(
                    "hd2_lut.toggle_custom_group", text="",
                    icon='TRIA_DOWN' if group.expanded else 'TRIA_RIGHT',
                )
                toggle.mode = mode
                toggle.group_index = group_index
                group_row.prop(group, "enabled", text="")
                group_row.label(text=group.label, icon='IMAGE_DATA')
                group_row.prop(group, "dds_path", text="")
                choose = group_row.operator("hd2_lut.select_dds", text="", icon='FILE_FOLDER')
                choose.mode = mode
                choose.slot_index = group_index
                choose.target_kind = "GROUP"
                if group.expanded:
                    group_key = custom_group_key(group)
                    for slot_index, item in enumerate(slots):
                        key = source_slot_key(item)
                        if group_key_for_slot(key, body_mode) != group_key:
                            continue
                        slot_row = source_box.row(align=True)
                        slot_row.separator(factor=1.5)
                        slot_row.prop(item, "enabled", text="")
                        child_label = (
                            f"{key[0]} / {key[2]}" if body_mode == "OVERALL"
                            else f"{key[2]}" + (f" #{key[3] + 1}" if key[3] else "")
                        )
                        slot_row.label(text=child_label, icon='DOT')
                        slot_row.prop(item, "dds_path", text="")
                        choose = slot_row.operator("hd2_lut.select_dds", text="", icon='FILE_FOLDER')
                        choose.mode = mode
                        choose.slot_index = slot_index
                        choose.target_kind = "SLOT"
        else:
            row = source_box.row(align=True)
            row.label(text=source_name or f"No {label} preset selected", icon='FILE_FOLDER')
            browse = row.operator("hd2_lut.browse_archives", text="", icon='ADD')
            browse.source_mode = True
            browse.mode = mode
            clear_row = row.row(align=True)
            clear_row.enabled = bool(source_id)
            clear_row.operator("hd2_lut.clear_source", text="", icon='X')
        if source_id and not is_dds_source(scene, mode):
            row = source_box.row(align=True)
            all_slots = row.operator("hd2_lut.set_all_source_slots", text="All", icon='CHECKMARK')
            all_slots.enabled = True
            no_slots = row.operator("hd2_lut.set_all_source_slots", text="None", icon='X')
            no_slots.enabled = False
            source_box.label(text="Source LUT groups (each applies all matching semantic slots):", icon='INFO')
            for material_lut, items in source_lut_groups(scene, mode):
                enabled = all(item.enabled for item in items)
                group_row = source_box.row(align=True)
                toggle = group_row.operator(
                    "hd2_lut.set_source_group",
                    text="",
                    icon='CHECKBOX_HLT' if enabled else 'CHECKBOX_DEHLT',
                )
                toggle.material_lut = material_lut
                toggle.enabled = not enabled
                toggle.mode = mode
                group_row.label(
                    text=f"{material_lut}  -  {len(items)} slot(s): {source_group_summary(items)}",
                    icon='IMAGE_DATA',
                )

        destination_box = layout.box()
        row = destination_box.row(align=True)
        row.label(text=f"2. Destination {label} archives", icon='FILE_FOLDER')
        browse = row.operator("hd2_lut.browse_archives", text="", icon='ADD')
        browse.source_mode = False
        browse.mode = mode
        class_row = destination_box.row(align=True)
        for armor_class, class_label in (("light", "Light"), ("medium", "Medium"), ("heavy", "Heavy")):
            operator = class_row.operator("hd2_lut.add_destination_class", text=class_label, icon='ADD')
            operator.armor_class = armor_class
            operator.mode = mode
        destination_box.prop(scene, filter_prop, text="", icon='VIEWZOOM')
        destination_box.template_list(
            "HD2LUT_UL_Destinations",
            "",
            scene,
            destinations_prop,
            scene,
            destinations_index_prop,
            rows=6,
        )
        destination_box.operator("hd2_lut.clear_destinations", text="Clear destination list", icon='TRASH')

        options_box = layout.box()
        options_box.label(text="3. LUT mapping options", icon='PREFERENCES')
        options_box.prop(scene, "hd2_lut_allow_shared_ids")

        write_box = layout.box()
        write_box.label(text="4. Write patch", icon='FILE_TICK')
        custom_slot_ready = (
            any(item.enabled and str(item.dds_path).strip() for item in active_custom_slots(scene, mode))
            or any(item.enabled and str(item.dds_path).strip() for item in active_custom_groups(scene, mode))
        )
        ready = bool(
            (custom_slot_ready if is_dds_source(scene, mode) else source_id and selected_source_items(scene, mode))
            and len(active_destinations(scene, mode))
        )
        write = write_box.row()
        write.enabled = ready
        write.operator("hd2_lut.generate_patch", text="Generate & Write LUT Patch", icon='FILE_TICK')
        layout.label(text=f"Connected to {sdk.__name__}", icon='CHECKMARK')


CLASSES = (
    HD2LUT_SourceSlotItem,
    HD2LUT_CustomGroupItem,
    HD2LUT_ArchiveItem,
    HD2LUT_UL_SourceSlots,
    HD2LUT_UL_Destinations,
    HD2LUT_OT_SetSourceArchive,
    HD2LUT_OT_ClearSource,
    HD2LUT_OT_SetAllSourceSlots,
    HD2LUT_OT_SetSourceGroup,
    HD2LUT_OT_AddDestinationArchive,
    HD2LUT_OT_AddDestinationClass,
    HD2LUT_OT_RemoveDestination,
    HD2LUT_OT_ClearDestinations,
    HD2LUT_OT_BrowseArchives,
    HD2LUT_OT_SelectDDS,
    HD2LUT_OT_ToggleCustomGroup,
    HD2LUT_OT_GeneratePatch,
    HD2LUT_OT_OpenSupportLink,
    HD2LUT_PT_MainPanel,
)


def register():
    global SUPPORT_ICONS
    for cls in CLASSES:
        bpy.utils.register_class(cls)

    SUPPORT_ICONS = bpy.utils.previews.new()
    icon_folder = os.path.join(bpy.app.tempdir, "hd2_lut_swap_icons")
    os.makedirs(icon_folder, exist_ok=True)
    for icon_name in ("paypal", "kofi"):
        icon_path = os.path.join(icon_folder, f"{icon_name}.png")
        with open(icon_path, "wb") as icon_file:
            icon_file.write(base64.b64decode(EMBEDDED_SUPPORT_ICONS[icon_name]))
        SUPPORT_ICONS.load(icon_name, icon_path, 'IMAGE')

    bpy.types.Scene.hd2_lut_mode = EnumProperty(
        name="Mode",
        items=(
            ("ARMOR", "Armor", "Use armor_detailed.json"),
            ("HELMET", "Helmet", "Use helmet_detailed.json"),
        ),
        default="ARMOR",
        update=on_lut_mode_changed,
    )
    bpy.types.Scene.hd2_lut_custom_body_mode = EnumProperty(
        name="Custom slot mode",
        items=(
            ("OVERALL", "Overall", "One LUT DDS per body part for all body types"),
            ("BODY", "Brawny / Lean", "Separate group LUT DDS for each body type"),
        ),
        default="OVERALL",
    )
    bpy.types.Scene.hd2_lut_armor_source_id = StringProperty(default="")
    bpy.types.Scene.hd2_lut_armor_source_name = StringProperty(default="")
    bpy.types.Scene.hd2_lut_helmet_source_id = StringProperty(default="")
    bpy.types.Scene.hd2_lut_helmet_source_name = StringProperty(default="")
    for prefix in ("armor", "helmet"):
        setattr(bpy.types.Scene, f"hd2_lut_{prefix}_source_kind", EnumProperty(
            name="Source",
            items=(
                ("ARCHIVE", "Game preset LUTs", "Use the selected armor/helmet's LUTs"),
                ("DDS", "Custom LUTs per slot", "Import group or individual LUT DDS files without a source preset"),
            ),
            default="ARCHIVE",
            update=on_lut_source_kind_changed,
        ))
        setattr(bpy.types.Scene, f"hd2_lut_{prefix}_source_dds", StringProperty(subtype='FILE_PATH', default=""))
        setattr(bpy.types.Scene, f"hd2_lut_{prefix}_source_dds_id", StringProperty(default=""))

    bpy.types.Scene.hd2_lut_armor_source_slots = CollectionProperty(type=HD2LUT_SourceSlotItem)
    bpy.types.Scene.hd2_lut_armor_source_slot_index = IntProperty(default=0)
    bpy.types.Scene.hd2_lut_helmet_source_slots = CollectionProperty(type=HD2LUT_SourceSlotItem)
    bpy.types.Scene.hd2_lut_helmet_source_slot_index = IntProperty(default=0)
    bpy.types.Scene.hd2_lut_armor_custom_slots = CollectionProperty(type=HD2LUT_SourceSlotItem)
    bpy.types.Scene.hd2_lut_armor_custom_slot_index = IntProperty(default=0)
    bpy.types.Scene.hd2_lut_helmet_custom_slots = CollectionProperty(type=HD2LUT_SourceSlotItem)
    bpy.types.Scene.hd2_lut_helmet_custom_slot_index = IntProperty(default=0)
    bpy.types.Scene.hd2_lut_armor_custom_overall_groups = CollectionProperty(type=HD2LUT_CustomGroupItem)
    bpy.types.Scene.hd2_lut_armor_custom_body_groups = CollectionProperty(type=HD2LUT_CustomGroupItem)
    bpy.types.Scene.hd2_lut_helmet_custom_overall_groups = CollectionProperty(type=HD2LUT_CustomGroupItem)
    bpy.types.Scene.hd2_lut_helmet_custom_body_groups = CollectionProperty(type=HD2LUT_CustomGroupItem)

    bpy.types.Scene.hd2_lut_armor_destinations = CollectionProperty(type=HD2LUT_ArchiveItem)
    bpy.types.Scene.hd2_lut_armor_destination_index = IntProperty(default=0)
    bpy.types.Scene.hd2_lut_helmet_destinations = CollectionProperty(type=HD2LUT_ArchiveItem)
    bpy.types.Scene.hd2_lut_helmet_destination_index = IntProperty(default=0)
    bpy.types.Scene.hd2_lut_armor_destination_filter = StringProperty(default="")
    bpy.types.Scene.hd2_lut_helmet_destination_filter = StringProperty(default="")

    bpy.types.Scene.hd2_lut_allow_shared_ids = BoolProperty(
        name="Allow shared LUT IDs",
        description="Keep the first mapping when one global destination Texture ID receives different source LUT requests",
        default=False,
    )
    bpy.types.Scene.hd2_lut_analysis = StringProperty(default="")

    bpy.types.Scene.hd2_lut_armor_generated_patch_path = StringProperty(default="")
    bpy.types.Scene.hd2_lut_armor_generated_material_ids = StringProperty(default="")
    bpy.types.Scene.hd2_lut_armor_generated_texture_ids = StringProperty(default="")
    bpy.types.Scene.hd2_lut_helmet_generated_patch_path = StringProperty(default="")
    bpy.types.Scene.hd2_lut_helmet_generated_material_ids = StringProperty(default="")
    bpy.types.Scene.hd2_lut_helmet_generated_texture_ids = StringProperty(default="")

    # bpy.data is intentionally restricted while Blender enables an add-on.
    # Defer existing-scene initialization until that restriction is lifted.
    bpy.app.timers.register(initialize_custom_slots_after_register, first_interval=0.0)


def unregister():
    global SUPPORT_ICONS
    if bpy.app.timers.is_registered(initialize_custom_slots_after_register):
        bpy.app.timers.unregister(initialize_custom_slots_after_register)
    properties = (
        "hd2_lut_helmet_custom_body_groups",
        "hd2_lut_helmet_custom_overall_groups",
        "hd2_lut_armor_custom_body_groups",
        "hd2_lut_armor_custom_overall_groups",
        "hd2_lut_custom_body_mode",
        "hd2_lut_helmet_custom_slot_index",
        "hd2_lut_helmet_custom_slots",
        "hd2_lut_armor_custom_slot_index",
        "hd2_lut_armor_custom_slots",
        "hd2_lut_helmet_generated_texture_ids",
        "hd2_lut_helmet_generated_material_ids",
        "hd2_lut_helmet_generated_patch_path",
        "hd2_lut_armor_generated_texture_ids",
        "hd2_lut_armor_generated_material_ids",
        "hd2_lut_armor_generated_patch_path",
        "hd2_lut_analysis",
        "hd2_lut_allow_shared_ids",
        "hd2_lut_helmet_destination_filter",
        "hd2_lut_armor_destination_filter",
        "hd2_lut_helmet_destination_index",
        "hd2_lut_helmet_destinations",
        "hd2_lut_armor_destination_index",
        "hd2_lut_armor_destinations",
        "hd2_lut_helmet_source_slot_index",
        "hd2_lut_helmet_source_slots",
        "hd2_lut_armor_source_slot_index",
        "hd2_lut_armor_source_slots",
        "hd2_lut_helmet_source_name",
        "hd2_lut_helmet_source_id",
        "hd2_lut_armor_source_name",
        "hd2_lut_armor_source_id",
        "hd2_lut_mode",
        "hd2_lut_armor_source_dds_id", "hd2_lut_armor_source_dds", "hd2_lut_armor_source_kind",
        "hd2_lut_helmet_source_dds_id", "hd2_lut_helmet_source_dds", "hd2_lut_helmet_source_kind",
    )
    for name in properties:
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    if SUPPORT_ICONS is not None:
        bpy.utils.previews.remove(SUPPORT_ICONS)
        SUPPORT_ICONS = None


if __name__ == "__main__":
    register()
