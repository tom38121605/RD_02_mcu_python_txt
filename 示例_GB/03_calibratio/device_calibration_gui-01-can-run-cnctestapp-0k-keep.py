import sys
sys.path.append('C:\\workspace\\ommo_python_core')

import configparser

import h5py
from PyQt5 import Qt
import semver
from PyQt5 import QtCore
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from requests import Response

import ommo_io_defs as ommo
from UI.device_calibration_base import DeviceCalibrationBase
from cnctestapp_runner import CNCTestAppRunner
import serial.tools.list_ports as list_ports
from datetime import datetime
import os
import time
import shlex
import subprocess
import logging
import ommo_fw_pb2 as pb
from s3_processing import get_sensor_calibration_bucket
from utils.calibration_result_polling_worker import get_target_file_names_from_calibration_runs, get_successful_runs, \
    get_target_file_from_calibration_run

from utils.custom_file_name_widget import CustomFileNameBox
from utils.constants import ORG_NAME, UUID_LENGTH

from utils.test_file_filter_combobox import TestFileFilterComboBox

from utils.directus import get_first_result_from_response, update_flashed_with_for_sensors
from utils.hardwares import write_gains_file_to_sensors, generate_set_of_uuids
from utils.helpers import get_files_in_folder, alert_window, check_and_install_update, ScrollMessageArea, clear_layout, \
    alert_dialog, SearchableComboBox, load_saved_value_to_combo_box
from utils.testgroup_combobox import TestGroupIdComboBox
from utils.version import APPLICATION_VERSION
from utils.constants import ORG_NAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("device_calib_gui")
logger.setLevel(logging.INFO)

CNCTESTAPP_VERSION = '1.3.1'

# def create_sensor_orientation_value_json_str(num_sensors, orientation_str):
#     orientations = []
#     for i in range(num_sensors):
#         orientations.append(orientation_str)
#     return json.dumps(orientations)
#
#
# def create_sensor_position_value_json_str(num_sensors, pos):
#     positions = []
#     assert len(pos) == 3
#     for i in range(num_sensors):
#         positions.append(
#             {"x":pos[0],
#              "y":pos[1],
#              "z":pos[2]
#             }
#         )
#     return json.dumps(positions)


