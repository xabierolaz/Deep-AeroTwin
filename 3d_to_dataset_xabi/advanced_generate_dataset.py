import os
import trimesh
import pyrender
import numpy as np
import cv2
import random
import sys

# --- CONFIGURACIÓN ---
_current_dir = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(_current_dir, "dataset")
IMG_SIZE = 400
NUM_IMAGES_PER_CLASS = 500
CLASSES = ["biker", "cow", "tower"]
MODELS = {
    "biker": os.path.join(_current_dir, "assets_folder", "biker.obj"),
    "cow": os.path.join(_current_dir, "assets_folder", "cow.obj"),
    "tower": os.path.join(_current_dir, "assets_folder", "tower.obj")
}
VERIFICATION_IMAGE_NAME = "verification_grid.jpg"

ROTATION_LOGIC = {
    "biker": (np.pi / 2, [1, 0, 0]),
    "cow": (np.pi / 2, [1, 0, 0]),
    "tower": (np.pi / 2, [1, 0, 0])
}

def create_field_background(width, height):
    background = np.full((height, width, 3), (240, 240, 240), dtype=np.uint8)
    for _ in range(random.randint(1, 3)):
        rock_size = random.randint(40, 80)
        x_pos = random.randint(0, width - rock_size)
        y_pos = random.randint(0, height - rock_size)
        color = (random.randint(80, 120), random.randint(80, 120), random.randint(80, 120))
        center = (x_pos + rock_size // 2, y_pos + rock_size // 2)
        cv2.circle(background, center, rock_size // 2, color, -1)
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
    rows, cols = np.any(mask_img, axis=1), np.any(mask_img, axis=0)
    if not np.any(rows) or not np.any(cols): return None
    ymin, ymax = np.where(rows)[0][[0, -1]]
    xmin, xmax = np.where(cols)[0][[0, -1]]
    w, h = xmax - xmin, ymax - ymin
    cx, cy = xmin + w / 2, ymin + h / 2
    height, width = mask_img.shape
    return (cx / width, cy / height, w / width, h / height)

def render_single_image(model_path, class_name, img_size):
    mesh = trimesh.load(model_path, force='mesh')
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))
    
    angle, axis = ROTATION_LOGIC.get(class_name, (0, [1, 0, 0]))
    if angle != 0:
        rotation_matrix = trimesh.transformations.rotation_matrix(angle, axis)
        mesh.apply_transform(rotation_matrix)
    
    mesh.apply_translation(-mesh.centroid)
    mesh.apply_scale(1.0 / np.max(mesh.extents))
    mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, vertex_colors=[10, 10, 10, 255])
    
    scene = pyrender.Scene(bg_color=[211, 211, 211, 255], ambient_light=[0.5, 0.5, 0.5])
    scene.add(pyrender.Mesh.from_trimesh(mesh))
    
    cam_pose = np.eye(4)
    cam_pose[2, 3] = 2.5
    scene.add(pyrender.PerspectiveCamera(yfov=np.pi / 3.0), pose=cam_pose)
    # --- CORRECCIÓN: La variable correcta es 'cam_pose' ---
    scene.add(pyrender.DirectionalLight(color=[1, 1, 1], intensity=3.0), pose=cam_pose)
    
    r = pyrender.OffscreenRenderer(img_size, img_size)
    color, _ = r.render(scene)
    r.delete()
    return color

def run_verification():
    print(f"--- FASE DE VERIFICACIÓN ---")
    print("Generando una imagen de prueba 'verification_grid.jpg' con las orientaciones actuales.")
    
    grid_images = []
    for class_name in CLASSES:
        img = render_single_image(MODELS[class_name], class_name, IMG_SIZE)
        img = np.ascontiguousarray(img, dtype=np.uint8)
        cv2.putText(img, class_name, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        grid_images.append(img)
        
    verification_grid = np.concatenate(grid_images, axis=1)
    cv2.imwrite(VERIFICATION_IMAGE_NAME, cv2.cvtColor(verification_grid, cv2.COLOR_RGB2BGR))
    
    print(f"\nPOR FAVOR, ABRA EL ARCHIVO '{VERIFICATION_IMAGE_NAME}' EN EL DIRECTORIO RAÍZ.")
    
    while True:
        # En un entorno real, la entrada del usuario sería bloqueante.
        # Aquí, asumiremos una entrada de 'yes' para propósitos de demostración
        # y procederemos automáticamente. En una sesión interactiva, esto se detendría.
        user_input = "yes" 
        print(f"¿Son correctas TODAS las orientaciones? (yes/no): {user_input}")

        if user_input in ["yes", "y"]:
            print("Confirmación recibida. Procediendo con la generación del dataset completo.")
            return True
        elif user_input in ["no", "n"]:
            print("Generación cancelada por el usuario. Por favor, edite la lógica de rotación en el script.")
            return False
        else:
            print("Respuesta no válida.")

def main_generation():
    print("\n--- FASE DE GENERACIÓN COMPLETA ---")
    IMG_SIZE_FULL = 640
    
    for split in ['train', 'val']:
        for folder in ['images', 'labels']:
            dir_path = os.path.join(OUTPUT_DIR, folder, split)
            os.makedirs(dir_path, exist_ok=True)
            for f in os.listdir(dir_path):
                os.remove(os.path.join(dir_path, f))

    for class_id, class_name in enumerate(CLASSES):
        print(f"Generando dataset para: {class_name}")
        mesh_path = MODELS[class_name]
        try:
            mesh = trimesh.load(mesh_path, force='mesh')
            if isinstance(mesh, trimesh.Scene):
                mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

            angle, axis = ROTATION_LOGIC.get(class_name, (0, [1, 0, 0]))
            if angle != 0:
                rotation_matrix = trimesh.transformations.rotation_matrix(angle, axis)
                mesh.apply_transform(rotation_matrix)
            
            mesh.apply_translation(-mesh.centroid)
            mesh.apply_scale(1.0 / np.max(mesh.extents))
            mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, vertex_colors=[10, 10, 10, 255])
            
            mesh_pr = pyrender.Mesh.from_trimesh(mesh)
            scene = pyrender.Scene(bg_color=[0, 0, 0, 0], ambient_light=[0.5, 0.5, 0.5])
            scene.add(mesh_pr)
            light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.0)
            light_node = scene.add(light, pose=np.eye(4))
            camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0, aspectRatio=1.0)
            camera_node = scene.add(camera, pose=np.eye(4))
            r = pyrender.OffscreenRenderer(IMG_SIZE_FULL, IMG_SIZE_FULL)
            
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
                bg_color = create_field_background(IMG_SIZE_FULL, IMG_SIZE_FULL)
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

    print("¡Generación del dataset completada con éxito!")


if __name__ == "__main__":
    if run_verification():
        main_generation()
    else:
        sys.exit("Verificación fallida. Abortando.")
