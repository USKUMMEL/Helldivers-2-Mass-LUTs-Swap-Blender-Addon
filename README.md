# HD2 Mass LUT / Texture ID Swap

Standalone Blender addon for HD2SDK Community Edition.

Repository: https://github.com/USKUMMEL/Helldivers-2-Mass-LUTs-Swap-Blender-Addon

It applies source Armor or Helmet LUTs to matching semantic slots on many
destination archives while preserving every destination Material, mesh, decal
sheet, normal map, mask, and other texture channel.

## Flow

1. Enable HD2SDK Community Edition and open its normal patch workflow.
2. In the ID_Swap tab, choose Armor or Helmet.
3. In **Custom LUTs per slot** mode, choose **Overall** to use one DDS for a
   body part across Brawny/Lean, or **Brawny / Lean** to use separate group
   DDS files. Expand a group to override individual layer slots. No source
   armor/helmet preset is required.

Custom sources may be DDS, PNG, TGA, JPG, BMP, or TIFF. They are normalized to
the game LUT layout (23×8, half-float RGBA, mip chain); source images must
already be 23×8 pixels.
4. Add destination archives individually or by Light / Medium / Heavy.
5. Click Generate & Write LUT Patch.

Only destination slots with the exact same BodyType / region / layer / ordinal
as an imported preset slot are replaced. Missing slots are ignored and remain
vanilla; there is no cross-body or spare-slot fallback.

The addon overrides only the primary material LUT. Destination pattern LUTs,
masks, decals, normals, and materials remain unchanged.

The addon overrides the existing destination LUT Texture IDs directly. It does
not redirect or replace Materials. Multiple target Texture IDs alias the same
TOC/GPU/stream offsets, so each unique source LUT payload is stored only once
in the patch while all original Materials continue to use their own LUT IDs
and masks.

The addon reads destination archives privately for preflight and does not add
them to HD2SDK's visible Loaded Archives list.

armor_detailed.json and helmet_detailed.json are bundled with the addon and
required at runtime.
