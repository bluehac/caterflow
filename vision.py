"""Bounded, ephemeral photo input. Decode and re-encode before model transmission."""
import base64
import io
import warnings

MAX_PHOTO_BYTES = 400_000
MAX_IMAGE_REQUEST = 550_000

def normalize_photo(photo):
    if not isinstance(photo, dict) or set(photo) != {'base64', 'consent'} or photo['consent'] is not True:
        raise ValueError('Explicit photo processing consent required')
    encoded = photo['base64']
    if not isinstance(encoded, str) or not 1 <= len(encoded) <= 533_336:
        raise ValueError('Photo is too large')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        raise ValueError('Invalid image encoding') from None
    if not 1 <= len(raw) <= MAX_PHOTO_BYTES:
        raise ValueError('Photo is too large')
    try:
        from PIL import Image, ImageOps
    except ImportError:
        raise RuntimeError('Photo support requires the optional Pillow dependency') from None
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ('JPEG', 'PNG') or getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('Use one JPEG or PNG photo')
                if not 1 <= image.width <= 4096 or not 1 <= image.height <= 4096 or image.width * image.height > 8_000_000:
                    raise ValueError('Image dimensions exceed limit')
                image.load()
                cleaned = ImageOps.exif_transpose(image).convert('RGB')
                cleaned.thumbnail((1280, 1280))
                # New pixels discard EXIF/GPS, filenames and embedded metadata.
                pixels = Image.new('RGB', cleaned.size)
                pixels.paste(cleaned)
                output = io.BytesIO()
                pixels.save(output, format='JPEG', quality=80)
        except Exception:
            raise ValueError('Photo could not be safely decoded') from None
    result = output.getvalue()
    if len(result) > MAX_PHOTO_BYTES:
        raise ValueError('Choose a smaller photo')
    return result
