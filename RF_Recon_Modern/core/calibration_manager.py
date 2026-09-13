"""
calibration_manager.py - Per-Device Calibration File Subsystem for Freqon.
Maintains persistent storage linked by Analyzer Serial Number (Device UID) and Model.
Supports auto-staging into active working directories before Device_Open, auto-migration,
detailed file introspection, and batch import/export.
"""

import os
import shutil
import re
import json
from pathlib import Path
from datetime import datetime


class CalibrationManager:
    """
    Manages Harogic spectrum analyzer calibration files segregated by Serial Number / Device UID.
    """
    def __init__(self):
        # Primary persistent directory under ~/.config/Freqon/calibrations
        self.base_dir = Path.home() / ".config" / "Freqon" / "calibrations"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Legacy directory for auto-migration
        self.legacy_dir = Path.home() / ".config" / "RF_Recon_App" / "calibrations"
        
        # Ingest legacy and local CalFile calibrations on startup
        self._auto_migrate_and_seed()

    def _format_keys(self, model, uid) -> tuple[str, str]:
        try:
            model_str = f"{int(model):03d}"
        except (ValueError, TypeError):
            model_str = str(model).zfill(3)
            
        try:
            uid_str = f"{int(uid):016x}"
        except (ValueError, TypeError):
            uid_str = str(uid).lower()
            
        return model_str, uid_str

    def _auto_migrate_and_seed(self):
        """
        Migrates calibrations from legacy ~/.config/RF_Recon_App/calibrations/
        and seeds from the local project's CalFile/ folder if present.
        """
        try:
            # 1. Migrate legacy folder
            if self.legacy_dir.exists() and self.legacy_dir.is_dir():
                for dev_dir in self.legacy_dir.iterdir():
                    if dev_dir.is_dir():
                        dest_dir = self.base_dir / dev_dir.name
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        for f in dev_dir.glob("*"):
                            if f.is_file() and not (dest_dir / f.name).exists():
                                shutil.copy2(f, dest_dir / f.name)

            # 2. Seed from local project CalFile directory if present
            local_cal_dirs = [
                Path.cwd() / "CalFile",
                Path(__file__).resolve().parent.parent / "CalFile"
            ]
            for ldir in local_cal_dirs:
                if ldir.exists() and ldir.is_dir():
                    self.import_from_directory(str(ldir))
        except Exception as e:
            print(f"[CalibrationManager] Warning during auto-migration: {e}")

    def get_cal_dir(self, model, uid) -> Path | None:
        """
        Returns the Path to the calibration directory for a given model and UID if it exists and is populated.
        """
        model_str, uid_str = self._format_keys(model, uid)
        target_dir = self.base_dir / f"{model_str}_{uid_str}"
        if target_dir.exists() and any(target_dir.iterdir()):
            return target_dir
        return None

    def is_calibrated(self, model, uid) -> bool:
        """
        Returns True if the required RF and IF calibration files are present and non-empty.
        """
        cal_dir = self.get_cal_dir(model, uid)
        if not cal_dir:
            return False
        model_str, uid_str = self._format_keys(model, uid)
        rf_cal = cal_dir / f"{model_str}_{uid_str}_rfacal.txt"
        if_cal = cal_dir / f"{model_str}_{uid_str}_ifacal.txt"
        
        has_rf = rf_cal.exists() and rf_cal.stat().st_size > 100
        has_if = if_cal.exists() and if_cal.stat().st_size > 100
        return has_rf and has_if

    def get_cal_summary(self, model, uid) -> dict:
        """
        Returns a detailed dictionary describing the calibration status and constituent files for an analyzer.
        """
        model_str, uid_str = self._format_keys(model, uid)
        target_dir = self.base_dir / f"{model_str}_{uid_str}"
        
        meta = self._load_metadata(model, uid)
        
        summary = {
            "model": int(model) if str(model).isdigit() else 0,
            "model_str": model_str,
            "uid": int(uid, 16) if isinstance(uid, str) and all(c in "0123456789abcdefABCDEF" for c in uid) else int(uid) if isinstance(uid, int) else 0,
            "uid_str": uid_str,
            "alias": meta.get("alias", f"Analyzer {model_str}-{uid_str[-4:].upper()}"),
            "dir_path": str(target_dir),
            "rfacal": {"present": False, "filename": "", "path": "", "size_bytes": 0, "points": 0},
            "ifacal": {"present": False, "filename": "", "path": "", "size_bytes": 0, "points": 0},
            "config": {"present": False, "filename": "", "path": "", "size_bytes": 0, "ampcomp_links": []},
            "ampcomp_files": [],
            "license_files": [],
            "other_files": [],
            "status": "missing",
            "last_updated": meta.get("last_updated", "Unknown")
        }

        if not target_dir.exists():
            return summary

        for f in target_dir.iterdir():
            if not f.is_file():
                continue
            name = f.name
            size = f.stat().st_size
            
            if name.endswith("_rfacal.txt"):
                points = 0
                try:
                    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                        points = sum(1 for line in fp if line.strip() and not line.startswith("#"))
                except Exception:
                    pass
                summary["rfacal"] = {
                    "present": True,
                    "filename": name,
                    "path": str(f),
                    "size_bytes": size,
                    "points": points
                }
            elif name.endswith("_ifacal.txt"):
                points = 0
                try:
                    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                        points = sum(1 for line in fp if line.strip() and not line.startswith("#"))
                except Exception:
                    pass
                summary["ifacal"] = {
                    "present": True,
                    "filename": name,
                    "path": str(f),
                    "size_bytes": size,
                    "points": points
                }
            elif name.endswith("_config.txt") or name == "config.txt":
                ampcomps = []
                try:
                    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                        lines = fp.readlines()
                        for idx, l in enumerate(lines):
                            if "Enable" in l and idx + 1 < len(lines):
                                ampcomps.append(lines[idx + 1].strip())
                except Exception:
                    pass
                summary["config"] = {
                    "present": True,
                    "filename": name,
                    "path": str(f),
                    "size_bytes": size,
                    "ampcomp_links": ampcomps
                }
            elif "ampcomp" in name:
                summary["ampcomp_files"].append({
                    "filename": name,
                    "path": str(f),
                    "size_bytes": size
                })
            elif name.endswith(".lic") or "lic" in name:
                summary["license_files"].append({
                    "filename": name,
                    "path": str(f),
                    "size_bytes": size
                })
            elif not name.endswith(".json"):
                summary["other_files"].append({
                    "filename": name,
                    "path": str(f),
                    "size_bytes": size
                })

        has_rf = summary["rfacal"]["present"]
        has_if = summary["ifacal"]["present"]
        has_cfg = summary["config"]["present"]
        
        if has_rf and has_if and has_cfg:
            summary["status"] = "calibrated"
        elif has_rf and has_if:
            summary["status"] = "calibrated"
        elif has_rf or has_if:
            summary["status"] = "incomplete"
        else:
            summary["status"] = "missing"

        return summary

    def deploy_cal_files(self, model, uid, target_dir=None) -> bool:
        """
        Stages the calibration files for a specific analyzer (model, uid) into the target directory (default: ./CalFile).
        This guarantees that when Harogic libhtraapi.so invokes Device_Open, it loads the exact calibration for this hardware.
        """
        cal_dir = self.get_cal_dir(model, uid)
        if not cal_dir:
            return False

        model_str, uid_str = self._format_keys(model, uid)
        prefix = f"{model_str}_{uid_str}_"

        if target_dir is None:
            target_dir = Path.cwd() / "CalFile"
        else:
            target_dir = Path(target_dir)

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Remove any stale rfacal/ifacal/config from other devices in the active stage
            for existing in target_dir.glob("*"):
                if existing.is_file():
                    name = existing.name
                    if ("_rfacal.txt" in name or "_ifacal.txt" in name or "_config.txt" in name) and not name.startswith(prefix):
                        try:
                            existing.unlink()
                        except Exception:
                            pass
            
            # Copy all calibration, config, license, and ampcomp files into the active stage
            for f in cal_dir.glob("*"):
                if f.is_file() and not f.name.endswith(".json"):
                    dest = target_dir / f.name
                    shutil.copy2(f, dest)
            return True
        except Exception as e:
            print(f"[CalibrationManager] Failed to stage cal files to {target_dir}: {e}")
            return False

    def import_from_directory(self, source_dir: str) -> tuple[int, list[str]]:
        """
        Scans a directory for calibration files, extracting Model and UID from filenames.
        Files without a UID prefix (like ampcomp.txt) are copied into relevant or all device folders.
        """
        source_path = Path(source_dir)
        if not source_path.exists() or not source_path.is_dir():
            return 0, [f"Directory does not exist: {source_dir}"]

        pattern = re.compile(r"^(\d{3})_([a-fA-F0-9]{16})_.*\.txt$")
        imported_files = []
        general_files = []

        for f in source_path.glob("*"):
            if not f.is_file():
                continue
            name = f.name
            match = pattern.match(name)
            if match:
                model_str, uid_str = match.groups()
                dest_dir = self.base_dir / f"{model_str}_{uid_str}"
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest_dir / name)
                imported_files.append(name)
                self._touch_metadata(model_str, uid_str)
            elif "ampcomp" in name or name.endswith(".lic") or name == "config.txt":
                general_files.append(f)

        # Distribute general ampcomp/lic files to all existing calibration directories
        if general_files:
            for child in self.base_dir.iterdir():
                if child.is_dir():
                    for gf in general_files:
                        shutil.copy2(gf, child / gf.name)

        return len(imported_files) + len(general_files), imported_files

    def import_files_for_device(self, file_paths: list[str], model: int, uid: int) -> tuple[bool, str]:
        """
        Imports a list of files explicitly for a given Model and UID.
        If files lack the `{model}_{uid}_` prefix, they are renamed appropriately.
        """
        model_str, uid_str = self._format_keys(model, uid)
        target_dir = self.base_dir / f"{model_str}_{uid_str}"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        imported = 0
        try:
            for p_str in file_paths:
                p = Path(p_str)
                if not p.is_file():
                    continue
                name = p.name
                
                # Check if it already matches standard format
                if name.startswith(f"{model_str}_{uid_str}_"):
                    dest_name = name
                elif "_rfacal" in name:
                    dest_name = f"{model_str}_{uid_str}_rfacal.txt"
                elif "_ifacal" in name:
                    dest_name = f"{model_str}_{uid_str}_ifacal.txt"
                elif "_config" in name or name == "config.txt":
                    dest_name = f"{model_str}_{uid_str}_config.txt"
                else:
                    # Keep original filename for ampcomp, lic, etc.
                    dest_name = name
                    
                shutil.copy2(p, target_dir / dest_name)
                imported += 1
                
            self._touch_metadata(model_str, uid_str)
            return True, f"Successfully imported {imported} file(s) for Analyzer {model_str}_{uid_str}."
        except Exception as e:
            return False, f"Error saving files: {e}"

    def import_single_file_as(self, file_path: str, cal_type: str, model: int, uid: int) -> bool:
        """
        Explicitly imports a file as rfacal, ifacal, config, or ampcomp for a specific device.
        """
        src = Path(file_path)
        if not src.is_file():
            return False
            
        model_str, uid_str = self._format_keys(model, uid)
        target_dir = self.base_dir / f"{model_str}_{uid_str}"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        if cal_type == "rfacal":
            dest_name = f"{model_str}_{uid_str}_rfacal.txt"
        elif cal_type == "ifacal":
            dest_name = f"{model_str}_{uid_str}_ifacal.txt"
        elif cal_type == "config":
            dest_name = f"{model_str}_{uid_str}_config.txt"
        else:
            dest_name = src.name
            
        try:
            shutil.copy2(src, target_dir / dest_name)
            self._touch_metadata(model_str, uid_str)
            return True
        except Exception:
            return False

    def get_all_devices(self) -> list[dict]:
        """
        Returns a list of summaries for all analyzers currently stored in the calibration library.
        """
        devices = []
        if not self.base_dir.exists():
            return devices
            
        for child in sorted(self.base_dir.iterdir()):
            if child.is_dir():
                parts = child.name.split("_")
                if len(parts) >= 2:
                    model_str = parts[0]
                    uid_str = parts[1]
                    summary = self.get_cal_summary(model_str, uid_str)
                    devices.append(summary)
        return devices

    def set_device_alias(self, model, uid, alias: str):
        """
        Sets a user-friendly name/alias for an analyzer (e.g., 'Studio Rack NXE-100').
        """
        meta = self._load_metadata(model, uid)
        meta["alias"] = alias.strip()
        self._save_metadata(model, uid, meta)

    def delete_calibration(self, model, uid) -> bool:
        """
        Deletes the calibration directory and all files for the specified analyzer.
        """
        model_str, uid_str = self._format_keys(model, uid)
        target_dir = self.base_dir / f"{model_str}_{uid_str}"
        if target_dir.exists() and target_dir.is_dir():
            try:
                shutil.rmtree(target_dir)
                return True
            except Exception:
                return False
        return False

    def export_calibration(self, model, uid, export_dir: str) -> tuple[bool, str]:
        """
        Copies all calibration files for an analyzer into the specified export directory.
        """
        cal_dir = self.get_cal_dir(model, uid)
        if not cal_dir:
            return False, "No calibration files found for this analyzer."
            
        dest = Path(export_dir)
        try:
            dest.mkdir(parents=True, exist_ok=True)
            copied = 0
            for f in cal_dir.glob("*"):
                if f.is_file():
                    shutil.copy2(f, dest / f.name)
                    copied += 1
            return True, f"Exported {copied} file(s) to {export_dir}."
        except Exception as e:
            return False, f"Export failed: {e}"

    def _load_metadata(self, model, uid) -> dict:
        model_str, uid_str = self._format_keys(model, uid)
        meta_file = self.base_dir / f"{model_str}_{uid_str}" / "device_meta.json"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as fp:
                    return json.load(fp)
            except Exception:
                pass
        return {
            "alias": f"Analyzer {model_str}-{uid_str[-4:].upper()}",
            "model_str": model_str,
            "uid_str": uid_str,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

    def _save_metadata(self, model, uid, meta: dict):
        model_str, uid_str = self._format_keys(model, uid)
        target_dir = self.base_dir / f"{model_str}_{uid_str}"
        target_dir.mkdir(parents=True, exist_ok=True)
        meta_file = target_dir / "device_meta.json"
        meta["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            with open(meta_file, "w", encoding="utf-8") as fp:
                json.dump(meta, fp, indent=2)
        except Exception as e:
            print(f"[CalibrationManager] Failed to write metadata: {e}")

    def _touch_metadata(self, model_str, uid_str):
        meta = self._load_metadata(model_str, uid_str)
        self._save_metadata(model_str, uid_str, meta)
