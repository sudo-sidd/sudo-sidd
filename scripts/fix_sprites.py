import os
from PIL import Image, ImageSequence

SPRITES_DIR = '/home/zoryu/projects/sudo-sidd/sprites'
TARGET_SIZE = 256
ORIGINAL_SIZE = 64

def process_gif(filepath):
    print(f"Processing {filepath}...")
    try:
        with Image.open(filepath) as im:
            frames = []
            # Iterate over frames
            for frame in ImageSequence.Iterator(im):
                # Convert to RGBA to handle transparency and coalescing
                frame = frame.convert('RGBA')
                
                # Downscale to original resolution to "clean" artifacts if any
                # We use NEAREST to snap back to grid if it was just a bad upscale
                # If it's really blurry, this might lose detail, but for pixel art it's usually the best bet
                small = frame.resize((ORIGINAL_SIZE, ORIGINAL_SIZE), resample=Image.NEAREST)
                
                # Upscale back to target size with NEAREST
                large = small.resize((TARGET_SIZE, TARGET_SIZE), resample=Image.NEAREST)
                
                # Convert back to P mode for GIF compatibility if needed, 
                # but saving as GIF usually handles quantization. 
                # Better to keep as RGBA or RGB for now and let the saver handle it,
                # or quantize explicitly.
                # For pixel art, we want to preserve the palette.
                
                # To ensure crispness, we can quantize to a small palette?
                # Let's just append the RGB/RGBA image.
                frames.append(large)

            if not frames:
                print(f"No frames found in {filepath}")
                return

            # Save
            # duration per frame
            duration = im.info.get('duration', 100)
            loop = im.info.get('loop', 0)
            
            output_path = filepath # Overwrite
            
            # Saving
            frames[0].save(
                output_path,
                save_all=True,
                append_images=frames[1:],
                optimize=False,
                duration=duration,
                loop=loop,
                disposal=2 # Restore to background color. Helps with transparency artifacts.
            )
            print(f"Saved {output_path}")

    except Exception as e:
        print(f"Error processing {filepath}: {e}")

def main():
    for filename in os.listdir(SPRITES_DIR):
        if filename.lower().endswith('.gif'):
            filepath = os.path.join(SPRITES_DIR, filename)
            process_gif(filepath)

if __name__ == '__main__':
    main()
