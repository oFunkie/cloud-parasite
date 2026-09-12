import base64
import math

def encode_chunks(image_path, chunk_size=3950):
    with open(image_path, "rb") as file:
        file_content = file.read()

    b64_encoded_file = base64.b64encode(file_content).decode("ascii")
    len_image = len(b64_encoded_file)
    chunk_number = math.ceil(len_image / chunk_size)

    chunks = [b64_encoded_file[i * chunk_size : (i + 1) * chunk_size]
              for i in range(chunk_number)]

    print(f"Taille totale base64 : {len_image} caractères")
    print(f"Nombre de chunks : {len(chunks)}")
    return chunks

encode_chunks("medium_image.jpg")