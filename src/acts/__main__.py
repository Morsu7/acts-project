from acts.visualization.server import create_server
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="mesa")

if __name__ == "__main__":
    print("Starting ACTS Server...")
    server = create_server()
    server.launch(open_browser=False)