from utils.config import dicom_original_path
import numpy as np
import pydicom
from pathlib import Path
import base64

# Load CT images and sort them by InstanceNumber, returns a dictionary with index : UID, etc
def ct_slice_info(path):
    ct_files = Path(path).glob("*.dcm")

    slices = []
    for file in ct_files:
        ds = pydicom.dcmread(file)
        if ds.Modality != 'CT':
            continue
        slices.append({
            "name":" ".join(part.capitalize() for part in reversed(str(ds.PatientName).split("^"))),
            "id": str(ds.PatientID),
            "dob": f"{str(ds.PatientBirthDate)[6:8]}/{str(ds.PatientBirthDate)[4:6]}/{str(ds.PatientBirthDate)[:4]}",
            "file_name": file.name,
            "uid": str(ds.SOPInstanceUID),
            "position": list(map(float, ds.ImagePositionPatient)),          
            "orientation": list(map(float, ds.ImageOrientationPatient)),    
            "spacing": list(map(float, ds.PixelSpacing)) + [float(ds.SliceThickness)],
            "rows": int(ds.Rows),
            "cols": int(ds.Columns),
            "buffer":  base64.b64encode(ds.PixelData).decode(),
            "slope": int(ds.RescaleSlope),
            "intercept": int(ds.RescaleIntercept)
        })

    # Sort using normal vector
    orientation = slices[0]["orientation"]
    normal = np.cross(orientation[:3], orientation[3:])
    reverse = normal[2] < 0
    slices.sort(key=lambda s: s["position"][2], reverse=reverse)

    uid_to_index = {s["uid"]: i for i, s in enumerate(slices)}

    return slices, uid_to_index, slices[0]['position'], slices[0]['spacing']
       
def get_rtstruct_name(dcm_dir):
    dcm_files = Path(dcm_dir).glob("*.dcm")
    for file in dcm_files:
        ds = pydicom.dcmread(file)
        if ds.Modality == 'RTSTRUCT':

            return file.name

def mm_to_voxel(points_mm, origin, spacing):
    arr = np.array(points_mm, dtype=np.float32).reshape(-1, 3)
    
    return ((arr[:, :2] - origin[:2]) / spacing[:2])

def parse_rtstruct(path, filename, uid_to_index, origin, spacing):
    fullpath = path / filename
    ds = pydicom.dcmread(fullpath)
    
    structures = []
    for_mask = []

    for roi, contours, observation in zip(ds.StructureSetROISequence, ds.ROIContourSequence, ds.RTROIObservationsSequence):
        name = roi.ROIName
        color = list(contours.ROIDisplayColor) if hasattr(contours.ROIDisplayColor, '__iter__') else []

        if observation.RTROIInterpretedType == 'BOLUS':
            for_mask.append([name, observation.ReferencedROINumber])

        structure_data = {}

        for contour_seq in contours.ContourSequence:
            sop_uid = contour_seq.ContourImageSequence[0].ReferencedSOPInstanceUID
            index = uid_to_index[sop_uid]

            voxel_coords = mm_to_voxel(contour_seq.ContourData, origin, spacing)      
            
            if index not in structure_data:
                structure_data[index] = []

            structure_data[index].append(voxel_coords.tolist())
        
        structures.append({
            "name": name,
            "color": color,
            "contours": structure_data
        })

    structures.sort(key=lambda d: d['name'])
    return structures, for_mask