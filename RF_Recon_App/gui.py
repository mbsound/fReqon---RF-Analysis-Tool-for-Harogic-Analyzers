import sys
import math
import json
import gzip
import numpy as np
import pyqtgraph as pg
import webbrowser
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem, QMenu, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QFrame, QDoubleSpinBox, QFileDialog, QMessageBox, QMenuBar,
    QSplitter, QSpinBox, QInputDialog, QSizePolicy, QApplication, QSizeGrip, QSplitterHandle,
    QComboBox, QCheckBox, QGridLayout, QDialog, QGroupBox, QScrollArea, QProgressBar, QRadioButton, QButtonGroup, QTreeWidget, QTreeWidgetItem, QSlider, QDialogButtonBox
)
from PyQt6.QtGui import QAction, QActionGroup, QPalette, QColor, QPainter, QValidator, QBrush, QPen, QPixmap, QIcon
from PyQt6.QtCore import Qt, QTimer, QSettings, QRectF, pyqtSignal, QPoint
import time
from device_controller import DeviceController
from calibration_manager import CalibrationManager
from fcc_database import FCCDatabaseManager
from ofcom_database import OfcomDatabaseManager
from dialogs import MissingCalDialog, DragDropCalDialog, ClearCalDialog, WaterfallSettingsDialog, QuickSettingsDialog, LaunchSettingsDialog
from dect_analyzer import DECTAnalyzerEngine, TDMATimeslotDialog, DECT_BANDS
from showlink_crmx_analyzer import ShowLinkCRMXEngine, ShowlinkMapDialog, SHOWLINK_CHANNELS
from transmitter_classifier import TransmitterClassifier
from PyQt6.QtCore import QObject

TV_CHANNEL_STANDARDS = {
    "North America": [
        {
            "start_ch": 2,
            "end_ch": 4,
            "start_freq": 54.0,
            "spacing": 6.0
        },
        {
            "start_ch": 5,
            "end_ch": 6,
            "start_freq": 76.0,
            "spacing": 6.0
        },
        {
            "start_ch": 7,
            "end_ch": 13,
            "start_freq": 174.0,
            "spacing": 6.0
        },
        {
            "start_ch": 14,
            "end_ch": 36,
            "start_freq": 470.0,
            "spacing": 6.0
        },
        {
            "start_ch": 37,
            "end_ch": 37,
            "start_freq": 608.0,
            "spacing": 6.0
        },
        {
            "custom_items": [
                {"id": "GB_616", "label": "GB", "display_name": "Guard Band (616-617)", "start": 616.0, "stop": 617.0, "type": "guard"},
                {"id": "DL_A", "label": "A", "display_name": "Downlink A (617-622)", "start": 617.0, "stop": 622.0, "type": "downlink"},
                {"id": "DL_B", "label": "B", "display_name": "Downlink B (622-627)", "start": 622.0, "stop": 627.0, "type": "downlink"},
                {"id": "DL_C", "label": "C", "display_name": "Downlink C (627-632)", "start": 627.0, "stop": 632.0, "type": "downlink"},
                {"id": "DL_D", "label": "D", "display_name": "Downlink D (632-637)", "start": 632.0, "stop": 637.0, "type": "downlink"},
                {"id": "DL_E", "label": "E", "display_name": "Downlink E (637-642)", "start": 637.0, "stop": 642.0, "type": "downlink"},
                {"id": "DL_F", "label": "F", "display_name": "Downlink F (642-647)", "start": 642.0, "stop": 647.0, "type": "downlink"},
                {"id": "DL_G", "label": "G", "display_name": "Downlink G (647-652)", "start": 647.0, "stop": 652.0, "type": "downlink"},
                {"id": "GB_652", "label": "GB", "display_name": "Guard Band (652-653)", "start": 652.0, "stop": 653.0, "type": "guard"},
                {"id": "UL_A", "label": "A", "display_name": "Uplink A (663-668)", "start": 663.0, "stop": 668.0, "type": "uplink"},
                {"id": "UL_B", "label": "B", "display_name": "Uplink B (668-673)", "start": 668.0, "stop": 673.0, "type": "uplink"},
                {"id": "UL_C", "label": "C", "display_name": "Uplink C (673-678)", "start": 673.0, "stop": 678.0, "type": "uplink"},
                {"id": "UL_D", "label": "D", "display_name": "Uplink D (678-683)", "start": 678.0, "stop": 683.0, "type": "uplink"},
                {"id": "UL_E", "label": "E", "display_name": "Uplink E (683-688)", "start": 683.0, "stop": 688.0, "type": "uplink"},
                {"id": "UL_F", "label": "F", "display_name": "Uplink F (688-693)", "start": 688.0, "stop": 693.0, "type": "uplink"},
                {"id": "UL_G", "label": "G", "display_name": "Uplink G (693-698)", "start": 693.0, "stop": 698.0, "type": "uplink"},
                *[
                    {
                        "id": ch,
                        "label": str(ch),
                        "display_name": f"DTV {ch} • LMR/SMR ({698.0 + (ch - 52) * 6.0:g}-{698.0 + (ch - 51) * 6.0:g})",
                        "start": 698.0 + (ch - 52) * 6.0,
                        "stop": 698.0 + (ch - 51) * 6.0,
                        "type": "lmr_smr"
                    }
                    for ch in range(52, 84)
                ],
                {
                    "id": "LMR_890",
                    "label": "LMR",
                    "display_name": "LMR/SMR (890-902)",
                    "start": 890.0,
                    "stop": 902.0,
                    "type": "lmr_smr"
                }
            ]
        }
    ],
    "UK": [
        {
            "start_ch": 21,
            "end_ch": 48,
            "start_freq": 470.0,
            "spacing": 8.0
        },
        {
            "custom_items": [
                {"id": "700_GB1", "label": "GB", "display_name": "700M Guard (694-703)", "start": 694.0, "stop": 703.0, "type": "guard"},
                {"id": "700_UL_1", "label": "1", "display_name": "700M Uplink 1 (703-708)", "start": 703.0, "stop": 708.0, "type": "uplink"},
                {"id": "700_UL_2", "label": "2", "display_name": "700M Uplink 2 (708-713)", "start": 708.0, "stop": 713.0, "type": "uplink"},
                {"id": "700_UL_3", "label": "3", "display_name": "700M Uplink 3 (713-718)", "start": 713.0, "stop": 718.0, "type": "uplink"},
                {"id": "700_UL_4", "label": "4", "display_name": "700M Uplink 4 (718-723)", "start": 718.0, "stop": 723.0, "type": "uplink"},
                {"id": "700_UL_5", "label": "5", "display_name": "700M Uplink 5 (723-728)", "start": 723.0, "stop": 728.0, "type": "uplink"},
                {"id": "700_UL_6", "label": "6", "display_name": "700M Uplink 6 (728-733)", "start": 728.0, "stop": 733.0, "type": "uplink"},
                {"id": "700_DL_1", "label": "1", "display_name": "700M Downlink 1 (758-763)", "start": 758.0, "stop": 763.0, "type": "downlink"},
                {"id": "700_DL_2", "label": "2", "display_name": "700M Downlink 2 (763-768)", "start": 763.0, "stop": 768.0, "type": "downlink"},
                {"id": "700_DL_3", "label": "3", "display_name": "700M Downlink 3 (768-773)", "start": 768.0, "stop": 773.0, "type": "downlink"},
                {"id": "700_DL_4", "label": "4", "display_name": "700M Downlink 4 (773-778)", "start": 773.0, "stop": 778.0, "type": "downlink"},
                {"id": "700_DL_5", "label": "5", "display_name": "700M Downlink 5 (778-783)", "start": 778.0, "stop": 783.0, "type": "downlink"},
                {"id": "700_DL_6", "label": "6", "display_name": "700M Downlink 6 (783-788)", "start": 783.0, "stop": 788.0, "type": "downlink"},
                {"id": "700_GB2", "label": "GB", "display_name": "Guard Band (788-791)", "start": 788.0, "stop": 791.0, "type": "guard"},
                {"id": "800_DL_1", "label": "1", "display_name": "800M Downlink 1 (791-796)", "start": 791.0, "stop": 796.0, "type": "downlink"},
                {"id": "800_DL_2", "label": "2", "display_name": "800M Downlink 2 (796-801)", "start": 796.0, "stop": 801.0, "type": "downlink"},
                {"id": "800_DL_3", "label": "3", "display_name": "800M Downlink 3 (801-806)", "start": 801.0, "stop": 806.0, "type": "downlink"},
                {"id": "800_DL_4", "label": "4", "display_name": "800M Downlink 4 (806-811)", "start": 806.0, "stop": 811.0, "type": "downlink"},
                {"id": "800_DL_5", "label": "5", "display_name": "800M Downlink 5 (811-816)", "start": 811.0, "stop": 816.0, "type": "downlink"},
                {"id": "800_DL_6", "label": "6", "display_name": "800M Downlink 6 (816-821)", "start": 816.0, "stop": 821.0, "type": "downlink"},
                {"id": "800_GB1", "label": "GB", "display_name": "800M Guard (821-823)", "start": 821.0, "stop": 823.0, "type": "guard"},
                {"id": "800_UL_1", "label": "1", "display_name": "800M Uplink 1 (832-837)", "start": 832.0, "stop": 837.0, "type": "uplink"},
                {"id": "800_UL_2", "label": "2", "display_name": "800M Uplink 2 (837-842)", "start": 837.0, "stop": 842.0, "type": "uplink"},
                {"id": "800_UL_3", "label": "3", "display_name": "800M Uplink 3 (842-847)", "start": 842.0, "stop": 847.0, "type": "uplink"},
                {"id": "800_UL_4", "label": "4", "display_name": "800M Uplink 4 (847-852)", "start": 847.0, "stop": 852.0, "type": "uplink"},
                {"id": "800_UL_5", "label": "5", "display_name": "800M Uplink 5 (852-857)", "start": 852.0, "stop": 857.0, "type": "uplink"},
                {"id": "800_UL_6", "label": "6", "display_name": "800M Uplink 6 (857-862)", "start": 857.0, "stop": 862.0, "type": "uplink"},
                {"id": "800_GB2", "label": "GB", "display_name": "Guard Band (862-863)", "start": 862.0, "stop": 863.0, "type": "guard"},
                # European PMR, Public Safety (Airwave TETRA), and Railway (GSM-R) in UK (Teal)
                {"id": "UK_TETRA_UL", "label": "TETRA", "display_name": "Airwave Emergency TETRA UL (380-385)", "start": 380.0, "stop": 385.0, "type": "lmr_smr"},
                {"id": "UK_PMR385_UL", "label": "PMR", "display_name": "Civil PMR UL (385-390)", "start": 385.0, "stop": 390.0, "type": "lmr_smr"},
                {"id": "UK_TETRA_DL", "label": "TETRA", "display_name": "Airwave Emergency TETRA DL (390-395)", "start": 390.0, "stop": 395.0, "type": "lmr_smr"},
                {"id": "UK_PMR395_DL", "label": "PMR", "display_name": "Civil PMR DL (395-400)", "start": 395.0, "stop": 400.0, "type": "lmr_smr"},
                {"id": "UK_PMR410", "label": "PMR", "display_name": "Commercial PMR/PAMR (410-430)", "start": 410.0, "stop": 430.0, "type": "lmr_smr"},
                {"id": "UK_PMR446", "label": "446", "display_name": "PMR446 License-Free (446.0-446.2)", "start": 446.0, "stop": 446.2, "type": "lmr_smr"},
                {"id": "UK_PMR450", "label": "PMR", "display_name": "Utility & Private PMR (450-470)", "start": 450.0, "stop": 470.0, "type": "lmr_smr"},
                {"id": "UK_PMR870", "label": "PMR", "display_name": "Digital PMR / IoT (870-876)", "start": 870.0, "stop": 876.0, "type": "lmr_smr"},
                {"id": "UK_GSMR_UL", "label": "GSM-R", "display_name": "Network Rail GSM-R UL (876-880)", "start": 876.0, "stop": 880.0, "type": "lmr_smr"},
                {"id": "UK_PMR915", "label": "PMR", "display_name": "Digital PMR / IoT (915-921)", "start": 915.0, "stop": 921.0, "type": "lmr_smr"},
                {"id": "UK_GSMR_DL", "label": "GSM-R", "display_name": "Network Rail GSM-R DL (921-925)", "start": 921.0, "stop": 925.0, "type": "lmr_smr"}
            ]
        }
    ],
    "Spain": [
        {
            "start_ch": 21,
            "end_ch": 48,
            "start_freq": 470.0,
            "spacing": 8.0
        },
        {
            "custom_items": [
                {"id": "700_GB1", "label": "GB", "display_name": "700M Guard (694-703)", "start": 694.0, "stop": 703.0, "type": "guard"},
                {"id": "700_UL_1", "label": "1", "display_name": "700M Uplink 1 (703-708)", "start": 703.0, "stop": 708.0, "type": "uplink"},
                {"id": "700_UL_2", "label": "2", "display_name": "700M Uplink 2 (708-713)", "start": 708.0, "stop": 713.0, "type": "uplink"},
                {"id": "700_UL_3", "label": "3", "display_name": "700M Uplink 3 (713-718)", "start": 713.0, "stop": 718.0, "type": "uplink"},
                {"id": "700_UL_4", "label": "4", "display_name": "700M Uplink 4 (718-723)", "start": 718.0, "stop": 723.0, "type": "uplink"},
                {"id": "700_UL_5", "label": "5", "display_name": "700M Uplink 5 (723-728)", "start": 723.0, "stop": 728.0, "type": "uplink"},
                {"id": "700_UL_6", "label": "6", "display_name": "700M Uplink 6 (728-733)", "start": 728.0, "stop": 733.0, "type": "uplink"},
                {"id": "700_DL_1", "label": "1", "display_name": "700M Downlink 1 (758-763)", "start": 758.0, "stop": 763.0, "type": "downlink"},
                {"id": "700_DL_2", "label": "2", "display_name": "700M Downlink 2 (763-768)", "start": 763.0, "stop": 768.0, "type": "downlink"},
                {"id": "700_DL_3", "label": "3", "display_name": "700M Downlink 3 (768-773)", "start": 768.0, "stop": 773.0, "type": "downlink"},
                {"id": "700_DL_4", "label": "4", "display_name": "700M Downlink 4 (773-778)", "start": 773.0, "stop": 778.0, "type": "downlink"},
                {"id": "700_DL_5", "label": "5", "display_name": "700M Downlink 5 (778-783)", "start": 778.0, "stop": 783.0, "type": "downlink"},
                {"id": "700_DL_6", "label": "6", "display_name": "700M Downlink 6 (783-788)", "start": 783.0, "stop": 788.0, "type": "downlink"},
                {"id": "700_GB2", "label": "GB", "display_name": "Guard Band (788-791)", "start": 788.0, "stop": 791.0, "type": "guard"},
                {"id": "800_DL_1", "label": "1", "display_name": "800M Downlink 1 (791-796)", "start": 791.0, "stop": 796.0, "type": "downlink"},
                {"id": "800_DL_2", "label": "2", "display_name": "800M Downlink 2 (796-801)", "start": 796.0, "stop": 801.0, "type": "downlink"},
                {"id": "800_DL_3", "label": "3", "display_name": "800M Downlink 3 (801-806)", "start": 801.0, "stop": 806.0, "type": "downlink"},
                {"id": "800_DL_4", "label": "4", "display_name": "800M Downlink 4 (806-811)", "start": 806.0, "stop": 811.0, "type": "downlink"},
                {"id": "800_DL_5", "label": "5", "display_name": "800M Downlink 5 (811-816)", "start": 811.0, "stop": 816.0, "type": "downlink"},
                {"id": "800_DL_6", "label": "6", "display_name": "800M Downlink 6 (816-821)", "start": 816.0, "stop": 821.0, "type": "downlink"},
                {"id": "800_GB1", "label": "GB", "display_name": "800M Guard (821-823)", "start": 821.0, "stop": 823.0, "type": "guard"},
                {"id": "800_UL_1", "label": "1", "display_name": "800M Uplink 1 (832-837)", "start": 832.0, "stop": 837.0, "type": "uplink"},
                {"id": "800_UL_2", "label": "2", "display_name": "800M Uplink 2 (837-842)", "start": 837.0, "stop": 842.0, "type": "uplink"},
                {"id": "800_UL_3", "label": "3", "display_name": "800M Uplink 3 (842-847)", "start": 842.0, "stop": 847.0, "type": "uplink"},
                {"id": "800_UL_4", "label": "4", "display_name": "800M Uplink 4 (847-852)", "start": 847.0, "stop": 852.0, "type": "uplink"},
                {"id": "800_UL_5", "label": "5", "display_name": "800M Uplink 5 (852-857)", "start": 852.0, "stop": 857.0, "type": "uplink"},
                {"id": "800_UL_6", "label": "6", "display_name": "800M Uplink 6 (857-862)", "start": 857.0, "stop": 862.0, "type": "uplink"},
                {"id": "800_GB2", "label": "GB", "display_name": "Guard Band (862-863)", "start": 862.0, "stop": 863.0, "type": "guard"},
                # European PMR, Public Safety (SIRDEE TETRA), and Railway (GSM-R) in Spain (Teal)
                {"id": "ES_TETRA_UL", "label": "TETRA", "display_name": "SIRDEE Emergencias TETRA UL (380-385)", "start": 380.0, "stop": 385.0, "type": "lmr_smr"},
                {"id": "ES_PMR385_UL", "label": "PMR", "display_name": "PMR Civil UL (385-390)", "start": 385.0, "stop": 390.0, "type": "lmr_smr"},
                {"id": "ES_TETRA_DL", "label": "TETRA", "display_name": "SIRDEE Emergencias TETRA DL (390-395)", "start": 390.0, "stop": 395.0, "type": "lmr_smr"},
                {"id": "ES_PMR395_DL", "label": "PMR", "display_name": "PMR Civil DL (395-400)", "start": 395.0, "stop": 400.0, "type": "lmr_smr"},
                {"id": "ES_PMR410", "label": "PMR", "display_name": "PMR / PAMR Comercial (410-430)", "start": 410.0, "stop": 430.0, "type": "lmr_smr"},
                {"id": "ES_PMR446", "label": "446", "display_name": "PMR446 Uso Libre (446.0-446.2)", "start": 446.0, "stop": 446.2, "type": "lmr_smr"},
                {"id": "ES_PMR450", "label": "PMR", "display_name": "PMR Servicios / Smart Grid (450-470)", "start": 450.0, "stop": 470.0, "type": "lmr_smr"},
                {"id": "ES_PMR870", "label": "PMR", "display_name": "PMR Digital / IoT (870-876)", "start": 870.0, "stop": 876.0, "type": "lmr_smr"},
                {"id": "ES_GSMR_UL", "label": "GSM-R", "display_name": "ADIF Ferrocarril GSM-R UL (876-880)", "start": 876.0, "stop": 880.0, "type": "lmr_smr"},
                {"id": "ES_PMR915", "label": "PMR", "display_name": "PMR Digital / IoT (915-921)", "start": 915.0, "stop": 921.0, "type": "lmr_smr"},
                {"id": "ES_GSMR_DL", "label": "GSM-R", "display_name": "ADIF Ferrocarril GSM-R DL (921-925)", "start": 921.0, "stop": 925.0, "type": "lmr_smr"}
            ]
        }
    ]
}

DEFAULT_REGIONS = {
    "North America": [
        {"name": "VHF-Low", "start": 54.0, "stop": 88.0},
        {"name": "VHF-High", "start": 174.0, "stop": 216.0},
        {"name": "UHF", "start": 470.0, "stop": 608.0},
        {"name": "Duplex Gap", "start": 653.0, "stop": 663.0},
        {"name": "ISM", "start": 902.0, "stop": 928.0},
        {"name": "STL", "start": 940.0, "stop": 960.0},
        {"name": "DECT", "start": 1920.0, "stop": 1930.0}
    ],
    "UK": [
        {"name": "VHF", "start": 173.0, "stop": 175.0},
        {"name": "UHF Site License", "start": 470.0, "stop": 606.0},
        {"name": "UHF Shared License", "start": 606.0, "stop": 613.0},
        {"name": "600MHz Site License", "start": 614.0, "stop": 694.0},
        {"name": "Duplex Gap", "start": 823.0, "stop": 832.0},
        {"name": "DECT", "start": 1880.0, "stop": 1900.0}
    ],
    "Spain": [
        {"name": "VHF", "start": 174.0, "stop": 216.0},
        {"name": "UHF", "start": 470.0, "stop": 694.0},
        {"name": "700MHz Duplex Gap", "start": 694.0, "stop": 703.0},
        {"name": "800MHz Duplex Gap", "start": 823.0, "stop": 832.0},
        {"name": "ISM", "start": 863.0, "stop": 865.0},
        {"name": "DECT", "start": 1880.0, "stop": 1900.0}
    ]
}

DEFAULT_NORTH_AMERICA_ACTIVE = {
    37: True,
    "GB_616": True,
    "DL_A": True,
    "DL_B": True,
    "DL_C": True,
    "DL_D": True,
    "DL_E": True,
    "DL_F": True,
    "DL_G": True,
    "GB_652": True,
    "UL_A": True,
    "UL_B": True,
    "UL_C": True,
    "UL_D": True,
    "UL_E": True,
    "UL_F": True,
    "UL_G": True,
    **{ch: True for ch in range(52, 84)},
    "LMR_890": True
}

DEFAULT_EUROPE_ACTIVE = {
    "700_GB1": True,
    "700_UL_1": True,
    "700_UL_2": True,
    "700_UL_3": True,
    "700_UL_4": True,
    "700_UL_5": True,
    "700_UL_6": True,
    "700_DL_1": True,
    "700_DL_2": True,
    "700_DL_3": True,
    "700_DL_4": True,
    "700_DL_5": True,
    "700_DL_6": True,
    "700_GB2": True,
    "800_DL_1": True,
    "800_DL_2": True,
    "800_DL_3": True,
    "800_DL_4": True,
    "800_DL_5": True,
    "800_DL_6": True,
    "800_GB1": True,
    "800_UL_1": True,
    "800_UL_2": True,
    "800_UL_3": True,
    "800_UL_4": True,
    "800_UL_5": True,
    "800_UL_6": True,
    "800_GB2": True,
    # UK PMR / TETRA / GSM-R
    "UK_TETRA_UL": True,
    "UK_PMR385_UL": True,
    "UK_TETRA_DL": True,
    "UK_PMR395_DL": True,
    "UK_PMR410": True,
    "UK_PMR446": True,
    "UK_PMR450": True,
    "UK_PMR870": True,
    "UK_GSMR_UL": True,
    "UK_PMR915": True,
    "UK_GSMR_DL": True,
    # Spain PMR / TETRA / GSM-R
    "ES_TETRA_UL": True,
    "ES_PMR385_UL": True,
    "ES_TETRA_DL": True,
    "ES_PMR395_DL": True,
    "ES_PMR410": True,
    "ES_PMR446": True,
    "ES_PMR450": True,
    "ES_PMR870": True,
    "ES_GSMR_UL": True,
    "ES_PMR915": True,
    "ES_GSMR_DL": True
}

class ProgressSignal(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool)

