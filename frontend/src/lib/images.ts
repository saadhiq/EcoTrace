/**
 * Resize a photo in the browser before upload: longest side <= maxSize px,
 * re-encoded as JPEG. Re-encoding through a canvas also drops EXIF metadata
 * (including GPS location), which is what we want for privacy.
 */
export async function resizeImage(source: Blob, maxSize = 1600, quality = 0.85): Promise<Blob> {
  const bitmap = await createImageBitmap(source);
  try {
    const scale = Math.min(1, maxSize / Math.max(bitmap.width, bitmap.height));
    const width = Math.round(bitmap.width * scale);
    const height = Math.round(bitmap.height * scale);
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas is not available");
    ctx.drawImage(bitmap, 0, 0, width, height);
    return await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("Could not encode image"))), "image/jpeg", quality),
    );
  } finally {
    bitmap.close();
  }
}
