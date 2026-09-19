"""
VIF framework: VIF directory under user_interaction, selected file from config.
Payload for PutVIFData is built from VIF XML via XMLProcessor.process_xml(); same shape as HAR.
"""
from .vif_framework import (
    VifFramework,
    _repo_root,
    _resolve_output_dir,
    _get_vif_options_from_config,
    DEFAULT_VIF_DIR,
)
from .xml_processor import XMLProcessor

__all__ = [
    "VifFramework",
    "XMLProcessor",
    "_repo_root",
    "_resolve_output_dir",
    "_get_vif_options_from_config",
    "DEFAULT_VIF_DIR",
]
