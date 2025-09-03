from flask import Flask, render_template, send_from_directory
import os
from routes.routes import (
    upload_routes,
    slice_data,
    structures,
    generate_synthetic_ct,
    validate,
    download,
)

# --------------------
# Flask app setup
# --------------------
app = Flask(__name__, static_folder="static", template_folder="templates")

# --------------------
# Register API blueprints
# --------------------
app.register_blueprint(upload_routes, url_prefix="/api")
app.register_blueprint(slice_data, url_prefix="/api")
app.register_blueprint(structures, url_prefix="/api")
app.register_blueprint(generate_synthetic_ct, url_prefix="/api")
app.register_blueprint(validate, url_prefix="/api")
app.register_blueprint(download, url_prefix="/api")

# --------------------
# Vue frontend integration
# --------------------

# Root route serves index.html
@app.route("/")
def index():
    return render_template("index.html")

# Catch-all route for Vue router & static assets
@app.route("/<path:path>")
def catch_all(path):
    # Check if the requested file exists in static/
    static_path = os.path.join(app.static_folder, path)
    if os.path.exists(static_path):
        return send_from_directory(app.static_folder, path)
    # Otherwise serve Vue's index.html
    return render_template("index.html")

# --------------------
# Run app
# --------------------
if __name__ == "__main__":
    app.run(port=8000, debug=True)
