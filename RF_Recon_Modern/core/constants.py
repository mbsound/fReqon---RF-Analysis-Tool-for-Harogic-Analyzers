"""
Constants, TV channel band plans, regional definitions, and RF parameter options.
"""

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
                        "display_name": f"DTV {ch} - LMR/SMR ({698.0 + (ch - 52) * 6.0:g}-{698.0 + (ch - 51) * 6.0:g})",
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

WATERFALL_COLORMAPS = ['viridis', 'inferno', 'plasma', 'magma', 'turbo', 'jet', 'bipolar']

COLORMAP_CSS = {
    'viridis': "stop:0 #440154, stop:0.25 #3b528b, stop:0.5 #21918c, stop:0.75 #5ec962, stop:1 #fde725",
    'inferno': "stop:0 #000004, stop:0.25 #57106e, stop:0.5 #bc3754, stop:0.75 #f98d0a, stop:1 #fcffa4",
    'plasma': "stop:0 #0d0887, stop:0.25 #7e03a8, stop:0.5 #cc4678, stop:0.75 #f89441, stop:1 #f0f921",
    'magma': "stop:0 #000004, stop:0.25 #50127b, stop:0.5 #b63679, stop:0.75 #fb8861, stop:1 #fcfdbf",
    'turbo': "stop:0 #30123b, stop:0.25 #28bbec, stop:0.5 #a2ffa3, stop:0.75 #fb8022, stop:1 #7a0403",
    'jet': "stop:0 #00007f, stop:0.25 #007fff, stop:0.5 #7fff7f, stop:0.75 #ff7f00, stop:1 #7f0000",
    'bipolar': "stop:0 #00ffff, stop:0.5 #000000, stop:1 #ffff00"
}

SWT_MODES = [
    "minSWT", "minSWTx2", "minSWTx4", "minSWTx10", "minSWTx20", "minSWTx50", "minSWTxN", "Manual", "minSMPxN"
]

SPUR_REJECTION_MODES = ["Bypass", "Standard", "Enhanced"]

WINDOW_FUNCTIONS = ["FlatTop", "Blackman-Nuttall", "LowSideLobe", "Rectangle", "Kaiser"]

DETECTOR_TYPES = ["Sample", "PosPeak", "Average", "NegPeak", "MaxPower", "RawFrames", "RMS"]

TRACE_DETECTOR_TYPES = ["AutoSample", "Sample", "PosPeak", "NegPeak", "RMS", "Bypass", "AutoPeak", "Normal"]

RBW_MODES = ["Manual", "Automatic", "0.001*Span", "0.01*Span"]

VBW_MODES = ["Manual", "VBW=RBW", "0.1*RBW", "0.01*RBW", "10*RBW"]

PREAMP_OPTIONS = [
    ("Auto On", 0x00),
    ("Forced Off", 0x01),
    ("Low Gain", 0x02),
    ("Medium Gain", 0x03),
    ("High Gain", 0x04)
]
