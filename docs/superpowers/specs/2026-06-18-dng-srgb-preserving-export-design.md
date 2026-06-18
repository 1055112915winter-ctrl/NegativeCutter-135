# DNG sRGB-Preserving Export Design

## Goal

Make DNG cropped-image exports color-managed sRGB without changing the decoded 16-bit pixel values, while preserving ordinary TIFF pixels and existing profiles. Reuse the coordinate export button for DNG sidecars without copying or modifying the source DNG.

## Color policy

- DNG: decode explicitly with rawpy as 16-bit sRGB. Generate a standard sRGB ICC profile with the bundled Pillow/ImageCms runtime and attach it to the temporary TIFF. Cropped TIFF exports copy the same ICC profile and slice the source array without a second color conversion.
- TIFF with ICC: preserve pixel values and copy the source ICC profile.
- TIFF without ICC: preserve pixel values, leave the output untagged, and report `色彩空间未知` in the GUI. Never assume sRGB.

## User interface

- Keep `导出裁切图像` as the image-export action.
- Reuse the existing coordinate action. When a DNG is loaded, label it `导出原始 DNG 坐标`; for other formats retain `保存坐标数据`.
- The coordinate action writes the existing `.negativecutter.json` sidecar only. It never copies or modifies the source image.

## Data flow

1. `load_dng_preview_array()` explicitly requests `rawpy.ColorSpace.sRGB` and `output_bps=16`.
2. `MainWindow._load_dng()` writes the returned RGB array to the temporary TIFF with an embedded standard sRGB ICC tag.
3. `crop_and_save()` reads the temporary TIFF, slices the frame rectangle, writes the 16-bit RGB TIFF, and copies the ICC bytes unchanged.
4. Ordinary TIFF exports continue through the same direct array-crop path. Existing ICC bytes are preserved; missing ICC remains missing.
5. The coordinate button serializes the current frames through the existing `to_json()` function.

## Error handling

- Failure to create the sRGB ICC profile aborts DNG loading with the existing GUI load-error path; it must not silently create an untagged DNG preview.
- An ordinary TIFF without ICC is accepted and shown as `色彩空间未知`.
- Coordinate export cancellation produces no files, matching current behavior.

## Verification

- RED/GREEN tests prove rawpy receives explicit sRGB output settings.
- Tests prove the DNG temporary TIFF and cropped export contain identical ICC bytes.
- Tests compare exported crop samples with the corresponding temporary TIFF samples exactly.
- Tests prove an untagged TIFF stays untagged and is reported as unknown.
- GUI contract tests prove the coordinate button label changes for DNG and remains unchanged for TIFF.
- Run all GUI tests, package contract tests, the package script, and strict code-sign verification.

## Git scope

Commit only the relevant APP source, tests, this specification, the implementation plan, and the project handoff. Exclude the packaged `.app`, source DNG/TIFF fixtures, temporary files, and unrelated Lightroom plugin changes.
