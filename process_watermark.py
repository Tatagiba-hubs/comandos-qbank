from PIL import Image
import numpy as np

src_path = r"C:\Users\joaot\.gemini\antigravity\brain\5991f4b5-837b-471e-9885-6d8fd919dcbd\comandos_skull_sketch_1773957583957.png"
dst_path = r"C:\Users\joaot\.gemini\antigravity\scratch\espcex_qbank\watermark.png"

try:
    img = Image.open(src_path).convert("RGBA")
    data = np.array(img)
    
    # We want true black lines with alpha transparency.
    # Convert white (or near-white) to transparent.
    r, g, b, a = data.T
    
    # Tolerância alta para remover bordas sujas
    white_areas = (r > 150) & (g > 150) & (b > 150)
    
    data[..., :-1][white_areas.T] = (255, 255, 255) # keep colors
    data[..., -1][white_areas.T] = 0 # set alpha to 0
    
    # Para o preto (desenho), a gente força ele ser preto puro
    black_areas = (r <= 150) & (g <= 150) & (b <= 150)
    data[..., :-1][black_areas.T] = (0, 0, 0)
    
    img2 = Image.fromarray(data)
    img2.save(dst_path)
    print("SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
