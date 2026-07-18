import pytest
from unittest.mock import MagicMock
from acts.agents.traffic_light import (
    TrafficLightAgent, 
    Request, 
    ControlledDirection, 
    IncomingTrafficWave
)
from acts.agents.state import LightStatus

# ==========================================
# FIXTURES (Preparazione dell'ambiente)
# ==========================================

@pytest.fixture
def mock_model():
    """Crea un finto modello Mesa per isolare il semaforo dal resto della simulazione."""
    model = MagicMock()
    model.G = MagicMock()
    model.grid = MagicMock()
    model.intersection_meta = {
        "inter_1": {"phases": {"tl_1_dir0": 1, "tl_2_dir0": 2, "tl_3_dir0": 3}}
    }
    return model

@pytest.fixture
def basic_traffic_light(mock_model):
    """Fornisce un semaforo di base già inizializzato e pronto per i test."""
    controlled_dirs = [
        {"edges": [(0, 1), (0, 2)], "destinations": ["tl_ext_A", "tl_ext_B"], "phase_index": 1}
    ]
    
    tl = TrafficLightAgent(
        unique_id="tl_1",
        model=mock_model,
        intersection_id="inter_1",
        node_id=0,
        controlled_directions=controlled_dirs,
        inter_neighbors=3,
        outgoing_external_neighbors_travel_times={
            "tl_ext_A": 10, 
            "tl_ext_B": 15  
        }
    )
    return tl


# ==========================================
# TESTS
# ==========================================

def test_dataclasses_storage():
    """Verifica che le strutture dati semplici memorizzino i valori correttamente."""
    req = Request(requester_id="tl_2", requester_direction_id="dir_x", requester_score=15.0, request_clock=5, requester_phase=1)
    wave = IncomingTrafficWave(source_id="tl_ext_A", num_cars=10, expected_arrival_time=5)
    assert req.requester_id == "tl_2"
    assert req.requester_score == 15.0
    assert req.requester_phase == 1
    assert wave.num_cars == 10
    assert wave.expected_arrival_time == 5


def test_traffic_light_initialization(basic_traffic_light):
    """Verifica che il semaforo legga bene la configurazione e crei le direzioni."""
    tl = basic_traffic_light
    assert len(tl.directions) == 1
    direction = tl.directions[0]
    assert direction.direction_id == "tl_1_dir0"
    assert direction.destinations_ids == ["tl_ext_A", "tl_ext_B"]
    assert direction.phase_index == 1

def test_compute_score_with_incoming_waves(basic_traffic_light):
    """Verifica il calcolo dello score quando ci sono auto in arrivo da altri incroci."""
    tl = basic_traffic_light
    direction = tl.directions[0]
    direction.state.runtime.queue_length = 5
    direction.state.runtime.waiting_time = 2
    score_without_waves = tl._compute_score(direction)
    wave = IncomingTrafficWave(source_id="tl_ext_A", num_cars=10, expected_arrival_time=10)
    tl.possible_incoming_waves.append(wave)
    assert score_without_waves < tl._compute_score(direction)


def test_store_request_lamport_clock_logic(basic_traffic_light):
    """Verifica che vengano memorizzate solo le richieste con Lamport Clock più recente."""
    tl = basic_traffic_light
    tl._store_request("tl_2", "tl_2_dir0", requester_score=10.0, request_clock=1, requester_phase=1)
    assert tl.requests["tl_2_dir0"].requester_score == 10.0
    tl._store_request("tl_2", "tl_2_dir0", requester_score=50.0, request_clock=3, requester_phase=1)
    assert tl.requests["tl_2_dir0"].requester_score == 50.0
    tl._store_request("tl_2", "tl_2_dir0", requester_score=99.0, request_clock=2, requester_phase=1)
    assert tl.requests["tl_2_dir0"].requester_score == 50.0

def test_lamport_clock_synchronization(basic_traffic_light):
    """Verifica che il Lamport Clock si aggiorni correttamente ricevendo messaggi dal futuro."""
    tl = basic_traffic_light
    tl.lamport_clock = 5
    tl.directions[0].state.runtime.queue_length = 50 
    tl.directions[0].state.score = tl._compute_score(tl.directions[0])

    mock_msg = {
        "event": "REQUEST_GREEN", 
        "agent_id": "tl_2", 
        "clock": 10, 
        "data": {"direction_id": "tl_2_dir0", "queue_score": 10.0, "request_clock": 10, "phase_index": 2}
    }
    tl.get_messages = MagicMock(return_value=[mock_msg])
    tl.get_broadcast_messages = MagicMock(return_value=[])
    tl._receive_messages()
    assert tl.lamport_clock == 11