class SettingsDialog(QDialog):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.setWindowTitle("Settings")
        self.resize(500, 300)
        
        layout = QVBoxLayout(self)
        
        # Regional Spectrum Data Group
        region_group = QGroupBox("Regional Spectrum Data")
        region_layout = QFormLayout()
        
        self.region_combo = QComboBox()
        self.region_combo.addItems(["US - FCC", "UK - Ofcom"])
        self.region_combo.setCurrentText(self.main_app.spectrum_region)
        self.region_combo.currentTextChanged.connect(self.on_region_changed)
        
        self.status_label = QLabel("Checking status...")
        
        self.action_btn = QPushButton("Download Latest Data")
        self.action_btn.clicked.connect(self.on_action_clicked)
        
        region_layout.addRow("Active Region:", self.region_combo)
        region_layout.addRow("Database Status:", self.status_label)
        region_layout.addRow("", self.action_btn)
        
        # Link for UK manual download
        self.ofcom_link_container = QWidget()
        ofcom_link_layout = QHBoxLayout(self.ofcom_link_container)
        ofcom_link_layout.setContentsMargins(0, 0, 0, 0)
        
        self.ofcom_open_btn = QPushButton("Open Ofcom Page")
        self.ofcom_open_btn.clicked.connect(lambda: webbrowser.open("https://www.ofcom.org.uk/spectrum/information/broadcast/television-transmitter-details"))
        
        self.ofcom_copy_btn = QPushButton("Copy Link")
        self.ofcom_copy_btn.clicked.connect(lambda: QApplication.clipboard().setText("https://www.ofcom.org.uk/spectrum/information/broadcast/television-transmitter-details"))
        
        ofcom_link_layout.addWidget(self.ofcom_open_btn)
        ofcom_link_layout.addWidget(self.ofcom_copy_btn)
        
        self.ofcom_link_container.hide()
        region_layout.addRow("", self.ofcom_link_container)
        
        # Progress Tracking
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        
        self.progress_label = QLabel("")
        self.progress_label.hide()
        
        region_layout.addRow("", self.progress_bar)
        region_layout.addRow("", self.progress_label)
        
        region_group.setLayout(region_layout)
        layout.addWidget(region_group)
        layout.addStretch()
        
        self.update_status()
        
    def on_region_changed(self, text):
        self.main_app.spectrum_region = text
        self.main_app.settings.setValue("spectrum_region", text)
        self.update_status()
        
    def update_status(self):
        region = self.main_app.spectrum_region
        if region == "US - FCC":
            db = self.main_app.fcc_db
            self.action_btn.setText("Download Latest Data")
            self.ofcom_link_container.hide()
        else:
            db = self.main_app.ofcom_db
            self.action_btn.setText("Import Ofcom Excel File...")
            self.ofcom_link_container.show()
            
        if not db.has_data():
            self.status_label.setText("<font color='red'>Not Installed</font>")
        else:
            last_update = db.get_last_update_time()
            if last_update == 0.0:
                self.status_label.setText("<font color='orange'>Unknown age</font>")
            else:
                days = int((time.time() - last_update) / (24*3600))
                color = "green" if days <= 30 else "orange"
                self.status_label.setText(f"<font color='{color}'>Updated {days} days ago</font>")
                
    def on_action_clicked(self):
        region = self.main_app.spectrum_region
        
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.progress_label.setText("Starting...")
        self.progress_label.show()
        
        # Setup thread-safe signal
        self.progress_signal = ProgressSignal()
        self.progress_signal.progress.connect(self.on_progress_update)
        self.progress_signal.finished.connect(self.on_download_finished)
        
        if region == "US - FCC":
            self.action_btn.setEnabled(False)
            self.action_btn.setText("Downloading...")
            
            def progress_callback(pct, text):
                self.progress_signal.progress.emit(pct, text)
                
            def completion_callback(success):
                self.progress_signal.finished.emit(success)
                
            self.main_app.fcc_db.download_and_update_async(progress_callback=progress_callback, completion_callback=completion_callback)
        else:
            file_name, _ = QFileDialog.getOpenFileName(self, "Open Ofcom Data", "", "Excel Files (*.xlsx)")
            if file_name:
                self.action_btn.setEnabled(False)
                self.action_btn.setText("Importing...")
                
                def progress_callback(pct, text):
                    self.progress_signal.progress.emit(pct, text)
                    QApplication.processEvents() # Needed since it's blocking in this branch
                    
                success = self.main_app.ofcom_db.import_excel(file_name, progress_callback=progress_callback)
                
                self.action_btn.setEnabled(True)
                self.action_btn.setText("Import Ofcom Excel File...")
                self.progress_bar.hide()
                self.progress_label.hide()
                self.update_status()
                if success:
                    QMessageBox.information(self, "Success", "UK Ofcom Database imported successfully.")
                else:
                    QMessageBox.critical(self, "Error", "Failed to import Ofcom database.")
            else:
                self.progress_bar.hide()
                self.progress_label.hide()
                
    def on_progress_update(self, pct, text):
        self.progress_bar.setValue(pct)
        self.progress_label.setText(text)
        
    def on_download_finished(self, success):
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Download Latest Data")
        self.progress_bar.hide()
        self.progress_label.hide()
        self.update_status()
        if success:
            QMessageBox.information(self, "Success", "US FCC Database updated successfully.")
        else:
            QMessageBox.critical(self, "Error", "Failed to download FCC database.")

class CustomMenuBar(QMenuBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._is_tracking = False
        self._start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.globalPosition().toPoint()
            self._is_tracking = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_tracking and self.parent_window:
            delta = event.globalPosition().toPoint() - self._start_pos
            self.parent_window.move(self.parent_window.pos() + delta)
            self._start_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_tracking = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.parent_window:
            if self.parent_window.isMaximized():
                self.parent_window.showNormal()
            else:
                self.parent_window.showMaximized()
        super().mouseDoubleClickEvent(event)

class DotSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setMouseTracking(True)
        self._hover = False

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        settings = QSettings("Harogic", "RF_Recon")
        is_dark = settings.value("dark_theme", True, type=bool)
        
        bg_color = QColor(0, 0, 0) if is_dark else QColor(255, 255, 255)
        painter.fillRect(self.rect(), bg_color)
        
        line_color = QColor("#5ec962") if self._hover else (QColor("#333333") if is_dark else QColor("#cccccc"))
        dot_color = QColor("#5ec962") if self._hover else (QColor("#888888") if is_dark else QColor("#555555"))
        
        painter.setPen(line_color)
        if self.orientation() == Qt.Orientation.Horizontal:
            # Vertical line in the horizontal splitter
            x = self.width() // 2
            painter.drawLine(x, 0, x, self.height())
            
            # Dots
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(dot_color)
            cy = self.height() // 2
            painter.drawEllipse(x - 1, cy - 6, 2, 2)
            painter.drawEllipse(x - 1, cy, 2, 2)
            painter.drawEllipse(x - 1, cy + 6, 2, 2)
        else:
            # Horizontal line in the vertical splitter
            y = self.height() // 2
            painter.drawLine(0, y, self.width(), y)
            
            # Dots
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(dot_color)
            cx = self.width() // 2
            painter.drawEllipse(cx - 6, y - 1, 2, 2)
            painter.drawEllipse(cx, y - 1, 2, 2)
            painter.drawEllipse(cx + 6, y - 1, 2, 2)

class DotSplitter(QSplitter):
    def createHandle(self):
        return DotSplitterHandle(self.orientation(), self)

COLORMAP_CSS = {
    'viridis': "stop:0 #440154, stop:0.25 #3b528b, stop:0.5 #21918c, stop:0.75 #5ec962, stop:1 #fde725",
    'inferno': "stop:0 #000004, stop:0.25 #57106e, stop:0.5 #bc3754, stop:0.75 #f98d0a, stop:1 #fcffa4",
    'plasma': "stop:0 #0d0887, stop:0.25 #7e03a8, stop:0.5 #cc4678, stop:0.75 #f89441, stop:1 #f0f921",
    'magma': "stop:0 #000004, stop:0.25 #50127b, stop:0.5 #b63679, stop:0.75 #fb8861, stop:1 #fcfdbf",
    'turbo': "stop:0 #30123b, stop:0.25 #28bbec, stop:0.5 #a2ffa3, stop:0.75 #fb8022, stop:1 #7a0403",
    'jet': "stop:0 #00007f, stop:0.25 #007fff, stop:0.5 #7fff7f, stop:0.75 #ff7f00, stop:1 #7f0000",
    'bipolar': "stop:0 #00ffff, stop:0.5 #000000, stop:1 #ffff00"
}

class MHzAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [f"{v:g}" for v in values]

class ClickableChannelItem(pg.GraphicsObject):
    channel_clicked = pyqtSignal(object, float, float)

    def __init__(self, ch_num, start_x, width, height=1.0, label_text=None, item_type="default", display_name=None):
        super().__init__()
        self.ch_num = ch_num
        self.start_freq = start_x
        self.stop_freq = start_x + width
        self.rect = QRectF(start_x, 0, width, height)
        self.item_type = item_type
        self.display_name = display_name or f"Channel {ch_num}"
        self.short_label = label_text or str(ch_num)
        self.full_label = self.display_name
        
        self.text = pg.TextItem(self.short_label, anchor=(0.5, 0.5), color='w')
        if self.item_type == "guard":
            f = self.text.textItem.font()
            if f.pointSizeF() > 0:
                f.setPointSizeF(f.pointSizeF() * 0.8)
            elif f.pointSize() > 0:
                f.setPointSize(max(int(f.pointSize() * 0.8), 6))
            self.text.setFont(f)
            
        self.text.setParentItem(self)
        self.text.setPos(start_x + width / 2.0, height / 2.0)
        self.setToolTip(f"{self.display_name}: {start_x/1e6:g} MHz - {(start_x+width)/1e6:g} MHz")
        
    def boundingRect(self):
        return self.rect
        
    def paint(self, p, *args):
        view = self.getViewBox()
        if view is not None:
            v_range = view.viewRange()[0]
            # Frustum culling
            if self.stop_freq < v_range[0] or self.start_freq > v_range[1]:
                self.text.setVisible(False)
                return
                
            hz_per_pixel = view.viewPixelSize()[0]
            pixel_width = self.rect.width() / hz_per_pixel
            
            # Show the clean short label without visual clutter
            min_px = 10 if self.item_type == "guard" else 14
            self.text.setVisible(pixel_width >= min_px)
            
            # Guarantee at least a 2-pixel gap between boxes so they always look distinct
            hz_gap = hz_per_pixel * 2
        else:
            hz_gap = self.rect.width() * 0.02

        if getattr(self, 'is_active', False):
            if self.item_type == "uplink":
                p.setBrush(QBrush(QColor(233, 30, 99))) # Active PINK
                p.setPen(QPen(QColor(255, 64, 129), 1))
            elif self.item_type == "downlink":
                p.setBrush(QBrush(QColor(142, 36, 170))) # Active PURPLE
                p.setPen(QPen(QColor(186, 104, 200), 1))
            elif self.item_type == "guard":
                p.setBrush(QBrush(QColor(110, 110, 110))) # Active GRAY
                p.setPen(QPen(QColor(170, 170, 170), 1))
            elif self.item_type in ("lmr_smr", "teal"):
                p.setBrush(QBrush(QColor(0, 150, 136))) # Active TEAL
                p.setPen(QPen(QColor(38, 166, 154), 1))
            elif self.ch_num == 37 or self.item_type == "ch37":
                p.setBrush(QBrush(QColor(100, 100, 100))) # Active GREY
                p.setPen(QPen(QColor(200, 200, 200), 1))
            elif getattr(self, 'is_public_safety', False):
                p.setBrush(QBrush(QColor(150, 0, 0))) # Active RED (Public Safety)
                p.setPen(QPen(QColor(200, 0, 0), 1))
            else:
                p.setBrush(QBrush(QColor(0, 100, 200))) # Active BLUE
                p.setPen(QPen(QColor(0, 150, 255), 1))
        else:
            if self.item_type == "uplink":
                p.setBrush(QBrush(QColor(90, 20, 45))) # Inactive Pink tint
                p.setPen(QPen(QColor(60, 60, 60), 1))
            elif self.item_type == "downlink":
                p.setBrush(QBrush(QColor(60, 20, 75))) # Inactive Purple tint
                p.setPen(QPen(QColor(60, 60, 60), 1))
            elif self.item_type == "guard":
                p.setBrush(QBrush(QColor(60, 60, 60))) # Inactive Gray
                p.setPen(QPen(QColor(45, 45, 45), 1))
            elif self.item_type in ("lmr_smr", "teal"):
                p.setBrush(QBrush(QColor(0, 77, 64))) # Inactive Teal tint
                p.setPen(QPen(QColor(0, 105, 92), 1))
            else:
                p.setBrush(QBrush(QColor(120, 120, 120)))
                p.setPen(QPen(QColor(50, 50, 50), 1))
        
        # Calculate width with gap, but never less than 10% of the channel width
        draw_width = max(self.rect.width() - hz_gap, self.rect.width() * 0.1)
        draw_rect = QRectF(self.rect.x() + hz_gap/2, self.rect.y(), draw_width, self.rect.height() * 0.8)
        draw_rect.moveTop(0.1) # Center vertically slightly
        p.drawRect(draw_rect)
        
    def mouseClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.channel_clicked.emit(self.ch_num, self.start_freq, self.stop_freq)
            ev.accept()
        else:
            ev.ignore()

class ChannelMarkerBar(pg.PlotWidget):
    channel_clicked = pyqtSignal(object, float, float)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedHeight(30)
        self.hideAxis('bottom')
        self.getPlotItem().layout.removeItem(self.getAxis('bottom'))
        
        # Keep left axis to align perfectly with the main plots, but make it invisible
        left_axis = self.getAxis('left')
        left_axis.setPen(pg.mkPen(color=(0,0,0,0)))
        left_axis.setTextPen(pg.mkPen(color=(0,0,0,0)))
        
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)
        self.setBackground('k')
        self.setYRange(0, 1, padding=0)
        self.hideButtons()
        
        # Aggressively hide Pyqtgraph's auto-range button which can sometimes re-appear
        if hasattr(self.plotItem, 'autoBtn') and self.plotItem.autoBtn:
            self.plotItem.autoBtn.setParentItem(None)
            self.plotItem.autoBtn.hide()

    def update_visibility(self, view_box, range):
        x_min, x_max = range
        for item in getattr(self.plotItem, 'items', []):
            if isinstance(item, ClickableChannelItem):
                if item.start_freq <= x_max and item.stop_freq >= x_min:
                    item.setVisible(True)
                else:
                    item.setVisible(False)

    def set_active_channels(self, active_dict, ps_dict=None):
        if ps_dict is None:
            ps_dict = {}
        for item in getattr(self.plotItem, 'items', []):
            if isinstance(item, ClickableChannelItem):
                item.is_active = active_dict.get(item.ch_num, False)
                item.is_public_safety = ps_dict.get(item.ch_num, False)
                item.update()

    def draw_channels(self, standard, x_mult=1e6):
        self.clear()
        if not standard: return
        
        if isinstance(standard, dict):
            standard = [standard]
            
        for band in standard:
            if "custom_items" in band:
                for c_item in band["custom_items"]:
                    c_id = c_item["id"]
                    start_freq = c_item["start"] * (1e6 / x_mult)
                    stop_freq = c_item["stop"] * (1e6 / x_mult)
                    width = stop_freq - start_freq
                    item = ClickableChannelItem(
                        ch_num=c_id,
                        start_x=start_freq,
                        width=width,
                        label_text=c_item.get("label", str(c_id)),
                        item_type=c_item.get("type", "default"),
                        display_name=c_item.get("display_name")
                    )
                    item.channel_clicked.connect(self.on_channel_clicked)
                    self.addItem(item)
                continue
                
            start_ch = band["start_ch"]
            end_ch = band["end_ch"]
            start_freq = band["start_freq"] * (1e6 / x_mult)
            spacing = band["spacing"] * (1e6 / x_mult)
            
            for ch in range(start_ch, end_ch + 1):
                ch_idx = ch - start_ch
                f_start = start_freq + (ch_idx * spacing)
                
                item = ClickableChannelItem(ch, f_start, spacing)
                item.channel_clicked.connect(self.on_channel_clicked)
                self.addItem(item)
            
    def on_channel_clicked(self, ch_num, start_freq, stop_freq):
        self.channel_clicked.emit(ch_num, start_freq, stop_freq)

