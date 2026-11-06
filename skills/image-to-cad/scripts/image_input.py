"""Load raster images and render a selected PDF page."""
import hashlib

import cv2
import numpy as np
from PIL import Image, ImageOps


def digest(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_image(path, *, page=1, dpi=200, max_pixels=40_000_000):
    """Decode without cropping/resizing. EXIF and PDF transformations are explicit."""
    meta = {'source_name': path.name, 'source_sha256': digest(path), 'page': page,
            'coordinate_system': 'oriented raster pixel centers; x right, y down',
            'crop': None, 'resized': False}
    if path.suffix.lower() == '.pdf':
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(path) as doc:
            if page < 1 or page > len(doc):
                raise ValueError(f'PDF page must be in 1..{len(doc)}')
            meta['page_count'] = len(doc)
            sheet = doc[page - 1]
            try:
                pw, ph = sheet.get_size()
                if np.ceil(pw * dpi / 72) * np.ceil(ph * dpi / 72) > max_pixels:
                    raise ValueError('PDF page exceeds --max-pixels; lower --dpi explicitly')
                bitmap = sheet.render(scale=dpi / 72)
                try:
                    rgb = np.array(bitmap.to_pil().convert('RGB'))
                finally:
                    bitmap.close()
                meta.update(pdf_page_size_pt=[pw, ph], dpi=dpi,
                            pdf_display_points_per_pixel=[pw / rgb.shape[1], ph / rgb.shape[0]],
                            pdf_rotation_degrees=sheet.get_rotation(),
                            pdf_coordinates='displayed page; intrinsic PDF rotation applied by PDFium')
            finally:
                sheet.close()
    else:
        if page != 1:
            raise ValueError('--page is only supported for PDF')
        with Image.open(path) as im:
            if im.width * im.height > max_pixels:
                raise ValueError('Input exceeds --max-pixels; no automatic resizing is performed')
            if getattr(im, 'n_frames', 1) != 1:
                raise ValueError('Use a single static image')
            w, h = im.size
            orientation = im.getexif().get(274, 1)
            transforms = {
                1: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                2: [[-1, 0, w-1], [0, 1, 0], [0, 0, 1]],
                3: [[-1, 0, w-1], [0, -1, h-1], [0, 0, 1]],
                4: [[1, 0, 0], [0, -1, h-1], [0, 0, 1]],
                5: [[0, 1, 0], [1, 0, 0], [0, 0, 1]],
                6: [[0, -1, h-1], [1, 0, 0], [0, 0, 1]],
                7: [[0, -1, h-1], [-1, 0, w-1], [0, 0, 1]],
                8: [[0, 1, 0], [-1, 0, w-1], [0, 0, 1]],
            }
            oriented = ImageOps.exif_transpose(im).convert('RGBA')
            # Alpha is composited on white, rather than silently becoming black ink.
            base = Image.new('RGBA', oriented.size, 'white')
            rgb = np.array(Image.alpha_composite(base, oriented).convert('RGB'))
            meta.update(encoded_size_px=[w, h], exif_orientation=orientation,
                        encoded_to_pixel_matrix=transforms.get(orientation, transforms[1]),
                        pixel_to_encoded_matrix=np.linalg.inv(transforms.get(orientation, transforms[1])).tolist())
    h, w = rgb.shape[:2]
    meta.update(width=w, height=h)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), meta
