from flask import Blueprint, current_app, jsonify, request, send_file
from utils.dicom_reader import ct_slice_info, get_rtstruct_name, parse_rtstruct
from utils.config import dicom_original_path, dicom_modified_path, prefix, suffix_length, margin, hu_mask
from utils.synthetic_bolus import load_ct_images, create_mask_from_structure, merge_masks, save_modified_ct_series, rtstructure, integrity, summarize
import io
import zipfile

structures = Blueprint("structures", __name__)
slice_data = Blueprint("slice_data", __name__)
upload_routes = Blueprint("upload_routes", __name__)
generate_synthetic_ct = Blueprint("generate_synthetic_ct", __name__)
validate = Blueprint("validate", __name__)
download = Blueprint("download", __name__)

@upload_routes.route("/upload_dicom_folder", methods=["POST"])
def upload_dicom_folder():
    for file in dicom_original_path.iterdir():
        file.unlink()
    for file in dicom_modified_path.iterdir():
        file.unlink()
    try:
        files = request.files.getlist("files")
        if not files:
            return jsonify({"error": "No files received"}), 400

        saved_files = []
        for f in files:
            save_path = dicom_original_path / f.filename
            save_path.parent.mkdir(parents=True, exist_ok=True) 
            f.save(str(save_path))
            saved_files.append(f.filename)

        return jsonify({"status": "success", "files": saved_files}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@slice_data.route("/slice_data")
def get_slice_info():
    slices, uid_to_index, origin, spacing = ct_slice_info(dicom_original_path)

    current_app.config["uid_to_index"] = uid_to_index
    current_app.config["origin"] = origin
    current_app.config["spacing"] = spacing

    return jsonify({"slices": slices})

@structures.route("/structures")
def get_structures():
    uid_to_index = current_app.config["uid_to_index"]
    origin = current_app.config["origin"]
    spacing = current_app.config["spacing"]
    
    rtstruct = get_rtstruct_name(dicom_original_path)    
    structures, for_mask = parse_rtstruct(dicom_original_path, rtstruct, uid_to_index, origin, spacing[:2])

    return jsonify({"structures": structures, "for_mask": for_mask})


@generate_synthetic_ct.route("/generate_synthetic_ct", methods=["POST"])
def generate():
    for file in dicom_modified_path.iterdir():
        file.unlink()

    roi_number = request.get_json()
    indexed_dict, uid_to_index, origin, spacing = ct_slice_info(dicom_original_path)

    # RTSTRUCT path
    rtstruct_path = dicom_original_path / get_rtstruct_name(dicom_original_path)

    # Sort CT slices for processing
    sorted_slices = load_ct_images(dicom_original_path)

    # Parameters for mask    
    raw_mask = (hu_mask-indexed_dict[0]['intercept'])/indexed_dict[0]['slope']
    
    # Generate singular mask from potentially multiple boluses
    all_masks, stats = create_mask_from_structure(spacing, origin, rtstruct_path, margin, raw_mask, roi_number)
    mask_dict = merge_masks(all_masks)

    # Create new synthetic CT 
    save_modified_ct_series(sorted_slices, raw_mask, mask_dict, rtstruct_path, prefix, suffix_length, dicom_modified_path)

    # Create new RTSTRUCT file with new UID and bolus type set to CONTROL
    rtstruct_mod = rtstructure(rtstruct_path, prefix, suffix_length, roi_number)
    rtstruct_mod.save_as(dicom_modified_path / 'RS.Struct_mod.dcm')

    slices2, uid_to_index2, origin2, spacing2 = ct_slice_info(dicom_modified_path)

    return jsonify({"status": "success", "slices2": slices2, "mask_uids": list(mask_dict.keys()), "uid_to_index2": uid_to_index2, 'stats': stats})

@validate.route("/validate", methods=["POST"])
def validate_synthetic_bolus():
    uids = request.get_json()
    original = load_ct_images(dicom_original_path)
    modified = load_ct_images(dicom_modified_path)
    integrity_ok, integrity_ko = integrity(original, modified)
    uid_index_dict = uids['a']
    modified_slices = uids['b']

    if modified_slices.sort()==integrity_ko.sort():
        unmodified_indices = [uid_index_dict[k] for k in integrity_ok]
        unmodified_indices.sort()
        modified_indices = [uid_index_dict[k] for k in integrity_ko]
        modified_indices.sort()

        return jsonify({"status": "success", "modified": summarize(modified_indices), "unmodified": summarize(unmodified_indices)})
    else: 
        return jsonify({"status": "failed", "modified": summarize(modified_indices), "unmodified": summarize(unmodified_indices)})

@download.route("/download", methods=["POST"])
def download_files():
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_STORED) as zipf:
        for file in dicom_modified_path.rglob("*"):
            arcname = file.relative_to(dicom_modified_path)
            zipf.write(file, arcname)
    memory_file.seek(0)
    return send_file(memory_file, as_attachment=True, download_name="archive.zip", mimetype="application/zip")
