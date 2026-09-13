import os
import shutil
import re
from pathlib import Path

class CalibrationManager:
    def __init__(self):
        # Persistent storage in the user's home directory
        self.base_dir = Path.home() / ".config" / "RF_Recon_App" / "calibrations"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_cal_dir(self, model, uid) -> str:
        """
        Returns the path to the calibration directory for a specific device,
        or None if it doesn't exist or is empty.
        """
        try:
            model_str = f"{int(model):03d}"
        except (ValueError, TypeError):
            model_str = str(model)
            
        try:
            uid_str = f"{int(uid):016x}"
        except (ValueError, TypeError):
            uid_str = str(uid)
        
        target_dir = self.base_dir / f"{model_str}_{uid_str}"
        
        if target_dir.exists() and any(target_dir.iterdir()):
            # Also ensure local CalFile/ directory has these calibration files
            try:
                local_cal = Path.cwd() / "CalFile"
                local_cal.mkdir(parents=True, exist_ok=True)
                for f in target_dir.glob("*.txt"):
                    shutil.copy2(f, local_cal / f.name)
            except Exception:
                pass
            return str(target_dir)
        return None

    def import_cal_files(self, source_dir: str) -> tuple[bool, str]:
        """
        Scans a source directory for Harogic calibration files, extracts their
        Model and UID from the filename, and copies them to the persistent storage.
        
        Returns:
            (success_bool, message)
        """
        source_path = Path(source_dir)
        if not source_path.exists() or not source_path.is_dir():
            return False, f"Source directory {source_dir} does not exist."

        imported_count = 0
        # Typical format: 066_5230500d00220016_ifacal.txt
        pattern = re.compile(r"^(\d{3})_([a-fA-F0-9]{16})_.*\.txt$")
        
        try:
            for file_path in source_path.glob("*.txt"):
                match = pattern.match(file_path.name)
                if match:
                    model_str, uid_str = match.groups()
                    target_dir = self.base_dir / f"{model_str}_{uid_str}"
                    target_dir.mkdir(parents=True, exist_ok=True)
                    
                    shutil.copy2(file_path, target_dir / file_path.name)
                    imported_count += 1
                    
            if imported_count > 0:
                return True, f"Successfully imported {imported_count} calibration files."
            else:
                return False, "No valid Harogic calibration files found in the selected directory."
                
        except Exception as e:
            return False, f"Error importing calibration files: {e}"

    def save_dragged_files(self, file_paths: list[str], model: int, uid: int) -> bool:
        """
        Saves a list of dragged file paths into the persistent directory for the given model/uid.
        """
        model_str = f"{model:03d}"
        uid_str = f"{uid:016x}"
        target_dir = self.base_dir / f"{model_str}_{uid_str}"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            for path in file_paths:
                src = Path(path)
                if src.exists() and src.is_file():
                    shutil.copy2(src, target_dir / src.name)
            return True
        except Exception:
            return False

    def get_available_calibrations(self) -> list[tuple[int, int]]:
        """
        Returns a list of tuples (model, uid) for all currently stored calibrations.
        """
        calibrations = []
        if not self.base_dir.exists():
            return calibrations
            
        for child in self.base_dir.iterdir():
            if child.is_dir():
                parts = child.name.split('_')
                if len(parts) == 2:
                    try:
                        model = int(parts[0])
                        uid = int(parts[1], 16)
                        calibrations.append((model, uid))
                    except ValueError:
                        pass
        return calibrations

    def clear_calibration(self, model: int, uid: int) -> bool:
        """
        Forcefully deletes the calibration directory for the specified model and uid.
        """
        model_str = f"{model:03d}"
        uid_str = f"{uid:016x}"
        target_dir = self.base_dir / f"{model_str}_{uid_str}"
        
        if target_dir.exists() and target_dir.is_dir():
            try:
                shutil.rmtree(target_dir)
                return True
            except Exception:
                return False
        return False
