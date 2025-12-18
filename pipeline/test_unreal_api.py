import unittest
import json
import sys
import os
from unittest.mock import MagicMock

# Mockear modulos de MAVLink que requieren conexion real
sys.modules['pymavlink'] = MagicMock()
sys.modules['pymavlink.mavutil'] = MagicMock()

# Importar la app Flask del flight_controller
# Necesitamos agregar el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flight_controller import app, state

class TestUnrealAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        
        # Simular un estado de dron activo
        state['telemetry'] = {
            'lat': 42.123,
            'lon': -1.456,
            'alt': 100.0,
            'last_update': 9999999999, # Futuro para simular activo
            'heading': 90.0,
            'armed': True,
            'groundspeed': 15.0,
            'mode': 'GUIDED'
        }

    def test_api_states_format(self):
        """Verificar que /api/states devuelve el formato OpenSky correcto"""
        print("\n[TEST] Probando endpoint /api/states (Unreal Integration)...")
        
        response = self.app.get('/api/states')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        
        # Verificar estructura raiz
        self.assertIn('time', data)
        self.assertIn('states', data)
        
        # Verificar contenido de states
        states = data['states']
        self.assertTrue(len(states) > 0, "Deberia haber al menos un vehiculo")
        
        vehicle = states[0]
        
        # Verificar longitud del array OpenSky (debe ser 17 elementos)
        # [icao, callsign, country, time, last, lon, lat, alt, ground, vel, hdg, vert, sensors, geo_alt, squawk, spi, src]
        self.assertEqual(len(vehicle), 17, "El formato OpenSky debe tener 17 campos")
        
        # Verificar datos criticos
        self.assertEqual(vehicle[0], "ARDU001") # ICAO
        self.assertAlmostEqual(vehicle[5], -1.456) # Lon
        self.assertAlmostEqual(vehicle[6], 42.123) # Lat
        self.assertEqual(vehicle[10], 90.0) # Heading
        
        print(f"[OK] Formato verificado: {vehicle[:7]}...")

if __name__ == '__main__':
    unittest.main()
