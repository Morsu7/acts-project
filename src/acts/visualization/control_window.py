import os
import tornado.web
import tornado.template

class TrafficLightResourceHandler(tornado.web.RequestHandler):
    def get(self, path=None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        if path == "style.css":
            css_path = os.path.join(base_dir, "static", "style.css")
            if os.path.exists(css_path):
                self.set_header("Content-Type", "text/css")
                with open(css_path, "r") as f:
                    self.write(f.read())
                return
            self.send_error(404)
            return

        template_dir = os.path.join(base_dir, "templates")
        loader = tornado.template.Loader(template_dir)
        overview = self.application.model.get_traffic_light_overview()
        
        html = loader.load("traffic_lights.html").generate(
            port=self.application.port, 
            overview=overview
        )
        self.write(html)

    def post(self):
        traffic_light_id = self.get_body_argument("traffic_light_id", default="")
        if traffic_light_id:
            self.application.model.toggle_traffic_light(traffic_light_id)
        self.redirect("/traffic-lights")