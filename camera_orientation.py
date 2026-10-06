"""Shared upright camera transform for snapshots and shot recordings."""
import json
from pathlib import Path

def rotation():
    value=json.loads((Path(__file__).resolve().parent/'camera-orientation.json').read_text())['rotation']
    if type(value) is not int or value not in (0,90,180,270):
        raise ValueError('Camera rotation must be 0, 90, 180 or 270 degrees')
    return value

def video_filter(angle=None):
    angle=rotation() if angle is None else angle
    transforms={0:'',90:'transpose=1,',180:'hflip,vflip,',270:'transpose=2,'}
    if angle not in transforms:raise ValueError('Invalid camera rotation')
    return transforms[angle]+('scale=-2:640' if angle in (90,270) else 'scale=640:-2')

def standoff_limit():
    # Same target pixel size relative to the short edge after a 16:9 rotation.
    return 11.25 if rotation() in (90,270) else 20.0