class SimpleColorPicker(QPushButton):
    colorChanged = pyqtSignal(QColor)
    
    def __init__(self, default_color_name, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setStyleSheet(f"background-color: {default_color_name}; border-radius: 8px; border: 1px solid #555;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.current_color = QColor(default_color_name)
        
        self.menu = QMenu(self)
        self.menu.setStyleSheet("QMenu { border: 1px solid #555; } QMenu::item { padding: 4px 10px; }")
        
        colors = [
            ("Yellow", 'yellow'),
            ("Green", 'green'),
            ("Cyan", 'cyan'),
            ("Magenta", 'magenta'),
            ("Red", 'red'),
            ("Blue", 'blue'),
            ("White", 'white'),
            ("Orange", 'orange')
        ]
        
        for name, color_code in colors:
            action = self.menu.addAction(name)
            pixmap = QPixmap(12, 12)
            pixmap.fill(QColor(color_code))
            action.setIcon(QIcon(pixmap))
            action.setData(QColor(color_code))
            
        self.menu.triggered.connect(self.on_color_picked)
        self.clicked.connect(self.show_menu)
        
    def show_menu(self):
        self.menu.popup(self.mapToGlobal(QPoint(0, self.height())))
        
    def on_color_picked(self, action):
        color = action.data()
        self.current_color = color
        self.setStyleSheet(f"background-color: {color.name()}; border-radius: 8px; border: 1px solid #555;")
        self.colorChanged.emit(color)
        
    def color(self):
        return self.current_color

class FreqSpinBox(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSuffix("") # Suffix is handled dynamically
        self.setMinimumWidth(140)
        
    def valueFromText(self, text):
        text = text.lower().strip()
        text = text.replace(" ", "")
        multiplier = 1.0 # Default is MHz since internal value is MHz
        if text.endswith("ghz"):
            multiplier = 1000.0
            text = text[:-3]
        elif text.endswith("mhz"):
            multiplier = 1.0
            text = text[:-3]
        elif text.endswith("khz"):
            multiplier = 1e-3
            text = text[:-3]
        elif text.endswith("hz"):
            multiplier = 1e-6
            text = text[:-2]
            
        try:
            return float(text) * multiplier
        except ValueError:
            return 0.0

    def textFromValue(self, value):
        return f"{value:.3f} MHz"
            
    def validate(self, text, pos):
        return (QValidator.State.Acceptable, text, pos)

class BWSpinBox(FreqSpinBox):
    def textFromValue(self, value):
        val_hz = value * 1e6
        if val_hz >= 1e6:
            return f"{val_hz / 1e6:g} MHz"
        elif val_hz >= 1e3:
            return f"{val_hz / 1e3:g} kHz"
        else:
            return f"{val_hz:g} Hz"

    def stepBy(self, steps):
        current_val = self.value()
        if current_val <= 0:
            current_val = 1e-6
            
        if steps > 0:
            for _ in range(steps):
                order = math.floor(math.log10(current_val))
                base = round(current_val / (10**order), 5)
                
                if base < 1.0: base = 1.0
                elif base < 3.0: base = 3.0
                elif base < 10.0:
                    base = 10.0
                    order += 1
                    base = 1.0
                current_val = base * (10**order)
        elif steps < 0:
            for _ in range(-steps):
                order = math.floor(math.log10(current_val))
                base = round(current_val / (10**order), 5)
                
                if base > 3.0: base = 3.0
                elif base > 1.0: base = 1.0
                else:
                    base = 3.0
                    order -= 1
                current_val = base * (10**order)
                
        self.setValue(current_val)

class CollapsibleSection(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.header = QPushButton(f"▼ {title}")
        self.header.setObjectName("collapsibleHeader")
        self.header.setCheckable(True)
        self.header.setChecked(True)
        self.header.toggled.connect(self.toggle_content)
        
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 10, 0, 10)
        
        self.layout.addWidget(self.header)
        self.layout.addWidget(self.content_area)
        
    def toggle_content(self, checked):
        self.content_area.setVisible(checked)
        base_title = self.header.text().split(" ", 1)[-1]
        symbol = "▼" if checked else "▶"
        self.header.setText(f"{symbol} {base_title}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._initializing = True
        
        self.settings = QSettings("Harogic", "RF_Recon")
        try:
            self.region_configs = json.loads(self.settings.value("regions", json.dumps(DEFAULT_REGIONS)))
            for reg_k, reg_v in DEFAULT_REGIONS.items():
                if reg_k not in self.region_configs:
                    self.region_configs[reg_k] = reg_v
                else:
                    existing_names = {p.get("name") for p in self.region_configs[reg_k]}
                    if "VHF-Low" in {p.get("name") for p in reg_v} and "VHF-Low" not in existing_names:
                        self.region_configs[reg_k] = reg_v
                    elif any("Downlink" in n for n in existing_names):
                        self.region_configs[reg_k] = reg_v
        except Exception:
            self.region_configs = DEFAULT_REGIONS.copy()
        self.current_region = self.settings.value("launch_default_region", self.settings.value("current_region", "North America"))
        if self.current_region not in self.region_configs:
            self.current_region = list(self.region_configs.keys())[0]
        self.waterfall_history_depth = int(self.settings.value("waterfall_depth", 100))
        self.waterfall_colormap = self.settings.value("waterfall_colormap", "viridis")
        self.spectrum_region = self.settings.value("spectrum_region", "US - FCC")
        
        self.fcc_db = FCCDatabaseManager()
        self.ofcom_db = OfcomDatabaseManager()
        self.dtv_detect_active = False
        self.tband_detect_active = False
        self.tband_history = []
        self.tband_markers = {}
        self.active_channels = {}
        self.channel_masks = {}
        
        self.cal_manager = CalibrationManager()
        
        # Load launch quick-setting anchors
        raw_sweep_anchors = self.settings.value("launch_sweep_anchors", None)
        if raw_sweep_anchors:
            try:
                self._explicit_quick_anchors = set(tuple(a) for a in json.loads(raw_sweep_anchors))
            except Exception:
                self._explicit_quick_anchors = set()
        else:
            self._explicit_quick_anchors = set()
            
        raw_view_anchors = self.settings.value("launch_view_anchors", None)
        if raw_view_anchors:
            try:
                self._explicit_view_quick_anchors = set(tuple(a) for a in json.loads(raw_view_anchors))
            except Exception:
                self._explicit_view_quick_anchors = set()
        else:
            self._explicit_view_quick_anchors = set()
        
        self.setWindowTitle("Freqon")
        self.resize(1000, 600)
        
        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Frameless Window
        # Window frame is active for desktop dragging
        
        # Menu Bar acting as Title Bar
        menu_bar = CustomMenuBar(self)
        self.setMenuBar(menu_bar)
        

        file_menu = menu_bar.addMenu("File")
        
        import_action = QAction("Import Calibration Files...", self)
        import_action.triggered.connect(self.import_calibration_files)
        file_menu.addAction(import_action)
        
        clear_action = QAction("Clear Calibration Files...", self)
        clear_action.triggered.connect(self.clear_calibration_files)
        file_menu.addAction(clear_action)
        
        launch_settings_action = QAction("Launch Settings...", self)
        launch_settings_action.triggered.connect(self.open_launch_settings_dialog)
        file_menu.addAction(launch_settings_action)
        
        file_menu.addSeparator()
        
        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self.show_settings_dialog)
        file_menu.addAction(settings_action)
        
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        # Settings Menu
        settings_menu = menu_bar.addMenu("Settings")
        
        self.theme_action = QAction("Dark Theme", self)
        self.theme_action.setCheckable(True)
        is_dark = self.settings.value("dark_theme", True, type=bool)
        self.theme_action.setChecked(is_dark)
        self.theme_action.triggered.connect(self.toggle_theme)
        settings_menu.addAction(self.theme_action)
        
        region_menu = settings_menu.addMenu("Region")
        self.region_action_group = QActionGroup(self)
        for region in self.region_configs.keys():
            action = QAction(region, self)
            action.setCheckable(True)
            if region == self.current_region:
                action.setChecked(True)
            action.setData(region)
            action.triggered.connect(self.change_region_from_menu)
            self.region_action_group.addAction(action)
            region_menu.addAction(action)
        
        waterfall_color_menu = settings_menu.addMenu("Waterfall Color Theme")
        self.color_action_group = QActionGroup(self)
        
        for cmap in ['viridis', 'inferno', 'plasma', 'magma', 'turbo', 'jet', 'bipolar']:
            action = QAction(cmap.capitalize(), self)
            action.setCheckable(True)
            if cmap == self.waterfall_colormap:
                action.setChecked(True)
            action.setData(cmap)
            action.triggered.connect(self.change_colormap_from_menu)
            self.color_action_group.addAction(action)
            waterfall_color_menu.addAction(action)
            
        # Marker Settings Menu
        marker_menu = settings_menu.addMenu("Marker")
        marker_opacity_action = QAction("Marker Opacity & Saturation...", self)
        marker_opacity_action.triggered.connect(self.show_marker_settings_dialog)
        marker_menu.addAction(marker_opacity_action)
        
        marker_menu.addSeparator()
        
        self.nb_labels_action = QAction("Show Narrowband Labels", self)
        self.nb_labels_action.setCheckable(True)
        self.nb_labels_action.setChecked(self.settings.value("show_nb_labels", True, type=bool))
        self.nb_labels_action.triggered.connect(self.on_nb_labels_toggled)
        marker_menu.addAction(self.nb_labels_action)
        
        self.dtv_labels_action = QAction("Show DTV Labels", self)
        self.dtv_labels_action.setCheckable(True)
        self.dtv_labels_action.setChecked(self.settings.value("show_dtv_labels", True, type=bool))
        self.dtv_labels_action.triggered.connect(self.on_dtv_labels_toggled)
        marker_menu.addAction(self.dtv_labels_action)
        
        # For the horizontal splitter (separating columns)
        self.main_splitter = DotSplitter(Qt.Orientation.Horizontal)        
        # Give right panel a bit more room so traces settings don't clip
        self.main_splitter.setSizes([270, 600, 250])
        
        main_layout.addWidget(self.main_splitter)
        
        # --- LEFT PANEL ---
        self.left_scroll = QScrollArea()
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setMinimumWidth(270)
        self.left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.left_panel = QWidget()
        self.left_panel.setMaximumWidth(300)
        left_layout = QVBoxLayout(self.left_panel)
        self.left_scroll.setWidget(self.left_panel)
        
        self.analyzer_section = CollapsibleSection("Analyzer Settings")
        left_layout.addWidget(self.analyzer_section)
        
        self.connect_btn = QPushButton("Connect Device")
        self.connect_btn.setMaximumWidth(200)
        self.connect_btn.clicked.connect(self.toggle_connection)
        
        self.status_label = QLabel("<span style='color: gray;'>Status:</span> <span style='color: red;'>Disconnected</span>")
        self.status_label.setStyleSheet("font-weight: bold;")
        self.status_label.setWordWrap(True)
        
        self.analyzer_section.content_layout.addWidget(self.connect_btn)
        self.analyzer_section.content_layout.addWidget(self.status_label)
        
        self.spectrum_section = CollapsibleSection("Analyzer Sweep Settings")
        left_layout.addWidget(self.spectrum_section)
        
        launch_sweep_start = self.settings.value("launch_sweep_start", None)
        launch_sweep_stop = self.settings.value("launch_sweep_stop", None)
        default_start = float(launch_sweep_start) if launch_sweep_start is not None else 470.0
        default_stop = float(launch_sweep_stop) if launch_sweep_stop is not None else 608.0

        self.start_spin = FreqSpinBox()
        self.start_spin.setRange(0.1, 20000.0) # 0.1 MHz to 20 GHz
        self.start_spin.setDecimals(1)
        self.start_spin.setValue(default_start)
        self.start_spin.editingFinished.connect(self.apply_frequencies)
        self.start_spin.setMaximumWidth(110)
        
        self.stop_spin = FreqSpinBox()
        self.stop_spin.setRange(0.1, 20000.0)
        self.stop_spin.setDecimals(1)
        self.stop_spin.setValue(default_stop)
        self.stop_spin.editingFinished.connect(self.apply_frequencies)
        self.stop_spin.setMaximumWidth(110)
        
        self.center_spin = FreqSpinBox()
        self.center_spin.setRange(0.1, 20000.0)
        self.center_spin.setDecimals(1)
        self.center_spin.setValue((default_start + default_stop) / 2.0)
        self.center_spin.editingFinished.connect(self.apply_frequencies)
        self.center_spin.setMaximumWidth(110)
        
        self.span_spin = FreqSpinBox()
        self.span_spin.setRange(0.001, 20000.0)
        self.span_spin.setDecimals(1)
        self.span_spin.setValue(default_stop - default_start)
        self.span_spin.editingFinished.connect(self.apply_frequencies)
        self.span_spin.setMaximumWidth(110)
        
        self.step_spin = FreqSpinBox()
        self.step_spin.setRange(0.001, 20000.0)
        self.step_spin.setDecimals(3)
        self.step_spin.setValue(1.0)
        self.center_spin.setSingleStep(self.step_spin.value())
        self.step_spin.setMaximumWidth(110)
        
        freq_form = QFormLayout()
        freq_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        freq_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        freq_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        freq_form.addRow("Start:", self.start_spin)
        freq_form.addRow("Stop:", self.stop_spin)
        freq_form.addRow("Center:", self.center_spin)
        freq_form.addRow("Span:", self.span_spin)
        freq_form.addRow("CF Step:", self.step_spin)
        
        
        # Quick-Settings Grid
        self.quick_settings_header = QHBoxLayout()
        qs_label = QLabel("Quick Settings")
        qs_label.setStyleSheet("color: #aaaaaa; font-weight: bold;")
        self.quick_settings_header.addWidget(qs_label)
        
        self.edit_qs_btn = QPushButton("⚙️ Edit")
        self.edit_qs_btn.setStyleSheet("background: transparent; color: #5cafff; font-weight: bold;")
        self.edit_qs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_qs_btn.clicked.connect(self.open_quick_settings_dialog)
        self.quick_settings_header.addWidget(self.edit_qs_btn)
        self.quick_settings_header.addStretch()
        
        self.spectrum_section.content_layout.addLayout(self.quick_settings_header)
        
        self.quick_btn_layout = QGridLayout()
        self.quick_btn_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.quick_btn_layout.setHorizontalSpacing(2)
        self.quick_btns = []
        for i in range(10):
            btn = QPushButton()
            btn.setObjectName("quickSettingBtn")
            btn.setCheckable(True)
            btn.clicked.connect(self.on_quick_btn_toggled)
            self.quick_btns.append(btn)
            self.quick_btn_layout.addWidget(btn, i // 2, i % 2)
            
        self.spectrum_section.content_layout.addLayout(self.quick_btn_layout)
        self.update_quick_settings_ui()
        self.spectrum_section.content_layout.addLayout(freq_form)

        # --- Amplitude Section ---
        self.amplitude_section = CollapsibleSection("Amplitude")
        left_layout.addWidget(self.amplitude_section)
        
        amp_form = QFormLayout()
        amp_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        amp_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        amp_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # 1. Reference Level
        self.ref_level_spin = QDoubleSpinBox()
        self.ref_level_spin.setRange(-200.0, 100.0)
        self.ref_level_spin.setDecimals(1)
        self.ref_level_spin.setValue(0.0)
        self.ref_level_spin.setSuffix(" dBm")
        self.ref_level_spin.setSingleStep(5.0)
        self.ref_level_spin.setMaximumWidth(110)
        
        self.auto_ref_btn = QPushButton("Auto Ref. Level")
        self.auto_ref_btn.setMaximumWidth(200)
        self.auto_ref_btn.clicked.connect(self.auto_reference_level)
        
        amp_form.addRow("Ref. Level:", self.ref_level_spin)
        amp_form.addRow("", self.auto_ref_btn)
        
        # 2. Attenuation
        self.atten_spin = QSpinBox()
        self.atten_spin.setRange(-128, 128)
        self.atten_spin.setValue(0)
        self.atten_spin.setSuffix(" dB")
        self.atten_spin.setMaximumWidth(110)
        amp_form.addRow("Attenuation:", self.atten_spin)
        
        # 3. Pre-Amplifier
        self.preamp_combo = QComboBox()
        self.preamp_combo.addItem("Auto On", 0x00)
        self.preamp_combo.addItem("Forced Off", 0x01)
        self.preamp_combo.addItem("Low Gain", 0x02)
        self.preamp_combo.addItem("Medium Gain", 0x03)
        self.preamp_combo.addItem("High Gain", 0x04)
        self.preamp_combo.setMaximumWidth(110)
        amp_form.addRow("Pre-Amplifier:", self.preamp_combo)
        
        # 4. Amplitude Offset
        self.amp_offset_spin = QDoubleSpinBox()
        self.amp_offset_spin.setRange(-200.0, 200.0)
        self.amp_offset_spin.setDecimals(1)
        self.amp_offset_spin.setValue(0.0)
        self.amp_offset_spin.setSuffix(" dB")
        self.amp_offset_spin.setMaximumWidth(110)
        amp_form.addRow("Amp. Offset:", self.amp_offset_spin)
        
        # 5. IFAGC
        self.ifagc_check = QCheckBox()
        self.ifagc_check.setChecked(False)
        amp_form.addRow("Enable IFAGC:", self.ifagc_check)
        
        # 6. IFAGC Target
        self.ifagc_target_spin = QDoubleSpinBox()
        self.ifagc_target_spin.setRange(-200.0, 100.0)
        self.ifagc_target_spin.setDecimals(1)
        self.ifagc_target_spin.setValue(-9.0)
        self.ifagc_target_spin.setSuffix(" dB")
        self.ifagc_target_spin.setMaximumWidth(110)
        amp_form.addRow("IFAGC Target:", self.ifagc_target_spin)

        # 7. IFAGC Period
        self.ifagc_period_spin = QDoubleSpinBox()
        self.ifagc_period_spin.setRange(0.001, 10.0)
        self.ifagc_period_spin.setDecimals(3)
        self.ifagc_period_spin.setValue(0.01)
        self.ifagc_period_spin.setSuffix(" s")
        self.ifagc_period_spin.setMaximumWidth(110)
        amp_form.addRow("IFAGC Period:", self.ifagc_period_spin)

        # 8. IF Out
        self.if_out_check = QCheckBox()
        self.if_out_check.setChecked(False)
        amp_form.addRow("Enable IF Out:", self.if_out_check)
        
        self.amplitude_section.content_layout.addLayout(amp_form)
        
        # --- Sweep Settings ---
        self.sweep_section = CollapsibleSection("Sweep Settings")
        left_layout.addWidget(self.sweep_section)
        
        sweep_form = QFormLayout()
        sweep_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        sweep_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        sweep_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.swt_mode_combo = QComboBox()
        self.swt_mode_combo.addItems(["minSWT", "minSWTx2", "minSWTx4", "minSWTx10", "minSWTx20", "minSWTx50", "minSWTxN", "Manual", "minSMPxN"])
        self.swt_mode_combo.setMaximumWidth(110)
        sweep_form.addRow("SWTMode:", self.swt_mode_combo)
        
        self.sweep_time_spin = QDoubleSpinBox()
        self.sweep_time_spin.setRange(0.001, 1000.0)
        self.sweep_time_spin.setDecimals(3)
        self.sweep_time_spin.setSuffix(" s")
        self.sweep_time_spin.setEnabled(False) 
        self.sweep_time_spin.setMaximumWidth(110)
        sweep_form.addRow("Sweep Time:", self.sweep_time_spin)
        
        self.trace_points_spin = QSpinBox()
        self.trace_points_spin.setRange(0, 100000)
        self.trace_points_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.trace_points_spin.setSpecialValueText(" ") # Show blank when 0
        self.trace_points_spin.setValue(0)
        self.trace_points_spin.setReadOnly(True)
        self.trace_points_spin.setMaximumWidth(110)
        sweep_form.addRow("TracePoints:", self.trace_points_spin)
        
        self.spur_combo = QComboBox()
        self.spur_combo.addItems(["Bypass", "Standard", "Enhanced"])
        self.spur_combo.setCurrentIndex(1)
        self.spur_combo.setMaximumWidth(110)
        sweep_form.addRow("Spur Rejection:", self.spur_combo)
        
        self.window_combo = QComboBox()
        # FlatTop = 0, Blackman_Nuttall = 1, LowSideLobe = 2, Rect = 3, Kaiser = 4
        self.window_combo.addItems(["FlatTop", "Blackman-Nuttall", "LowSideLobe", "Rectangle", "Kaiser"])
        self.window_combo.setCurrentIndex(0)
        self.window_combo.setMaximumWidth(110)
        sweep_form.addRow("Window:", self.window_combo)
        
        self.sweep_section.content_layout.addLayout(sweep_form)
        
        self.swt_mode_combo.currentIndexChanged.connect(self.on_swt_mode_changed)
        self.swt_mode_combo.currentIndexChanged.connect(self.apply_sweep_settings)
        self.sweep_time_spin.editingFinished.connect(self.apply_sweep_settings)
        self.spur_combo.currentIndexChanged.connect(self.apply_sweep_settings)
        self.window_combo.currentIndexChanged.connect(self.apply_sweep_settings)

        # --- Detect Settings ---
        self.detect_section = CollapsibleSection("Detect Settings")
        left_layout.addWidget(self.detect_section)
        
        detect_form = QFormLayout()
        detect_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        detect_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        detect_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.detector_combo = QComboBox()
        self.detector_combo.addItems(["Sample", "PosPeak", "Average", "NegPeak", "MaxPower", "RawFrames", "RMS"])
        self.detector_combo.setCurrentIndex(4) # Default to MaxPower as it's useful for recon
        self.detector_combo.setMaximumWidth(110)
        detect_form.addRow("Detector:", self.detector_combo)
        
        self.trace_detector_combo = QComboBox()
        self.trace_detector_combo.addItems(["AutoSample", "Sample", "PosPeak", "NegPeak", "RMS", "Bypass", "AutoPeak", "Normal"])
        self.trace_detector_combo.setCurrentIndex(0) # Default to AutoSample
        self.trace_detector_combo.setMaximumWidth(110)
        detect_form.addRow("Trace Detector:", self.trace_detector_combo)
        
        self.detect_section.content_layout.addLayout(detect_form)
        
        self.detector_combo.currentIndexChanged.connect(self.apply_detect_settings)
        self.trace_detector_combo.currentIndexChanged.connect(self.apply_detect_settings)

        left_layout.addStretch()
        
        # --- CENTER-LEFT PANEL (Blank Canvas) ---
        self.center_left_scroll = QScrollArea()
        self.center_left_scroll.setWidgetResizable(True)
        self.center_left_scroll.setMinimumWidth(270)
        self.center_left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.center_left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.center_left_panel = QWidget()
        self.center_left_panel.setMaximumWidth(300)
        center_left_layout = QVBoxLayout(self.center_left_panel)
        self.center_left_scroll.setWidget(self.center_left_panel)
        
        # Intruder Alert Section
        self.intruder_section = CollapsibleSection("Intruder Alert")
        center_left_layout.addWidget(self.intruder_section)
        
        self.intruder_enable_cb = QCheckBox("Enable Intruder Alert")
        self.intruder_enable_cb.setChecked(False)
        self.intruder_enable_cb.toggled.connect(self.on_intruder_alert_toggled)
        self.intruder_section.content_layout.addWidget(self.intruder_enable_cb)
        
        intr_thresh_layout = QHBoxLayout()
        intr_thresh_layout.addWidget(QLabel("Threshold (dBm):"))
        self.intruder_threshold_spin = QDoubleSpinBox()
        self.intruder_threshold_spin.setRange(-150, 20)
        self.intruder_threshold_spin.setValue(-80)
        self.intruder_threshold_spin.setSingleStep(1)
        self.intruder_threshold_spin.valueChanged.connect(self.on_intruder_threshold_changed)
        intr_thresh_layout.addWidget(self.intruder_threshold_spin)
        self.intruder_section.content_layout.addLayout(intr_thresh_layout)
        
        self.intruder_table = QTableWidget(0, 3)
        self.intruder_table.setHorizontalHeaderLabels(["Freq (MHz)", "RSSI", "Identified Signature"])
        self.intruder_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.intruder_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.intruder_table.horizontalHeader().setStretchLastSection(True)
        self.intruder_table.verticalHeader().setVisible(False)
        self.intruder_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.intruder_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.intruder_table.setMinimumHeight(150)
        self.intruder_section.content_layout.addWidget(self.intruder_table)
        
        intr_btn_layout = QHBoxLayout()
        self.intruder_clear_btn = QPushButton("Clear")
        self.intruder_clear_btn.clicked.connect(self.clear_intruders)
        self.intruder_add_btn = QPushButton("Add to Markers...")
        self.intruder_add_btn.clicked.connect(self.add_intruder_to_markers)
        intr_btn_layout.addWidget(self.intruder_clear_btn)
        intr_btn_layout.addWidget(self.intruder_add_btn)
        self.intruder_section.content_layout.addLayout(intr_btn_layout)

        # Markers Section
        self.markers_section = CollapsibleSection("Markers")
        center_left_layout.addWidget(self.markers_section)
        
        self.markers_tree = QTreeWidget()
        self.markers_tree.setHeaderHidden(True)
        self.markers_tree.setMinimumHeight(150)
        self.markers_tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.markers_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.markers_tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid gray;
            }
            QTreeWidget::item {
                border: 1px solid lightgray;
                margin: 1px;
            }
            QTreeWidget::item:hover {
                background: rgba(255, 255, 255, 0.05);
            }
            QTreeWidget::indicator {
                width: 18px;
                height: 18px;
            }
            QTreeWidget::indicator:unchecked {
                image: url(cross.svg);
            }
            QTreeWidget::indicator:checked {
                image: url(check.svg);
            }
        """)
        self.markers_tree.itemChanged.connect(self.on_marker_tree_item_changed)
        self.markers_section.content_layout.addWidget(self.markers_tree)

        # DTV Layout Section
        self.dtv_layout_section = CollapsibleSection("DTV Layout")
        center_left_layout.addWidget(self.dtv_layout_section)
        
        self.dtv_zones_table = QTableWidget()
        self.dtv_zones_table.setColumnCount(2)
        self.dtv_zones_table.setHorizontalHeaderLabels(["Select", "Zone"])
        
        # Room for exactly 4 zones
        self.dtv_zones_table.setMaximumHeight(190)
        
        self.dtv_zones_table.setStyleSheet("""
            QTableWidget {
                gridline-color: gray;
            }
        """)
        
        self.dtv_zones_table.horizontalHeader().setStretchLastSection(True)
        self.dtv_zones_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.dtv_zones_table.verticalHeader().setVisible(False)
        self.dtv_zones_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.dtv_zones_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        self.dtv_zone_btn_group = QButtonGroup(self)
        
        self.dtv_layout_section.content_layout.addWidget(self.dtv_zones_table)

        # Imports Section
        self.imports_section = CollapsibleSection("Imports")
        center_left_layout.addWidget(self.imports_section)
        
        self.btn_soundbase_json = QPushButton("Soundbase Site JSON")
        self.btn_soundbase_json.setStyleSheet("background-color: gray; color: white; font-weight: bold;")
        self.btn_soundbase_json.setToolTip("No file loaded")
        self.btn_soundbase_json.clicked.connect(self.load_soundbase_json)
        
        self.imports_section.content_layout.addWidget(self.btn_soundbase_json)
        
        # DECT & Intercom Analysis Section (Beneath Imports)
        self.dect_section = CollapsibleSection("DECT & Intercom Analysis")
        center_left_layout.addWidget(self.dect_section)
        
        self.dect_engine = DECTAnalyzerEngine(self)
        self.dect_engine.analysis_updated.connect(self.on_dect_analysis_updated)
        
        dect_form = QFormLayout()
        dect_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        dect_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        dect_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.dect_band_combo = QComboBox()
        self.dect_band_combo.addItems(list(DECT_BANDS.keys()))
        self.dect_band_combo.currentTextChanged.connect(self.on_dect_band_changed)
        dect_form.addRow("DECT Band:", self.dect_band_combo)
        
        self.dect_enable_cb = QCheckBox("Enable DECT Monitor")
        self.dect_enable_cb.setChecked(False)
        self.dect_enable_cb.toggled.connect(self.on_dect_enable_toggled)
        dect_form.addRow(self.dect_enable_cb)
        
        self.dect_thresh_spin = QDoubleSpinBox()
        self.dect_thresh_spin.setRange(-150.0, 0.0)
        self.dect_thresh_spin.setValue(-85.0)
        self.dect_thresh_spin.setSuffix(" dBm")
        self.dect_thresh_spin.valueChanged.connect(lambda v: self.dect_engine.set_threshold(v))
        dect_form.addRow("Threshold:", self.dect_thresh_spin)
        
        self.dect_section.content_layout.addLayout(dect_form)
        
        self.dect_tune_btn = QPushButton("🎯 Tune Sweep to DECT")
        self.dect_tune_btn.setStyleSheet("background-color: #00796b; color: white; font-weight: bold; padding: 4px;")
        self.dect_tune_btn.clicked.connect(self.tune_to_dect_band)
        self.dect_section.content_layout.addWidget(self.dect_tune_btn)
        
        # Discovered Carriers & Capacity Table
        self.dect_table = QTableWidget(0, 4)
        self.dect_table.setHorizontalHeaderLabels(["Carrier", "RSSI", "Load %", "Transceivers & Status"])
        self.dect_table.horizontalHeader().setStretchLastSection(True)
        self.dect_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.dect_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.dect_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.dect_table.verticalHeader().setVisible(False)
        self.dect_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.dect_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.dect_table.setMinimumHeight(140)
        self.dect_table.setMaximumHeight(200)
        self.dect_section.content_layout.addWidget(self.dect_table)
        
        self.dect_summary_lbl = QLabel("Load: 0% (CLEAN) | 0 Ant | 0 Packs")
        self.dect_summary_lbl.setStyleSheet("color: #00bcd4; font-weight: bold; font-size: 8.5pt;")
        self.dect_section.content_layout.addWidget(self.dect_summary_lbl)
        
        dect_action_layout = QHBoxLayout()
        self.dect_matrix_btn = QPushButton("📊 DECT Capacity Inspector...")
        self.dect_matrix_btn.setStyleSheet("background-color: #5cafff; color: black; font-weight: bold; padding: 4px;")
        self.dect_matrix_btn.clicked.connect(self.open_tdma_matrix_dialog)
        
        self.dect_clear_btn = QPushButton("Clear")
        self.dect_clear_btn.clicked.connect(self.clear_dect_data)
        
        dect_action_layout.addWidget(self.dect_matrix_btn)
        dect_action_layout.addWidget(self.dect_clear_btn)
        self.dect_section.content_layout.addLayout(dect_action_layout)
        
        # 2.4 GHz ShowLink & Wireless DMX / CRMX Section (Beneath DECT)
        self.showlink_section = CollapsibleSection("2.4 GHz ShowLink & CRMX / DMX")
        center_left_layout.addWidget(self.showlink_section)
        
        self.showlink_engine = ShowLinkCRMXEngine(self)
        self.showlink_engine.analysis_updated.connect(self.on_showlink_analysis_updated)
        
        sl_form = QFormLayout()
        sl_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        sl_form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        sl_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.showlink_enable_cb = QCheckBox("Enable 2.4G Monitor")
        self.showlink_enable_cb.setChecked(False)
        self.showlink_enable_cb.toggled.connect(self.on_showlink_enable_toggled)
        sl_form.addRow(self.showlink_enable_cb)
        
        self.showlink_thresh_spin = QDoubleSpinBox()
        self.showlink_thresh_spin.setRange(-150.0, 0.0)
        self.showlink_thresh_spin.setValue(-80.0)
        self.showlink_thresh_spin.setSuffix(" dBm")
        self.showlink_thresh_spin.valueChanged.connect(lambda v: self.showlink_engine.set_threshold(v))
        sl_form.addRow("Threshold:", self.showlink_thresh_spin)
        
        self.showlink_section.content_layout.addLayout(sl_form)
        
        self.showlink_tune_btn = QPushButton("🎯 Tune Sweep to 2.4 GHz")
        self.showlink_tune_btn.setStyleSheet("background-color: #00796b; color: white; font-weight: bold; padding: 4px;")
        self.showlink_tune_btn.clicked.connect(self.tune_to_showlink_band)
        self.showlink_section.content_layout.addWidget(self.showlink_tune_btn)
        
        # ShowLink Channel Table
        self.showlink_table = QTableWidget(0, 4)
        self.showlink_table.setHorizontalHeaderLabels(["ShowLink Ch", "Freq", "RSSI", "Health / Overlap"])
        self.showlink_table.horizontalHeader().setStretchLastSection(True)
        self.showlink_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.showlink_table.verticalHeader().setVisible(False)
        self.showlink_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.showlink_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.showlink_table.setMinimumHeight(140)
        self.showlink_table.setMaximumHeight(200)
        self.showlink_section.content_layout.addWidget(self.showlink_table)
        
        sl_action_layout = QHBoxLayout()
        self.showlink_map_btn = QPushButton("📊 2.4 GHz Map...")
        self.showlink_map_btn.setStyleSheet("background-color: #5cafff; color: black; font-weight: bold; padding: 4px;")
        self.showlink_map_btn.clicked.connect(self.open_showlink_map_dialog)
        
        self.showlink_clear_btn = QPushButton("Clear")
        self.showlink_clear_btn.clicked.connect(self.clear_showlink_data)
        
        sl_action_layout.addWidget(self.showlink_map_btn)
        sl_action_layout.addWidget(self.showlink_clear_btn)
        self.showlink_section.content_layout.addLayout(sl_action_layout)
        
        center_left_layout.addStretch()
        
        # --- RIGHT PANEL ---
        self.right_scroll = QScrollArea()
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setMinimumWidth(320)
        self.right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.right_panel = QWidget()
        self.right_scroll.setWidget(self.right_panel)
        
        right_layout = QVBoxLayout(self.right_panel)
        

        self.view_section = CollapsibleSection("View Sweep Settings")
        right_layout.addWidget(self.view_section)
        
        launch_link_view = self.settings.value("launch_link_view", True, type=bool)
        self.link_view_check = QCheckBox("Link to Analyzer")
        self.link_view_check.setChecked(launch_link_view)
        self.link_view_check.toggled.connect(self.on_link_view_toggled)
        self.view_section.content_layout.addWidget(self.link_view_check)
        
        self.view_panel_span_alert = QLabel("⚠️ Spectrum View larger than Spectrum Sweep")
        self.view_panel_span_alert.setWordWrap(True)
        self.view_panel_span_alert.setStyleSheet(
            "background-color: rgba(230, 126, 34, 0.15); "
            "color: #e67e22; "
            "border: 1px solid #e67e22; "
            "border-radius: 4px; "
            "padding: 4px 6px; "
            "font-weight: bold; "
            "font-size: 8.5pt;"
        )
        self.view_panel_span_alert.hide()
        self.view_section.content_layout.addWidget(self.view_panel_span_alert)
        
        launch_view_start = self.settings.value("launch_view_start", None)
        launch_view_stop = self.settings.value("launch_view_stop", None)
        default_v_start = float(launch_view_start) if (launch_view_start is not None and not launch_link_view) else default_start
        default_v_stop = float(launch_view_stop) if (launch_view_stop is not None and not launch_link_view) else default_stop

        self.view_start_spin = FreqSpinBox()
        self.view_start_spin.setRange(0.1, 20000.0) # 0.1 MHz to 20 GHz
        self.view_start_spin.setDecimals(1)
        self.view_start_spin.setValue(default_v_start)
        self.view_start_spin.editingFinished.connect(self.apply_view_frequencies)
        
        self.view_stop_spin = FreqSpinBox()
        self.view_stop_spin.setRange(0.1, 20000.0)
        self.view_stop_spin.setDecimals(1)
        self.view_stop_spin.setValue(default_v_stop)
        self.view_stop_spin.editingFinished.connect(self.apply_view_frequencies)
        
        self.view_center_spin = FreqSpinBox()
        self.view_center_spin.setRange(0.1, 20000.0)
        self.view_center_spin.setDecimals(1)
        self.view_center_spin.setValue((default_v_start + default_v_stop) / 2.0)
        self.view_center_spin.editingFinished.connect(self.apply_view_frequencies)
        
        self.view_span_spin = FreqSpinBox()
        self.view_span_spin.setRange(0.001, 20000.0)
        self.view_span_spin.setDecimals(1)
        self.view_span_spin.setValue(default_v_stop - default_v_start)
        self.view_span_spin.editingFinished.connect(self.apply_view_frequencies)
        
        self.view_step_spin = FreqSpinBox()
        self.view_step_spin.setRange(0.001, 20000.0)
        self.view_step_spin.setDecimals(3)
        self.view_step_spin.setValue(1.0)
        self.view_center_spin.setSingleStep(self.view_step_spin.value())
        
        view_form = QFormLayout()
        view_form.addRow("Start:", self.view_start_spin)
        view_form.addRow("Stop:", self.view_stop_spin)
        view_form.addRow("Center:", self.view_center_spin)
        view_form.addRow("Span:", self.view_span_spin)
        view_form.addRow("CF Step:", self.view_step_spin)
        
        
        # View Quick-Settings Grid
        self.view_quick_settings_header = QHBoxLayout()
        vqs_label = QLabel("Quick Settings")
        vqs_label.setStyleSheet("color: #aaaaaa; font-weight: bold;")
        self.view_quick_settings_header.addWidget(vqs_label)
        
        # We can reuse the same dialog or create a new one, but for now we'll just reuse the dialog 
        # and sync the buttons together in terms of their frequency definitions.
        # Wait, the user said "those same quick-settings buttons", implying the SAME bands.
        # So we just mirror the buttons.
        self.edit_view_qs_btn = QPushButton("⚙️ Edit")
        self.edit_view_qs_btn.setStyleSheet("background: transparent; color: #5cafff; font-weight: bold;")
        self.edit_view_qs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_view_qs_btn.clicked.connect(self.open_quick_settings_dialog)
        self.view_quick_settings_header.addWidget(self.edit_view_qs_btn)
        self.view_quick_settings_header.addStretch()
        
        self.view_section.content_layout.addLayout(self.view_quick_settings_header)
        
        self.view_quick_btn_layout = QGridLayout()
        self.view_quick_btn_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.view_quick_btn_layout.setHorizontalSpacing(2)
        self.view_quick_btns = []
        for i in range(10):
            btn = QPushButton()
            btn.setObjectName("quickSettingBtn")
            btn.setCheckable(True)
            btn.clicked.connect(self.on_view_quick_btn_toggled)
            self.view_quick_btns.append(btn)
            self.view_quick_btn_layout.addWidget(btn, i // 2, i % 2)
            
        self.view_section.content_layout.addLayout(self.view_quick_btn_layout)
        self.update_quick_settings_ui()
        
        self.view_section.content_layout.addLayout(view_form)
        
        # --- TRACE SETTINGS SECTION ---
        self.trace_section = CollapsibleSection("Trace Settings")
        right_layout.addWidget(self.trace_section)
        
        trace_layout = QGridLayout()
        trace_layout.setContentsMargins(5, 5, 5, 5)
        
        # Column headers
        type_lbl = QLabel("Type")
        type_lbl.setStyleSheet("font-weight: bold; color: #aaaaaa;")
        trace_layout.addWidget(type_lbl, 0, 0)
        
        freeze_lbl = QLabel("Freeze")
        freeze_lbl.setStyleSheet("font-weight: bold; color: #aaaaaa;")
        trace_layout.addWidget(freeze_lbl, 0, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        
        color_lbl = QLabel("Color")
        color_lbl.setStyleSheet("font-weight: bold; color: #aaaaaa;")
        trace_layout.addWidget(color_lbl, 0, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Setup the inline Average spinbox
        self.avg_sweeps_spin = QSpinBox()
        self.avg_sweeps_spin.setRange(2, 1000)
        self.avg_sweeps_spin.setValue(10)
        self.avg_sweeps_spin.setSuffix("")
        self.avg_sweeps_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.avg_sweeps_spin.setStyleSheet("QSpinBox { min-width: 50px; max-width: 50px; padding: 0px 5px 0px 5px; margin-left: 18px; }")
        self.avg_sweeps_spin.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.avg_sweeps_spin.setToolTip("Number of sweeps for Average trace")
        
        self.trace_controls = {}
        def add_trace_row(row, name, default_on, default_color):
            cb = QCheckBox(name)
            cb.setChecked(default_on)
            freeze_cb = QCheckBox("")
            color_btn = SimpleColorPicker(default_color)
            
            trace_layout.addWidget(cb, row, 0)
            trace_layout.addWidget(freeze_cb, row, 1, alignment=Qt.AlignmentFlag.AlignCenter)
            trace_layout.addWidget(color_btn, row, 2, alignment=Qt.AlignmentFlag.AlignCenter)
            
            if name == "Average":
                trace_layout.addWidget(self.avg_sweeps_spin, row+1, 0, alignment=Qt.AlignmentFlag.AlignLeft)
            
            self.trace_controls[name] = {'cb': cb, 'freeze_cb': freeze_cb, 'color_btn': color_btn}
            cb.toggled.connect(self.on_trace_toggled)
            color_btn.colorChanged.connect(self.on_trace_color_changed)
            
        add_trace_row(1, "Real-Time", True, 'yellow')
        add_trace_row(2, "Max. Hold", False, 'cyan')
        add_trace_row(3, "Min. Hold", False, 'magenta')
        add_trace_row(4, "Average", False, 'green')
        
        # Stretch an empty 4th column to pack everything tightly to the left
        empty_spacer = QLabel("")
        trace_layout.addWidget(empty_spacer, 0, 4)
        trace_layout.setColumnStretch(4, 1)
        
        self.trace_section.content_layout.addLayout(trace_layout)
        
        # Buffer states
        self.max_hold_data = None
        self.min_hold_data = None
        self.avg_history = None

        # --- BW SECTION ---
        self.bw_section = CollapsibleSection("BW")
        right_layout.addWidget(self.bw_section)
        
        self.rbw_mode_combo = QComboBox()
        self.rbw_mode_combo.addItems(["Manual", "Automatic", "0.001*Span", "0.01*Span"])
        self.rbw_mode_combo.setCurrentIndex(1) # Automatic
        
        self.rbw_spin = BWSpinBox()
        self.rbw_spin.setRange(1e-6, 1000.0) # 1Hz to 1GHz
        self.rbw_spin.setDecimals(6)
        self.rbw_spin.setValue(0.001) # 1kHz
        
        self.vbw_mode_combo = QComboBox()
        self.vbw_mode_combo.addItems(["Manual", "VBW=RBW", "0.1*RBW", "0.01*RBW", "10*RBW"])
        self.vbw_mode_combo.setCurrentIndex(1) # VBW=RBW
        
        self.vbw_spin = BWSpinBox()
        self.vbw_spin.setRange(1e-6, 1000.0)
        self.vbw_spin.setDecimals(6)
        self.vbw_spin.setValue(0.001)
        

        
        bw_form = QFormLayout()
        bw_form.addRow("RBW Mode:", self.rbw_mode_combo)
        bw_form.addRow("RBW:", self.rbw_spin)
        bw_form.addRow("VBW Mode:", self.vbw_mode_combo)
        bw_form.addRow("VBW:", self.vbw_spin)
        
        self.bw_section.content_layout.addLayout(bw_form)

        # --- DTV Detector SECTION ---
        self.dtv_section = CollapsibleSection("DTV Detector")
        right_layout.addWidget(self.dtv_section)
        
        dtv_form = QFormLayout()
        
        self.zip_input = QLineEdit()
        self.zip_input.setPlaceholderText("Enter ZIP Code")
        self.zip_input.setMaxLength(5)
        self.zip_input.setMaximumWidth(100)
        dtv_form.addRow("ZIP Code:", self.zip_input)
        
        self.fcc_lookup_btn = QPushButton("DTV Lookup")
        self.fcc_lookup_btn.setMaximumWidth(150)
        self.fcc_lookup_btn.clicked.connect(self.on_fcc_lookup)
        dtv_form.addRow("", self.fcc_lookup_btn)
        
        self.dtv_threshold_spin = QDoubleSpinBox()
        self.dtv_threshold_spin.setRange(-150, 0)
        self.dtv_threshold_spin.setValue(-70.0)
        self.dtv_threshold_spin.setSuffix(" dBm")
        dtv_form.addRow("Threshold:", self.dtv_threshold_spin)
        
        self.show_threshold_cb = QCheckBox("Show Threshold Line")
        self.show_threshold_cb.toggled.connect(self.on_show_threshold_toggled)
        dtv_form.addRow("", self.show_threshold_cb)
        
        self.dtv_detect_btn = QPushButton("DTV Detect")
        self.dtv_detect_btn.setCheckable(True)
        self.dtv_detect_btn.setMaximumWidth(150)
        self.dtv_detect_btn.toggled.connect(self.on_dtv_detect_toggled)
        dtv_form.addRow("", self.dtv_detect_btn)
        
        self.tband_scan_btn = QPushButton("Scan T-Band")
        self.tband_scan_btn.setCheckable(True)
        self.tband_scan_btn.setMaximumWidth(150)
        self.tband_scan_btn.toggled.connect(self.on_tband_scan_toggled)
        dtv_form.addRow("", self.tband_scan_btn)
        
        self.dtv_section.content_layout.addLayout(dtv_form)
        
        # --- DTV Marker SECTION ---
        self.dtv_marker_section = CollapsibleSection("DTV Marker")
        right_layout.addWidget(self.dtv_marker_section)
        
        marker_layout = QVBoxLayout()
        
        self.dtv_table = QTableWidget()
        self.dtv_table.setMaximumWidth(300)
        self.dtv_table.setColumnCount(4)
        self.dtv_table.setHorizontalHeaderLabels(["Ch", "Call Sign", "ERP", "Dist"])
        self.dtv_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dtv_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.dtv_table.setColumnWidth(0, 40)
        self.dtv_table.verticalHeader().setVisible(False)
        self.dtv_table.setMinimumHeight(150)
        self.dtv_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.dtv_table.cellClicked.connect(self.on_dtv_table_clicked)
        marker_layout.addWidget(self.dtv_table)
        
        self.dtv_marker_section.content_layout.addLayout(marker_layout)
        
        right_layout.addStretch()

        
        self.rbw_mode_combo.currentIndexChanged.connect(self.on_bw_mode_changed)
        self.vbw_mode_combo.currentIndexChanged.connect(self.on_bw_mode_changed)
        self.rbw_spin.valueChanged.connect(self.on_bw_manual_override)
        self.vbw_spin.valueChanged.connect(self.on_bw_manual_override)
        self._updating_bw = False

        right_layout.addStretch()
        
        # Connect signals for mutual updates
        self.start_spin.valueChanged.connect(self.on_start_stop_changed)
        self.stop_spin.valueChanged.connect(self.on_start_stop_changed)
        self.center_spin.valueChanged.connect(self.on_center_changed)
        self.span_spin.valueChanged.connect(self.on_span_changed)
        self.step_spin.valueChanged.connect(self.on_step_changed)
        self._updating_freqs = False
        self.view_start_spin.valueChanged.connect(self.on_view_start_stop_changed)
        self.view_stop_spin.valueChanged.connect(self.on_view_start_stop_changed)
        self.view_center_spin.valueChanged.connect(self.on_view_center_changed)
        self.view_span_spin.valueChanged.connect(self.on_view_span_changed)
        self.view_step_spin.valueChanged.connect(self.on_view_step_changed)
        self._updating_view_freqs = False
        
        # --- MIDDLE PANEL ---
        self.middle_panel = QWidget()
        middle_layout = QVBoxLayout(self.middle_panel)
        
        # Top Controls in Middle Panel
        top_middle_layout = QHBoxLayout()
        
        self.toggle_left_btn = QPushButton("◀")
        self.toggle_left_btn.setFixedSize(24, 24)
        self.toggle_left_btn.setToolTip("Toggle Analyzer Settings")
        self.toggle_left_btn.clicked.connect(self.toggle_left_panel)
        
        self.toggle_center_left_btn = QPushButton("◀")
        self.toggle_center_left_btn.setFixedSize(24, 24)
        self.toggle_center_left_btn.setToolTip("Toggle New Features Panel")
        self.toggle_center_left_btn.clicked.connect(self.toggle_center_left_panel)
        
        self.play_pause_btn = QPushButton("Pause")
        self.play_pause_btn.setCheckable(True)
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.play_pause_btn.setEnabled(False)
        
        self.intruder_prev_btn = QPushButton("◀")
        self.intruder_prev_btn.setFixedSize(24, 24)
        self.intruder_prev_btn.setVisible(False)
        self.intruder_prev_btn.clicked.connect(self.on_intruder_prev)
        
        self.intruder_alert_btn = QPushButton("Intruder Detected")
        self.intruder_alert_btn.setStyleSheet("color: red; font-weight: bold; border: none; background: transparent;")
        self.intruder_alert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.intruder_alert_btn.setVisible(False)
        self.intruder_alert_btn.clicked.connect(self.on_intruder_alert_clicked)
        
        self.intruder_next_btn = QPushButton("▶")
        self.intruder_next_btn.setFixedSize(24, 24)
        self.intruder_next_btn.setVisible(False)
        self.intruder_next_btn.clicked.connect(self.on_intruder_next)
        
        self.cursor_info_label = QLabel("Cursor: -- MHz | -- dBm")
        self.cursor_info_label.setStyleSheet("font-weight: bold; color: #0078D7;")
        
        self.toggle_right_btn = QPushButton("▶")
        self.toggle_right_btn.setFixedSize(24, 24)
        self.toggle_right_btn.setToolTip("Toggle Spectrum Settings")
        self.toggle_right_btn.clicked.connect(self.toggle_right_panel)
        
        top_middle_layout.addWidget(self.toggle_left_btn)
        top_middle_layout.addWidget(self.toggle_center_left_btn)
        top_middle_layout.addWidget(self.play_pause_btn)
        top_middle_layout.addWidget(self.intruder_prev_btn)
        top_middle_layout.addWidget(self.intruder_alert_btn)
        top_middle_layout.addWidget(self.intruder_next_btn)
        top_middle_layout.addStretch()
        top_middle_layout.addWidget(self.cursor_info_label)
        top_middle_layout.addWidget(self.toggle_right_btn)
        
        middle_layout.addLayout(top_middle_layout)
        
        # The inner vertical splitter for Waterfall and Spectrum
        self.splitter = DotSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(12)
        middle_layout.addWidget(self.splitter)
        
        # Add panels to the main horizontal splitter
        self.main_splitter.addWidget(self.left_scroll)
        self.main_splitter.addWidget(self.center_left_scroll)
        self.main_splitter.addWidget(self.middle_panel)
        self.main_splitter.addWidget(self.right_scroll)
        
        # Set initial sizes and restrict edge columns from auto-stretching
        self.main_splitter.setSizes([270, 270, 600, 250])
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 0)
        self.main_splitter.setStretchFactor(2, 1)
        self.main_splitter.setStretchFactor(3, 0)
        
        
        
        # Waterfall Container
        self.waterfall_container = QWidget()
        self.waterfall_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        waterfall_layout = QVBoxLayout(self.waterfall_container)
        waterfall_layout.setContentsMargins(0, 0, 0, 0)
        
        waterfall_top_layout = QHBoxLayout()
        self.waterfall_title = QLabel("Spectrogram")
        self.waterfall_title.setStyleSheet("font-weight: bold; font-size: 11pt;")
        
        self.color_scale_label = QLabel("-120 dBm           -70 dBm           -20 dBm")
        self.color_scale_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.color_scale_label.setFixedSize(280, 20)
        
        waterfall_top_layout.addWidget(self.waterfall_title)
        waterfall_top_layout.addStretch()
        waterfall_top_layout.addWidget(self.color_scale_label)
        
        waterfall_layout.addLayout(waterfall_top_layout)
        
        self.update_color_scale_css()
        
        # Waterfall Widget
        self.waterfall_widget = pg.PlotWidget(axisItems={'bottom': MHzAxisItem(orientation='bottom')})
        self.waterfall_widget.setLabel('left', 'History', units='Sweeps')
        self.waterfall_widget.showGrid(x=True, y=False)
        self.waterfall_widget.hideButtons()
        self.waterfall_widget.getViewBox().setMouseEnabled(x=True, y=False)
        waterfall_layout.addWidget(self.waterfall_widget)
        self.waterfall_channels = ChannelMarkerBar()
        waterfall_layout.addWidget(self.waterfall_channels)
        
        self.history_btn = QPushButton("⚙", self.waterfall_widget)
        self.history_btn.setToolTip("Change Waterfall History Depth")
        self.history_btn.setFixedSize(20, 20)
        self.history_btn.move(10, 10) # Place it near the Y axis
        self.history_btn.clicked.connect(self.change_waterfall_history)
        
        # Apply the loaded colormap
        colormap = pg.colormap.get(self.waterfall_colormap)
        self.waterfall_img = pg.ImageItem(autoDownsample=True)
        self.waterfall_img.setColorMap(colormap)
        self.waterfall_widget.addItem(self.waterfall_img)
        
        # Spectrum Container
        self.spectrum_container = QWidget()
        self.spectrum_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        spectrum_layout = QVBoxLayout(self.spectrum_container)
        spectrum_layout.setContentsMargins(0, 0, 0, 0)
        
        self.spectrum_title_layout = QHBoxLayout()
        self.spectrum_plot_title = QLabel("Real-Time Spectrum (SWP Mode)")
        self.spectrum_plot_title.setStyleSheet("font-weight: bold; font-size: 11pt;")
        self.spectrum_title_layout.addWidget(self.spectrum_plot_title)
        
        self.spectrum_title_layout.addStretch()
        
        self.spectrum_span_alert = QLabel("⚠️ Spectrum View larger than Spectrum Sweep")
        self.spectrum_span_alert.setStyleSheet(
            "background-color: rgba(230, 126, 34, 0.2); "
            "color: #f39c12; "
            "border: 1px solid #f39c12; "
            "border-radius: 4px; "
            "padding: 2px 8px; "
            "font-weight: bold; "
            "font-size: 9pt;"
        )
        self.spectrum_span_alert.hide()
        self.spectrum_title_layout.addWidget(self.spectrum_span_alert)
        
        spectrum_layout.addLayout(self.spectrum_title_layout)
        
        # Spectrum Widget
        self.plot_widget = pg.PlotWidget(axisItems={'bottom': MHzAxisItem(orientation='bottom')})
        self.plot_widget.setLabel('left', 'Power', units='dBm')
        # We moved the 'Frequency (MHz)' label to be underneath the DTV markers
        self.plot_widget.showGrid(x=True, y=True)
        self.waterfall_channels = ChannelMarkerBar()
        waterfall_layout.addWidget(self.waterfall_channels)
        
        mult = getattr(self, '_x_multiplier', 1e6)
        self.plot_widget.setXRange(self.view_start_spin.value() * (1e6 / mult), self.view_stop_spin.value() * (1e6 / mult), padding=0)
        self.plot_widget.setYRange(-120, 10)
        self.plot_widget.hideButtons()
        self.plot_widget.getViewBox().setMouseEnabled(x=True, y=False)
        self.plot_widget.getViewBox().sigRangeChanged.connect(self.on_plot_range_changed)
        spectrum_layout.addWidget(self.plot_widget)
        self.spectrum_channels = ChannelMarkerBar()
        spectrum_layout.addWidget(self.spectrum_channels)
        
        self.spectrum_freq_label = QLabel("Frequency (MHz)")
        self.spectrum_freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spectrum_freq_label.setStyleSheet("color: #aaaaaa; font-weight: bold;")
        spectrum_layout.addWidget(self.spectrum_freq_label)
        
        # Force identical left axis width to perfectly align the plotting areas
        axis_width = 50
        self.plot_widget.getAxis('left').setWidth(axis_width)
        self.waterfall_widget.getAxis('left').setWidth(axis_width)
        self.waterfall_channels.getAxis('left').setWidth(axis_width)
        self.spectrum_channels.getAxis('left').setWidth(axis_width)
        
        # Force identical right axis width to eliminate right-side layout skew
        right_width = 15
        for pw in (self.plot_widget, self.waterfall_widget, self.waterfall_channels, self.spectrum_channels):
            pw.showAxis('right')
            r_axis = pw.getAxis('right')
            r_axis.setPen(pg.mkPen(color=(0,0,0,0)))
            r_axis.setTextPen(pg.mkPen(color=(0,0,0,0)))
            r_axis.setWidth(right_width)
        
        # Link X axes
        self.waterfall_widget.setXLink(self.plot_widget)
        self.spectrum_channels.setXLink(self.plot_widget)
        self.waterfall_channels.setXLink(self.plot_widget)
        
        # Hide auto range buttons and explicitly disable auto-ranging on resize
        if hasattr(self.plot_widget.plotItem, 'autoBtn') and self.plot_widget.plotItem.autoBtn:
            self.plot_widget.plotItem.autoBtn.setParentItem(None)
            self.plot_widget.plotItem.autoBtn.hide()
        self.plot_widget.getViewBox().disableAutoRange()
        self.plot_widget.getViewBox().setAutoVisible(x=False, y=False)
            
        if hasattr(self.waterfall_widget.plotItem, 'autoBtn') and self.waterfall_widget.plotItem.autoBtn:
            self.waterfall_widget.plotItem.autoBtn.setParentItem(None)
            self.waterfall_widget.plotItem.autoBtn.hide()
        self.waterfall_widget.getViewBox().disableAutoRange()
        self.waterfall_widget.getViewBox().setAutoVisible(x=False, y=False)
        self.waterfall_widget.setYRange(0, self.waterfall_history_depth, padding=0)
        
        # Connect to main plot_widget signal since XLinked ViewBoxes suppress sigXRangeChanged
        self.plot_widget.getViewBox().sigXRangeChanged.connect(self.waterfall_channels.update_visibility)
        self.plot_widget.getViewBox().sigXRangeChanged.connect(self.spectrum_channels.update_visibility)
        
        if self.current_region == "North America":
            self.active_channels = dict(DEFAULT_NORTH_AMERICA_ACTIVE)
        elif self.current_region in ("UK", "Spain"):
            self.active_channels = dict(DEFAULT_EUROPE_ACTIVE)
        else:
            self.active_channels = {}
        
        self.waterfall_channels.channel_clicked.connect(self.on_channel_clicked)
        self.spectrum_channels.channel_clicked.connect(self.on_channel_clicked)
        
        # Add containers to splitter
        self.splitter.addWidget(self.waterfall_container)
        self.splitter.addWidget(self.spectrum_container)
        # Give more space to waterfall
        self.splitter.setSizes([300, 200])
        
        # The trace lines
        self.trace_curves = {
            "Real-Time": self.plot_widget.plot(pen=pg.mkPen('y', width=2)),
            "Average": self.plot_widget.plot(pen=pg.mkPen('g', width=2)),
            "Max. Hold": self.plot_widget.plot(pen=pg.mkPen('c', width=2)),
            "Min. Hold": self.plot_widget.plot(pen=pg.mkPen('m', width=2)),
        }
        for name, curve in self.trace_curves.items():
            curve.setVisible(self.trace_controls[name]['cb'].isChecked())
        
        # Crosshair / Cursor setup
        self.vLine = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('cyan', width=1, style=Qt.PenStyle.DashLine))
        self.plot_widget.addItem(self.vLine, ignoreBounds=True)
        
        self.waterfall_vLine = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('cyan', width=1, style=Qt.PenStyle.DashLine))
        self.waterfall_widget.addItem(self.waterfall_vLine, ignoreBounds=True)
        
        # DTV Threshold Line
        self.threshold_line = pg.InfiniteLine(angle=0, movable=True, pen=pg.mkPen('r', width=2, style=Qt.PenStyle.DashLine))
        self.plot_widget.addItem(self.threshold_line, ignoreBounds=True)
        self.threshold_line.setPos(self.dtv_threshold_spin.value())
        self.threshold_line.hide()
        self.threshold_line.sigDragged.connect(self.on_threshold_line_dragged)
        self.dtv_threshold_spin.valueChanged.connect(self.on_threshold_spin_changed)
        
        # Intruder Threshold Line
        self.intruder_threshold_line = pg.InfiniteLine(angle=0, movable=True, pen=pg.mkPen('magenta', width=2, style=Qt.PenStyle.DashLine))
        self.plot_widget.addItem(self.intruder_threshold_line, ignoreBounds=True)
        self.intruder_threshold_line.setPos(self.intruder_threshold_spin.value())
        self.intruder_threshold_line.hide()
        self.intruder_threshold_line.sigDragged.connect(self.on_intruder_line_dragged)
        
        self.intruders = {} # Mapping of freq to max_power
        self.current_intruder_index = -1
        
        self.proxy1 = pg.SignalProxy(self.plot_widget.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved)
        self.proxy2 = pg.SignalProxy(self.waterfall_widget.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved)
        
        self._latest_x = None
        self._latest_y = None
        
        # Important: Initialize _x_multiplier to 1e6 so that the ViewBox starts off scaled properly
        self._x_multiplier = 1e6
        
        self.waterfall_history = None
        
        # Device Controller        
        self.controller = DeviceController()
        self.controller.spectrum_data_ready.connect(self.update_plot)
        self.controller.status_message.connect(self.update_status)
        self.controller.connection_status.connect(self.update_ui_state)
        self.controller.device_info_received.connect(self.handle_device_info)
        self.controller.trace_points_received.connect(self.update_trace_points)
        
        # Apply initial theme
        self.toggle_theme(self.theme_action.isChecked())
        
        # Bottom layout for size grip
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addStretch()
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("width: 15px; height: 15px;")
        bottom_layout.addWidget(self.size_grip)
        
        main_layout.addLayout(bottom_layout)
        
        # Ensure default disabled state is applied properly on launch
        self.update_ui_state(False)
        self.update_channel_markers()
        self.apply_frequencies()
        self.apply_view_frequencies()
        self.sync_quick_buttons_state()
        self.sync_view_quick_buttons_state()
        self._initializing = False
        
    def toggle_connection(self):
        if self.connect_btn.text() == "Connect Device":
            self.update_status("Probing device...")
            start_hz = self.start_spin.value() * 1e6
            stop_hz = self.stop_spin.value() * 1e6
            # Always probe first
            self.controller.connect_device(start_freq_hz=start_hz, stop_freq_hz=stop_hz, probe_only=True)
        else:
            self.controller.disconnect_device()
            self.update_ui_state(False)
            
    def toggle_left_panel(self):
        if self.left_scroll.isVisible():
            self.left_scroll.hide()
            self.toggle_left_btn.setText("▶")
        else:
            self.left_scroll.show()
            self.toggle_left_btn.setText("◀")

    def toggle_center_left_panel(self):
        if self.center_left_scroll.isVisible():
            self.center_left_scroll.hide()
            self.toggle_center_left_btn.setText("▶")
        else:
            self.center_left_scroll.show()
            self.toggle_center_left_btn.setText("◀")

    def toggle_right_panel(self):
        is_visible = self.right_scroll.isVisible()
        self.right_scroll.setVisible(not is_visible)
        self.toggle_right_btn.setText("◀" if is_visible else "▶")

    def set_soundbase_file_loaded(self, loaded: bool):
        if loaded:
            self.btn_soundbase_json.setStyleSheet("background-color: green; color: white; font-weight: bold;")
            self.btn_soundbase_json.setToolTip("File loaded in memory")
        else:
            self.btn_soundbase_json.setStyleSheet("background-color: gray; color: white; font-weight: bold;")
            self.btn_soundbase_json.setToolTip("No file loaded")

    def load_soundbase_json(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Soundbase Site JSON",
            "",
            "Soundbase Files (*.sbcoordsite *.json);;All Files (*)"
        )
        if not file_path:
            return

        try:
            # Try to read as gzip first (.sbcoordsite is usually gzipped)
            try:
                with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                    self.soundbase_data = json.load(f)
            except OSError:
                # If it's not a gzip file, read as standard JSON
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.soundbase_data = json.load(f)
            
            self.set_soundbase_file_loaded(True)
            self.parse_soundbase_data()
        except Exception as e:
            self.set_soundbase_file_loaded(False)
            QMessageBox.critical(self, "Error", f"Failed to load Soundbase file:\n{str(e)}")

    def parse_soundbase_data(self):
        if not hasattr(self, 'soundbase_data') or self.soundbase_data is None:
            return

        self.sb_zones = {}
        self.sb_dtv_channels = {}
        self.sb_zone_active_dtv = {}
        self.sb_groups = {}
        self.sb_frequencies = {}

        items = []
        if isinstance(self.soundbase_data, list):
            items = self.soundbase_data
        elif isinstance(self.soundbase_data, dict):
            items = self.soundbase_data.get("collections", self.soundbase_data.get("items", self.soundbase_data.get("data", [])))
            if not items and all(isinstance(v, dict) for v in self.soundbase_data.values()):
                items = list(self.soundbase_data.values())

        for item in items:
            if not isinstance(item, dict):
                continue
            c_type = item.get("type")
            c_name = item.get("collectionName")
            c_val = item.get("value", {})
            if not isinstance(c_val, dict):
                continue

            if c_name == "coordSite":
                channels = c_val.get("lastChannelSearch", {}).get("channels", [])
                if not channels:
                    channels = c_val.get("allChannels", [])
                
                for ch in channels:
                    ch_num = str(ch.get("channel", ""))
                    if ch_num:
                        self.sb_dtv_channels[ch_num] = ch
            
            elif c_name == "coordZone":
                z_id = c_val.get("_id")
                if z_id:
                    self.sb_zones[z_id] = c_val.get("name", "Unknown Zone")
                    
            elif c_name == "coordGroup":
                g_id = c_val.get("_id")
                z_id = c_val.get("zoneId")
                name = c_val.get("name", "Unknown Group")
                color = c_val.get("color", "")
                if z_id and g_id:
                    if z_id not in self.sb_groups:
                        self.sb_groups[z_id] = {}
                    self.sb_groups[z_id][g_id] = {"name": name, "color": color}
            
            elif c_name == "coordFreq":
                z_id = c_val.get("zoneId")
                g_id = c_val.get("groupId", "ungrouped")
                f_id = c_val.get("_id")
                
                if z_id:
                    if z_id not in self.sb_zone_active_dtv:
                        self.sb_zone_active_dtv[z_id] = {}
                    active_dtvs = c_val.get("settings", {}).get("activeDtv", [])
                    for dtv in active_dtvs:
                        ch = str(dtv.get("channel"))
                        if ch not in self.sb_zone_active_dtv[z_id]:
                            self.sb_zone_active_dtv[z_id][ch] = dtv
                            
                    freq_val = c_val.get("freq")
                    if freq_val:
                        freq_mhz = freq_val / 1e6
                        name = c_val.get("name", "Unnamed")
                        model_obj = c_val.get("model", {})
                        device = f"{model_obj.get('manufacturer', '')} {model_obj.get('model', '')}".strip()
                        band = model_obj.get('modelRangeName', '')
                        bandwidth_hz = model_obj.get('bandwidth', 100000)
                        bandwidth_mhz = bandwidth_hz / 1e6
                        
                        if z_id not in self.sb_frequencies:
                            self.sb_frequencies[z_id] = {}
                        if g_id not in self.sb_frequencies[z_id]:
                            self.sb_frequencies[z_id][g_id] = []
                            
                        self.sb_frequencies[z_id][g_id].append({
                            "freq": freq_mhz,
                            "name": name,
                            "device": device,
                            "band": band,
                            "id": f_id,
                            "bandwidth": bandwidth_mhz
                        })

        self.populate_markers_tree()
        self.update_freq_markers()
        
        # Clear existing layout
        self.dtv_zones_table.setRowCount(0)
        
        for btn in self.dtv_zone_btn_group.buttons():
            self.dtv_zone_btn_group.removeButton(btn)
        self.zone_radio_group = []
        
        row = 0
        for z_id, z_name in self.sb_zones.items():
            self.dtv_zones_table.insertRow(row)
            
            rb = QRadioButton()
            rb.setProperty("zone_id", z_id)
            rb.toggled.connect(self.on_dtv_zone_toggled)
            self.dtv_zone_btn_group.addButton(rb)
            self.zone_radio_group.append(rb)
            
            rb.setStyleSheet("""
                QRadioButton::indicator {
                    width: 12px;
                    height: 12px;
                    border: 2px solid gray;
                    border-radius: 6px;
                }
                QRadioButton::indicator:checked {
                    background-color: blue;
                }
            """)
            
            rb_container = QWidget()
            rb_layout = QHBoxLayout(rb_container)
            rb_layout.addWidget(rb)
            rb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rb_layout.setContentsMargins(0, 0, 0, 0)
            self.dtv_zones_table.setCellWidget(row, 0, rb_container)
            
            name_item = QTableWidgetItem(z_name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.dtv_zones_table.setItem(row, 1, name_item)
            
            self.dtv_zones_table.setRowHeight(row, 40)
            row += 1

    def on_dtv_zone_toggled(self, checked):
        if not checked:
            return
        rb = self.sender()
        z_id = rb.property("zone_id")
        self.populate_dtv_table_for_zone(z_id)

    def populate_markers_tree(self):
        self.markers_tree.blockSignals(True)
        self.markers_tree.clear()
        
        for z_id, z_name in self.sb_zones.items():
            zone_node = QTreeWidgetItem(self.markers_tree)
            zone_node.setText(0, z_name)
            zone_node.setFlags(zone_node.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            zone_node.setCheckState(0, Qt.CheckState.Checked)
            zone_node.setData(0, Qt.ItemDataRole.UserRole, {"type": "zone", "id": z_id})
            
            groups = self.sb_groups.get(z_id, {})
            freq_groups = self.sb_frequencies.get(z_id, {})
            
            all_g_ids = set(groups.keys()).union(freq_groups.keys())
            
            for g_id in all_g_ids:
                freqs = freq_groups.get(g_id, [])
                if not freqs:
                    continue
                
                g_dict = groups.get(g_id, {"name": "Ungrouped", "color": ""})
                if isinstance(g_dict, str):
                    g_dict = {"name": g_dict, "color": ""}
                
                g_name = g_dict.get("name", "Ungrouped")
                g_color = g_dict.get("color", "")
                
                group_node = QTreeWidgetItem(zone_node)
                group_node.setText(0, g_name)
                if g_color:
                    group_node.setForeground(0, QBrush(QColor(g_color)))
                group_node.setFlags(group_node.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                group_node.setCheckState(0, Qt.CheckState.Checked)
                group_node.setData(0, Qt.ItemDataRole.UserRole, {"type": "group", "id": g_id})
                
                for freq in sorted(freqs, key=lambda x: x["freq"]):
                    freq_node = QTreeWidgetItem(group_node)
                    band_str = f", {freq.get('band')}" if freq.get('band') else ""
                    freq_str = f"{freq['freq']:.3f} MHz - {freq['name']}\n{freq['device']}{band_str}"
                    freq_node.setText(0, freq_str)
                    if g_color:
                        freq_node.setForeground(0, QBrush(QColor(g_color)))
                    freq_node.setFlags(freq_node.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    freq_node.setCheckState(0, Qt.CheckState.Checked)
                    freq_node.setData(0, Qt.ItemDataRole.UserRole, {
                        "type": "freq", 
                        "id": freq["id"], 
                        "freq": freq["freq"],
                        "device": freq["device"],
                        "bandwidth": freq["bandwidth"],
                        "color": g_color
                    })
                    
        self.markers_tree.blockSignals(False)

    def on_marker_tree_item_changed(self, item, column):
        self.markers_tree.blockSignals(True)
        check_state = item.checkState(column)
        
        def set_children_state(parent, state):
            for i in range(parent.childCount()):
                child = parent.child(i)
                child.setCheckState(0, state)
                set_children_state(child, state)
                
        set_children_state(item, check_state)
        self.markers_tree.blockSignals(False)
        self.update_freq_markers()

    def update_freq_markers(self):
        if not hasattr(self, 'freq_mask_items'):
            self.freq_mask_items = {}
            self.freq_text_items = {}
            
        for mask in self.freq_mask_items.values():
            self.plot_widget.removeItem(mask)
        self.freq_mask_items.clear()
        
        for text in self.freq_text_items.values():
            self.plot_widget.removeItem(text)
        self.freq_text_items.clear()
        
        KNOWN_CARRIERS = {
            "AD4Q": 0.090,
            "AD4D": 0.090,
            "ADTQ": 0.090,
            "ADTD": 0.090,
            "PSM 1000": 0.200,
            "PSM1000": 0.200,
            "MTK952": 0.200,
            "MTK982": 0.200,
            "SK 6000": 0.200,
            "EM 6000": 0.200,
            "Digital 6000": 0.200
        }
        
        root = self.markers_tree.invisibleRootItem()
        for i in range(root.childCount()):
            zone_node = root.child(i)
            for j in range(zone_node.childCount()):
                group_node = zone_node.child(j)
                for k in range(group_node.childCount()):
                    freq_node = group_node.child(k)
                    
                    if freq_node.checkState(0) == Qt.CheckState.Checked:
                        data = freq_node.data(0, Qt.ItemDataRole.UserRole)
                        freq_id = data.get("id")
                        fc = data.get("freq")
                        device = data.get("device", "")
                        bandwidth = data.get("bandwidth", 0.350)
                        hex_color = data.get("color", "")
                        
                        top_bw = 0.100
                        for key, val in KNOWN_CARRIERS.items():
                            if key in device:
                                top_bw = val
                                break
                                
                        color = QColor(hex_color) if hex_color else QColor("gray")
                        
                        saturation_pct = self.settings.value("marker_saturation", 100, type=int)
                        h, s, v, a = color.getHsv()
                        new_s = int(s * (saturation_pct / 100.0))
                        color.setHsv(h, new_s, v, a)
                        
                        opacity_pct = self.settings.value("marker_opacity", 25, type=int)
                        color.setAlpha(int(255 * (opacity_pct / 100.0)))
                        
                        bottom_bw = bandwidth
                        
                        x = [fc - bottom_bw/2, fc - top_bw/2, fc + top_bw/2, fc + bottom_bw/2]
                        y = [-150, 20, 20, -150]
                        
                        mask_item = pg.PlotDataItem(x, y, fillLevel=-150, fillBrush=QBrush(color), pen=pg.mkPen(color, width=2))
                        self.plot_widget.addItem(mask_item)
                        self.freq_mask_items[freq_id] = mask_item
                        
                        name = data.get("name", "Unnamed")
                        band = data.get("band", "")
                        
                        r = color.red()
                        g = color.green()
                        b = color.blue()
                        luminance = 0.299 * r + 0.587 * g + 0.114 * b
                        text_color = "black" if luminance > 128 else "white"
                        
                        html_text = f"<div style='text-align: center; color: {text_color};'><span style='font-size: 8pt; font-weight: bold;'>{fc:g} MHz / {name}</span><br><span style='font-size: 7pt;'>{device} / {band}</span></div>"
                        
                        text_item = pg.TextItem(html=html_text, anchor=(0.5, 1.0))
                        text_item.setPos(fc, -115)
                        self.plot_widget.addItem(text_item)
                        self.freq_text_items[freq_id] = text_item
                        
        self.update_marker_text_visibility()

    def populate_dtv_table_for_zone(self, zone_id):
        self.dtv_table.setRowCount(0)
        active_dtvs_dict = self.sb_zone_active_dtv.get(zone_id, {})
        
        active_ch_nums = [ch for ch, d in active_dtvs_dict.items() if d.get("isActive")]
        try:
            active_ch_nums.sort(key=int)
        except ValueError:
            active_ch_nums.sort()
        
        self.active_channels.clear()
        
        row = 0
        for ch_num in active_ch_nums:
            ch_data = self.sb_dtv_channels.get(ch_num)
            if not ch_data:
                continue
            
            self.dtv_table.insertRow(row)
            
            ch_item = QTableWidgetItem(str(ch_num))
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.dtv_table.setItem(row, 0, ch_item)
            
            call_sign = str(ch_data.get("callsign", ""))
            cs_item = QTableWidgetItem(call_sign)
            cs_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.dtv_table.setItem(row, 1, cs_item)
            
            erp = str(ch_data.get("power", ch_data.get("ant_ERP_kW", "")))
            erp_item = QTableWidgetItem(erp)
            erp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.dtv_table.setItem(row, 2, erp_item)
            
            dist_val = ch_data.get("distance", ch_data.get("distanceInMiles"))
            dist_str = str(dist_val).strip()
            
            if dist_val is None or dist_str == "" or dist_str.lower() == "none":
                dist_str = "NONE"
                is_ps = True
            else:
                is_ps = False
                
            dist_item = QTableWidgetItem(dist_str)
            dist_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.dtv_table.setItem(row, 3, dist_item)
            
            # Set public safety role on the channel item
            ch_item.setData(Qt.ItemDataRole.UserRole, is_ps)
            
            self.active_channels[int(ch_num)] = True
            
            row += 1
            
        ps_dict = {}
        for i in range(self.dtv_table.rowCount()):
            c_item = self.dtv_table.item(i, 0)
            if c_item and c_item.data(Qt.ItemDataRole.UserRole):
                ps_dict[int(c_item.text())] = True
                
        if hasattr(self, 'waterfall_channels'):
            self.waterfall_channels.set_active_channels(self.active_channels, ps_dict)
        if hasattr(self, 'spectrum_channels'):
            self.spectrum_channels.set_active_channels(self.active_channels, ps_dict)
            
        self.update_channel_masks()

    def toggle_play_pause(self):
        if not self.controller.is_connected:
            return
            
        if self.play_pause_btn.isChecked(): # Paused
            self.play_pause_btn.setText("Play")
            self.play_pause_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
            self.controller.pause()
            self.update_status("Connected, Paused")
        else: # Running
            self.play_pause_btn.setText("Pause")
            self.play_pause_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
            self.controller.start()
            self.set_running_status()

    def set_running_status(self):
        if self.controller.is_connected and not self.play_pause_btn.isChecked():
            self.update_status("Running")
            
    def check_span_correlation(self):
        if getattr(self, 'link_view_check', None) and self.link_view_check.isChecked():
            if hasattr(self, 'spectrum_span_alert'): self.spectrum_span_alert.hide()
            if hasattr(self, 'view_panel_span_alert'): self.view_panel_span_alert.hide()
            return
            
        sweep_start = self.start_spin.value()
        sweep_stop = self.stop_spin.value()
        view_start = self.view_start_spin.value()
        view_stop = self.view_stop_spin.value()
        
        # View is larger if it starts before or ends after what is actively swept
        is_larger = (view_start < sweep_start - 0.1) or (view_stop > sweep_stop + 0.1)
        
        if hasattr(self, 'spectrum_span_alert'):
            self.spectrum_span_alert.setVisible(is_larger)
        if hasattr(self, 'view_panel_span_alert'):
            self.view_panel_span_alert.setVisible(is_larger)

    def show_settings_dialog(self):
        dialog = SettingsDialog(self, self)
        dialog.exec()

    def apply_frequencies(self):
        start_hz = self.start_spin.value() * 1e6
        stop_hz = self.stop_spin.value() * 1e6
        
        if self.controller.is_connected:
            self.controller.configure(start_hz, stop_hz)
            self.apply_bandwidth()
            
        if hasattr(self, 'link_view_check') and self.link_view_check.isChecked():
            # Sync the view settings
            self._updating_view_freqs = True
            self.view_start_spin.setValue(self.start_spin.value())
            self.view_stop_spin.setValue(self.stop_spin.value())
            self.view_center_spin.setValue(self.center_spin.value())
            self.view_span_spin.setValue(self.span_spin.value())
            self._updating_view_freqs = False
            self.apply_view_frequencies()
            self.sync_view_quick_buttons_state()

        self.sync_quick_buttons_state()
        self.check_span_correlation()

    def apply_view_frequencies(self):
        if getattr(self, '_updating_view_freqs', False): return
        self._updating_view_freqs = True
        try:
            # Update the UI range immediately
            start_hz = self.view_start_spin.value() * 1e6
            stop_hz = self.view_stop_spin.value() * 1e6
            mult = getattr(self, '_x_multiplier', 1e6)
            self.plot_widget.setXRange(start_hz / mult, stop_hz / mult, padding=0)
            self.waterfall_widget.setXRange(start_hz / mult, stop_hz / mult, padding=0)
            self.reset_trace_buffers()
            self.check_span_correlation()
        finally:
            self._updating_view_freqs = False
            
    def on_plot_range_changed(self, *args):
        if getattr(self, '_updating_view_freqs', False) or getattr(self, '_initializing', False): return
        view_box = self.plot_widget.getViewBox()
        x_range = view_box.viewRange()[0]
        
        self._updating_view_freqs = True
        try:
            mult = getattr(self, '_x_multiplier', 1e6)
            self.view_start_spin.setValue(x_range[0] * (mult / 1e6))
            self.view_stop_spin.setValue(x_range[1] * (mult / 1e6))
            center = (x_range[0] + x_range[1]) / 2.0 * (mult / 1e6)
            span = (x_range[1] - x_range[0]) * (mult / 1e6)
            self.view_center_spin.setValue(center)
            self.view_span_spin.setValue(span)
            self.sync_view_quick_buttons_state()
            
            if hasattr(self, 'link_view_check') and self.link_view_check.isChecked():
                self._updating_freqs = True
                self.start_spin.setValue(x_range[0] * (mult / 1e6))
                self.stop_spin.setValue(x_range[1] * (mult / 1e6))
                self.center_spin.setValue(center)
                self.span_spin.setValue(span)
                self._updating_freqs = False
                self.sync_quick_buttons_state()
            
            y_range = view_box.viewRange()[1]
            self.update_marker_text_visibility(span, y_range[0])
            self.check_span_correlation()
        finally:
            self._updating_view_freqs = False
            
    def update_marker_text_visibility(self, span=None, y_min=None):
        if not hasattr(self, 'freq_text_items'):
            return
            
        view_box = self.plot_widget.getViewBox()
        if span is None or y_min is None:
            x_range = view_box.viewRange()[0]
            y_range = view_box.viewRange()[1]
            span = x_range[1] - x_range[0]
            y_min = y_range[0]
            
        show_nb_labels = self.settings.value("show_nb_labels", True, type=bool)
        show_text = (span < 6.0) and show_nb_labels
        
        # Calculate a safe Y position near the bottom of the screen (e.g. 2% from the bottom edge)
        y_range = view_box.viewRange()[1]
        y_pos = y_range[0] + (y_range[1] - y_range[0]) * 0.02
        
        for item in self.freq_text_items.values():
            if show_text:
                # Update position to always stay visible at the bottom of the current view
                current_x = item.pos().x()
                item.setPos(current_x, y_pos)
            item.setVisible(show_text)
        
    def on_link_view_toggled(self, checked):
        if checked:
            self.apply_frequencies()
            self.sync_view_quick_buttons_state()
        self.check_span_correlation()

    def on_nb_labels_toggled(self, checked):
        self.settings.setValue("show_nb_labels", checked)
        self.update_marker_text_visibility()
        
    def on_dtv_labels_toggled(self, checked):
        self.settings.setValue("show_dtv_labels", checked)
        self.update_channel_masks()

    def show_marker_settings_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Marker Opacity & Saturation")
        dialog.setFixedSize(350, 120)
        
        layout = QFormLayout(dialog)
        
        opacity_slider = QSlider(Qt.Orientation.Horizontal)
        opacity_slider.setRange(0, 100)
        opacity_slider.setValue(self.settings.value("marker_opacity", 25, type=int))
        
        saturation_slider = QSlider(Qt.Orientation.Horizontal)
        saturation_slider.setRange(0, 100)
        saturation_slider.setValue(self.settings.value("marker_saturation", 100, type=int))
        
        def on_changed():
            self.settings.setValue("marker_opacity", opacity_slider.value())
            self.settings.setValue("marker_saturation", saturation_slider.value())
            self.update_freq_markers()
            self.update_channel_masks()
            
        opacity_slider.valueChanged.connect(on_changed)
        saturation_slider.valueChanged.connect(on_changed)
        
        layout.addRow("Opacity (%):", opacity_slider)
        layout.addRow("Saturation (%):", saturation_slider)
        
        dialog.exec()

    def on_fcc_lookup(self):
        zip_code = self.zip_input.text().strip()
        if not zip_code or len(zip_code) != 5:
            QMessageBox.warning(self, "Invalid ZIP", "Please enter a valid 5-digit ZIP code.")
            return
            
        if self.spectrum_region == "US - FCC":
            db = self.fcc_db
        else:
            db = self.ofcom_db

        if db.needs_update():
            if not db.has_data():
                # Never downloaded, prompt
                reply = QMessageBox.question(self, "Download Required", 
                                          f"To use the {self.spectrum_region} Lookup, you must download or import the regional dataset.\nWould you like to do this now?",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self.show_settings_dialog()
            else:
                # Greater than 30 days old
                reply = QMessageBox.question(self, "Update Available", 
                                          f"Your {self.spectrum_region} spectrum dataset is over 30 days old.\nWould you like to update it now?",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self.show_settings_dialog()
                else:
                    self.populate_dtv_table(zip_code)
            return
            
        self.populate_dtv_table(zip_code)
        
    def update_table_colors(self):
        for i in range(self.dtv_table.rowCount()):
            ch_item = self.dtv_table.item(i, 0)
            if ch_item:
                try:
                    ch = int(ch_item.text())
                    is_active = self.active_channels.get(ch, False)
                    color = QColor(150, 0, 0) if (is_active and ch_item.data(Qt.ItemDataRole.UserRole)) else QColor(0, 0, 150)
                    if not is_active:
                        color.setAlpha(0)
                    else:
                        color.setAlpha(100)
                    for j in range(self.dtv_table.columnCount()):
                        self.dtv_table.item(i, j).setBackground(color)
                except ValueError:
                    pass

    def on_dtv_table_clicked(self, row, column):
        if column != 0:
            return
            
        ch_item = self.dtv_table.item(row, 0)
        if ch_item:
            try:
                ch = int(ch_item.text())
                self.active_channels[ch] = not self.active_channels.get(ch, False)
                self.update_table_colors()
                
                ps_dict = self._get_ps_dict()
                self.waterfall_channels.set_active_channels(self.active_channels, ps_dict)
                self.spectrum_channels.set_active_channels(self.active_channels, ps_dict)
                self.update_channel_masks()
            except ValueError:
                pass

    def populate_dtv_table(self, zip_code):
        if self.spectrum_region == "US - FCC":
            stations = self.fcc_db.get_stations_near_zip(zip_code)
        else:
            stations = []
            QMessageBox.information(self, "Not Implemented", "Ofcom postcode lookup is not fully implemented yet.")
        self.dtv_table.setRowCount(0)
        
        # Filter first to ensure we only deduplicate among actual threats
        valid_stations = []
        for s in stations:
            ch = s['channel']
            if ch < 2 or ch > 36:
                continue
            if self.should_auto_flag_station(s):
                valid_stations.append(s)
                
        # Deduplicate strictly by channel, keeping the highest ERP transmitter
        best_stations = {}
        for s in valid_stations:
            key = s['channel']
            
            # Give Public Safety / T-Band injections infinite priority so they aren't overwritten
            if s.get('is_public_safety'):
                erp_val = float('inf')
            else:
                erp = s.get('erp', 0.0)
                if erp == 'N/A' or erp is None:
                    erp_val = 0.0
                else:
                    try:
                        erp_val = float(erp)
                    except (ValueError, TypeError):
                        erp_val = 0.0
                    
            if key not in best_stations:
                best_stations[key] = (s, erp_val)
            else:
                if erp_val > best_stations[key][1]:
                    best_stations[key] = (s, erp_val)
                    
        dedup_stations = [item[0] for item in best_stations.values()]
                
        # Sort ascending by channel
        dedup_stations.sort(key=lambda x: x['channel'], reverse=False)
        
        for s in dedup_stations:
            ch = s['channel']
                
            row = self.dtv_table.rowCount()
            self.dtv_table.insertRow(row)
            
            ch_item = QTableWidgetItem(str(ch))
            ch_item.setData(Qt.ItemDataRole.UserRole, s['is_public_safety'])
            
            call_item = QTableWidgetItem(s['call_sign'])
            
            if s['is_public_safety']:
                type_str = ""
            else:
                type_str = f"{s['erp']} kW" if s['erp'] != 'N/A' else ""
                
            type_item = QTableWidgetItem(type_str)
            dist_item = QTableWidgetItem(f"{s['distance_km']} km")
            
            # Auto-enable threats
            self.active_channels[ch] = True
            
            self.dtv_table.setItem(row, 0, ch_item)
            self.dtv_table.setItem(row, 1, call_item)
            self.dtv_table.setItem(row, 2, type_item)
            self.dtv_table.setItem(row, 3, dist_item)
            
        self.update_table_colors()
        
        # Make sure the buttons update immediately
        ps_dict = self._get_ps_dict()
        self.waterfall_channels.set_active_channels(self.active_channels, ps_dict)
        self.spectrum_channels.set_active_channels(self.active_channels, ps_dict)
        self.update_channel_masks()

    def should_auto_flag_station(self, s):
        import math
        dist_km = s.get('distance_km')
        erp = s.get('erp')
        ch = s.get('channel')
        
        if dist_km is None:
            return True
            
        dist_miles = dist_km * 0.621371
        
        # Public Safety / T-Band injections
        if s.get('is_public_safety'):
            if dist_miles <= 60.0:  # FCC protects T-band within ~50 miles
                return True
            return False
            
        # Failsafe
        if erp == 'N/A' or erp is None:
            if dist_miles <= 10.0:
                return True
            return False
            
        try:
            erp_float = float(erp)
        except (ValueError, TypeError):
            if dist_miles <= 10.0:
                return True
            return False
            
        # Discount distant signals
        if dist_km >= 100.0 and erp_float < 175.0:
            return False
            
        if 2 <= ch <= 13: # VHF
            # Cap extreme ERP anomalies in the database for VHF
            effective_erp = min(erp_float, 316.0)
            radius_km = 80 * math.sqrt(effective_erp / 100.0)
            radius_miles = radius_km * 0.621371
            if math.floor(radius_miles) >= math.floor(dist_miles):
                return True
        elif ch >= 14: # UHF
            # A 1000 kW station covers roughly 75 km (46 miles) reliably
            radius_km = 75 * math.sqrt(erp_float / 1000.0)
            radius_miles = radius_km * 0.621371
            if math.floor(radius_miles) >= math.floor(dist_miles):
                return True
                
        return False
        
    def on_show_threshold_toggled(self, checked):
        if checked:
            self.threshold_line.setPos(self.dtv_threshold_spin.value())
            self.threshold_line.show()
        else:
            self.threshold_line.hide()
            
    def on_threshold_line_dragged(self):
        val = self.threshold_line.value()
        self.dtv_threshold_spin.setValue(val)
        
    def on_threshold_spin_changed(self, value):
        self.threshold_line.setPos(value)
        
    def on_intruder_alert_toggled(self, checked):
        if checked:
            self.intruder_threshold_line.show()
        else:
            self.intruder_threshold_line.hide()
            self.intruder_alert_btn.setVisible(False)
            self.intruder_prev_btn.setVisible(False)
            self.intruder_next_btn.setVisible(False)
            
    def on_intruder_line_dragged(self):
        val = self.intruder_threshold_line.value()
        self.intruder_threshold_spin.setValue(val)
        
    def on_intruder_threshold_changed(self, value):
        self.intruder_threshold_line.setPos(value)
        
    def clear_intruders(self):
        self.intruders.clear()
        self.current_intruder_index = -1
        self.intruder_table.setRowCount(0)
        self.intruder_alert_btn.setVisible(False)
        self.intruder_prev_btn.setVisible(False)
        self.intruder_next_btn.setVisible(False)
        
    def add_intruder_to_markers(self):
        selected_items = self.intruder_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select an intruder from the list first.")
            return
            
        freq_mhz = float(self.intruder_table.item(selected_items[0].row(), 0).text())
        
        matched_device = "Unknown"
        for f, d in self.intruders.items():
            if abs(f - freq_mhz) < 0.001 and isinstance(d, dict) and "classification" in d:
                matched_device = d["classification"]["device"]
                break
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Intruder to Markers")
        layout = QFormLayout(dialog)
        
        zone_id_map = getattr(self, 'sb_zones', {})
        zone_names = list(zone_id_map.values()) if zone_id_map else ["Intruders"]
        
        zone_combo = QComboBox()
        zone_combo.setEditable(True)
        zone_combo.addItems(zone_names)
        layout.addRow("Zone:", zone_combo)
        
        group_combo = QComboBox()
        group_combo.setEditable(True)
        
        def update_groups(selected_zone_name):
            group_combo.clear()
            matching_zid = next((zid for zid, name in getattr(self, 'sb_zones', {}).items() if name == selected_zone_name), None)
            if matching_zid and hasattr(self, 'sb_groups') and matching_zid in self.sb_groups:
                gnames = [g_info.get("name", "Group") for g_info in self.sb_groups[matching_zid].values()]
                group_combo.addItems(gnames)
            if group_combo.count() == 0:
                group_combo.addItem("Intruders")
                
        zone_combo.currentTextChanged.connect(update_groups)
        update_groups(zone_combo.currentText())
        layout.addRow("Group:", group_combo)
        
        name_input = QLineEdit("Intruder")
        layout.addRow("Name:", name_input)
        
        device_input = QLineEdit(matched_device)
        layout.addRow("Device:", device_input)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addRow(btn_box)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            zone_name = zone_combo.currentText().strip() or "Intruders"
            group_name = group_combo.currentText().strip() or "Intruders"
            marker_name = name_input.text().strip() or "Intruder"
            device_name = device_input.text().strip() or "Unknown"
            
            if not hasattr(self, 'sb_zones'):
                self.sb_zones = {}
            if not hasattr(self, 'sb_groups'):
                self.sb_groups = {}
            if not hasattr(self, 'sb_frequencies'):
                self.sb_frequencies = {}
                
            # Find or create zone ID
            z_id = next((zid for zid, name in self.sb_zones.items() if name == zone_name), None)
            if not z_id:
                z_id = f"zone_{int(time.time()*1000)}"
                self.sb_zones[z_id] = zone_name
                
            if z_id not in self.sb_groups:
                self.sb_groups[z_id] = {}
            if z_id not in self.sb_frequencies:
                self.sb_frequencies[z_id] = {}
                
            # Find or create group ID
            g_id = next((gid for gid, ginfo in self.sb_groups[z_id].items() if ginfo.get("name") == group_name), None)
            if not g_id:
                g_id = f"group_{int(time.time()*1000)}"
                self.sb_groups[z_id][g_id] = {"name": group_name, "color": "#FF0055"}
                
            if g_id not in self.sb_frequencies[z_id]:
                self.sb_frequencies[z_id][g_id] = []
                
            f_id = f"freq_{int(time.time()*1000)}"
            self.sb_frequencies[z_id][g_id].append({
                "id": f_id,
                "name": marker_name,
                "freq": float(freq_mhz),
                "bandwidth": 0.200,
                "device": device_name,
                "band": "Intruder"
            })
            
            keys_to_remove = [k for k in self.intruders.keys() if abs(k - freq_mhz) < 0.001]
            for k in keys_to_remove:
                self.intruders.pop(k, None)
                
            self._update_intruder_table()
            self.populate_markers_tree()

    def on_intruder_prev(self):
        if not self.intruders: return
        sorted_freqs = sorted(self.intruders.keys())
        self.current_intruder_index = (self.current_intruder_index - 1) % len(sorted_freqs)
        self._zoom_to_intruder(sorted_freqs[self.current_intruder_index])
        
    def on_intruder_alert_clicked(self):
        if not self.intruders: return
        sorted_freqs = sorted(self.intruders.keys())
        self.current_intruder_index = 0
        self._zoom_to_intruder(sorted_freqs[self.current_intruder_index])
        
    def on_intruder_next(self):
        if not self.intruders: return
        sorted_freqs = sorted(self.intruders.keys())
        self.current_intruder_index = (self.current_intruder_index + 1) % len(sorted_freqs)
        self._zoom_to_intruder(sorted_freqs[self.current_intruder_index])
        
    def _zoom_to_intruder(self, freq_mhz):
        span = 3.0
        start_mhz = freq_mhz - (span / 2)
        stop_mhz = freq_mhz + (span / 2)
        mult = getattr(self, '_x_multiplier', 1e6)
        
        self.plot_widget.setXRange(start_mhz * (1e6 / mult), stop_mhz * (1e6 / mult), padding=0)
        
        for row in range(self.intruder_table.rowCount()):
            item = self.intruder_table.item(row, 0)
            if item and abs(float(item.text()) - freq_mhz) < 0.001:
                self.intruder_table.selectRow(row)
                break
                
    def _update_intruder_table(self):
        self.intruder_table.setRowCount(0)
        sorted_intruders = sorted(self.intruders.items(), key=lambda x: x[0])
        for freq, data in sorted_intruders:
            power = data["power"] if isinstance(data, dict) else data
            cls_info = data.get("classification") if isinstance(data, dict) else None
            
            row = self.intruder_table.rowCount()
            self.intruder_table.insertRow(row)
            
            freq_item = QTableWidgetItem(f"{freq:.3f}")
            pwr_item = QTableWidgetItem(f"{power:.1f} dBm")
            
            if cls_info:
                dev_name = f"{cls_info['device']} ({cls_info['confidence']}%)"
                sig_item = QTableWidgetItem(dev_name)
                sig_item.setForeground(QColor(cls_info.get("color", "#00bcd4")))
                sig_item.setToolTip(f"{cls_info['device']}\nCategory: {cls_info.get('category', 'Unknown')}\n{cls_info.get('details', '')}\nOBW (-3dB): {cls_info.get('obw_3db_khz', 0):.0f} kHz\nShape Factor: {cls_info.get('shape_factor', 1.0):.2f}")
            else:
                sig_item = QTableWidgetItem("Unknown Carrier")
                sig_item.setForeground(QColor("#888888"))
                
            self.intruder_table.setItem(row, 0, freq_item)
            self.intruder_table.setItem(row, 1, pwr_item)
            self.intruder_table.setItem(row, 2, sig_item)
            
        has_intruders = len(sorted_intruders) > 0
        self.intruder_alert_btn.setVisible(has_intruders)
        self.intruder_prev_btn.setVisible(has_intruders)
        self.intruder_next_btn.setVisible(has_intruders)
        
    def on_dect_band_changed(self, band_name):
        if hasattr(self, 'dect_engine'):
            self.dect_engine.set_band(band_name)
            self.clear_dect_data()
            if hasattr(self, '_tdma_dialog') and self._tdma_dialog and self._tdma_dialog.isVisible():
                self._tdma_dialog._build_grid()

    def on_dect_enable_toggled(self, checked):
        if hasattr(self, 'dect_engine'):
            self.dect_engine.set_enabled(checked)
            if not checked:
                self.clear_dect_data()

    def tune_to_dect_band(self):
        band_name = self.dect_band_combo.currentText()
        band_info = DECT_BANDS.get(band_name)
        if band_info:
            self._updating_freqs = True
            self.start_spin.setValue(band_info["start_mhz"])
            self.stop_spin.setValue(band_info["stop_mhz"])
            self.center_spin.setValue(band_info["center_mhz"])
            self.span_spin.setValue(band_info["span_mhz"])
            self._updating_freqs = False
            self.apply_frequencies()

    def open_tdma_matrix_dialog(self):
        if not hasattr(self, '_tdma_dialog') or not self._tdma_dialog:
            self._tdma_dialog = TDMATimeslotDialog(self.dect_engine, self)
        self._tdma_dialog.show()
        self._tdma_dialog.raise_()
        self._tdma_dialog.activateWindow()

    def clear_dect_data(self):
        if hasattr(self, 'dect_engine'):
            self.dect_engine.reset_data()
        self.dect_table.setRowCount(0)

    def on_dect_analysis_updated(self, data):
        self.dect_table.setRowCount(0)
        carriers = data.get("carriers", {})
        antennas = data.get("total_antennas", 0)
        beltpacks = data.get("total_beltpacks", 0)
        band_load = data.get("band_load_pct", 0.0)
        
        load_text = "CLEAN" if band_load < 5.0 else ("LIGHT" if band_load < 20.0 else ("MODERATE" if band_load < 45.0 else "HEAVY"))
        if hasattr(self, 'dect_summary_lbl'):
            self.dect_summary_lbl.setText(f"Load: {band_load:.0f}% ({load_text}) | {antennas} Ant | ~{beltpacks} Packs")
            
        for cf, c in sorted(carriers.items(), key=lambda x: x[1]["ch"]):
            row = self.dect_table.rowCount()
            self.dect_table.insertRow(row)
            
            ch_item = QTableWidgetItem(f"Ch {c['ch']}")
            rssi_item = QTableWidgetItem(f"{c['smoothed_dbm']:.1f} dBm" if c['active'] else "—")
            duty_item = QTableWidgetItem(f"{c['duty_cycle_pct']:.0f}%")
            status_item = QTableWidgetItem(c["status"])
            
            status_item.setForeground(QColor(c["color"]))
            if c["active"]:
                rssi_item.setForeground(QColor("#00bcd4"))
                duty_item.setForeground(QColor(c["color"]))
            else:
                status_item.setForeground(QColor("#888888"))
                duty_item.setForeground(QColor("#888888"))
                
            self.dect_table.setItem(row, 0, ch_item)
            self.dect_table.setItem(row, 1, rssi_item)
            self.dect_table.setItem(row, 2, duty_item)
            self.dect_table.setItem(row, 3, status_item)
                
    def on_showlink_enable_toggled(self, checked):
        if hasattr(self, 'showlink_engine'):
            self.showlink_engine.set_enabled(checked)
            if not checked:
                self.clear_showlink_data()

    def tune_to_showlink_band(self):
        self._updating_freqs = True
        self.start_spin.setValue(2400.0)
        self.stop_spin.setValue(2483.5)
        self.center_spin.setValue(2441.75)
        self.span_spin.setValue(83.5)
        self._updating_freqs = False
        self.apply_frequencies()

    def open_showlink_map_dialog(self):
        if not hasattr(self, '_showlink_dialog') or not self._showlink_dialog:
            self._showlink_dialog = ShowlinkMapDialog(self.showlink_engine, self)
        self._showlink_dialog.show()
        self._showlink_dialog.raise_()
        self._showlink_dialog.activateWindow()

    def clear_showlink_data(self):
        if hasattr(self, 'showlink_engine'):
            self.showlink_engine.reset_data()
        self.showlink_table.setRowCount(0)

    def on_showlink_analysis_updated(self, data):
        self.showlink_table.setRowCount(0)
        channels = data.get("channels", {})
        
        # Sort by channel number
        for ch, info in sorted(channels.items(), key=lambda x: x[0]):
            row = self.showlink_table.rowCount()
            self.showlink_table.insertRow(row)
            
            ch_item = QTableWidgetItem(f"Ch {ch}")
            freq_item = QTableWidgetItem(f"{info['freq_mhz']:.0f} MHz")
            rssi_item = QTableWidgetItem(f"{info['peak_dbm']:.1f} dBm")
            status_item = QTableWidgetItem(info["status"])
            
            status_item.setForeground(QColor(info["color"]))
            if "EXCELLENT" in info["status"] or "CLEAR" in info["status"]:
                rssi_item.setForeground(QColor("#00e676"))
            elif "CONGESTED" in info["status"]:
                rssi_item.setForeground(QColor("#e53935"))
            else:
                rssi_item.setForeground(QColor("#ffb300"))
                
            self.showlink_table.setItem(row, 0, ch_item)
            self.showlink_table.setItem(row, 1, freq_item)
            self.showlink_table.setItem(row, 2, rssi_item)
            self.showlink_table.setItem(row, 3, status_item)
        
    def _process_intruder_detect(self, x, y):
        threshold = self.intruder_threshold_spin.value()
        
        # Simple peak detection: y[i] > y[i-1] and y[i] > y[i+1] and y[i] > threshold
        peaks = []
        for i in range(1, len(y) - 1):
            if y[i] > threshold and y[i] > y[i-1] and y[i] > y[i+1]:
                peaks.append((x[i] / 1e6, y[i]))
                
        if not peaks:
            return
            
        KNOWN_CARRIERS = {
            "AD4Q": 0.090, "AD4D": 0.090, "ADTQ": 0.090, "ADTD": 0.090,
            "PSM 1000": 0.200, "PSM1000": 0.200, "MTK952": 0.200, "MTK982": 0.200,
            "SK 6000": 0.200, "EM 6000": 0.200, "Digital 6000": 0.200
        }
            
        # Build list of active mask boundaries (min_freq, max_freq)
        active_masks = []
        
        # 1. DTV Active Channels
        for ch_key, is_active in self.active_channels.items():
            if not is_active:
                continue
            try:
                ch_num = int(ch_key)
            except (ValueError, TypeError):
                continue
            if ch_num <= 13:
                start_ch = 7
                start_freq_mhz = 174
            else:
                start_ch = 14
                start_freq_mhz = 470
            lower_edge = start_freq_mhz + (ch_num - start_ch) * 6
            upper_edge = lower_edge + 6
            active_masks.append((lower_edge, upper_edge))
            
        # 2. Soundbase/Imported Markers
        root = self.markers_tree.invisibleRootItem()
        for i in range(root.childCount()):
            zone_node = root.child(i)
            for j in range(zone_node.childCount()):
                group_node = zone_node.child(j)
                for k in range(group_node.childCount()):
                    freq_node = group_node.child(k)
                    if freq_node.checkState(0) == Qt.CheckState.Checked:
                        data = freq_node.data(0, Qt.ItemDataRole.UserRole)
                        fc = data.get("freq")
                        device = data.get("device", "")
                        bw = data.get("bandwidth", 0.350)
                        active_masks.append((fc - bw/2, fc + bw/2))
                        
        new_intruders_detected = False
        freqs_mhz = x / 1e6
        
        for freq_mhz, power in peaks:
            is_masked = False
            for m_min, m_max in active_masks:
                if m_min <= freq_mhz <= m_max:
                    is_masked = True
                    break
            
            if not is_masked:
                # Classify transmitter signature
                cls_info = TransmitterClassifier.classify_peak(
                    freqs_mhz, y, freq_mhz, power, region=getattr(self, 'current_region', 'North America')
                )
                
                # Check if it's close to an existing one
                merged = False
                for existing_freq in list(self.intruders.keys()):
                    if abs(existing_freq - freq_mhz) < 0.200: # 200kHz merge window
                        old_val = self.intruders[existing_freq]
                        old_pwr = old_val["power"] if isinstance(old_val, dict) else old_val
                        self.intruders[existing_freq] = {
                            "power": max(old_pwr, power),
                            "classification": cls_info
                        }
                        merged = True
                        break
                
                if not merged:
                    self.intruders[freq_mhz] = {
                        "power": power,
                        "classification": cls_info
                    }
                    new_intruders_detected = True
                    self.current_intruder_index = 0 # Point to most recent (which we will sort)
                    
        if new_intruders_detected or any(peaks):
            # We might just need to update the table if values changed
            self._update_intruder_table()
        
    def _process_dtv_detect(self, x, y):
        # Scan standard channels (Ch 7-13: 174-216, Ch 14-36: 470-608)
        # Pilot is at Lower Edge + 0.31 MHz
        threshold = self.dtv_threshold_spin.value()
        
        detected_channels = []
        
        # Helper to check channels
        def check_channels(start_ch, end_ch, start_freq_mhz):
            for ch in range(start_ch, end_ch + 1):
                lower_edge = (start_freq_mhz + (ch - start_ch) * 6) * 1e6
                pilot_freq = lower_edge + 0.31e6
                
                # Check if this freq is in our current sweep span
                if pilot_freq >= x[0] and pilot_freq <= x[-1]:
                    # Find closest index
                    idx = (np.abs(x - pilot_freq)).argmin()
                    if y[idx] > threshold:
                        detected_channels.append(ch)
                        
        check_channels(7, 13, 174.0)
        check_channels(14, 36, 470.0)
        
        # Add to table if not present
        if detected_channels:
            current_ch_detects = []
            for i in range(self.dtv_table.rowCount()):
                ch_item = self.dtv_table.item(i, 0)
                dist_item = self.dtv_table.item(i, 3)
                if ch_item and dist_item and dist_item.text() == "Detected":
                    current_ch_detects.append(int(ch_item.text()))
                    
            for ch in detected_channels:
                if ch not in current_ch_detects:
                    row = self.dtv_table.rowCount()
                    self.dtv_table.insertRow(row)
                    ch_item = QTableWidgetItem(str(ch))
                    ch_item.setBackground(QColor(0, 0, 150))
                    self.dtv_table.setItem(row, 0, ch_item)
                    self.dtv_table.setItem(row, 1, QTableWidgetItem(f"Auto-DTV"))
                    self.dtv_table.setItem(row, 2, QTableWidgetItem("> Threshold"))
                    self.dtv_table.setItem(row, 3, QTableWidgetItem("Detected"))
                    
                    self.active_channels[ch] = True
                    self.update_table_colors()
                    
            self.update_channel_masks()
                
    def _process_tband_detect(self, x, y):
        # T-Band is 470 - 512 MHz
        threshold = self.dtv_threshold_spin.value()
        
        if x[0] > 512e6 or x[-1] < 470e6:
            return
            
        mask = (x >= 470e6) & (x <= 512e6)
        x_tband = x[mask]
        y_tband = y[mask]
        
        hits = y_tband > threshold
        self.tband_history.append(hits)
        
        # Keep 20 seconds of history. Assuming ~20 sweeps per second = 400 sweeps max
        # To be safe, keep last 200 sweeps
        if len(self.tband_history) > 200:
            self.tband_history.pop(0)
            
        if len(self.tband_history) < 20:
            return
            
        history_arr = np.array(self.tband_history)
        
        # Criteria 1: 4s continuous -> ~40 sweeps continuous
        continuous_hits = np.sum(history_arr[-40:], axis=0) >= 38
        
        # Criteria 2: 4-5 hits in 20s
        # We can look for rising edges (0 -> 1)
        rising_edges = (history_arr[1:] & ~history_arr[:-1]).sum(axis=0)
        intermittent_hits = rising_edges >= 4
        
        detected_indices = np.where(continuous_hits | intermittent_hits)[0]
        
        current_tband_freqs = []
        for i in range(self.dtv_table.rowCount()):
            call_item = self.dtv_table.item(i, 1)
            if call_item and "T-Band" in call_item.text():
                current_tband_freqs.append(call_item.text())
                
        for idx in detected_indices:
            freq_mhz = x_tband[idx] / 1e6
            label = f"T-Band {freq_mhz:.3f}"
            if label not in current_tband_freqs:
                row = self.dtv_table.rowCount()
                self.dtv_table.insertRow(row)
                ch_item = QTableWidgetItem("-")
                ch_item.setBackground(QColor(150, 0, 0))
                self.dtv_table.setItem(row, 0, ch_item)
                self.dtv_table.setItem(row, 1, QTableWidgetItem(label))
                self.dtv_table.setItem(row, 2, QTableWidgetItem("PMSE/Trunked"))
                self.dtv_table.setItem(row, 3, QTableWidgetItem("Detected"))
                
            self.update_channel_masks()
            

    def on_dtv_detect_toggled(self, checked):
        self.dtv_detect_active = checked
        self.dtv_threshold = self.dtv_threshold_spin.value()
        
        if checked:
            self.show_threshold_cb.setChecked(False)
        else:
            # Clear algorithmic markers from table
            rows_to_remove = []
            for i in range(self.dtv_table.rowCount()):
                dist_item = self.dtv_table.item(i, 3)
                if dist_item and dist_item.text() == "Detected":
                    rows_to_remove.append(i)
            for i in reversed(rows_to_remove):
                ch_item = self.dtv_table.item(i, 0)
                if ch_item:
                    self.active_channels.pop(int(ch_item.text()), None)
                self.dtv_table.removeRow(i)
            self.update_channel_masks()
                
    def on_tband_scan_toggled(self, checked):
        self.tband_detect_active = checked
        if self.tband_detect_active:
            self.tband_scan_btn.setChecked(False)
        self.dtv_threshold = self.dtv_threshold_spin.value()
        if checked:
            self.show_threshold_cb.setChecked(False)
            self.tband_history = []
        else:
            rows_to_remove = []
            for i in range(self.dtv_table.rowCount()):
                call_item = self.dtv_table.item(i, 1)
                if call_item and "T-Band" in call_item.text():
                    rows_to_remove.append(i)
            for i in reversed(rows_to_remove):
                self.dtv_table.removeRow(i)
            self.update_channel_masks()

    def apply_amplitude(self):
        self.apply_frequencies()
        
    def on_swt_mode_changed(self):
        mode_text = self.swt_mode_combo.currentText()
        if mode_text == "Manual" or mode_text == "minSWTxN":
            self.sweep_time_spin.setEnabled(True)
        else:
            self.sweep_time_spin.setEnabled(False)

    def apply_sweep_settings(self):
        if not self.controller.is_connected:
            return
        
        swt_mode = self.swt_mode_combo.currentIndex()
        swt_time = self.sweep_time_spin.value()
        trace_points = 0 # 0 means we won't try to override it right now
        spur = self.spur_combo.currentIndex()
        window = self.window_combo.currentIndex()
        
        # Note: Gaussian_CISPR is 0x0A, but we only populated the first 5 standard options in the combobox,
        # so index 0-4 maps cleanly to the enums 0-4.
        
        self.controller.configure_sweep(swt_mode, swt_time, trace_points, spur, window)
        
    def update_trace_points(self, points):
        # Temporarily block signals so we don't trigger anything if we were to change it (though it's read-only)
        self.trace_points_spin.blockSignals(True)
        self.trace_points_spin.setValue(points)
        self.trace_points_spin.blockSignals(False)

    def apply_detect_settings(self):
        if not self.controller.is_connected:
            return
            
        detector = self.detector_combo.currentIndex()
        trace_detector = self.trace_detector_combo.currentIndex()
        
        self.controller.configure_detect(detector, trace_detector)

    def auto_reference_level(self):
        # Triggered by Auto Ref. Level button
        if not self.controller.is_connected or getattr(self, '_latest_y', None) is None:
            return
            
        peak_power = np.max(self._latest_y)
        new_ref = round((peak_power + 10.0) / 5.0) * 5.0
        self.ref_level_spin.setValue(new_ref)
        
        # Automatically apply
        self.apply_amplitude()
            
    def on_start_stop_changed(self):
        if self._updating_freqs: return
        self._updating_freqs = True
        center = (self.start_spin.value() + self.stop_spin.value()) / 2.0
        span = self.stop_spin.value() - self.start_spin.value()
        self.center_spin.setValue(center)
        self.span_spin.setValue(span)
        self._updating_freqs = False
        self.sync_quick_buttons_state()
        
        if getattr(self, 'link_view_check', None) and self.link_view_check.isChecked():
            self._updating_view_freqs = True
            self.view_start_spin.setValue(self.start_spin.value())
            self.view_stop_spin.setValue(self.stop_spin.value())
            self.view_center_spin.setValue(center)
            self.view_span_spin.setValue(span)
            self._updating_view_freqs = False
            self.apply_view_frequencies()
            self.sync_view_quick_buttons_state()

        self.update_bw_calculations()
        self.check_span_correlation()
        
    def update_color_scale_css(self):
        css_stops = COLORMAP_CSS.get(self.waterfall_colormap, COLORMAP_CSS['viridis'])
        self.color_scale_label.setStyleSheet(f"""
            QLabel {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, {css_stops});
                color: white;
                font-weight: bold;
                border: 1px solid black;
                border-radius: 3px;
                padding: 0px 5px;
            }}
        """)

    def change_waterfall_history(self):
        dialog = WaterfallSettingsDialog(self.waterfall_history_depth, self)
        if dialog.exec():
            depth = dialog.get_settings()
            self.waterfall_history_depth = depth
            self.settings.setValue("waterfall_depth", depth)
            
    def change_colormap_from_menu(self):
        action = self.sender()
        if action:
            colormap_name = action.data()
            if colormap_name != self.waterfall_colormap:
                self.waterfall_colormap = colormap_name
                self.settings.setValue("waterfall_colormap", colormap_name)
                new_cmap = pg.colormap.get(self.waterfall_colormap)
                self.waterfall_img.setColorMap(new_cmap)
                self.update_color_scale_css()
                
    def toggle_theme(self, checked):
        self.settings.setValue("dark_theme", checked)
        app = QApplication.instance()
        import os
        plus_png = os.path.abspath("plus.png").replace('\\', '/')
        minus_png = os.path.abspath("minus.png").replace('\\', '/')
        
        if checked:
            app.setStyle("Fusion")
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Base, QColor(10, 10, 10))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Button, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
            app.setPalette(palette)
            
            title_style = "font-weight: bold; font-size: 11pt; color: white;"
            self.waterfall_title.setStyleSheet(title_style)
            self.spectrum_plot_title.setStyleSheet(title_style)
            
            self.setStyleSheet("""
                QMenuBar {
                    border-bottom: 1px solid #333333;
                }
                QPushButton#collapsibleHeader {
                    text-align: left;
                    font-weight: bold;
                    font-size: 11pt;
                    padding: 5px;
                    background-color: transparent;
                    color: white;
                    border: none;
                    border-bottom: 1px solid #555555;
                    border-radius: 0px;
                }
                QPushButton#collapsibleHeader:hover {
                    background-color: #333333;
                }
                QPushButton#quickSettingBtn {
                    min-width: 110px;
                    max-width: 165px;
                    min-height: 25px;
                    max-height: 25px;
                    color: white;
                    background-color: #3d3d3d;
                    border: 1px solid #555555;
                    border-radius: 3px;
                }
                QPushButton#quickSettingBtn:checked {
                    background-color: #5cafff;
                    color: #000000;
                    font-weight: bold;
                    border: 1px solid #5cafff;
                }
                QPushButton#quickSettingBtn[btn_type="uplink"]:checked {
                    background-color: #e91e63;
                    color: #ffffff;
                    font-weight: bold;
                    border: 1px solid #ff4081;
                }
                QPushButton#quickSettingBtn[btn_type="downlink"]:checked {
                    background-color: #8e24aa;
                    color: #ffffff;
                    font-weight: bold;
                    border: 1px solid #ba68c8;
                }
                QPushButton#quickSettingBtn[btn_type="guard"]:checked {
                    background-color: #616161;
                    color: #ffffff;
                    font-weight: bold;
                    border: 1px solid #9e9e9e;
                }
                QLineEdit {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 5px;
                }
                QComboBox {
                    max-width: 110px;
                }
                QSpinBox, QDoubleSpinBox {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 0px 18px 0px 18px;
                    min-height: 28px;
                    min-width: 90px;
                    max-width: 110px;
                    qproperty-alignment: 'AlignHCenter';
                }
                QSpinBox::up-button, QDoubleSpinBox::up-button {
                    subcontrol-origin: border;
                    subcontrol-position: right;
                    width: 15px;
                    height: 28px;
                    border-left: 1px solid #555555;
                    background-color: #333333;
                    border-top-right-radius: 4px;
                    border-bottom-right-radius: 4px;
                }
                QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
                    image: url('""" + plus_png + """');
                    width: 14px;
                    height: 14px;
                }
                QSpinBox::down-button, QDoubleSpinBox::down-button {
                    subcontrol-origin: border;
                    subcontrol-position: left;
                    width: 15px;
                    height: 28px;
                    border-right: 1px solid #555555;
                    background-color: #333333;
                    border-top-left-radius: 4px;
                    border-bottom-left-radius: 4px;
                }
                QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
                    image: url('""" + minus_png + """');
                    width: 14px;
                    height: 14px;
                }
                QCheckBox::indicator {
                    border: 1px solid #555555;
                    border-radius: 2px;
                    width: 14px;
                    height: 14px;
                }
                QCheckBox::indicator:checked {
                    background-color: #0078D7;
                    border: 1px solid #0078D7;
                }
            """)
            
            self.plot_widget.setBackground('k')
            self.waterfall_channels.setBackground('k')
            self.spectrum_channels.setBackground('k')
            self.waterfall_widget.setBackground('k')
            self.plot_widget.getAxis('left').setPen('w')
            self.plot_widget.getAxis('bottom').setPen('w')
            self.waterfall_widget.getAxis('left').setPen('w')
            self.waterfall_widget.getAxis('bottom').setPen('w')
        else:
            app.setStyle("Fusion")
            app.setPalette(app.style().standardPalette())
            
            title_style = "font-weight: bold; font-size: 11pt; color: black;"
            self.waterfall_title.setStyleSheet(title_style)
            self.spectrum_plot_title.setStyleSheet(title_style)
            
            self.setStyleSheet("""
                QMenuBar {
                    border-bottom: 1px solid #cccccc;
                }
                QPushButton#collapsibleHeader {
                    text-align: left;
                    font-weight: bold;
                    font-size: 11pt;
                    padding: 5px;
                    background-color: transparent;
                    color: black;
                    border: none;
                    border-bottom: 1px solid #cccccc;
                    border-radius: 0px;
                }
                QPushButton#collapsibleHeader:hover {
                    background-color: #e0e0e0;
                }
                QPushButton#quickSettingBtn {
                    min-width: 110px;
                    max-width: 165px;
                    min-height: 25px;
                    max-height: 25px;
                    color: black;
                    background-color: #f0f0f0;
                    border: 1px solid #cccccc;
                    border-radius: 3px;
                }
                QPushButton#quickSettingBtn:checked {
                    background-color: #5cafff;
                    color: #000000;
                    font-weight: bold;
                    border: 1px solid #5cafff;
                }
                QPushButton#quickSettingBtn[btn_type="uplink"]:checked {
                    background-color: #e91e63;
                    color: #ffffff;
                    font-weight: bold;
                    border: 1px solid #ff4081;
                }
                QPushButton#quickSettingBtn[btn_type="downlink"]:checked {
                    background-color: #8e24aa;
                    color: #ffffff;
                    font-weight: bold;
                    border: 1px solid #ba68c8;
                }
                QPushButton#quickSettingBtn[btn_type="guard"]:checked {
                    background-color: #757575;
                    color: #ffffff;
                    font-weight: bold;
                    border: 1px solid #9e9e9e;
                }
                QLineEdit {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 5px;
                }
                QComboBox {
                    max-width: 110px;
                }
                QSpinBox, QDoubleSpinBox {
                    background-color: #f0f0f0;
                    color: #000000;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 0px 18px 0px 18px;
                    min-height: 28px;
                    min-width: 90px;
                    max-width: 110px;
                    qproperty-alignment: 'AlignHCenter';
                }
                QSpinBox::up-button, QDoubleSpinBox::up-button {
                    subcontrol-origin: border;
                    subcontrol-position: right;
                    width: 15px;
                    height: 28px;
                    border-left: 1px solid #cccccc;
                    background-color: #333333;
                    border-top-right-radius: 4px;
                    border-bottom-right-radius: 4px;
                }
                QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
                    image: url('""" + plus_png + """');
                    width: 18px;
                    height: 18px;
                }
                QSpinBox::down-button, QDoubleSpinBox::down-button {
                    subcontrol-origin: border;
                    subcontrol-position: left;
                    width: 15px;
                    height: 28px;
                    border-right: 1px solid #cccccc;
                    background-color: #333333;
                    border-top-left-radius: 4px;
                    border-bottom-left-radius: 4px;
                }
                QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
                    width: 18px;
                    height: 18px;
                }
                QCheckBox::indicator {
                    border: 1px solid #cccccc;
                    border-radius: 2px;
                    width: 14px;
                    height: 14px;
                }
                QCheckBox::indicator:checked {
                    background-color: #0078D7;
                    border: 1px solid #0078D7;
                }
            """)
            
            self.plot_widget.setBackground('w')
            self.waterfall_channels.setBackground('w')
            self.spectrum_channels.setBackground('w')
            self.waterfall_widget.setBackground('w')
            self.plot_widget.getAxis('left').setPen('k')
            self.plot_widget.getAxis('bottom').setPen('k')
            self.waterfall_widget.getAxis('left').setPen('k')
            self.waterfall_widget.getAxis('bottom').setPen('k')
            
    def on_center_changed(self):
        if self._updating_freqs: return
        self._updating_freqs = True
        span = self.span_spin.value()
        self.start_spin.setValue(self.center_spin.value() - span / 2.0)
        self.stop_spin.setValue(self.center_spin.value() + span / 2.0)
        self._updating_freqs = False
        self.sync_quick_buttons_state()
        if getattr(self, 'link_view_check', None) and self.link_view_check.isChecked():
            self._updating_view_freqs = True
            self.view_start_spin.setValue(self.start_spin.value())
            self.view_stop_spin.setValue(self.stop_spin.value())
            self.view_center_spin.setValue(self.center_spin.value())
            self.view_span_spin.setValue(self.span_spin.value())
            self._updating_view_freqs = False
            self.apply_view_frequencies()
            self.sync_view_quick_buttons_state()
        self.update_bw_calculations()
        self.check_span_correlation()
        
    def on_span_changed(self):
        if self._updating_freqs: return
        self._updating_freqs = True
        center = self.center_spin.value()
        span = self.span_spin.value()
        self.start_spin.setValue(center - span / 2.0)
        self.stop_spin.setValue(center + span / 2.0)
        self._updating_freqs = False
        self.sync_quick_buttons_state()
        if getattr(self, 'link_view_check', None) and self.link_view_check.isChecked():
            self._updating_view_freqs = True
            self.view_start_spin.setValue(self.start_spin.value())
            self.view_stop_spin.setValue(self.stop_spin.value())
            self.view_center_spin.setValue(self.center_spin.value())
            self.view_span_spin.setValue(self.span_spin.value())
            self._updating_view_freqs = False
            self.apply_view_frequencies()
            self.sync_view_quick_buttons_state()
        self.update_bw_calculations()
        self.check_span_correlation()

    def on_step_changed(self):
        self.center_spin.setSingleStep(self.step_spin.value())
            
    def on_view_start_stop_changed(self):
        if self._updating_view_freqs: return
        self._updating_view_freqs = True
        center = (self.view_start_spin.value() + self.view_stop_spin.value()) / 2.0
        span = self.view_stop_spin.value() - self.view_start_spin.value()
        self.view_center_spin.setValue(center)
        self.view_span_spin.setValue(span)
        self._updating_view_freqs = False
        self.apply_view_frequencies()
        self.sync_view_quick_buttons_state()
        
        if getattr(self, 'link_view_check', None) and self.link_view_check.isChecked():
            self._updating_freqs = True
            self.start_spin.setValue(self.view_start_spin.value())
            self.stop_spin.setValue(self.view_stop_spin.value())
            self.center_spin.setValue(center)
            self.span_spin.setValue(span)
            self._updating_freqs = False
            self.sync_quick_buttons_state()
            self.apply_frequencies()
        self.check_span_correlation()
        
    def on_view_center_changed(self):
        if self._updating_view_freqs: return
        self._updating_view_freqs = True
        span = self.view_span_spin.value()
        self.view_start_spin.setValue(self.view_center_spin.value() - span / 2.0)
        self.view_stop_spin.setValue(self.view_center_spin.value() + span / 2.0)
        self._updating_view_freqs = False
        self.apply_view_frequencies()
        self.sync_view_quick_buttons_state()
        
        if getattr(self, 'link_view_check', None) and self.link_view_check.isChecked():
            self._updating_freqs = True
            self.start_spin.setValue(self.view_start_spin.value())
            self.stop_spin.setValue(self.view_stop_spin.value())
            self.center_spin.setValue(self.view_center_spin.value())
            self.span_spin.setValue(span)
            self._updating_freqs = False
            self.sync_quick_buttons_state()
            self.apply_frequencies()
        self.check_span_correlation()
        
    def on_view_span_changed(self):
        if self._updating_view_freqs: return
        self._updating_view_freqs = True
        center = self.view_center_spin.value()
        span = self.view_span_spin.value()
        self.view_start_spin.setValue(center - span / 2.0)
        self.view_stop_spin.setValue(center + span / 2.0)
        self._updating_view_freqs = False
        self.apply_view_frequencies()
        self.sync_view_quick_buttons_state()
        
        if getattr(self, 'link_view_check', None) and self.link_view_check.isChecked():
            self._updating_freqs = True
            self.start_spin.setValue(self.view_start_spin.value())
            self.stop_spin.setValue(self.view_stop_spin.value())
            self.center_spin.setValue(center)
            self.span_spin.setValue(span)
            self._updating_freqs = False
            self.sync_quick_buttons_state()
            self.apply_frequencies()
        self.check_span_correlation()

    def on_view_step_changed(self):
        self.view_center_spin.setSingleStep(self.view_step_spin.value())

    def update_status(self, msg):
        if "successfully" in msg.lower():
            color = "green"
        elif "fail" in msg.lower() or "error" in msg.lower() or "disconnected" in msg.lower():
            color = "red"
        else:
            color = "gray"
            
        self.status_label.setText(f"<span style='color: gray;'>Status:</span> <span style='color: {color};'>{msg}</span>")
            
        if "reconfigured" in msg.lower():
            QTimer.singleShot(3000, self.set_running_status)
            
    def update_ui_state(self, connected):
        if connected:
            self.connect_btn.setText("Disconnect")
            
            self.play_pause_btn.setEnabled(True)
            
            is_dark = self.parent().property("theme") == "dark" if self.parent() else True
            active_btn_style = "background-color: #0078D7; color: white; font-weight: bold; border-radius: 4px; padding: 5px;"
            self.connect_btn.setStyleSheet(active_btn_style)
            
            self.controller.start()  # Start sweeping data
            start_hz = self.view_start_spin.value() * 1e6
            stop_hz = self.view_stop_spin.value() * 1e6
            mult = getattr(self, '_x_multiplier', 1e6)
            self.plot_widget.setXRange(start_hz / mult, stop_hz / mult, padding=0)
            
            # Start the 10 second timer for 'Running' status
            QTimer.singleShot(10000, self.set_running_status)
        else:
            self.connect_btn.setText("Connect Device")
            
            self.play_pause_btn.setChecked(False)
            
            is_dark = self.parent().property("theme") == "dark" if self.parent() else True
            inactive_btn_style = "background-color: #333333; color: #777777; font-weight: bold; border: 1px solid #555555; border-radius: 4px; padding: 5px;"
            if not is_dark:
                inactive_btn_style = "background-color: #f0f0f0; color: #aaaaaa; font-weight: bold; border: 1px solid #cccccc; border-radius: 4px; padding: 5px;"
            self.connect_btn.setStyleSheet(inactive_btn_style)
            
            self.play_pause_btn.setEnabled(False)
            self.play_pause_btn.setText("Pause")
            self.play_pause_btn.setStyleSheet("")
            self.update_status("Disconnected")
            
    def update_plot(self, x, y):
        if len(x) == 0 or len(y) == 0:
            return
            
        # Apply amplitude offset in software
        offset = self.amp_offset_spin.value()
        y_offset = y + offset
        
        start_hz = x[0]
        stop_hz = x[-1]
        
        self._x_multiplier = 1e6
        x_scaled = x / self._x_multiplier
        
        # High performance update
        self._latest_x = x
        self._latest_y = y_offset
        
        if self.trace_controls["Real-Time"]['cb'].isChecked():
            if not self.trace_controls["Real-Time"]['freeze_cb'].isChecked():
                self.trace_curves["Real-Time"].setData(x_scaled, y_offset)
            
        if self.trace_controls["Max. Hold"]['cb'].isChecked():
            if not self.trace_controls["Max. Hold"]['freeze_cb'].isChecked():
                if self.max_hold_data is None or len(self.max_hold_data) != len(y_offset):
                    self.max_hold_data = y_offset.copy()
                else:
                    self.max_hold_data = np.maximum(self.max_hold_data, y_offset)
                self.trace_curves["Max. Hold"].setData(x_scaled, self.max_hold_data)
            
        if self.trace_controls["Min. Hold"]['cb'].isChecked():
            if not self.trace_controls["Min. Hold"]['freeze_cb'].isChecked():
                if self.min_hold_data is None or len(self.min_hold_data) != len(y_offset):
                    self.min_hold_data = y_offset.copy()
                else:
                    self.min_hold_data = np.minimum(self.min_hold_data, y_offset)
                self.trace_curves["Min. Hold"].setData(x_scaled, self.min_hold_data)
            
        if self.trace_controls["Average"]['cb'].isChecked():
            if not self.trace_controls["Average"]['freeze_cb'].isChecked():
                target_depth = self.avg_sweeps_spin.value()
                if self.avg_history is None or self.avg_history.shape[1] != len(y_offset):
                    self.avg_history = np.zeros((target_depth, len(y_offset)))
                    self.avg_history[:] = y_offset
                else:
                    if self.avg_history.shape[0] != target_depth:
                        new_hist = np.zeros((target_depth, len(y_offset)))
                        copy_len = min(self.avg_history.shape[0], target_depth)
                        new_hist[-copy_len:] = self.avg_history[-copy_len:]
                        if copy_len < target_depth:
                            new_hist[:-copy_len] = y_offset
                        self.avg_history = new_hist
                        
                    self.avg_history = np.roll(self.avg_history, -1, axis=0)
                    self.avg_history[-1] = y_offset
                    
                self.trace_curves["Average"].setData(x_scaled, np.mean(self.avg_history, axis=0))
                
        # Run algorithmic detection if active
        if self.dtv_detect_active:
            self._process_dtv_detect(x, y_offset)
            
        if self.tband_detect_active:
            self._process_tband_detect(x, y_offset)
            
        if self.intruder_enable_cb.isChecked():
            self._process_intruder_detect(x, y_offset)
            
        if hasattr(self, 'dect_engine') and self.dect_engine.is_enabled:
            self.dect_engine.process_sweep_data(x, y_offset)
            
        if hasattr(self, 'showlink_engine') and self.showlink_engine.is_enabled:
            self.showlink_engine.process_sweep_data(x, y_offset)
        
        # Waterfall processing
        num_lines = self.waterfall_history_depth
        pts = len(x)
        
        if self.waterfall_history is None or self.waterfall_history.shape[0] != num_lines or self.waterfall_history.shape[1] != pts:
            self.waterfall_history = np.full((num_lines, pts), -160.0, dtype=np.float32)
            self.waterfall_widget.setYRange(0, num_lines)
            
        # Roll upwards: newest data goes at index 0, old data shifts towards num_lines
        self.waterfall_history = np.roll(self.waterfall_history, 1, axis=0)
        self.waterfall_history[0] = y_offset
        
        self.waterfall_img.setImage(self.waterfall_history.T, autoLevels=False, levels=(-120, -20))
        
        # Set bounds so image X matches the frequency bins, and Y matches history sweep index
        start_scaled = start_hz / self._x_multiplier
        stop_scaled = stop_hz / self._x_multiplier
        self.waterfall_img.setRect(pg.QtCore.QRectF(start_scaled, 0, stop_scaled - start_scaled, num_lines))
        
    def mouse_moved(self, evt):
        pos = evt[0]
        freq = None
        
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mousePoint = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            freq = mousePoint.x()
        elif self.waterfall_widget.sceneBoundingRect().contains(pos):
            mousePoint = self.waterfall_widget.plotItem.vb.mapSceneToView(pos)
            freq = mousePoint.x()
            
        if freq is not None:
            raw_freq = freq * self._x_multiplier
            self.vLine.setPos(freq)
            self.waterfall_vLine.setPos(freq)
            
            if self._latest_x is not None and self._latest_y is not None and len(self._latest_x) > 0:
                # Find the closest frequency
                idx = (np.abs(self._latest_x - raw_freq)).argmin()
                nearest_freq = self._latest_x[idx]
                power = self._latest_y[idx]
                
                # Format nearest_freq based on its magnitude
                if nearest_freq >= 1e9:
                    freq_str = f"{nearest_freq/1e9:.3f} GHz"
                elif nearest_freq >= 1e6:
                    freq_str = f"{nearest_freq/1e6:.3f} MHz"
                elif nearest_freq >= 1e3:
                    freq_str = f"{nearest_freq/1e3:.3f} kHz"
                else:
                    freq_str = f"{nearest_freq:.0f} Hz"
                    
                self.cursor_info_label.setText(f"Cursor: {freq_str} | {power:.2f} dBm")
        else:
            self.cursor_info_label.setText("Cursor: -- MHz | -- dBm")
        
    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()


    def _get_ps_dict(self):
        ps_dict = {}
        if hasattr(self, 'dtv_table'):
            for i in range(self.dtv_table.rowCount()):
                ch_item = self.dtv_table.item(i, 0)
                if ch_item:
                    try:
                        ch = int(ch_item.text())
                        ps_dict[ch] = bool(ch_item.data(Qt.ItemDataRole.UserRole))
                    except ValueError:
                        pass
        return ps_dict

    def update_channel_markers(self):
        standard = TV_CHANNEL_STANDARDS.get(self.current_region, None)
        x_mult = getattr(self, '_x_multiplier', 1e6)
        self.waterfall_channels.draw_channels(standard, x_mult)
        self.spectrum_channels.draw_channels(standard, x_mult)
        
        if standard:
            ps_dict = self._get_ps_dict()
            self.waterfall_channels.set_active_channels(self.active_channels, ps_dict)
            self.spectrum_channels.set_active_channels(self.active_channels, ps_dict)
            self.update_channel_masks()
        else:
            for s_mask, w_mask in self.channel_masks.values():
                self.plot_widget.removeItem(s_mask)
                self.waterfall_widget.removeItem(w_mask)
            self.channel_masks.clear()
        
        # Sync background
        is_dark = self.settings.value("dark_theme", True, type=bool)
        theme = 'k' if is_dark else 'w'
        self.waterfall_channels.setBackground(theme)
        self.spectrum_channels.setBackground(theme)

    def on_channel_clicked(self, ch_num, start_freq, stop_freq):
        current = self.active_channels.get(ch_num, False)
        self.active_channels[ch_num] = not current
        
        ps_dict = self._get_ps_dict()
        self.waterfall_channels.set_active_channels(self.active_channels, ps_dict)
        self.spectrum_channels.set_active_channels(self.active_channels, ps_dict)
        self.update_channel_masks()
        
    def update_channel_masks(self):
        for mask_tuple in self.channel_masks.values():
            self.plot_widget.removeItem(mask_tuple[0])
            self.waterfall_widget.removeItem(mask_tuple[1])
            if len(mask_tuple) > 2 and mask_tuple[2]:
                self.plot_widget.removeItem(mask_tuple[2])
        self.channel_masks.clear()
        
        standard = TV_CHANNEL_STANDARDS.get(self.current_region, None)
        if not standard: return
        
        if isinstance(standard, dict):
            standard = [standard]
        
        for ch_key, is_active in self.active_channels.items():
            if not is_active:
                continue
                
            # Check if this matches a custom item
            custom_info = None
            for b in standard:
                if "custom_items" in b:
                    for c_item in b["custom_items"]:
                        if c_item["id"] == ch_key:
                            custom_info = c_item
                            break
                if custom_info:
                    break
                    
            if custom_info:
                start_f = custom_info["start"]
                stop_f = custom_info["stop"]
                item_type = custom_info.get("type", "default")
                display_name = custom_info.get("display_name", str(ch_key))
                
                if item_type == "uplink":
                    brush = QBrush(QColor(233, 30, 99, 85)) # Pink
                elif item_type == "downlink":
                    brush = QBrush(QColor(142, 36, 170, 85)) # Purple
                elif item_type == "guard":
                    brush = QBrush(QColor(110, 110, 110, 95)) # Gray
                elif item_type in ("lmr_smr", "teal"):
                    brush = QBrush(QColor(0, 150, 136, 85)) # Teal
                else:
                    brush = QBrush(QColor(0, 120, 255, 100))
                    
                s_mask = pg.LinearRegionItem(values=[start_f, stop_f], movable=False, brush=brush)
                for line in s_mask.lines: line.setPen(pg.mkPen(None))
                s_mask.setZValue(10)
                self.plot_widget.addItem(s_mask)
                
                w_mask = pg.LinearRegionItem(values=[start_f, stop_f], movable=False, brush=brush)
                for line in w_mask.lines: line.setPen(pg.mkPen(None))
                w_mask.setZValue(10)
                self.waterfall_widget.addItem(w_mask)
                
                t_mask = None
                if self.settings.value("show_dtv_labels", True, type=bool):
                    if item_type == "guard":
                        html_text = f"<div style='white-space: nowrap; text-align: center; color: white;'><span style='font-size: 7.2pt; font-weight: bold;'>{display_name}</span> &nbsp;&bull;&nbsp; <span style='font-size: 6.4pt; color: #d0d0d0;'>{start_f:g}-{stop_f:g} MHz</span></div>"
                    else:
                        html_text = f"<div style='white-space: nowrap; text-align: center; color: white;'><span style='font-size: 9pt; font-weight: bold;'>{display_name}</span> &nbsp;&bull;&nbsp; <span style='font-size: 8pt; color: #d0d0d0;'>{start_f:g}-{stop_f:g} MHz</span></div>"
                    t_mask = pg.TextItem(html=html_text, anchor=(0.5, 0.5))
                    t_mask.setAngle(90)
                    t_mask.setZValue(15)
                    t_mask.setPos((start_f + stop_f) / 2.0, -65)
                    self.plot_widget.addItem(t_mask)
                    
                self.channel_masks[ch_key] = (s_mask, w_mask, t_mask)
                continue
                
            # Otherwise, check numeric TV channels
            if not isinstance(ch_key, int) and not (isinstance(ch_key, str) and ch_key.isdigit()):
                continue
            ch_num = int(ch_key)
            
            band = None
            for b in standard:
                if "start_ch" in b and "end_ch" in b:
                    if b["start_ch"] <= ch_num <= b["end_ch"]:
                        band = b
                        break
            if not band: continue
            
            if ch_num == 37:
                brush = QBrush(QColor(120, 120, 120, 120)) # Darker grey, more opaque
            else:
                is_public_safety = False
                if hasattr(self, 'dtv_table'):
                    for i in range(self.dtv_table.rowCount()):
                        ch_item = self.dtv_table.item(i, 0)
                        if ch_item and ch_item.text() == str(ch_num):
                            if ch_item.data(Qt.ItemDataRole.UserRole):
                                is_public_safety = True
                            break
                if is_public_safety:
                    brush = QBrush(QColor(255, 0, 0, 100)) # Saturated Red
                else:
                    brush = QBrush(QColor(0, 120, 255, 100)) # Deeper blue, more opaque
            
            start_freq = (band["start_freq"] + (ch_num - band["start_ch"]) * band["spacing"]) * 1e6
            stop_freq = start_freq + band["spacing"] * 1e6
            
            if getattr(self, '_x_multiplier', 1e6) == 1e9:
                start_f = start_freq / 1e9
                stop_f = stop_freq / 1e9
            else:
                start_f = start_freq / 1e6
                stop_f = stop_freq / 1e6
            
            s_mask = pg.LinearRegionItem(values=[start_f, stop_f], movable=False, brush=brush)
            for line in s_mask.lines: line.setPen(pg.mkPen(None))
            s_mask.setZValue(10)
            self.plot_widget.addItem(s_mask)
            
            w_mask = pg.LinearRegionItem(values=[start_f, stop_f], movable=False, brush=brush)
            for line in w_mask.lines: line.setPen(pg.mkPen(None))
            w_mask.setZValue(10)
            self.waterfall_widget.addItem(w_mask)
            
            t_mask = None
            if self.settings.value("show_dtv_labels", True, type=bool):
                station_name = "Unknown"
                if hasattr(self, 'dtv_table'):
                    for i in range(self.dtv_table.rowCount()):
                        ch_item = self.dtv_table.item(i, 0)
                        if ch_item and ch_item.text() == str(ch_num):
                            cs_item = self.dtv_table.item(i, 1)
                            if cs_item and cs_item.text():
                                station_name = cs_item.text()
                            break
                            
                html_text = f"<div style='white-space: nowrap; text-align: center; color: white;'><span style='font-size: 9pt; font-weight: bold;'>DTV {ch_num}</span> &nbsp;&bull;&nbsp; <span style='font-size: 8.5pt;'>{station_name}</span> &nbsp;&bull;&nbsp; <span style='font-size: 8pt; color: #d0d0d0;'>{start_f:g}-{stop_f:g} MHz</span></div>"
                
                t_mask = pg.TextItem(html=html_text, anchor=(0.5, 0.5))
                t_mask.setAngle(90)
                t_mask.setZValue(15)
                t_mask.setPos((start_f + stop_f) / 2.0, -65)
                self.plot_widget.addItem(t_mask)
            
            self.channel_masks[ch_num] = (s_mask, w_mask, t_mask)

    def change_region_from_menu(self):
        action = self.sender()
        if action:
            self.current_region = action.data()
            self.settings.setValue("current_region", self.current_region)
            if self.current_region == "North America":
                self.active_channels = dict(DEFAULT_NORTH_AMERICA_ACTIVE)
            elif self.current_region in ("UK", "Spain"):
                self.active_channels = dict(DEFAULT_EUROPE_ACTIVE)
            else:
                self.active_channels = {}
            self.update_quick_settings_ui()
            self.update_channel_markers()
            if self.current_region == "North America":
                self._updating_freqs = True
                self.start_spin.setValue(470.0)
                self.stop_spin.setValue(698.0)
                self.center_spin.setValue(584.0)
                self.span_spin.setValue(228.0)
                self._updating_freqs = False
                self.apply_frequencies()
            elif self.current_region in ("UK", "Spain"):
                self._updating_freqs = True
                self.start_spin.setValue(470.0)
                self.stop_spin.setValue(694.0)
                self.center_spin.setValue(582.0)
                self.span_spin.setValue(224.0)
                self._updating_freqs = False
                self.apply_frequencies()
                
            if hasattr(self, 'dect_band_combo'):
                if self.current_region == "North America":
                    self.dect_band_combo.setCurrentText("US DECT 6.0 (1920-1930 MHz)")
                elif self.current_region in ("UK", "Spain"):
                    self.dect_band_combo.setCurrentText("EU DECT (1880-1900 MHz)")
            
    def reset_trace_buffers(self):
        self.max_hold_data = None
        self.min_hold_data = None
        self.avg_history = None

    def on_trace_toggled(self):
        for name, controls in self.trace_controls.items():
            is_on = controls['cb'].isChecked()
            self.trace_curves[name].setVisible(is_on)
            if is_on:
                if name == "Average": self.avg_history = None
                elif name == "Max. Hold": self.max_hold_data = None
                elif name == "Min. Hold": self.min_hold_data = None

    def on_trace_color_changed(self):
        for name, controls in self.trace_controls.items():
            color = controls['color_btn'].color()
            self.trace_curves[name].setPen(pg.mkPen(color, width=2))
            
    def open_launch_settings_dialog(self):
        saved_region = self.settings.value("launch_default_region", self.current_region)
        saved_sweep_start = float(self.settings.value("launch_sweep_start", self.start_spin.value()))
        saved_sweep_stop = float(self.settings.value("launch_sweep_stop", self.stop_spin.value()))
        raw_sweep_anchors = self.settings.value("launch_sweep_anchors", None)
        saved_sweep_anchors = json.loads(raw_sweep_anchors) if raw_sweep_anchors else list(self._explicit_quick_anchors)
        
        saved_view_start = float(self.settings.value("launch_view_start", self.view_start_spin.value()))
        saved_view_stop = float(self.settings.value("launch_view_stop", self.view_stop_spin.value()))
        raw_view_anchors = self.settings.value("launch_view_anchors", None)
        saved_view_anchors = json.loads(raw_view_anchors) if raw_view_anchors else list(self._explicit_view_quick_anchors)
        saved_link_view = self.settings.value("launch_link_view", self.link_view_check.isChecked(), type=bool)
        
        dialog = LaunchSettingsDialog(
            region_configs=self.region_configs,
            current_region=saved_region,
            sweep_start=saved_sweep_start,
            sweep_stop=saved_sweep_stop,
            sweep_anchors=saved_sweep_anchors,
            view_start=saved_view_start,
            view_stop=saved_view_stop,
            view_anchors=saved_view_anchors,
            link_view=saved_link_view,
            parent=self
        )
        if dialog.exec():
            res = dialog.get_settings()
            self.settings.setValue("launch_default_region", res["region"])
            self.settings.setValue("launch_sweep_start", res["sweep_start"])
            self.settings.setValue("launch_sweep_stop", res["sweep_stop"])
            self.settings.setValue("launch_sweep_anchors", json.dumps(res["sweep_anchors"]))
            self.settings.setValue("launch_view_start", res["view_start"])
            self.settings.setValue("launch_view_stop", res["view_stop"])
            self.settings.setValue("launch_view_anchors", json.dumps(res["view_anchors"]))
            self.settings.setValue("launch_link_view", res["link_view"])
            
            QMessageBox.information(
                self,
                "Launch Settings Saved",
                f"Startup defaults saved successfully!\n\n"
                f"• Region: {res['region']}\n"
                f"• Analyzer Sweep: {res['sweep_start']:.1f} - {res['sweep_stop']:.1f} MHz\n"
                f"• Spectrum View: {res['view_start']:.1f} - {res['view_stop']:.1f} MHz (Linked: {'Yes' if res['link_view'] else 'No'})"
            )

    def open_quick_settings_dialog(self):
        buttons_data = self.region_configs.get(self.current_region, [])
        dialog = QuickSettingsDialog(self.current_region, buttons_data, self)
        if dialog.exec():
            self.region_configs[self.current_region] = dialog.buttons_data
            self.settings.setValue("regions", json.dumps(self.region_configs))
            self.update_quick_settings_ui()
            
    def update_quick_settings_ui(self):
        self._updating_freqs = True # Prevent circular triggers during setup
        buttons_data = self.region_configs.get(self.current_region, [])
        
        while len(self.quick_btns) < len(buttons_data):
            idx = len(self.quick_btns)
            btn = QPushButton()
            btn.setObjectName("quickSettingBtn")
            btn.setCheckable(True)
            btn.clicked.connect(self.on_quick_btn_toggled)
            self.quick_btns.append(btn)
            self.quick_btn_layout.addWidget(btn, idx // 2, idx % 2)

        for i, btn in enumerate(self.quick_btns):
            if i < len(buttons_data):
                b_name = buttons_data[i]["name"]
                btn.setText(b_name)
                btn.setProperty("start_freq", buttons_data[i]["start"])
                btn.setProperty("stop_freq", buttons_data[i]["stop"])
                
                b_lower = b_name.lower()
                if "uplink" in b_lower:
                    btn_type = "uplink"
                elif "downlink" in b_lower:
                    btn_type = "downlink"
                elif "guard" in b_lower:
                    btn_type = "guard"
                else:
                    btn_type = "default"
                btn.setProperty("btn_type", btn_type)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.setVisible(True)
            else:
                btn.setVisible(False)
        self._updating_freqs = False
        self.sync_quick_buttons_state()
        
        if hasattr(self, 'view_quick_btns'):
            while len(self.view_quick_btns) < len(buttons_data):
                idx = len(self.view_quick_btns)
                btn = QPushButton()
                btn.setObjectName("quickSettingBtn")
                btn.setCheckable(True)
                btn.clicked.connect(self.on_view_quick_btn_toggled)
                self.view_quick_btns.append(btn)
                self.view_quick_btn_layout.addWidget(btn, idx // 2, idx % 2)

            for i, btn in enumerate(self.view_quick_btns):
                if i < len(buttons_data):
                    band = buttons_data[i]
                    b_name = band["name"]
                    btn.setText(b_name)
                    btn.setProperty("start_freq", band["start"])
                    btn.setProperty("stop_freq", band["stop"])
                    
                    b_lower = b_name.lower()
                    if "uplink" in b_lower:
                        btn_type = "uplink"
                    elif "downlink" in b_lower:
                        btn_type = "downlink"
                    elif "guard" in b_lower:
                        btn_type = "guard"
                    else:
                        btn_type = "default"
                    btn.setProperty("btn_type", btn_type)
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)
                    btn.setVisible(True)
                else:
                    btn.setVisible(False)
            self.sync_view_quick_buttons_state()

    def on_bw_mode_changed(self):
        if self._updating_bw: return
        self.update_bw_calculations()
        self.apply_bandwidth()

    def on_bw_manual_override(self):
        if self._updating_bw: return
        self._updating_bw = True
        
        if self.sender() == self.rbw_spin and self.rbw_mode_combo.currentIndex() != 0:
            self.rbw_mode_combo.setCurrentIndex(0)
            
        if self.sender() == self.vbw_spin and self.vbw_mode_combo.currentIndex() != 0:
            self.vbw_mode_combo.setCurrentIndex(0)
            
        self._updating_bw = False
        self.apply_bandwidth()

    def update_bw_calculations(self):
        self._updating_bw = True
        
        span = self.stop_spin.value() - self.start_spin.value()
        
        rbw_idx = self.rbw_mode_combo.currentIndex()
        if rbw_idx == 1:
            self.rbw_spin.setValue(span / 2000.0)
        elif rbw_idx == 2:
            self.rbw_spin.setValue(span * 0.001)
        elif rbw_idx == 3:
            self.rbw_spin.setValue(span * 0.01)
            
        rbw = self.rbw_spin.value()
        
        vbw_idx = self.vbw_mode_combo.currentIndex()
        if vbw_idx == 1:
            self.vbw_spin.setValue(rbw)
        elif vbw_idx == 2: # 0.1 * RBW
            self.vbw_spin.setValue(rbw * 0.1)
        elif vbw_idx == 3: # 0.01 * RBW
            self.vbw_spin.setValue(rbw * 0.01)
        elif vbw_idx == 4: # 10 * RBW
            self.vbw_spin.setValue(rbw * 10.0)
            
        self._updating_bw = False
        self.apply_bandwidth()
        
    def apply_bandwidth(self):
        if not hasattr(self, 'controller') or not self.controller.is_connected:
            return
            
        rbw_mode = self.rbw_mode_combo.currentIndex()
        rbw_hz = int(self.rbw_spin.value() * 1e6)
        
        vbw_mode = self.vbw_mode_combo.currentIndex()
        vbw_hz = int(self.vbw_spin.value() * 1e6)
        
        # We need to send these to the device controller
        self.controller.update_bandwidth(rbw_mode, rbw_hz, vbw_mode, vbw_hz)
        

    def on_view_quick_btn_toggled(self):
        if getattr(self, '_updating_view_freqs', False) or getattr(self, '_toggling_view_quick_btns', False): return
        self._toggling_view_quick_btns = True
        try:
            clicked_btn = self.sender()
            if not hasattr(self, '_explicit_view_quick_anchors'):
                self._explicit_view_quick_anchors = set()
                
            if clicked_btn is not None:
                btn_start = clicked_btn.property("start_freq")
                btn_stop = clicked_btn.property("stop_freq")
                if btn_start is not None and btn_stop is not None:
                    band_key = (float(btn_start), float(btn_stop))
                    if clicked_btn.isChecked():
                        self._explicit_view_quick_anchors.add(band_key)
                    else:
                        self._explicit_view_quick_anchors.discard(band_key)
            else:
                self._explicit_view_quick_anchors = {
                    (float(b.property("start_freq")), float(b.property("stop_freq")))
                    for b in self.view_quick_btns if not b.isHidden() and b.isChecked() and b.property("start_freq") is not None
                }

            if self._explicit_view_quick_anchors:
                min_start = min(r[0] for r in self._explicit_view_quick_anchors)
                max_stop = max(r[1] for r in self._explicit_view_quick_anchors)
                
                self._updating_view_freqs = True
                self.view_start_spin.setValue(min_start)
                self.view_stop_spin.setValue(max_stop)
                self.view_center_spin.setValue((min_start + max_stop) / 2.0)
                self.view_span_spin.setValue(max_stop - min_start)
                self._updating_view_freqs = False
                self.apply_view_frequencies()
                self.sync_view_quick_buttons_state()
                
                if getattr(self, 'link_view_check', None) and self.link_view_check.isChecked():
                    if hasattr(self, '_explicit_quick_anchors'):
                        self._explicit_quick_anchors = set(self._explicit_view_quick_anchors)
                    self._updating_freqs = True
                    self.start_spin.setValue(min_start)
                    self.stop_spin.setValue(max_stop)
                    self.center_spin.setValue((min_start + max_stop) / 2.0)
                    self.span_spin.setValue(max_stop - min_start)
                    self._updating_freqs = False
                    self.apply_frequencies()
                    self.sync_quick_buttons_state()
            else:
                for btn in self.view_quick_btns:
                    btn.blockSignals(True)
                    btn.setChecked(False)
                    btn.blockSignals(False)
                if getattr(self, 'link_view_check', None) and self.link_view_check.isChecked():
                    if hasattr(self, '_explicit_quick_anchors'):
                        self._explicit_quick_anchors.clear()
                    for s_btn in self.quick_btns:
                        s_btn.blockSignals(True)
                        s_btn.setChecked(False)
                        s_btn.blockSignals(False)
        finally:
            self._toggling_view_quick_btns = False

    def sync_view_quick_buttons_state(self):
        if getattr(self, '_updating_view_freqs', False): return
        if not hasattr(self, 'view_quick_btns'): return
        
        start_val = self.view_start_spin.value()
        stop_val = self.view_stop_spin.value()
        
        for btn in self.view_quick_btns:
            btn.blockSignals(True)
            if not btn.isHidden():
                btn_start = btn.property("start_freq")
                btn_stop = btn.property("stop_freq")
                if btn_start is not None and btn_stop is not None:
                    # An intermediate band or selected band is a true activation if enclosed in the active span
                    if (start_val <= btn_start + 0.5) and (stop_val >= btn_stop - 0.5):
                        btn.setChecked(True)
                    else:
                        btn.setChecked(False)
            btn.blockSignals(False)

    def on_quick_btn_toggled(self):
        if getattr(self, '_updating_freqs', False) or getattr(self, '_toggling_quick_btns', False): return
        self._toggling_quick_btns = True
        try:
            clicked_btn = self.sender()
            if not hasattr(self, '_explicit_quick_anchors'):
                self._explicit_quick_anchors = set()
                
            if clicked_btn is not None:
                btn_start = clicked_btn.property("start_freq")
                btn_stop = clicked_btn.property("stop_freq")
                if btn_start is not None and btn_stop is not None:
                    band_key = (float(btn_start), float(btn_stop))
                    if clicked_btn.isChecked():
                        self._explicit_quick_anchors.add(band_key)
                    else:
                        self._explicit_quick_anchors.discard(band_key)
            else:
                self._explicit_quick_anchors = {
                    (float(b.property("start_freq")), float(b.property("stop_freq")))
                    for b in self.quick_btns if not b.isHidden() and b.isChecked() and b.property("start_freq") is not None
                }

            if self._explicit_quick_anchors:
                min_start = min(r[0] for r in self._explicit_quick_anchors)
                max_stop = max(r[1] for r in self._explicit_quick_anchors)
                
                self._updating_freqs = True
                self.start_spin.setValue(min_start)
                self.stop_spin.setValue(max_stop)
                self.center_spin.setValue((min_start + max_stop) / 2.0)
                self.span_spin.setValue(max_stop - min_start)
                self._updating_freqs = False
                self.apply_frequencies()
                self.sync_quick_buttons_state()
                
                if getattr(self, 'link_view_check', None) and self.link_view_check.isChecked():
                    if hasattr(self, '_explicit_view_quick_anchors'):
                        self._explicit_view_quick_anchors = set(self._explicit_quick_anchors)
                    self._updating_view_freqs = True
                    self.view_start_spin.setValue(min_start)
                    self.view_stop_spin.setValue(max_stop)
                    self.view_center_spin.setValue((min_start + max_stop) / 2.0)
                    self.view_span_spin.setValue(max_stop - min_start)
                    self._updating_view_freqs = False
                    self.apply_view_frequencies()
                    self.sync_view_quick_buttons_state()
            else:
                for btn in self.quick_btns:
                    btn.blockSignals(True)
                    btn.setChecked(False)
                    btn.blockSignals(False)
                if getattr(self, 'link_view_check', None) and self.link_view_check.isChecked():
                    if hasattr(self, '_explicit_view_quick_anchors'):
                        self._explicit_view_quick_anchors.clear()
                    for v_btn in self.view_quick_btns:
                        v_btn.blockSignals(True)
                        v_btn.setChecked(False)
                        v_btn.blockSignals(False)
        finally:
            self._toggling_quick_btns = False

    def sync_quick_buttons_state(self):
        if getattr(self, '_updating_freqs', False): return
        if not hasattr(self, 'quick_btns'): return
        
        start_val = self.start_spin.value()
        stop_val = self.stop_spin.value()
        
        for btn in self.quick_btns:
            btn.blockSignals(True)
            if not btn.isHidden():
                btn_start = btn.property("start_freq")
                btn_stop = btn.property("stop_freq")
                if btn_start is not None and btn_stop is not None:
                    # An intermediate band or selected band is a true activation if enclosed in the active span
                    if (start_val <= btn_start + 0.5) and (stop_val >= btn_stop - 0.5):
                        btn.setChecked(True)
                    else:
                        btn.setChecked(False)
            btn.blockSignals(False)

    def closeEvent(self, event):
        self.controller.disconnect_device()
        event.accept()

    def handle_device_info(self, model, uid):
        cal_dir = self.cal_manager.get_cal_dir(model, uid)
        if cal_dir is None:
            self.controller.disconnect_device()
            
            dialog = MissingCalDialog(model, uid, self)
            dialog.exec()
            
            if dialog.result_action == "continue":
                self.update_status("Continuing without calibration files...")
                start_hz = self.start_spin.value() * 1e6
                stop_hz = self.stop_spin.value() * 1e6
                self.controller.connect_device(start_freq_hz=start_hz, stop_freq_hz=stop_hz, probe_only=False, cal_dir=None)
            
            elif dialog.result_action == "import":
                dd_dialog = DragDropCalDialog(model, uid, self)
                if dd_dialog.exec():
                    if dd_dialog.is_ready:
                        success = self.cal_manager.save_dragged_files(dd_dialog.dropped_files, model, uid)
                        if success:
                            QMessageBox.information(self, "Success", "Calibration files imported successfully.")
                            # Now connect
                            cal_dir = self.cal_manager.get_cal_dir(model, uid)
                            self.update_status("Calibration files found. Initializing...")
                            start_hz = self.start_spin.value() * 1e6
                            stop_hz = self.stop_spin.value() * 1e6
                            self.controller.connect_device(start_freq_hz=start_hz, stop_freq_hz=stop_hz, probe_only=False, cal_dir=cal_dir)
                        else:
                            QMessageBox.warning(self, "Error", "Failed to save calibration files.")
                            self.update_ui_state(False)
                    else:
                        self.update_status("Import cancelled.")
                        self.update_ui_state(False)
                else:
                    self.update_status("Import cancelled.")
                    self.update_ui_state(False)
            else:
                self.update_status("Connection cancelled.")
                self.update_ui_state(False)
        else:
            self.update_status("Calibration files found. Initializing...")
            start_hz = self.start_spin.value() * 1e6
            stop_hz = self.stop_spin.value() * 1e6
            self.controller.connect_device(start_freq_hz=start_hz, stop_freq_hz=stop_hz, probe_only=False, cal_dir=cal_dir)

    def import_calibration_files(self):
        dd_dialog = DragDropCalDialog(model=None, uid=None, parent=self)
        if dd_dialog.exec():
            if dd_dialog.is_ready and dd_dialog.model is not None and dd_dialog.uid is not None:
                success = self.cal_manager.save_dragged_files(dd_dialog.dropped_files, dd_dialog.model, dd_dialog.uid)
                if success:
                    QMessageBox.information(self, "Success", f"Calibration files imported successfully for SN: {dd_dialog.uid:016x}.")
                else:
                    QMessageBox.warning(self, "Error", "Failed to save calibration files.")
            else:
                QMessageBox.warning(self, "Error", "Import was not completed properly.")

    def clear_calibration_files(self):
        cals = self.cal_manager.get_available_calibrations()
        if not cals:
            QMessageBox.information(self, "No Calibrations", "There are no saved calibration files to clear.")
            return
            
        dialog = ClearCalDialog(cals, self)
        if dialog.exec():
            success = self.cal_manager.clear_calibration(dialog.selected_model, dialog.selected_uid)
            if success:
                QMessageBox.information(self, "Success", f"Calibration data for SN: {dialog.selected_uid:016x} has been cleared.")
            else:
                QMessageBox.warning(self, "Error", "Failed to clear calibration data.")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos') and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)
        
    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)