def test_distributed_consensus_to_turn_green(basic_traffic_light):
    """Verifica che il semaforo diventi verde SOLO dopo aver ricevuto tutti i permessi necessari."""
    tl = basic_traffic_light
    direction = tl.directions[0]
    direction.state.runtime.status = LightStatus.RED
    direction.state.request_clock = 5
    mock_messages = [
        {"event": "ALLOW_GREEN", "agent_id": "tl_2", "clock": 6, "data": {"target_tl_id": "tl_1", "target_direction_id": "tl_1_dir0", "request_clock": 5}},
        {"event": "ALLOW_GREEN", "agent_id": "tl_3", "clock": 7, "data": {"target_tl_id": "tl_1", "target_direction_id": "tl_1_dir0", "request_clock": 5}},
        {"event": "ALLOW_GREEN", "agent_id": "tl_4", "clock": 8, "data": {"target_tl_id": "tl_1", "target_direction_id": "tl_1_dir0", "request_clock": 5}}
    ]
    
    tl.get_messages = MagicMock(return_value=mock_messages)
    tl.get_broadcast_messages = MagicMock(return_value=[])
    tl._receive_messages()
    assert len(direction.state.permissions) == 3
    tl._decide_state()
    assert direction.state.runtime.status == LightStatus.GREEN
    assert len(direction.state.permissions) == 0

def test_starvation_prevention(basic_traffic_light):
    """
    Dimostra che la formula dello score impedisce la 'starvation': 
    poche auto che aspettano da molto tempo superano molte auto appena arrivate.
    """
    tl = basic_traffic_light
    direction = tl.directions[0]
    direction.state.runtime.queue_length = 1
    direction.state.runtime.waiting_time = 30
    direction.state.score = tl._compute_score(direction)
    req = Request(requester_id="tl_2", requester_direction_id="tl_2_dir0", requester_score=20.0, request_clock=10, requester_phase=2)
    assert tl._can_give_permission(req) is False

def test_allow_green_for_same_phase_regardless_of_score(basic_traffic_light):
    """
    Verifica che se due semafori appartengono alla stessa fase di traffico (non si scontrano),
    il permesso venga accordato anche se chi decide ha una coda immensa.
    """
    tl = basic_traffic_light
    direction = tl.directions[0]
    direction.state.runtime.queue_length = 10
    direction.state.runtime.waiting_time = 9
    direction.state.score = tl._compute_score(direction)
    req = Request(requester_id="tl_2", requester_direction_id="tl_2_dir0", requester_score=direction.state.score+1.0, request_clock=10, requester_phase=1)
    assert tl._can_give_permission(req) is True

def test_ignore_outdated_green_permissions(basic_traffic_light):
    """
    Verifica la resilienza di rete: un messaggio ALLOW_GREEN arrivato troppo tardi 
    (riferito a un ciclo precedente) viene scartato per evitare falsi verdi.
    """
    tl = basic_traffic_light
    direction = tl.directions[0]
    direction.state.request_clock = 20
    mock_msg = {
        "event": "ALLOW_GREEN", 
        "agent_id": "tl_2", 
        "clock": 22, # L'orologio di invio è aggiornato...
        "data": {
            "target_tl_id": "tl_1", 
            "target_direction_id": "tl_1_dir0", 
            "request_clock": 15 # ...ma il payload fa riferimento a una vecchia richiesta!
        }
    }
    tl._store_permission(mock_msg)
    assert len(direction.state.permissions) == 0

def test_state_machine_forces_yellow_phase(basic_traffic_light):
    """
    Verifica che il passaggio Verde -> Rosso passi obbligatoriamente per il Giallo 
    e rispetti i tempi configurati (YELLOW_TIME).
    """
    tl = basic_traffic_light
    direction = tl.directions[0]
    direction.state.runtime.status = LightStatus.GREEN
    direction.state.runtime.status_time = 10
    direction.state.must_turn_yellow = True
    tl._decide_state()
    assert direction.state.runtime.status == LightStatus.YELLOW
    assert direction.state.runtime.status_time == 0
    tl._decide_state()
    assert direction.state.runtime.status == LightStatus.YELLOW
    direction.state.runtime.status_time = tl.YELLOW_TIME
    tl._decide_state()
    assert direction.state.runtime.status == LightStatus.RED

def test_tie_breaking_equal_scores(basic_traffic_light):
    """
    Dimostra che in caso di parità di score (es. 10.0 vs 10.0), il sistema usa il 
    Lamport Clock e l'ID per decidere chi passa, evitando che entrambi diventino verdi.
    """
    tl = basic_traffic_light # Il suo ID è "tl_1"
    direction = tl.directions[0]
    direction.state.runtime.queue_length = 5
    direction.state.runtime.waiting_time = 1   
    direction.state.score = tl._compute_score(direction)
    direction.state.request_clock = 5
    req_older = Request(requester_id="tl_2", requester_direction_id="tl_2_dir0", requester_score=direction.state.score, request_clock=3, requester_phase=2)
    assert tl._can_give_permission(req_older) is True
    req_newer = Request(requester_id="tl_2", requester_direction_id="tl_2_dir0", requester_score=direction.state.score, request_clock=8, requester_phase=2)
    assert tl._can_give_permission(req_newer) is False
    req_tie = Request(requester_id="tl_2", requester_direction_id="tl_2_dir0", requester_score=direction.state.score, request_clock=5, requester_phase=2)
    assert tl._can_give_permission(req_tie) is False