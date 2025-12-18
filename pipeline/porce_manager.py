#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PORCE MANAGER (Path Planning Core) v1.1 - FIXED
-----------------------------------------------
Corrección:
- UnboundLocalError resuelto: Se generan los obstáculos (Step 3) ANTES de usarlos
  en la validación de la meta (Boundary Sliding).
"""

import math
import heapq
from constants import EARTH_RADIUS_M, GRID_CELL_SIZE_M, SAFETY_DISTANCE_M

class Node:
    """Un nodo en el grid de pathfinding."""
    def __init__(self, x, y, parent=None):
        self.x = x
        self.y = y
        self.parent = parent
        self.g = 0  # Coste desde el inicio
        self.h = 0  # Heurística (distancia a meta)
        self.f = 0  # Coste total (g + h)

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y
    
    def __lt__(self, other):
        return self.f < other.f
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def __repr__(self):
        return f"Node({self.x}, {self.y})"

class PorcePlanner:
    def __init__(self):
        # Configuración del Grid
        self.cell_size = GRID_CELL_SIZE_M  # Metros por celda
        self.safety_radius_m = SAFETY_DISTANCE_M # Radio de seguridad alrededor del obstáculo
        self.grid_radius_cells = 40 # Radio del grid local (40 celdas * 5m = 200m de horizonte)
        
    def latlon_to_meters(self, lat_ref, lon_ref, lat, lon):
        """Convierte Lat/Lon a offset en metros (North, East) relativo a un punto de referencia."""
        dlat = math.radians(lat - lat_ref)
        dlon = math.radians(lon - lon_ref)
        
        # Aproximación plana local (suficiente para grids pequeños < 1km)
        north_m = dlat * EARTH_RADIUS_M
        east_m = dlon * EARTH_RADIUS_M * math.cos(math.radians(lat_ref))
        
        return north_m, east_m

    def meters_to_latlon(self, lat_ref, lon_ref, north_m, east_m):
        """Convierte offset en metros a Lat/Lon."""
        dlat = north_m / EARTH_RADIUS_M
        # Evitar división por cero en polos
        cos_lat = math.cos(math.radians(lat_ref)) or 0.000001
        dlon = east_m / (EARTH_RADIUS_M * cos_lat)
        
        new_lat = lat_ref + math.degrees(dlat)
        new_lon = lon_ref + math.degrees(dlon)
        return new_lat, new_lon

    def _get_neighbors(self, node, grid_obstacles):
        """Genera vecinos válidos (8 direcciones)."""
        children = []
        # (dx, dy)
        moves = [
            (0, -1), (0, 1), (-1, 0), (1, 0),       # Ortogonales
            (-1, -1), (-1, 1), (1, -1), (1, 1)      # Diagonales
        ]
        
        for dx, dy in moves:
            nx, ny = node.x + dx, node.y + dy
            
            # 1. Chequear límites del Grid Local (Hard limit)
            if abs(nx) > self.grid_radius_cells or abs(ny) > self.grid_radius_cells:
                continue
                
            # 2. Chequear Colisiones
            if (nx, ny) in grid_obstacles:
                continue
                
            children.append(Node(nx, ny, node))
            
        return children

    def plan_route(self, start_lat, start_lon, end_lat, end_lon, obstacles):
        """
        Calcula una ruta segura usando A*.
        Retorna: Lista de dicts [{'lat':..., 'lon':...}, ...] o None si falla.
        """
        # 1. Definir Centro del Grid (Usamos la posición del dron como (0,0))
        ref_lat, ref_lon = start_lat, start_lon
        
        # 2. Convertir Meta a Grid (Coordenadas crudas)
        goal_n, goal_e = self.latlon_to_meters(ref_lat, ref_lon, end_lat, end_lon)
        
        # 3. Mapear Obstáculos al Grid (MOVIDO ANTES DEL USO)
        # ------------------------------------------------------------------
        grid_obstacles = set()
        safety_cells = math.ceil(self.safety_radius_m / self.cell_size)
        
        for obs in obstacles:
            # Posición del obstáculo relativa al dron
            obs_n, obs_e = self.latlon_to_meters(ref_lat, ref_lon, obs['lat'], obs['lon'])
            ox = int(obs_e / self.cell_size)
            oy = int(obs_n / self.cell_size)
            
            # Inflar (Cuadrado simple por eficiencia)
            for dx in range(-safety_cells, safety_cells + 1):
                for dy in range(-safety_cells, safety_cells + 1):
                    grid_obstacles.add((ox + dx, oy + dy))

        # CORRECCIÓN: Permitir escape si el dron ya está "técnicamente" dentro del radio
        if (0,0) in grid_obstacles:
            grid_obstacles.remove((0,0))
        # ------------------------------------------------------------------

        # 4. Procesar Meta (Clamping y Boundary Sliding)
        # Si la meta está fuera del grid, proyectarla al borde.
        grid_radius_m = self.grid_radius_cells * self.cell_size
        dist_to_goal = math.sqrt(goal_n**2 + goal_e**2)
        
        if dist_to_goal > grid_radius_m:
            # Escalar vector para poner la meta justo en el borde del grid
            scale = grid_radius_m / dist_to_goal
            goal_n *= scale
            goal_e *= scale
            
        goal_x = int(goal_e / self.cell_size)
        goal_y = int(goal_n / self.cell_size)
        
        # Asegurar que incluso con redondeo no se salga de limites
        goal_x = max(-self.grid_radius_cells, min(self.grid_radius_cells, goal_x))
        goal_y = max(-self.grid_radius_cells, min(self.grid_radius_cells, goal_y))
        
        # --- MEJORA LITERATURA: BOUNDARY SLIDING ---
        # Ahora sí podemos chequear grid_obstacles porque ya está definido
        if (goal_x, goal_y) in grid_obstacles:
            print("[PORCE] Meta ideal bloqueada. Buscando salida alternativa en borde...")
            found_alt = False
            best_dist = float('inf')
            alt_x, alt_y = goal_x, goal_y
            
            # Buscar en un radio razonable alrededor del punto de choque
            search_range = 10 # Celdas
            for dx in range(-search_range, search_range+1):
                for dy in range(-search_range, search_range+1):
                    cand_x, cand_y = goal_x + dx, goal_y + dy
                    
                    if abs(cand_x) > self.grid_radius_cells or abs(cand_y) > self.grid_radius_cells:
                        continue
                        
                    if (cand_x, cand_y) not in grid_obstacles:
                        dist = math.sqrt(dx**2 + dy**2)
                        if dist < best_dist:
                            best_dist = dist
                            alt_x, alt_y = cand_x, cand_y
                            found_alt = True
            
            if found_alt:
                goal_x, goal_y = alt_x, alt_y
                print(f"[PORCE] Salida alternativa encontrada en ({goal_x}, {goal_y})")
            else:
                print("[PORCE] CRITICO: Muro de obstaculos infranqueable en direccion meta.")
                return None

        # 5. Algoritmo A*
        start_node = Node(0, 0)
        end_node = Node(goal_x, goal_y)

        # Validación final rápida
        if (goal_x, goal_y) in grid_obstacles:
            return None 

        open_list = []
        closed_set = set()
        
        heapq.heappush(open_list, start_node)
        
        iterations = 0
        max_iterations = 10000 
        
        while open_list:
            iterations += 1
            if iterations > max_iterations:
                print("[PORCE] A* Timeout: No se encontró ruta.")
                return None
            
            current_node = heapq.heappop(open_list)
            closed_set.add((current_node.x, current_node.y))
            
            if abs(current_node.x - end_node.x) <= 1 and abs(current_node.y - end_node.y) <= 1:
                path = []
                curr = current_node
                while curr:
                    east_m = curr.x * self.cell_size
                    north_m = curr.y * self.cell_size
                    lat, lon = self.meters_to_latlon(ref_lat, ref_lon, north_m, east_m)
                    path.append({'lat': lat, 'lon': lon})
                    curr = curr.parent
                return path[::-1] 
            
            children = self._get_neighbors(current_node, grid_obstacles)
            
            for child in children:
                if (child.x, child.y) in closed_set:
                    continue
                
                is_diagonal = (child.x != current_node.x) and (child.y != current_node.y)
                move_cost = 1.414 if is_diagonal else 1.0
                
                child.g = current_node.g + move_cost
                child.h = math.sqrt((child.x - end_node.x)**2 + (child.y - end_node.y)**2)
                child.f = child.g + child.h
                
                heapq.heappush(open_list, child)
                
        return None

if __name__ == '__main__':
    planner = PorcePlanner()
    print("Testing PorcePlanner...")
    obstacles = [{'lat': 0.00018, 'lon': 0.0}] 
    path = planner.plan_route(0, 0, 0.00036, 0, obstacles)
    if path:
        print(f"Ruta encontrada: {len(path)} pasos.")
    else:
        print("Ruta no encontrada.")