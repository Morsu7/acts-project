import pytest
from unittest.mock import MagicMock, patch
from acts.agents.vehicle import VehicleAgent

@pytest.fixture
def mock_model():
    """Mock del CityModel per isolare il veicolo."""
    model = MagicMock()
    model.G = MagicMock()
    model.grid = MagicMock()
    model.random = MagicMock()
    return model

@pytest.fixture
def vehicle(mock_model):
    """Fornisce un VehicleAgent in stato QUEUED sul nodo 0."""
    # Disabilitiamo il replan_destination per testare solo il movimento base
    v = VehicleAgent(unique_id="car_0", model=mock_model, replan_destination=False)
    v.pos = 0
    return v

def test_vehicle_initialization(vehicle):
    """Verifica che il veicolo nasca nello stato corretto."""
    assert vehicle.state == "QUEUED"
    assert vehicle.travel_timer == 0

@patch("acts.agents.vehicle.find_constrained_path")
def test_vehicle_respects_red_light(mock_find_path, vehicle):
    """Verifica che il veicolo NON parta se il semaforo non è VERDE."""
    # Arrange: simuliamo un percorso pianificato [0, 1]
    vehicle.runtime.path = [0, 1]
    vehicle.runtime.destination = 1
    vehicle.model.G.has_edge.return_value = True
    
    # Simuliamo che l'arco (0 -> 1) abbia il semaforo ROSSO
    vehicle.model.G.get_edge_data.return_value = {"tl_state": "RED"}
    
    # Act
    vehicle.step()
    
    # Assert: Il veicolo deve rimanere QUEUED e non deve muoversi
    assert vehicle.state == "QUEUED"
    vehicle.model.grid.remove_agent.assert_not_called()

@patch("acts.agents.vehicle.find_constrained_path")
def test_vehicle_starts_driving_on_green(mock_find_path, vehicle):
    """Verifica la transizione a DRIVING e il calcolo del travel_timer."""
    vehicle.runtime.path = [0, 1]
    vehicle.runtime.destination = 1
    vehicle.model.G.has_edge.return_value = True
    
    # Simuliamo semaforo VERDE, lunghezza 30m e velocità 5m/tick
    vehicle.model.G.get_edge_data.return_value = {
        "tl_state": "GREEN",
        "length": 30.0,
        "max_speed": 5.0
    }
    
    # Act
    vehicle.step()
    
    # Assert
    assert vehicle.state == "DRIVING"
    # travel_timer = max(1, round(30 / 5)) = 6
    assert vehicle.travel_timer == 6
    assert vehicle.pos == (0, 1) # Si è spostato sull'arco

def test_vehicle_arrival_transition(vehicle):
    """Verifica che a fine corsa il veicolo torni QUEUED e si riposizioni sul nodo."""
    # Arrange: veicolo in transito che sta per finire il timer
    vehicle.runtime.status = "DRIVING"
    vehicle.pos = (0, 1)
    vehicle.runtime.path = [0, 1, 2] # Era sul nodo 0, sta andando all'1, poi andrà al 2
    vehicle.runtime.next_node_buffer = 1
    vehicle.runtime.travel_timer = 1 # Manca 1 solo tick all'arrivo
    
    # Act
    vehicle.step()
    
    # Assert
    assert vehicle.travel_timer == 0
    assert vehicle.state == "QUEUED"
    assert vehicle.runtime.path == [1, 2] # Il nodo 0 è stato rimosso (pop)
    vehicle.model.grid.place_agent.assert_called_with(vehicle, 1) # Riposizionato fisicamente sul nodo