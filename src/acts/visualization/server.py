import time
import tornado.autoreload as autoreload

# Disattiva l'autoreload di Tornado a livello globale, PRIMA che
# ModularServer/Application lo avviino internamente (debug=True hardcoded
# in mesa_viz_tornado). Il modulo non espone un .stop() pubblico, quindi
# impediamo che .start() faccia qualcosa fin dall'inizio.
autoreload.start = lambda *args, **kwargs: None

from mesa.visualization.ModularVisualization import ModularServer
from acts.core.simulation import UnifiedCityModel
from acts.visualization.network_module_custom import CustomNetworkModule
from acts.visualization.portrayal import network_portrayal
from acts.visualization.parameters import get_model_params
from acts.visualization.control_window import TrafficLightResourceHandler
from tornado.web import StaticFileHandler
import os


class ACTSServer(ModularServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        template_path = os.path.join(os.path.dirname(__file__), "templates")
        self.settings["template_path"] = template_path
        self.settings["debug"] = False
        self.settings["autoreload"] = False

        self.add_handlers(
            r".*$",
            [
                (r"/traffic-lights/?", TrafficLightResourceHandler),
                (
                    r"/acts-static/(.*)",
                    StaticFileHandler,
                    {"path": os.path.join(os.path.dirname(__file__), "static")},
                ),
            ],
        )


def create_server():
    network = CustomNetworkModule(network_portrayal, 600, 600)
    server = ACTSServer(
        UnifiedCityModel,
        [network],
        "ACTS: Dynamic Simulator",
        get_model_params()
    )
    server.port = 8521
    return server