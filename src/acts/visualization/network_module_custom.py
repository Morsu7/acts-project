import os
from mesa_viz_tornado.ModularVisualization import D3_JS_FILE, VisualizationElement


class CustomNetworkModule(VisualizationElement):
    package_includes = [D3_JS_FILE]
    local_includes = ["NetworkModule_d3_custom.js"]
    local_dir = os.path.join(os.path.dirname(__file__), "static")

    def __init__(self, portrayal_method, canvas_width=500, canvas_height=500):
        self.portrayal_method = portrayal_method
        self.canvas_height = canvas_height
        self.canvas_width = canvas_width
        new_element = f"new NetworkModule({self.canvas_width}, {self.canvas_height})"
        self.js_code = "elements.push(" + new_element + ");"

    def render(self, model):
        return self.portrayal_method(model.G)
