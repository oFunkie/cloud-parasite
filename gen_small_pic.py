from PIL import Image
import io

# 1. Créer une image (ex: 50x50 pixels)
img = Image.new('RGB', (50, 50), color='blue')

# 2. Sauvegarder dans un buffer
buffer = io.BytesIO()
img.save(buffer, format='BMP')
data = bytearray(buffer.getvalue())

# 3. Ajuster le tableau à exactement 3500 octets
target_size = 3400
if len(data) < target_size:
    data.extend(b'\x00' * (target_size - len(data)))
elif len(data) > target_size:
    data = data[:target_size]

# 4. Enregistrer sur le disque
with open('image_3500bytes.bmp', 'wb') as f:
    f.write(data)

print(f"Taille finale : {len(data)} octets")