class DeviceCalibrationApp(DeviceCalibrationBase, QMainWindow):

    FILE_FILTER_SETTING_KEY = "dc_file_filter"
    DEVICE_PALLET_FILE_SETTING_KEY = "dc_device_pallet_file"
    TEST_FILE_SETTING_KEY = "dc_test_file"
    # TODO migrate the other keys
    
    def __init__(self, app_root_name):
        DeviceCalibrationBase.__init__(self, app_name=app_root_name, logger=logger)
        QMainWindow.__init__(self)
        self.setWindowTitle('Device Calibration Gui')

        self.setWindowTitle('Device Calibration Gui')

        self.development_mode = self.config.has_option('DEFAULT', 'development')
        self.output_directory = self.config['DEFAULT']['output_directory']

        # instance vars
        self.is_setup = False
        self.dt_str = ''
        self.cnctestapp_path='C:\\workspace\\Debug No VISA\\CNCTestApplication.exe'

        # exit the program is cnctestapp version is outdated
        with CNCTestAppRunner(self.cnctestapp_path) as cnctestapp:
            success, version = cnctestapp.check_cnctestapp_version()
            if not success or semver.compare(version[1:], CNCTESTAPP_VERSION) < 0:
                alert_window("CNCTestApp Outdated", "Please update your CNCTestApp version to v{0} or above.".format(CNCTESTAPP_VERSION))
                exit(0)

        # find pallet file names
        pallet_files = get_files_in_folder(os.path.join(self.cnctestapp_testfiles_path, "PalletFiles"), '.senpallet')
        # find test file names
        test_files = get_files_in_folder(os.path.join(self.cnctestapp_testfiles_path, "StandardTests"), '.ftest')

        # Create setup box with grid layout
        self.setup_box = QGroupBox('Setup')
        setup_box_layout = QGridLayout()
        setup_box_y = 0
        # Add SIU selector
        setup_box_layout.addWidget(QLabel('Select SIU'), setup_box_y, 0)
        self.siu_selector = SearchableComboBox()
        # self.siu_selector.addItems([hw.description for hw in ommo.Hardware if hw.is_siu])
        self.siu_selector.addItems([hw.description for hw in ommo.Hardware])
        setup_box_layout.addWidget(self.siu_selector, setup_box_y, 1)
        # Add buttons
        setup_button = QPushButton('Setup')
        setup_button.clicked.connect(self.setup)
        setup_box_layout.addWidget(setup_button, setup_box_y, 2)
        setup_box_y = setup_box_y + 1
        self.run_all_button = QPushButton('Run All')
        self.run_all_button.clicked.connect(self.run_all)
        setup_box_layout.addWidget(self.run_all_button, setup_box_y, 2)
        # Add Device selector
        setup_box_layout.addWidget(QLabel('Select Device Part'), setup_box_y, 0)
        self.device_part_selector = SearchableComboBox()
        self.device_part_selector.addItems([part.description for part in ommo.DevicePart])
        setup_box_layout.addWidget(self.device_part_selector, setup_box_y, 1)
        setup_box_y = setup_box_y + 1
        # Add disabled ports selector
        setup_box_layout.addWidget(QLabel('Select Enabled Ports'), setup_box_y, 0)
        self.ports_enabled = QComboBox()
        self.ports_enabled.addItem('All')
        self.ports_enabled.addItems([str(num) for num in range(12)])
        setup_box_layout.addWidget(self.ports_enabled, setup_box_y, 1)

        check_layout = QGridLayout()
        # Ignore onboard sensor errors
        self.disable_onboard_sensors_cb = QCheckBox('Disable onboard sensors')
        self.disable_onboard_sensors_cb.setChecked(False)
        check_layout.addWidget(self.disable_onboard_sensors_cb, 0, 1)
        #setup_box_layout.addWidget(self.ignore_set_onboard_sensor_errors_cb, 2, 2)
        # Add Part num check
        self.part_num_cb = QCheckBox('Device Part Verify')
        self.part_num_cb.setChecked(False)
        check_layout.addWidget(self.part_num_cb, 0, 0)
        setup_box_layout.addItem(check_layout, setup_box_y, 2, 1, 1)
        setup_box_y = setup_box_y + 1
        #setup_box_layout.addWidget(self.part_num_cb, 2, 1)

        # Add devices box
        self.active_siu_box = QGroupBox('SIUs')
        self.active_siu_box_layout = QHBoxLayout()

        # Add scroll area for active devices
        self.active_siu_scroll = QScrollArea()
        self.active_siu_scroll.setWidgetResizable(True)
        self.active_siu_scroll.setFixedHeight(180)
        self.active_siu_scroll.setFrameShape(QFrame.NoFrame)

        # Add scroll to active siu box
        self.active_siu_box.setLayout(self.active_siu_box_layout)
        self.active_siu_scroll.setWidget(self.active_siu_box)

        setup_box_layout.addWidget(self.active_siu_scroll, setup_box_y, 0, -1, -1)
        setup_box_layout.setColumnStretch(2, 1)
        self.setup_box.setLayout(setup_box_layout)

        # Create DeviceInfo initialization box
        self.init_box = QGroupBox('Initialize DeviceInfo and UUID')
        init_box_layout = QGridLayout()
        init_box_y = 0
        # Add options
        self.write_uuids_cb = QCheckBox('Write Device UUIDs')
        self.write_uuids_cb.setChecked(False)
        self.init_box_enabled_cb = QCheckBox('Enable')
        self.init_box_enabled_cb.setChecked(True)
        init_box_layout.addWidget(self.write_uuids_cb, init_box_y, 0)
        init_box_layout.addWidget(self.init_box_enabled_cb, init_box_y, 1, alignment=Qt.AlignRight)
        init_box_y = init_box_y + 1
        if self.development_mode:
            self.create_custom_uuids_cb = QCheckBox('Create Custom UUIDs')
            self.create_custom_uuids_cb.setChecked(False)
            self.custom_uuids_input = QLineEdit()
            self.custom_uuids_input.setEnabled(False)
            self.custom_uuids_input.setPlaceholderText('Write your 19-digit UUID here...')
            self.custom_uuids_input.setMaxLength(19)  # 19 digit uuids allowed
            self.create_custom_uuids_cb.toggled.connect(self.custom_uuids_input.setEnabled)
            init_box_layout.addWidget(self.create_custom_uuids_cb, init_box_y, 0)
            init_box_y = init_box_y + 1
            init_box_layout.addWidget(self.custom_uuids_input, init_box_y, 0, 1, 1)
        self.run_init_button = QPushButton('Run')
        self.run_init_button.clicked.connect(self.run_device_info_uuid_initialization)
        init_box_layout.addWidget(self.run_init_button, init_box_y, 1, alignment=Qt.AlignRight)
        init_box_y = init_box_y + 1
        self.init_box_msg_area = ScrollMessageArea()
        init_box_layout.addWidget(self.init_box_msg_area, init_box_y, 0, 1, 2)
        self.init_box.setLayout(init_box_layout)
        # self.ignore_set_onboard_sensor_errors_cb = QCheckBox('Ignore set onboard sensor errors')
        # self.ignore_set_onboard_sensor_errors_cb.setChecked(False)
        # init_box_layout.addWidget(self.ignore_set_onboard_sensor_errors_cb, 1, 0)

        # Create collect data box
        self.collect_data_box = QGroupBox('Collect Freq/Amp Data')
        collect_data_box_layout = QGridLayout()
        waveform_gen_selector_box = QGroupBox('Waveform Generator Source')
        waveform_gen_selector_box_layout = QGridLayout()
        self.use_agilent_rbutton = QRadioButton('Use Agilent')
        waveform_gen_selector_box_layout.addWidget(self.use_agilent_rbutton, 0, 0, 1, 2)
        self.use_keithley_rbutton = QRadioButton('Use Keithley')
        self.use_keithley_rbutton.setChecked(True)
        waveform_gen_selector_box_layout.addWidget(self.use_keithley_rbutton, 1, 0, 1, 2)
        self.waveform_gen_port_selector = QComboBox()
        waveform_gen_selector_box_layout.addWidget(QLabel('Port'), 2, 0)
        waveform_gen_selector_box_layout.addWidget(self.waveform_gen_port_selector, 2, 1)
        waveform_gen_selector_box.setLayout(waveform_gen_selector_box_layout)
        collect_data_box_layout.addWidget(waveform_gen_selector_box, 1, 0, 2, 1)

        self.collect_data_box_enabled_cb = QCheckBox('Enable')
        self.collect_data_box_enabled_cb.setChecked(True)
        collect_data_box_layout.addWidget(self.collect_data_box_enabled_cb, 0, 1, alignment=Qt.AlignRight)

        collect_data_box_layout.addWidget(self.create_test_file_setup_box(), 1, 1, 2, 1)

        self.test_group_combobox = TestGroupIdComboBox(logger)
        collect_data_box_layout.addWidget(self.test_group_combobox, 3, 0, alignment=Qt.AlignLeft)

        self.run_collect_data_button = QPushButton('Run')
        self.run_collect_data_button.clicked.connect(self.run_collect_data)
        collect_data_box_layout.addWidget(self.run_collect_data_button, 3, 1, alignment=Qt.AlignRight)
        self.collect_data_box_msg_area = ScrollMessageArea()
        collect_data_box_layout.addWidget(self.collect_data_box_msg_area, 4, 0, 1, 2)
        self.collect_data_box.setLayout(collect_data_box_layout)

        # Create calibrate devices box
        self.calibrate_devices_box = None
        self.data_file_path_input = None
        self.config_yaml_path_input = None
        self.calibrate_devices_box_enabled_cb = None
        self.calibrate_devices_box_msg_area = None
        self.remote_sensor_calibration_cb = None
        self.run_calibrate_devices_button = None
        self.local_calibration_widget = None
        self.remote_calibration_widget = None
        self.upload_progressbar = None
        self.polling_status_label = None
        self.create_calibration_box()

        # Create upload gains box
        self.upload_gains_box = QGroupBox('Upload Gains')
        upload_gains_box_layout = QGridLayout()
        upload_gains_box_layout.addWidget(QLabel('Gain File Path'), 0, 0)
        self.gain_file_path_input = QLineEdit('N/A')
        upload_gains_box_layout.addWidget(self.gain_file_path_input, 1, 0, 1, 4)
        self.select_gain_file_button = QPushButton('Select Gain File')
        self.select_gain_file_button.clicked.connect(self.select_gain_file)
        upload_gains_box_layout.addWidget(self.select_gain_file_button, 2, 0)

        self.upload_gains_box_enabled_cb = QCheckBox('Enable')
        self.upload_gains_box_enabled_cb.setChecked(True)
        upload_gains_box_layout.addWidget(self.upload_gains_box_enabled_cb, 0, 3, alignment=Qt.AlignRight)
        self.run_upload_gains_button = QPushButton('Run')
        self.run_upload_gains_button.clicked.connect(self.run_upload_gains)
        upload_gains_box_layout.addWidget(self.run_upload_gains_button, 2, 3, alignment=Qt.AlignRight)
        self.upload_gains_box_msg_area = ScrollMessageArea()
        upload_gains_box_layout.addWidget(self.upload_gains_box_msg_area, 3, 0, 1, 4)
        self.upload_gains_box.setLayout(upload_gains_box_layout)

        main_layout = QGridLayout()
        main_layout.addWidget(self.setup_box, 0, 0, 1, 2)
        main_layout.addWidget(self.init_box, 1, 0)
        main_layout.addWidget(self.collect_data_box, 1, 1)
        main_layout.addWidget(self.calibrate_devices_box, 2, 0)
        main_layout.addWidget(self.upload_gains_box, 2, 1)
        main_layout.addWidget(self.create_disable_ic_box(), 3, 0, 1, 2)
        if self.development_mode:
            self.custom_file_name_box = CustomFileNameBox(logger)
            main_layout.addWidget(self.custom_file_name_box, 4, 0, 1, 2)
        widget = QWidget()
        widget.setLayout(main_layout)
        # Set the central widget of the Window. Widget will expand
        # to take up all the space in the window by default.
        self.setCentralWidget(widget)

        self.load_settings()
        self.siu_selector.currentTextChanged.connect(lambda selected_text: QSettings().setValue('selected_siu', selected_text))
        self.device_part_selector.currentTextChanged.connect(lambda selected_text: QSettings().setValue('selected_device_part', selected_text))

        self.use_agilent_rbutton.clicked.connect(lambda checked: QSettings().setValue('waveform_gen', 'agilent'))
        self.use_keithley_rbutton.clicked.connect(lambda checked: QSettings().setValue('waveform_gen', 'keithley'))

        self.waveform_gen_port_selector.currentTextChanged.connect(lambda selected_text: QSettings().setValue('wavegen_port', selected_text) if selected_text else None)
        self.device_pallet_file.currentTextChanged.connect(lambda selected_text: QSettings().setValue(self.DEVICE_PALLET_FILE_SETTING_KEY, selected_text))
        self.test_file.currentTextChanged.connect(lambda selected_text: QSettings().setValue(self.TEST_FILE_SETTING_KEY, selected_text))

        self.config_yaml_path_input.textChanged.connect(lambda text: QSettings().setValue('config_yml_path', text))
        #  custom output file names are r&d only
        if self.development_mode:
            (self.custom_file_name_box.output_filename_line_edit.textChanged
             .connect(lambda text: QSettings().setValue('custom_output_file', text)))

        # reset state
        self.reset()

    def generate_ic_list(self):
        ic_list = []
        # close all port leds if applicable
        for siu in self.matched_sius:
            siu.open_port()

            for device in siu.device_list:
                for index, ic in enumerate(device.device_info.ics):
                    print(f"{ic.ic_ss_index} - {pb.ICType.Name(ic.ic_type)}")
                    ic_list.append(f"{ic.ic_ss_index} - {pb.ICType.Name(ic.ic_type)}")
            ic_list.append("- Onboard Sensors")
        return ic_list

    def create_disable_ic_box(self):
        disable_ic_box = QGroupBox('Disable ICs')
        self.disable_ic_box_layout = QGridLayout()

        size_policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        disable_ic_box.setSizePolicy(size_policy)

        disable_ic_box.setLayout(self.disable_ic_box_layout)
        return disable_ic_box

    def refresh_disable_ic_box(self):
        clear_layout(self.disable_ic_box_layout)
        self.disable_ic_checkboxes = []
        self.disable_ic_box_layout.addWidget(QLabel('IC to disable:'), 0, 0)

        disable_ic_scroll_area = QScrollArea()
        disable_ic_scroll_area.setWidgetResizable(True)
        disable_ic_scroll_area.setMaximumHeight(150)

        disable_ic_scroll_area.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        disable_ic_scroll_widget = QWidget()
        disable_ic_scroll_layout = QVBoxLayout(disable_ic_scroll_widget)

        ic_list = self.generate_ic_list()
        for index, ic_string in enumerate(ic_list):
            checkbox = QCheckBox(ic_string)
            disable_ic_scroll_layout.addWidget(checkbox)
            self.disable_ic_checkboxes.append(checkbox)

        disable_ic_scroll_widget.setLayout(disable_ic_scroll_layout)
        disable_ic_scroll_area.setWidget(disable_ic_scroll_widget)

        # Add the scroll area to main layout
        self.disable_ic_box_layout.addWidget(disable_ic_scroll_area, 0, 0)

        disable_ics_button = QPushButton('Disable Checked ICs')
        disable_ics_button.clicked.connect(self.disable_ics)
        self.disable_ic_box_layout.addWidget(disable_ics_button, len(ic_list) + 1, 0)

    def disable_ics(self):
        failure = False
        devices_written = 0
        for siu in self.matched_sius:
            siu.open_port()
            for device in siu.device_list:
                port_id = device.port_num

                user_proto = siu.read_device_info(port_id, pb.DEVICE_INFO_FIELD_USER)

                config_disable_ic = 0
                for checkbox in self.disable_ic_checkboxes:
                    if checkbox.isChecked():
                        text = checkbox.text()
                        words = text.split("-")

                        # Grab ss index
                        words[0] = words[0].strip()
                        if len(words[0]) > 0:
                            ss_index = int(words[0])
                            config_disable_ic += 2 ** ss_index
                        elif 'Onboard' in words[1]:
                            user_proto.config_disable_onboard_sensors = True

                print(f"config_disable_ic {config_disable_ic}")
                print(f"user_proto.config_disable_onboard_sensors {user_proto.config_disable_onboard_sensors}")
                user_proto.config_disable_ic = config_disable_ic

                success = siu.write_device_info(port_id, user_proto, pb.DEVICE_INFO_FIELD_USER)

                if not success:
                    siu.set_port_led_color(port_id, ommo.PortLed.DEVICE_FAIL)
                    alert_window('SIU Error',
                                 f"Failed to write User Info on port {port_id}. \nwritten=\n{user_proto} \n")
                    failure = True
                    break
                user_proto_read = siu.read_device_info(port_id, pb.DEVICE_INFO_FIELD_USER)
                print(user_proto_read.config_disable_ic)
                if user_proto_read and user_proto != user_proto_read:
                    siu.set_port_led_color(port_id, ommo.PortLed.DEVICE_FAIL)
                    alert_window('SIU Error',
                                 f"User Info on port {port_id} does not match. \nwritten=\n{user_proto} \nread=\n{user_proto_read}")
                    failure = True
                    break
                devices_written += 1
        if not failure:
            alert_window(f"{devices_written} devices written",
                         f"ICs disabled on {devices_written} devices", QMessageBox.Information)

    def create_test_file_setup_box(self):
        test_setup_box = QGroupBox('Test Setup')
        test_setup_box_layout = QGridLayout()
        current_y = 0
        test_setup_box_layout.addWidget(QLabel(self.tr("Files Filter")), current_y, 0)
        self.test_files_filter = TestFileFilterComboBox(self.cnctestapp_path,
                                                        self.cnctestapp_settingsfiles_path,
                                                        self.cnctestapp_testfiles_path)
        current_y = current_y + 1
        test_setup_box_layout.addWidget(self.test_files_filter, current_y, 0)
        self.test_files_filter.load_checked_from_string(QSettings().value(self.FILE_FILTER_SETTING_KEY, ''))
        self.test_files_filter.test_file_filter_changed.connect(self.refresh_dropdown_files)
        current_y = current_y + 1

        test_setup_box_layout.addWidget(QLabel('Device Pallet'), current_y, 0)
        current_y = current_y + 1
        self.device_pallet_file = SearchableComboBox()
        test_setup_box_layout.addWidget(self.device_pallet_file, current_y, 0)
        current_y = current_y + 1
        test_setup_box_layout.addWidget(QLabel('Test File'), current_y, 0)
        current_y = current_y + 1
        self.test_file = SearchableComboBox()
        test_setup_box_layout.addWidget(self.test_file, current_y, 0)
        current_y = current_y + 1
        test_setup_box.setLayout(test_setup_box_layout)
        return test_setup_box

    @QtCore.pyqtSlot()
    def refresh_dropdown_files(self):
        # save
        QSettings().setValue(self.FILE_FILTER_SETTING_KEY, self.test_files_filter.get_checked_items_string())

        self.refreshing_dropdown_files = True
        # find pallet file names
        pallet_files = self.test_files_filter.get_compatible_files_for_suffix('.senpallet')
        self.device_pallet_file.clear()
        self.device_pallet_file.addItems(pallet_files)

        test_files = self.test_files_filter.get_compatible_files_for_suffix('.ftest')
        self.test_file.clear()
        self.test_file.addItems(test_files)

        self.refreshing_dropdown_files = False

        load_saved_value_to_combo_box(self.device_pallet_file, self.DEVICE_PALLET_FILE_SETTING_KEY)
        load_saved_value_to_combo_box(self.test_file, self.TEST_FILE_SETTING_KEY)

    def create_calibration_box(self):
        self.calibrate_devices_box = QGroupBox('Calibrate Devices')
        calibrate_devices_box_layout = QGridLayout()
        calibrate_devices_box_layout.addWidget(QLabel('Data File Path'), 0, 0)
        self.data_file_path_input = QLineEdit('N/A')
        calibrate_devices_box_layout.addWidget(self.data_file_path_input, 1, 0, 1, 4)
        select_calibration_data_file_button = QPushButton('Select Data File')
        select_calibration_data_file_button.clicked.connect(self.select_calibration_data_file)
        calibrate_devices_box_layout.addWidget(select_calibration_data_file_button, 3, 0)

        self.remote_sensor_calibration_cb = QCheckBox('Remote Run')
        self.remote_sensor_calibration_cb.setChecked(True)
        self.remote_sensor_calibration_cb.stateChanged.connect(self.remote_sensor_calibration_state_changed)
        calibrate_devices_box_layout.addWidget(self.remote_sensor_calibration_cb, 0, 2, alignment=Qt.AlignRight)

        self.calibrate_devices_box_enabled_cb = QCheckBox('Enable')
        self.calibrate_devices_box_enabled_cb.setChecked(True)
        calibrate_devices_box_layout.addWidget(self.calibrate_devices_box_enabled_cb, 0, 3, alignment=Qt.AlignRight)

        self.run_calibrate_devices_button = QPushButton('Run')
        self.run_calibrate_devices_button.clicked.connect(self.run_calibrate_devices)
        calibrate_devices_box_layout.addWidget(self.run_calibrate_devices_button, 3, 3, alignment=Qt.AlignRight)


        # the followings are only relevant when we are doing calibration locally
        self.local_calibration_widget = QWidget()
        local_calibration_widget_layout = QGridLayout()
        local_calibration_widget_layout.addWidget(QLabel('config.yml Path'), 0, 0)
        self.config_yaml_path_input = QLineEdit('N/A')
        local_calibration_widget_layout.addWidget(self.config_yaml_path_input, 0, 1, 1, 3)
        select_config_yaml_file_button = QPushButton('Select config.yml File')
        select_config_yaml_file_button.clicked.connect(self.select_config_yaml_file)
        local_calibration_widget_layout.addWidget(select_config_yaml_file_button, 1, 0)
        self.calibrate_devices_box_msg_area = ScrollMessageArea()
        local_calibration_widget_layout.addWidget(self.calibrate_devices_box_msg_area, 2, 0, 1, 4)
        self.local_calibration_widget.setLayout(local_calibration_widget_layout)
        local_calibration_widget_layout.setContentsMargins(0, 0, 0, 0)
        calibrate_devices_box_layout.addWidget(self.local_calibration_widget, 4, 0, 1, 4)
        # end local calibration widget

        # remote calibration widget
        self.remote_calibration_widget = QWidget()
        remote_calibration_widget_layout = QGridLayout()
        remote_calibration_widget_layout.addWidget(QLabel('Upload Progress:'), 0, 0)
        self.upload_progressbar = QProgressBar()
        remote_calibration_widget_layout.addWidget(self.upload_progressbar, 1, 0)

        self.polling_status_label = QLabel()
        remote_calibration_widget_layout.addWidget(self.polling_status_label, 2, 0)

        self.remote_calibration_widget.setLayout(remote_calibration_widget_layout)
        calibrate_devices_box_layout.addWidget(self.remote_calibration_widget, 4, 0, 1, 4)
        # end remote calibration widget

        self.calibrate_devices_box.setLayout(calibrate_devices_box_layout)
        self.remote_sensor_calibration_state_changed()

    def remote_sensor_calibration_state_changed(self):
        if self.remote_sensor_calibration_cb.isChecked():
            self.local_calibration_widget.setVisible(False)
            self.remote_calibration_widget.setVisible(True)
        else:
            self.local_calibration_widget.setVisible(True)
            self.remote_calibration_widget.setVisible(False)

    def closeEvent(self, event: QCloseEvent):
        self.save_settings()
        event.accept()
        QMainWindow.closeEvent(self, event)

    def load_settings(self):
        settings = QSettings()

        # must first load the filter before loading the values for the combobox
        self.refresh_dropdown_files()

        prev_selected_siu = settings.value('selected_siu', '')
        if prev_selected_siu:
            self.siu_selector.setCurrentText(prev_selected_siu)

        prev_selected_device_part = settings.value('selected_device_part', '')
        if prev_selected_device_part:
            self.device_part_selector.setCurrentText(prev_selected_device_part)

        prev_waveform_gen = settings.value('waveform_gen', '')
        if prev_waveform_gen == 'keithley':
            self.use_agilent_rbutton.setChecked(False)
            self.use_keithley_rbutton.setChecked(True)
        elif prev_waveform_gen == 'agilent':
            self.use_keithley_rbutton.setChecked(False)
            self.use_agilent_rbutton.setChecked(True)

        prev_device_pallet_file = settings.value(self.DEVICE_PALLET_FILE_SETTING_KEY, '')
        if prev_device_pallet_file:
            self.device_pallet_file.setCurrentText(prev_device_pallet_file)

        prev_test_file = settings.value(self.TEST_FILE_SETTING_KEY, '')
        if prev_test_file:
            self.test_file.setCurrentText(prev_test_file)

        config_yml_path = settings.value('config_yml_path', '')
        if config_yml_path:
            self.config_yaml_path_input.setText(config_yml_path)

        geometry = settings.value("geometry", QByteArray())
        if not geometry.isEmpty():
            self.restoreGeometry(geometry)

        prev_custom_output_file = settings.value('custom_output_file', '')
        if prev_custom_output_file and self.development_mode:
            self.custom_file_name_box.output_filename_line_edit.setText(prev_custom_output_file)

    def save_settings(self):
        settings = QSettings()
        settings.setValue("geometry", self.saveGeometry())

    def select_calibration_data_file(self):
        fname = QFileDialog.getOpenFileName(self, 'Open file', self.output_directory, "HDF5 (*.hdf5)")
        if fname[0]:
            self.data_file_path_input.setText(fname[0])

    def select_config_yaml_file(self):
        fname = QFileDialog.getOpenFileName(self, 'Open file', self.output_directory, "config.yml (config.yml)")
        if fname[0]:
            self.config_yaml_path_input.setText(fname[0])

    def select_gain_file(self):
        fname = QFileDialog.getOpenFileName(self, 'Open file', self.output_directory, "HDF5 (*.hdf5)")
        if fname[0]:
            self.gain_file_path_input.setText(fname[0])

    def setup(self):
        self.reset()

        if self.part_num_cb.isChecked():
            self.init_box.setEnabled(False)
        else:
            self.init_box.setEnabled(True)

        selected_siu = ommo.Hardware.from_desc(self.siu_selector.currentText())
        selected_device_part = ommo.DevicePart.from_desc(self.device_part_selector.currentText())
        other_ports = []

        for portInfo in list_ports.comports(include_links=False):
            if portInfo.vid == ommo.VENDOR_ID and portInfo.pid == selected_siu.pid:
                self.matched_sius.append(ommo.DataUnit(portInfo))
            elif portInfo.vid != ommo.VENDOR_ID:
                other_ports.append(portInfo.name)

        self.is_setup = False
        if self.matched_sius:
            init_siu_box_layout = self.active_siu_box.layout()
            success = False
            # create a copy of sius so sius items can be removed in the loop
            for siu in self.matched_sius:
                success = siu.open_port()
                if not success:
                    alert_window('Setup Error', "Unable to open SIU {}".format(siu.port_info.name))
                    break
                if selected_device_part.onboard_sensor:
                    success = siu.set_onboard_sensor_enabled(self.disable_onboard_sensors_cb.isChecked())
                    if not success:
                        alert_window('Setup Error', "Could not enable/disable onboard sensor for SIU {}".format(siu.port_info.name))
                        break

                # turn off leds
                siu.set_all_port_leds_off()

                # Enable / Disable ports
                for port in range(selected_siu.num_ports):
                    if self.ports_enabled.currentText() == 'All' or int(self.ports_enabled.currentText()) == port:
                        siu.set_port_disabled(port, 0x00)
                    else:
                        siu.set_port_disabled(port, 0xFF)

                siu.set_mag_cal_mode(True)
                siu.request_data_descriptor(False)
                siu.set_mag_cal_mode(False)

                if not siu.descriptor:
                    success = False
                    alert_window('Setup Error', "Could not get data descriptor for SIU {}".format(siu.port_info.name))
                    break

                error_msg_list, filtered_device_list = siu.get_filtered_device_list(
                    selected_device_part.device_proto.device_part_num if self.part_num_cb.isChecked() else None,
                    int(self.ports_enabled.currentText()) if self.ports_enabled.currentText() != 'All' else None,
                    selected_device_part)

                if len(error_msg_list) > 0:
                    error_message = ""
                    for i, error in enumerate(error_msg_list):
                        if len(error_msg_list) > 1:
                            error_message += "Error " + str(i) + ": " + error
                        else:
                            error_message += error
                    alert_window('Device Error', error_message)

                active_siu_device_container = QWidget()
                active_siu_device_container_layout = QVBoxLayout(active_siu_device_container)

                siu_title_frame = QFrame()
                siu_title_frame.setFrameShape(QFrame.Box)
                siu_title_frame.setMaximumHeight(35)
                siu_title_frame_layout = QHBoxLayout()

                siu_title_frame_layout.addWidget(QLabel('Port Name: ' + siu.port_info.name), alignment=Qt.AlignCenter)
                siu_title_frame_layout.addWidget(QLabel('Connected Devices: ' + str(len(filtered_device_list))), alignment=Qt.AlignCenter)

                siu_title_frame.setLayout(siu_title_frame_layout)
                active_siu_device_container_layout.addWidget(siu_title_frame)

                for device in siu.device_list:
                    siu_frame = QFrame()
                    siu_frame.setFrameShape(QFrame.Box)
                    siu_frame.setMaximumHeight(35)
                    siu_frame_layout = QHBoxLayout()
                    # add port number
                    port_number = QLabel('Port: ' + str(device.port_num))
                    port_number.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                    siu_frame_layout.addWidget(port_number, alignment=Qt.AlignCenter)
                    # add uuid
                    uuid = QLabel('UUID: ' + str(device.device_info.uuid))
                    uuid.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                    siu_frame_layout.addWidget(uuid, alignment=Qt.AlignCenter)

                    siu_frame.setLayout(siu_frame_layout)
                    active_siu_device_container_layout.addWidget(siu_frame)
                    init_siu_box_layout.addWidget(active_siu_device_container, alignment=Qt.AlignTop)

            # close ports
            if self.matched_sius:
                for siu in self.matched_sius:
                    siu.close_port()
                self.is_setup = success

        if self.is_setup:
            # setup
            self.run_all_button.setEnabled(True)
            # init_box
            self.run_init_button.setEnabled(True)
            # collect_data_box
            # load saved port before adding ports as it'll overwrite current
            prev_wavegen_port = QSettings().value('wavegen_port', '')
            self.waveform_gen_port_selector.addItems(other_ports)
            self.waveform_gen_port_selector.setEnabled(True)
            if prev_wavegen_port:
                self.waveform_gen_port_selector.setCurrentText(prev_wavegen_port)

            self.run_collect_data_button.setEnabled(True)
            # upload_gain_box
            self.run_upload_gains_button.setEnabled(True)

            self.refresh_disable_ic_box()
        else:
            alert_window('Setup Error', 'No matching SIUs found for {} with pid=0x{:x}'.format(selected_siu.description,
                                                                                               selected_siu.pid))
            self.reset()

    def reset(self):
        self.is_setup = False
        self.dt_str = ''

        if self.matched_sius:
            for siu in self.matched_sius:
                if siu.is_open():
                    siu.close_port()
        self.matched_sius = []
        clear_layout(self.active_siu_box.layout())

        # setup
        self.run_all_button.setEnabled(False)
        # init_box
        self.run_init_button.setEnabled(False)
        # collect_data_box
        self.waveform_gen_port_selector.clear()
        self.waveform_gen_port_selector.setEnabled(False)
        self.run_collect_data_button.setEnabled(False)
        # upload_gain_box
        self.run_upload_gains_button.setEnabled(False)

    def run_all(self):
        # determine if we should use generated file paths
        if self.is_setup and self.collect_data_box_enabled_cb.isChecked():
            # use auto generated file from collected data
            now = datetime.now()
            self.dt_str = now.strftime("%Y%m%d_%H%M%S")
            # set data file and gain files automatically
            data_file = 'sensor_calib_' + self.dt_str + '.HDF5'
            data_file_path = os.path.join(self.output_directory, data_file)
            self.data_file_path_input.setText(data_file_path)

        if self.is_setup and self.calibrate_devices_box_enabled_cb.isChecked() and self.upload_gains_box_enabled_cb.isChecked():
            data_file_path = self.data_file_path_input.text()
            gain_file_path = os.path.join(os.path.splitext(data_file_path)[0], 'v0.15.7/sensor_calibration.hdf5')
            self.gain_file_path_input.setText(gain_file_path)

        if self.is_setup and self.init_box_enabled_cb.isChecked() and not self.part_num_cb.isChecked():
            self.run_device_info_uuid_initialization()
        if self.is_setup and self.collect_data_box_enabled_cb.isChecked():
            self.run_collect_data()
        if self.is_setup and self.calibrate_devices_box_enabled_cb.isChecked():
            self.run_calibrate_devices()
        if self.is_setup and self.upload_gains_box_enabled_cb.isChecked() and not self.remote_sensor_calibration_cb.isChecked():
            # if we are doing remote processing, wait for the result before calling run_upload_gains()
            self.run_upload_gains()

    def run_device_info_uuid_initialization(self):
        self.init_box_msg_area.reset()
        write_device_uuids = self.write_uuids_cb.isChecked()
        if self.development_mode:
            create_custom_uuids = self.create_custom_uuids_cb.isChecked()

        selected_device_part = ommo.DevicePart.from_desc(self.device_part_selector.currentText())
        success = False
        for siu in self.matched_sius:
            success = siu.open_port()
            if not success:
                alert_window('SIU Error', "Unable to open SIU {}".format(siu.port_info.name))
                break
            success = siu.set_mag_cal_mode(True)
            if not success:
                alert_window('SIU Error', "Could not enable mag cal mode for SIU {}".format(siu.port_info.name))
                break

            success, return_str, filtered_device_list = siu.verify_data_unit(
                selected_device_part.device_proto.device_part_num if self.part_num_cb.isChecked() else None,
                int(self.ports_enabled.currentText()) if self.ports_enabled.currentText() != 'All' else None,
                selected_device_part)
            if not success:
                alert_window('SIU Error', return_str)
                break

            self.init_box_msg_area.widget().layout().addWidget(QLabel('Processing SIU {}'.format(siu.port_info.name)))
            devices_processed = 0
            for device in filtered_device_list:
                port_id = device.port_num

                # read previous device info
                prev_device_info = siu.read_device_info(port_id, pb.DEVICE_INFO_FIELD_PERM)

                if self.development_mode and create_custom_uuids:
                    uuid_to_use = self.validate_custom_uuids()
                    if uuid_to_use is None:
                        self.logger.error("Invalid UUID", "Custom UUID could not be validated.")
                        return  # operation failed
                elif prev_device_info and prev_device_info.uuid != 0:
                    uuid_to_use = prev_device_info.uuid
                elif selected_device_part.device_proto.uuid != 0:
                    uuid_to_use = selected_device_part.device_proto.uuid
                elif write_device_uuids:
                    uuid_to_use = None
                else:
                    alert_window('Error UUID Missing!',
                                 "Failed to read a valid UUID on port {}. "
                                 "If this is a blank device, please check 'Write UUID'. \nread=\n{}"
                                 .format(port_id, prev_device_info))
                    siu.set_port_led_color(port_id, ommo.PortLed.DEVICE_FAIL)
                    siu.set_port_led_if_supported()
                    return

                # create proto to write
                device_proto = ommo.device_info_proto_create(selected_device_part.device_proto.device_part_num, uuid_to_use)

                # write device info
                success, device_info = siu.write_device_info(port_id, device_proto, pb.DEVICE_INFO_FIELD_PERM)

                # verify device info
                device_info_read = siu.read_device_info(port_id, pb.DEVICE_INFO_FIELD_PERM)
                print(device_info_read)
                if not success:
                    siu.set_port_led_color(port_id, ommo.PortLed.DEVICE_FAIL)
                    alert_dialog('SIU Error', "Failed to write Device Info on port {0}.\nwritten=\n{1} \nread=\n{2}"
                                 .format(port_id, device_info, device_info_read))
                    break
                # elif device_info_read is None or device_info != device_info_read:
                elif device_info_read is None:
                    siu.set_port_led_color(port_id, ommo.PortLed.DEVICE_FAIL)
                    alert_dialog('SIU Error', "Failed to read Device Info on port {0}.\nwritten=\n{1} \nread=\n{2}"
                                 .format(port_id, device_info, device_info_read))
                    break
                elif device_info_read and device_info != device_info_read:
                    siu.set_port_led_color(port_id, ommo.PortLed.DEVICE_FAIL)
                    alert_window('SIU Error', "Device Info on port {0} does not match. \nwritten=\n{1} \nread=\n{2}"
                                 .format(port_id, device_info, device_info_read))
                    break

                user_proto = pb.DeviceInfoUserProto()
                user_proto.user_device_type = 0xFF
                success = siu.write_device_info(port_id, user_proto, pb.DEVICE_INFO_FIELD_USER)
                user_proto_read = siu.read_device_info(port_id, pb.DEVICE_INFO_FIELD_USER)
                if not success:
                    siu.set_port_led_color(port_id, ommo.PortLed.DEVICE_FAIL)
                    alert_window('SIU Error', "Failed to write User Info on port {0}. \nwritten=\n{1} \nread=\n{2}"
                                 .format(port_id, user_proto, user_proto_read))
                    break
                elif user_proto_read is None:
                    siu.set_port_led_color(port_id, ommo.PortLed.DEVICE_FAIL)
                    alert_window('SIU Error', "Failed to read User Info on port {0}. \nwritten=\n{1} \nread=\n{2}"
                                 .format(port_id, user_proto, user_proto_read))
                    break
                elif user_proto_read and user_proto != user_proto_read:
                    siu.set_port_led_color(port_id, ommo.PortLed.DEVICE_FAIL)
                    alert_window('SIU Error', "User Info on port {0} does not match. \nwritten=\n{1} \nread=\n{2}"
                                 .format(port_id, user_proto, user_proto_read))
                    break
                devices_processed += 1

            siu.set_port_led_if_supported()
            # turn off mag cal mode
            success = siu.set_mag_cal_mode(False)
            if not success:
                alert_window('SIU Error', "Could not disable mag cal mode for SIU {}".format(siu.port_info.name))
                break
            siu.close_port()
            self.init_box_msg_area.widget().layout().addWidget(QLabel("Processing SIU {0} with {1} devices -- completed"
                                                                      .format(siu.port_info.name, devices_processed)))
            self.init_box_msg_area.widget().layout().addWidget(QLabel("[{0}]".format(datetime.now().strftime('%H:%M:%S'))))
        if not success:
            self.reset()

    def validate_custom_uuids(self):
        custom_uuid = self.custom_uuids_input.text()
        if custom_uuid is None or custom_uuid == '':
            alert_window('Custom uuid field is blank.',
                         'To use randomly generated UUIDs instead, uncheck the\n"Create Custom UUIDs" box.')
            return None
        elif len(custom_uuid) != UUID_LENGTH:  # check for 19 digits
            alert_window('Error', 'Custom UUID must be a 19 digit integer.')
            self.custom_uuids_input.setText('')
            return None
        for char in custom_uuid:  # might not be necessary with new input widget
            if not char.isnumeric():
                alert_window('Error', 'Non-integer characters found.\nPlease enter a 19-digit integer to proceed')
                self.custom_uuids_input.setText('')
                return None
        print(custom_uuid)
        logger.info("Writing custom UUID {0}".format(custom_uuid))
        return int(custom_uuid)

    def run_collect_data(self):
        if not self.test_group_combobox.is_test_group_id_valid():
            alert_window(self.tr('Test group ID invalid'),
                         self.tr('ERR-16001: Your test group id is invalid (or still being validated)'))
            logger.warning('ERR-16001: Your test group id is invalid (or still being validated)')
            return

        # close all port leds if applicable
        for siu in self.matched_sius:
            siu.open_port()

            # Turn off port leds
            siu.set_all_port_leds_off()

            # Disable IMU's
            for device in siu.device_list:
                flags = 0
                for index, ic in enumerate(device.device_info.ics):
                    if ic.ic_type in ommo.KnownIMUICTypeList:
                        flags |= (1 << index)
                siu.set_port_disabled(device.port_num, flags)

            siu.close_port()

        if not os.path.exists(self.cnctestapp_path):
            alert_window('Collect Data Error', 'CNCTestApp not found at {}'.format(self.cnctestapp_path))
            self.reset()
            return

        sen_pallet_file_path = os.path.join(self.cnctestapp_testfiles_path, self.device_pallet_file.currentText())
        if not os.path.exists(sen_pallet_file_path):
            alert_window('Collect Data Error', 'CNCTestApp pallet file not found at {}'.format(sen_pallet_file_path))
            self.reset()
            return

        test_file_path = os.path.join(self.cnctestapp_testfiles_path, self.test_file.currentText())
        if not os.path.exists(test_file_path):
            alert_window('Collect Data Error', 'CNCTestApp test file not found at {}'.format(test_file_path))
            self.reset()
            return

        current_adc_port = ''
        relay_board_port = ''
        digital_input_board_port = ''
        wavegen_port = self.waveform_gen_port_selector.currentText()
        wavegen_found = False
        for portInfo in list_ports.comports(include_links=False):
            if portInfo.vid == ommo.VENDOR_ID and \
               (portInfo.pid == ommo.Hardware.HW_10117.pid or portInfo.pid == ommo.Hardware.HW_11763.pid):
                siu = ommo.DataUnit(portInfo)
                success = siu.open_port()
                if not success:
                    alert_window('Setup Error', "Unable to open SIU {}".format(siu.port_info.name))
                    self.reset()
                    return

                # Get data descriptor and close port
                siu.request_data_descriptor()
                siu.close_port()
                if not siu.descriptor:
                    alert_window('Setup Error', "Could not get data descriptor for SIU {}".format(siu.port_info.name))
                    self.reset()
                    return

                if siu.device_list[0].device_info.ics[0].sensors[0].sensor_class == pb.SENSOR_CLASS_CURRENT:
                    current_adc_port = portInfo.name
            elif portInfo.vid == ommo.VENDOR_ID and portInfo.pid == ommo.Hardware.HW_12105.pid:
                relay_board_port = portInfo.name
            elif portInfo.vid == ommo.VENDOR_ID and portInfo.pid == ommo.Hardware.HW_12004.pid:
                digital_input_board_port = portInfo.name
            elif portInfo.name == wavegen_port:
                wavegen_found = True

        if not wavegen_found:
            alert_window('Collect Data Error', "Waveform generator not found at {}".format(wavegen_port))
            self.reset()
            return
        if not current_adc_port:
            alert_window('Collect Data Error', "No current ADC found.")
            self.reset()
            return
        if not relay_board_port:
            alert_window('Collect Data Error', "No relay board found")
            self.reset()
            return
        if not digital_input_board_port:
            alert_window('Collect Data Error', "No digital input board found")
            self.reset()
            return
        #  custom output file name for r&d
        if self.development_mode and self.custom_file_name_box.is_checked():
            output_file_name = self.custom_file_name_box.get_custom_output_file_name()
            if not output_file_name:
                alert_window('Collect Data Error', 'Unable to process output file name.')
                self.reset()
                return
        else:
            now = datetime.now()
            self.dt_str = now.strftime("%Y%m%d_%H%M%S")
            output_file_name = 'sensor_calib_' + self.dt_str + '.HDF5'
        output_file_path = os.path.join(self.output_directory, output_file_name)

        use_agilent = self.use_agilent_rbutton.isChecked()
        use_keithley = self.use_keithley_rbutton.isChecked()

        with CNCTestAppRunner(self.cnctestapp_path) as cnctestapp:
            if use_agilent and not cnctestapp.open_agilent_device(wavegen_port):
                alert_window('Collect Data Error', "Failed to open Agilent 33120A device {}".format(wavegen_port))
                self.reset()
                return
            if use_keithley and not cnctestapp.open_keithley_device(wavegen_port):
                alert_window('Collect Data Error', "Failed to open Keithley 6221 device {}".format(wavegen_port))
                self.reset()
                return
            if not cnctestapp.open_ommo_device(current_adc_port):
                alert_window('Collect Data Error', "Failed to open Current ADC board {}".format(current_adc_port))
                self.reset()
                return
            if not cnctestapp.open_ommo_device(relay_board_port):
                alert_window('Collect Data Error', "Failed to open relay board {}".format(relay_board_port))
                self.reset()
                return
            if not cnctestapp.open_ommo_device(digital_input_board_port):
                alert_window('Collect Data Error', "Failed to open digital input board {}".format(digital_input_board_port))
                self.reset()
                return
            for siu in self.matched_sius:
                if not cnctestapp.open_ommo_device(siu.port_info.name):
                    alert_window('Collect Data Error', "Failed to open siu {}".format(siu.port_info.name))
                    self.reset()
                    return

            # Wait for devices to start sending data
            time.sleep(6)

            if not cnctestapp.run_freq_amp_test(output_file_path,
                                                self.device_pallet_file.currentText(),
                                                self.test_file.currentText(),
                                                self.test_group_combobox.get_current_text()):
                alert_window('Collect Data Error', "Failed to collect freq/amp data")
                self.reset()

    def run_calibrate_devices(self):
        # recover port led status (was turned off)
        for siu in self.matched_sius:
            siu.open_port()
            siu.set_port_led_if_supported()
            siu.close_port()

        # First check whether we have found a file
        data_file_path = self.data_file_path_input.text()

        if not os.path.exists(data_file_path):
            alert_window('Calibrate Device Error', 'Data file not found at {}'.format(data_file_path))
            self.reset()
            return

        if self.remote_sensor_calibration_cb.isChecked():
            self.upload_file_to_s3(self.output_data_file_path,
                                   get_sensor_calibration_bucket(False), #Device calibration doesn't have sandbox support yet
                                   self.upload_percentage_callback,
                                   self.upload_result_callback)
        else:
            self.run_sensor_calibration_locally(data_file_path)

    def upload_result_callback(self, result_code: int, uploaded_filename: str):
        if result_code == 0:
            alert_window(self.tr('File Uploaded'), self.tr('File Successfully Uploaded to S3'), level=QMessageBox.Information)
            logger.info('File Successfully Uploaded to S3')
            self.poll_for_results(data_file_path=uploaded_filename,
                                  collection_name="sensor_calibration_runs",
                                  file_field_name="sensor_calibration_hdf5_file",
                                  extra_field_names=[],
                                  polling_progress_callback=self.polling_progress_callback,
                                  polling_result_callback=self.polling_result_callback)
        else:
            alert_window(self.tr('File Upload Failed'), self.tr('ERR-16001: Failed to upload file to S3'), level=QMessageBox.Critical)
            logger.critical(f'ERR-16001: Failed to upload file to S3 {self.data_file}')
            self.run_calibrate_devices_button.setEnabled(True)

    def upload_percentage_callback(self, percentage: int):
        self.upload_progressbar.setValue(percentage)

    def run_sensor_calibration_locally(self, data_file_path):
        config_yml_path = self.config_yaml_path_input.text()

        if not os.path.exists(config_yml_path):
            alert_window('Calibrate Device Error', 'config.yml not found at {}'.format(config_yml_path))
            self.reset()
            return

        out_dir, data_file = os.path.split(data_file_path)
        yml_dir, yml_file = os.path.split(config_yml_path)
        residual_tolerance = '1e-4'
        selected_device_part = ommo.DevicePart.from_desc(self.device_part_selector.currentText())

        # run calibration
        config_yml_command_options = '-v "' + yml_dir + '":/config -e OMMOALG_CONFIG_YAML=/config/config.yml'
        data_file_command_options = '-v "' + out_dir + '":/data -e DATA_FILE="/data/' + data_file + '"'
        calib_command = ''
        # calib_command = ' -e MAX_CURRENT_SENSOR_DELAY_US=50'
        # calib_command += ' -e MAG_RESIDUALS_ABS_TOL=8'
        # calib_command += ' -e MODEL_ANG_ABS_RANGE=0.22'
        # calib_command += ' -e FIELD_RESIDUALS_ABS_TOL=3.5'
        # calib_command += ' -e FIELD_RESIDUAL_REL_TOL=0.03'
        calib_command += ' -e COIL_NAME=coil4'
        # calib_command += ' -e MODEL_SENSITIVITY_RANGE=0.06'
        # calib_command += ' -e MODEL_SKEW_RANGE=0.06'
        # calib_command += ' -e CURRENT_RESIDUALS_ABS_TOL=' + residual_tolerance
        # calib_command += ' -e TRANSIENT_RESIDUALS=TRUE'
        calib_command += ' -e CALIBRATION_TYPE=' + selected_device_part.calibration_type.name
        # calib_command += ' --entrypoint /opt/ommoalg/calibrate_sensor.sh ommotech/analysis:latest'
        calib_command += 'ommotech/analysis:v0.15.7 python /opt/ommoalg/ommoalg/calibrate_sensor.py'
        final_command = 'docker run --rm ' + data_file_command_options + ' ' + config_yml_command_options + calib_command

        print(final_command)

        process = subprocess.Popen(shlex.split(final_command), stdout=subprocess.PIPE)
        for line in iter(process.stdout.readline, b''):
            logger.info(line)
        process.stdout.close()
        ret = process.wait()
        self.calibrate_devices_box_msg_area.widget().layout().addWidget(
            QLabel("Calibration command completed with ret={}".format(ret)))

    def run_upload_gains(self, test_run_id=None):
        gain_file_path = self.gain_file_path_input.text()

        if not os.path.exists(gain_file_path):
            alert_window('Upload Gain Error', 'Gain file not found at {}'.format(gain_file_path))
            self.reset()
            return

        with h5py.File(gain_file_path, mode='r') as gain_file_h5:
            failed_uuids = write_gains_file_to_sensors(matched_sius=self.matched_sius,
                                                       uuid_to_calibration_bytes=gain_file_h5,
                                                       selected_device_part=ommo.DevicePart.from_desc(self.device_part_selector.currentText()),
                                                       verify_device_part=self.part_num_cb.isChecked(),
                                                       ports_enabled_text=self.ports_enabled.currentText(),
                                                       messages_callback=lambda message: self.upload_gains_box_msg_area.widget().layout().addWidget(QLabel(message)))
            all_uuids = generate_set_of_uuids(gain_file_h5)
            succeeded_uuids = all_uuids - failed_uuids
            update_flashed_with_for_sensors([str(uuid) for uuid in succeeded_uuids],
                                            test_run_id=test_run_id,
                                            app_name="sensor_calib_gui",
                                            app_version=APPLICATION_VERSION)

    def polling_result_callback(self, calibration_runs: list):
        try:
            successful_runs = get_successful_runs(calibration_runs)
            if len(successful_runs) > 0:
                file = get_target_file_from_calibration_run(successful_runs[0], "sensor_calibration_hdf5_file")
                logger.info(f'flashing sensor with file {file}')

                self.gain_file_path_input.setText(file)
                self.run_upload_gains(successful_runs[0]['test_run']['id'])
            else:
                alert_window(self.tr("Polling timed out"), self.tr("ERR-16002: We did not find any constant file in the DB"))
                logger.error(f'ERR-16002: Cannot find gains file within the time limit')
            # self.stop_polling_button.setEnabled(False)
        except Exception as e:
            logger.critical(f'ERR-16003: Unexpected error while polling for result {str(e)}')

        self.run_calibrate_devices_button.setEnabled(True)

    def polling_progress_callback(self, response: Response):
        logger.debug(str(response))
        status_color = "transparent"
        datetime_str = datetime.now().strftime("%H:%M:%S")

        if response.status_code == 200:
            # update polling status label
            calib_run = get_first_result_from_response(response.json(), 'sensor_calibration_runs')
            if calib_run is None:
                status_text = self.tr('Calibration run does not exist on DB yet. Maybe image is starting')
            elif calib_run['status'] == "processing":
                status_text = self.tr('processing')
            elif calib_run['status'] == "failed":
                status_color = "red"
                status_text = self.tr('analysis failed')
            elif calib_run['status'] == "completed" or calib_run['status'] == 'draft':
                #if calib_run['success']:
                status_color = "green"
                status_text = self.tr('successfully completed')
                #else:
                #    status_color = "#FFFF00" # yellow
                #    status_text = self.tr('completed with warnings')
            else:
                status_text = str(response)
        else:
            status_color = "red"
            status_text = self.tr('polling failed')
        self.polling_status_label.setStyleSheet(f'background-color:{status_color}')
        self.polling_status_label.setText(f'{datetime_str}: {status_text}')


if __name__ == '__main__':
    import sys

    app_name = 'device_calibration'

    app = QApplication(sys.argv)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationName(app_name)
    app.setApplicationVersion(APPLICATION_VERSION)

    if check_and_install_update(current_version=APPLICATION_VERSION, collection_name='release_device_calibration',
                                app_name=app_name):
        exit(0)

    mainWindow = DeviceCalibrationApp(app_name)
    mainWindow.show()
    sys._excepthook = sys.excepthook

    def exception_hook(exctype, value, traceback):
        print(exctype, value, traceback)
        sys._excepthook(exctype, value, traceback)
        sys.exit(1)

    sys.excepthook = exception_hook

    sys.exit(app.exec_())

