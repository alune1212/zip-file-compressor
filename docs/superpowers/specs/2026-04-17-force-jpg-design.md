# Force JPG Output Format - Design Spec

## Overview

Add `--force-jpg` CLI flag that forces all compressed image and PDF files to be output as JPEG format, regardless of their original type.

## Configuration Change

**File:** `zip_compressor/models.py`

Add `force_jpg: bool = False` to `CompressionConfig`.

## CLI Change

**File:** `zip_compressor/pipeline.py`

Add `--force-jpg` argument that sets `config.force_jpg = True`.

## Image Compression Changes

**File:** `zip_compressor/compressors/image_compressor.py`

### PNG Handling
- When `force_jpg=True`: PNG is always converted to JPEG (ignores `png_allow_jpg` setting)
- Conversion: open image → convert to RGB → save as JPEG
- Output path: `file_path.with_suffix(".jpg")`
- Delete original PNG file after successful conversion

### JPEG Handling
- When `force_jpg=True`: Ensure output remains JPEG
- Already JPEG format, no change needed
- If original is `.jpeg` extension, consider normalizing to `.jpg`

## PDF Compression Changes

**File:** `zip_compressor/compressors/pdf_compressor.py`

### PDF → JPG Conversion
- When `force_jpg=True`: Convert each PDF page to a separate JPEG file
- Naming: `{original_name}_page_{n}.jpg` (e.g., `document_page_1.jpg`)
- Render each page at reasonable resolution (150-300 DPI)
- Delete original PDF after successful conversion
- Return `FileProcessResult` with `relative_path` reflecting the first page, and track additional pages

### Implementation Approach
- Use `pypdf` or `PyPDF2` to read page count
- Use `Pillow` (PIL) to render each page as image
- Or use `ghostscript` if available for better quality

## Scanner Considerations

**File:** `zip_compressor/scanner.py`

- No changes needed to initial scan
- Post-processing: newly created `.jpg` files from PNG/PDF conversion should be picked up during re-packaging

## Data Flow

1. Extract ZIP → temp directory
2. Scan for PDF/JPG/JPEG/PNG files
3. For each file:
   - If PNG and `force_jpg=True`: convert to JPG, update path
   - If PDF and `force_jpg=True`: convert each page to JPG, remove PDF
   - If JPEG: compress and keep as JPG
4. Re-package processed files to output ZIP

## FileProcessResult Updates

When PNG or PDF is converted:
- `relative_path` should reflect the new `.jpg` path
- For multi-page PDF, first page gets the result; additional pages tracked separately

## Error Handling

- If PNG→JPG conversion fails: report as `FAILED` with reason `IMAGE_SAVE_FAILED`
- If PDF page rendering fails: report partial failure, continue with other pages
- If any page exceeds target size: compress using image compression strategy

## Backward Compatibility

- Default `force_jpg=False` preserves existing behavior
- Existing `--png-allow-jpg` continues to work when `force_jpg=False`
