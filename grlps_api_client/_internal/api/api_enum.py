"""
C2-EPR API names (reference: GRLPS_PY_API_C3_ALL API/api_enum.py).
Maps to config in grlps_api_config.json.
"""
from enum import Enum


class ApiName(Enum):
    """C2-EPR API endpoint names."""

    # Connection / setup
    CONNECTION_SETUP = "ConnectionSetup"
    FORCE_STOP = "ForceStop"
    GET_IP_ADDRESS_HISTORY = "GetIPAddressHistory"
    LATEST_FIRMWARE_AND_ELOAD_VERSION = "LatestFirmwareAndEloadVersion"

    # App
    GET_SOFTWARE_VERSION = "GetSoftwareVersion"
    GET_APP_STATE = "GetAppState"
    GET_MESSAGE_BOX = "GetMessageBox"
    PUT_MESSAGE_BOX_RESPONSE = "PutMessageBoxResponse"
    PUT_PROJECT_FOLDER = "PutProjectFolder"
    PUT_DISABLE_POP_UP_STATUS = "DisablePop"
    GET_TEMPERATURE_INFO = "GetTemperatureInfo"

    # Test configuration
    GET_TEST_CASE_LIST = "GetTestCaseList"
    POST_TEST_LIST_TO_EXECUTE = "PostTestListToExecute"
    STOP_TEST_EXECUTION = "StopTestExecution"
    PUT_COMMON_TEST_CONFIGURATION = "PutCommonTestConfiguration"
    PUT_CURRENT_SELECTED_PORT = "PutCurrentSelectedPort"
    GET_CURRENT_SELECTED_PORT_STATUS = "GetCurrentSelectedPortStatus"
    PDM = "PDM"
    GET_CABLE_NAME = "GetCableName"
    PUT_PD3_CONFIGURATION = "PutPD3Configuration"
    PUT_DP_ALT_CONFIGURATION = "PutDpAltConfiguration"
    PUT_QC3_CONFIGURATION = "PutQC3Configuration"
    PUT_QC4_CONFIGURATION = "PutQC4Configuration"
    PUT_SPT_CONFIGURATION = "PutSPTConfiguration"
    PUT_TBT_CONFIGURATION = "PutTBTConfiguration"
    PUT_DETERMINISTIC_CONFIGURATION = "PutDeterministicConfiguration"
    PUT_FUNCTIONAL_CONFIGURATION = "PutFunctionalConfiguration"
    PUT_PD2_CONFIGURATION = "PutPd2Configuration"
    PUT_CB_CONFIGURATION = "PutCBConfiguration"
    PUT_BC_1_2_CONFIGURATION = "PutBC_1_2Configuration"
    PUT_MFI_CHARGER_TEST_CONFIGURATION = "PutMfiChargerTestConfiguration"

    # Product capability / VIF
    PUT_PORT_CONFIGURATIONS = "PutPortConfigurations"
    GET_PORT_CONFIGURATIONS = "GetPortConfigurations"
    VIF_PATH = "VifPath"
    PUT_VIF_DATA = "PutVIFData"

    # IR drop calibration
    GET_IR_DROP_CALIBRATION_STATUS = "GetIrDropCalibrationStatus"
    GET_IR_DROP_CALIBRATION_TABLE_VALUES = "GetIRDropCalibrationTableValues"

    # Plot / waveform
    GET_ALL_CHANNEL_DATA = "GetAllChannelData"
    GET_CC_LINE_PACKETS = "GetCCLinePackets"
    GET_CHANNEL_LIST = "GetChannelList"
    PUT_LOAD_WAVEFORM_FILE = "PutLoadWaveformFile"
    GET_FILE_READ_STATUS = "GetFileReadStatus"
    GET_WAVEFORM_START_TIME = "GetWaveformStartTime"
    GET_WAVEFORM_STOP_TIME = "GetWaveformStopTime"
    GET_PD_MESSAGE_COUNT = "GetPDMessageCount"

    # Results
    GET_TEST_RESULTS = "GetTestResults"

    # Reports
    POST_UPDATE_REPORT_INPUTS = "PostUpdateReportInputs"
    GET_REPORT_INPUTS = "GetReportInputs"
    GET_TEST_RUN_INFO = "GetTestRunInfo"
    GET_RESULTS_FOLDER_NAME = "GetResultsFolderName"
    GET_REPORT_FILE_NAME = "GetReportFileName"
    GET_REPORT_PATH_STATUS = "GetReportPathStatus"
