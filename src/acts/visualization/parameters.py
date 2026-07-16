from mesa.visualization.UserParam import Slider, Choice
import os

def discover_manual_scenarios():
    choices = ["Procedurale"]
    try:
        import acts.city_model.demo as demo_pkg
        demo_dir = os.path.dirname(demo_pkg.__file__)
    
        
        if os.path.exists(demo_dir) and os.path.isdir(demo_dir):
            files = os.listdir(demo_dir)
            
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    scenario_name = file.replace(".py", "")
                    choices.append(f"Manuale: {scenario_name}")
    except Exception as e:
        print(f"Errore durante la scoperta degli scenari manuali: {e}")
                    
    return choices


def get_model_params():

    return {
        "config_type": Choice(
            "Configurazione Mappa",
            value="Procedurale",
            choices=discover_manual_scenarios()
        ),

        "num_cars": Slider(
            "Numero di Auto",
            10,
            1,
            50
        ),

        "num_intersections": 16
    }