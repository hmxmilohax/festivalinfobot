from configparser import ConfigParser
import PIL
from PIL import Image, ImageOps, ImageDraw
import numpy as np

def get_season_most_dominant_color() -> tuple[int, int, int]:
    with Image.open("bot/data/Logo/FNFest_pfp_s9.jpg") as img:
        img = img.convert('RGB')
        img = img.resize((100, 100))  # Resize for faster processing
        arr = np.array(img).reshape(-1, 3)

        # Calculate colorfulness as the standard deviation across RGB channels
        colorfulness = arr.std(axis=1)
        # Only keep pixels with low colorfulness (i.e., "white-looking" or grayish)
        mask = colorfulness < 15

        filtered_arr = arr[~mask]  # Exclude "white-looking" pixels

        # If all pixels are filtered out, fall back to original array
        if filtered_arr.size == 0:
            filtered_arr = arr

        # Group similar colors by rounding to nearest 16 (can adjust for more/less grouping)
        grouped_arr = (filtered_arr // 16) * 16

        # Find unique colors and their counts
        colors, counts = np.unique(grouped_arr, axis=0, return_counts=True)

        # Get indices of counts sorted descending
        sorted_indices = np.argsort(-counts)

        # Get the second most common color (if available)
        if len(sorted_indices) > 1:
            dominant_color = tuple(colors[sorted_indices[1]])
        else:
            dominant_color = tuple(colors[sorted_indices[0]])
        return dominant_color

def get_logo(colour) -> PIL.Image.Image:
    logo_path = 'bot/data/Logo/fest_tracker_no_gradient.png'
    img = Image.open(logo_path).convert('RGBA')

    dominant_color = colour
    arr = np.array(img)
    target_color = np.array([88, 253, 1, 255])
    tolerance = 30

    color_diff = np.linalg.norm(arr[:, :, :3] - target_color[:3], axis=-1)
    mask = color_diff < tolerance

    height = arr.shape[0]
    gradient = np.linspace(
        np.array([255, 255, 255]), 
        np.array(dominant_color), 
        height
    ).astype(np.uint8)

    for y in range(height):
        arr[y, mask[y]] = np.append(gradient[y], 255)

    result_img = Image.fromarray(arr)
    return result_img

def get_logo_with_circle_background(logo_path) -> PIL.Image.Image:
    img = Image.open(logo_path).convert('RGBA')
    size = img.size

    # Create a new image for the circle background
    circle_bg = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(circle_bg)

    # Draw a black circle with 10% opacity (alpha=25)
    radius = min(size) // 2
    center = (size[0] // 2, size[1] // 2)
    draw.ellipse(
        [
            (center[0] - radius, center[1] - radius),
            (center[0] + radius, center[1] + radius)
        ],
        fill=(0, 0, 0, 100)
    )

    # Composite the logo on top of the circle background
    combined = Image.alpha_composite(circle_bg, img)
    return combined

colour = [0,0,0]

pick = input("Select colour or enter your own? enter/2:")
if pick.strip() == "2":
    r = int(input("R (0-255): "))
    g = int(input("G (0-255): "))
    b = int(input("B (0-255): "))
    colour = (r, g, b)
else:
    colour = get_season_most_dominant_color()

logo_img = get_logo(colour)
logo_img.save("bot/data/Brand/logo.png", format="PNG")

logo_circ = get_logo_with_circle_background("bot/data/Brand/logo.png")
logo_circ.save("bot/data/Brand/logo_circle.png", format="PNG")