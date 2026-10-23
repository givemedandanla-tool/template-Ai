"""Shared typed-path recognition: hashes and historical original names are not current assets."""
from pathlib import Path,PureWindowsPath

PATH_KEYS={'path','preview','svg','pdf','png','jpg','image','vector','raster','thumbnail','approval_file','model_file','checkpoint_file','current_path','cache_path','font_path','model_path','source_path','directory'}


def is_asset_path(key,value):
    return (isinstance(value,str) and bool(value) and key!='original_path' and
            (key in PATH_KEYS or key.endswith('_path')) and
            (Path(value).is_absolute() or PureWindowsPath(value).is_absolute()))
