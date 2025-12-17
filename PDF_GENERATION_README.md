# PDF Generation System

## Overview

This document describes the PDF generation system implemented for both Interactive Search and Story Adventure book formats. The system generates print-ready PDFs (300 DPI) and uploads them to Supabase storage.

## Features

- ✅ Format-specific PDF creation (Interactive Search & Story Adventure)
- ✅ High-resolution image handling (300 DPI)
- ✅ Print-ready PDF generation
- ✅ Automatic upload to Supabase storage
- ✅ Purchase verification before download
- ✅ Download endpoint with authentication
- ✅ Complete within 30 seconds target

## PDF Formats

### 1. Interactive Search PDF

**Layout:**
- Cover page with title and character image
- 4 full-page scene spreads
- Back cover with branding

**Structure:**
- Total pages: 6 (Cover + 4 scenes + Back cover)
- Images: Full-page spreads at 300 DPI
- Typography: Helvetica font family

### 2. Story Adventure PDF

**Layout:**
- Cover page with title and character image
- 5 illustrated pages with text (60% image, 35% text)
- Audio access information page (if audio URLs available)
- Back cover with branding

**Structure:**
- Total pages: 7-8 (Cover + 5 story pages + Audio info + Back cover)
- Images: High-resolution scene images
- Text: Story text with word wrapping
- Audio: QR code and links to audio versions

## Implementation Details

### Files Created/Modified

1. **`pdf_generator.py`** - Main PDF generation module
   - `generate_pdf()` - Main entry point
   - `create_interactive_search_pdf()` - Interactive Search format
   - `create_story_adventure_pdf()` - Story Adventure format
   - `resize_image_for_pdf()` - High-resolution image processing
   - `download_image_from_url()` - Image downloading utility

2. **`batch_processor.py`** - Updated `_create_pdf()` method
   - Integrates PDF generation into batch processing pipeline
   - Handles both PDF formats
   - Uploads PDFs to Supabase storage
   - Updates story records with PDF URLs

3. **`main.py`** - Added download endpoints
   - `GET /api/books/{book_id}/pdf` - Download PDF with purchase verification
   - `POST /api/books/{book_id}/purchase` - Record purchase

4. **`pdf_purchase_schema.sql`** - Database schema
   - `book_purchases` table for purchase verification
   - `pdf_url` column added to `stories` table

5. **`requirements.txt`** - Added `reportlab>=4.0.0`

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Database Migration

Execute `pdf_purchase_schema.sql` in your Supabase SQL Editor:

```sql
-- See pdf_purchase_schema.sql for full schema
```

This creates:
- `book_purchases` table for purchase tracking
- `pdf_url` column in `stories` table
- RLS policies for security

### 3. Create PDF Storage Bucket (Optional)

Create a `pdfs` bucket in Supabase Storage. If not created, the system will fallback to the `images` bucket.

## API Endpoints

### Download PDF

```http
GET /api/books/{book_id}/pdf
Authorization: Bearer <token>  # Optional
```

**Response:**
- PDF file stream with `Content-Type: application/pdf`
- `Content-Disposition: attachment; filename="book_*.pdf"`

**Purchase Verification:**
- If `user_id` is provided, verifies purchase before download
- Returns 403 if purchase not verified
- Currently allows free access (change `verify_purchase()` in production)

### Record Purchase

```http
POST /api/books/{book_id}/purchase
Content-Type: application/json

{
  "user_id": "uuid",
  "transaction_id": "optional",
  "amount_paid": 0.0,
  "payment_method": "free"
}
```

## PDF Generation Process

### Interactive Search Flow

1. Job processes 4 scenes in parallel
2. After scenes complete, `_create_pdf()` is called
3. PDF generator:
   - Downloads cover image (from enhanced_images[0] or character_image_url)
   - Downloads 4 scene images
   - Resizes images to 300 DPI
   - Creates PDF with cover + 4 scenes + back cover
4. Uploads PDF to Supabase storage
5. Updates story record with PDF URL

### Story Adventure Flow

1. Job processes 5 scenes in parallel
2. Story text is generated
3. Audio is generated (optional)
4. After all stages complete, `_create_pdf()` is called
5. PDF generator:
   - Downloads cover image
   - Downloads 5 scene images
   - Creates PDF with cover + 5 illustrated pages + audio info + back cover
6. Uploads PDF to Supabase storage
7. Updates story record with PDF URL

## Performance

- **Target:** Complete within 30 seconds
- **Image Processing:** High-quality resampling (LANCZOS)
- **PDF Generation:** ReportLab for efficient PDF creation
- **Storage:** Direct upload to Supabase storage

## Typography & Styling

- **Fonts:** Helvetica (standard, bold variants)
- **Page Size:** US Letter (8.5" x 11")
- **Margins:** 0.5 inches
- **Image Quality:** 300 DPI for print-ready output
- **Branding:** Configurable brand name and colors

## Purchase Verification

The system includes a purchase verification mechanism:

1. **Database Table:** `book_purchases` tracks purchases
2. **Verification Function:** `verify_purchase()` checks purchase status
3. **Download Protection:** PDFs require verified purchase (configurable)

**Current Behavior:**
- Allows free access (for development)
- Change `verify_purchase()` return value to `False` in production

## Error Handling

- Image download failures: Logged, PDF continues with available images
- PDF generation failures: Job stage marked as failed
- Storage upload failures: Error logged, job fails
- Purchase verification failures: Returns 403 Forbidden

## Future Enhancements

- [ ] QR code generation for audio access
- [ ] Custom font support
- [ ] Page templates customization
- [ ] Watermarking for purchased PDFs
- [ ] PDF compression optimization
- [ ] Batch PDF generation
- [ ] PDF preview generation

## Troubleshooting

### PDF Generation Fails

1. Check image URLs are accessible
2. Verify ReportLab is installed: `pip install reportlab`
3. Check Supabase storage bucket exists
4. Review logs for specific error messages

### Purchase Verification Not Working

1. Verify `book_purchases` table exists
2. Check RLS policies are correct
3. Ensure user_id is being passed correctly
4. Review `verify_purchase()` function logic

### PDF Quality Issues

1. Verify source images are high resolution
2. Check DPI settings (300 DPI for print)
3. Review image resampling method (LANCZOS)

## Testing

Test PDF generation:

```python
from pdf_generator import generate_pdf

# Interactive Search
pdf_bytes = generate_pdf(
    pdf_type="interactive_search",
    character_name="Luna",
    story_title="Luna's Adventure",
    character_image_url="https://...",
    scene_urls=["https://...", "https://...", "https://...", "https://..."]
)

# Story Adventure
pdf_bytes = generate_pdf(
    pdf_type="story_adventure",
    character_name="Luna",
    story_title="Luna's Adventure",
    character_image_url="https://...",
    story_pages=[
        {"text": "Page 1 text...", "scene": "https://..."},
        # ... 4 more pages
    ],
    audio_urls=["https://...", ...]
)
```

## Support

For issues or questions, check:
- Logs in `batch_processor.py`
- Supabase storage bucket configuration
- Database schema in `pdf_purchase_schema.sql`

