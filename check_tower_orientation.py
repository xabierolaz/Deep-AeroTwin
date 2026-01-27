import os
import trimesh
import pyrender
import numpy as np
import cv2

def check_orientation():
    print("Verificando la orientación del modelo de la torre...")
    model_path = "D:/ArduPilot_SITL_Install/tower.obj"
    output_image_path = "D:/ArduPilot_SITL_Install/tower_test.jpg"
    
    try:
        mesh = trimesh.load(model_path, force='mesh')
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

        # --- Matriz de Rotación para Probar ---
        # Aplicamos la rotación que SÍ funcionó para Biker/Cow como base
        base_rotation = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
        # Y ahora una rotación adicional para la torre
        tower_adj_rotation = trimesh.transformations.rotation_matrix(np.pi / 2, [0, 0, 1])
        
        # Transformación combinada
        combined_transform = np.dot(tower_adj_rotation, base_rotation)
        mesh.apply_transform(combined_transform)
        # --- Fin Matriz de Rotación ---

        mesh.apply_translation(-mesh.centroid)
        scale = 1.0 / np.max(mesh.extents)
        mesh.apply_scale(scale)

        mesh.visual = trimesh.visual.ColorVisuals(mesh=mesh, vertex_colors=[10, 10, 10, 255])
        mesh_pr = pyrender.Mesh.from_trimesh(mesh)
        scene = pyrender.Scene(bg_color=[240, 240, 240], ambient_light=[0.5, 0.5, 0.5])
        scene.add(mesh_pr)
        
        light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=3.0)
        
        camera_pose = np.eye(4)
        camera_pose[2, 3] = 2 
        
        scene.add(pyrender.PerspectiveCamera(yfov=np.pi / 3.0), pose=camera_pose)
        scene.add(light, pose=camera_pose)
        
        r = pyrender.OffscreenRenderer(640, 640)
        color, _ = r.render(scene)
        r.delete()
        
        cv2.imwrite(output_image_path, cv2.cvtColor(color, cv2.COLOR_RGB2BGR))
        
        print(f"Imagen de prueba 'tower_test.jpg' actualizada. Por favor, verifíquela.")

    except Exception as e:
        print(f"Ocurrió un error: {e}")

if __name__ == "__main__":
    check_orientation()
