import os
import trimesh
import pyrender
import numpy as np
import cv2
import random

# Configuración
OUTPUT_DIR = "D:/ArduPilot_SITL_Install/3d_to_dataset_xabi/dataset"
IMG_SIZE = 640
NUM_IMAGES_PER_CLASS = 500
CLASSES = ["biker", "cow", "tower"]

# Rutas de los modelos (.obj)
MODELS = {
    "biker": "D:/ArduPilot_SITL_Install/biker.obj",
    "cow": "D:/ArduPilot_SITL_Install/cow.obj",
    "tower": "D:/ArduPilot_SITL_Install/tower.obj"
}

def create_field_background(width, height):
    # Base de tierra
    background = np.full((height, width, 3), (139, 115, 85), dtype=np.uint8)
    
    # Parches de hierba/arbustos
    for _ in range(30):
        patch_size_w = random.randint(50, 150)
        patch_size_h = random.randint(50, 150)
        x_pos = random.randint(0, width - patch_size_w)
        y_pos = random.randint(0, height - patch_size_h)
        color = random.choice([(34, 139, 34), (85, 107, 47), (107, 142, 35)])
        center = (x_pos + patch_size_w // 2, y_pos + patch_size_h // 2)
        axes = (patch_size_w // 2, patch_size_h // 2)
        angle = random.randint(0, 360)
        cv2.ellipse(background, center, axes, angle, 0, 360, color, -1)

    # --- MODIFICACIÓN: Añadir "rocas" para dificultar la detección ---
    for _ in range(random.randint(1, 3)): # Añadir de 1 a 3 rocas
        rock_size = random.randint(80, 120)
        x_pos = random.randint(0, width - rock_size)
        y_pos = random.randint(0, height - rock_size)
        color = (105, 105, 105) # Gris oscuro
        center = (x_pos + rock_size // 2, y_pos + rock_size // 2)
        cv2.circle(background, center, rock_size // 2, color, -1)

    noise = np.random.randint(-15, 15, (height, width, 3), dtype=np.int16)
    background = np.clip(background.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    return background

def get_cam_pose(distance, elevation, azimuth):
    camera_pose = np.eye(4)
    elevation = np.radians(elevation)
    azimuth = np.radians(azimuth)
    x = distance * np.cos(elevation) * np.sin(azimuth)
    y = distance * np.cos(elevation) * np.cos(azimuth)
    z = distance * np.sin(elevation)
    camera_location = np.array([x, y, z])
    forward = -camera_location / np.linalg.norm(camera_location)
    up_temp = np.array([0, 0, 1])
    right = np.cross(forward, up_temp)
    if np.linalg.norm(right) < 1e-6: right = np.array([1, 0, 0])
    right = right / np.linalg.norm(right)
    up = np.cross(right, forward)
    up = up / np.linalg.norm(up)
    camera_pose[:3, 0] = right
    camera_pose[:3, 1] = up
    camera_pose[:3, 2] = -forward
    camera_pose[:3, 3] = camera_location
    return camera_pose

def get_bbox_from_mask(mask_img):
    rows = np.any(mask_img, axis=1)
    cols = np.any(mask_img, axis=0)
    if not np.any(rows) or not np.any(cols): return None
    ymin, ymax = np.where(rows)[0][[0, -1]]
    xmin, xmax = np.where(cols)[0][[0, -1]]
    w_px = xmax - xmin
    h_px = ymax - ymin
    cx = xmin + w_px / 2
    cy = ymin + h_px / 2
    height, width = mask_img.shape
    return (cx / width, cy / height, w_px / width, h_px / height)

def process_mesh(mesh_path, class_name, class_id):
    print(f"Procesando {class_name} desde {mesh_path}...")
    try:
        mesh = trimesh.load(mesh_path, force='mesh')
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

        # --- FINAL CORRECTION: Unified rotation for all models ---
        # Rotar +90 grados en el eje X para poner todos los modelos de pie.
        rotation_matrix = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
        mesh.apply_transform(rotation_matrix)
        
        mesh.apply_translation(-mesh.centroid)
        scale = 1.0 / np.max(mesh.extents)
        mesh.apply_scale(scale)

        mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, vertex_colors=[10, 10, 10, 255])
        mesh_pr = pyrender.Mesh.from_trimesh(mesh)
        scene = pyrender.Scene(bg_color=[0, 0, 0, 0], ambient_light=[0.5, 0.5, 0.5])
        scene.add(mesh_pr)
        light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.0)
        light_node = scene.add(light, pose=np.eye(4))
        camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0, aspectRatio=1.0)
        camera_node = scene.add(camera, pose=np.eye(4))
        r = pyrender.OffscreenRenderer(IMG_SIZE, IMG_SIZE)
        
        for i in range(NUM_IMAGES_PER_CLASS):
            split = "train" if random.random() < 0.8 else "val"
            dist = random.uniform(1.5, 3.0)
            elev = random.uniform(5, 45)
            azim = random.uniform(0, 360)
            pose = get_cam_pose(dist, elev, azim)
            scene.set_pose(camera_node, pose)
            scene.set_pose(light_node, pose)
            color, depth = r.render(scene)
            mask = depth > 0
            bbox = get_bbox_from_mask(mask)
            if bbox is None: continue
            filename = f"{class_name}_{i:04d}"
            img_path = os.path.join(OUTPUT_DIR, "images", split, filename + ".jpg")
            lbl_path = os.path.join(OUTPUT_DIR, "labels", split, filename + ".txt")
            bg_color = create_field_background(IMG_SIZE, IMG_SIZE)
            fg_img = color.copy()
            alpha_mask = (mask[:, :, np.newaxis]).astype(np.uint8)
            final_img = np.where(alpha_mask, fg_img, bg_color)
            cv2.imwrite(img_path, cv2.cvtColor(final_img, cv2.COLOR_RGB2BGR))
            with open(lbl_path, "w") as f:
                f.write(f"{class_id} {bbox[0]:.6f} {bbox[1]:.6f} {bbox[2]:.6f} {bbox[3]:.6f}\n")
        r.delete()
        print(f"  -> Generadas imagenes para {class_name}")
    except Exception as e:
        print(f"Error procesando {class_name}: {e}")

if __name__ == "__main__":
    print("Iniciando generación de dataset con rotación y fondos finales.")
    for split in ['train', 'val']:
        os.makedirs(os.path.join(OUTPUT_DIR, 'images', split), exist_ok=True)
        os.makedirs(os.path.join(OUTPUT_DIR, 'labels', split), exist_ok=True)

    for split in ['train', 'val']:
        for TIPO in ['images', 'labels']:
            dir_path = os.path.join(OUTPUT_DIR, TIPO, split)
            if os.path.exists(dir_path):
                for f in os.listdir(dir_path):
                    os.remove(os.path.join(dir_path, f))

    for class_id, class_name in enumerate(CLASSES):
        model_path = MODELS[class_name]
        if os.path.exists(model_path):
            process_mesh(model_path, class_name, class_id)
        else:
            print(f"No se encontró: {model_path}")
    print("Generación completada.")
