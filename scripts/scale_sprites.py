import os
from PIL import Image, ImageSequence

SPRITES_DIR = 'sprites'
SCALE_FACTOR = 4

def scale_gif(path):
    try:
        with Image.open(path) as im:
            # Check if it's a GIF
            if getattr(im, "is_animated", False):
                frames = []
                for frame in ImageSequence.Iterator(im):
                    # Resize each frame
                    # First, if it was already upscaled with interpolation, we might want to downscale first?
                    # But let's assume we just want to ensure it's pixelated.
                    # If the user says it's blurry, maybe it's already large but interpolated.
                    # Let's try to resize to original (e.g. 64x64) then back up?
                    # Or just resize to target size with NEAREST.
                    
                    # If the image is already 256x256, resizing to 256x256 with NEAREST won't fix blur if the pixels are already blended.
                    # We might need to downscale then upscale.
                    # Let's assume original size was around 64x64.
                    
                    w, h = frame.size
                    if w >= 256:
                        # Downscale first to recover pixels?
                        frame = frame.resize((w // SCALE_FACTOR, h // SCALE_FACTOR), Image.NEAREST)
                    
                    # Upscale
                    new_size = (frame.size[0] * SCALE_FACTOR, frame.size[1] * SCALE_FACTOR)
                    frame = frame.resize(new_size, Image.NEAREST)
                    frames.append(frame)
                
                # Save
                frames[0].save(
                    path,
                    save_all=True,
                    append_images=frames[1:],
                    optimize=False,
                    duration=im.info.get('duration', 100),
                    loop=im.info.get('loop', 0),
                    disposal=2 # Restore to background
                )
                print(f"Scaled {path} (Animated)")
            else:
                # Static image
                w, h = im.size
                if w >= 256:
                    im = im.resize((w // SCALE_FACTOR, h // SCALE_FACTOR), Image.NEAREST)
                
                new_size = (im.size[0] * SCALE_FACTOR, im.size[1] * SCALE_FACTOR)
                im = im.resize(new_size, Image.NEAREST)
                im.save(path)
                print(f"Scaled {path} (Static)")
                
    except Exception as e:
        print(f"Error scaling {path}: {e}")

def main():
    if not os.path.exists(SPRITES_DIR):
        print("Sprites directory not found.")
        return

    for filename in os.listdir(SPRITES_DIR):
        if filename.lower().endswith(('.gif', '.png')):
            path = os.path.join(SPRITES_DIR, filename)
            scale_gif(path)

if __name__ == '__main__':
    main()
