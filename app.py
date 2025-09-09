from flask import Flask, current_app, render_template, send_from_directory
from pathlib import Path
from routes.routes import upload_routes, slice_data, structures, generate_synthetic_ct, validate, download


app = Flask(__name__, static_folder="static", template_folder="templates")

app.register_blueprint(upload_routes, url_prefix="/api")
app.register_blueprint(slice_data, url_prefix="/api")
app.register_blueprint(structures, url_prefix="/api")
app.register_blueprint(generate_synthetic_ct, url_prefix="/api")
app.register_blueprint(validate, url_prefix="/api")
app.register_blueprint(download, url_prefix="/api")

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_vue(path):
    static_path = Path(current_app.static_folder) / path
    if path and static_path.exists():
        return send_from_directory(current_app.static_folder, path)
    return render_template("index.html")


if __name__ == "__main__":
    app.run(port=8000, debug=True)
