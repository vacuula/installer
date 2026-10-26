"""The wizard's main window.

Owns the left and right panelsand handles start animation.
Business logic itself (detection, install dispatch) lives
in ``app.core`` -- here are signals connecting ui and core.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable

import usb.core  # type: ignore[reportMissingTypeStubs]
from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    QTimer,
)
from PySide6.QtGui import Qt
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QLabel,
    QMainWindow,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from vacuula_installer.constants import (
    APP_VERSION,
    BACK_BUTTON_MARGIN,
    INTRO_DELAY_MS,
    LEFT_PANEL_RATIO,
    LOGO_MOVE_DURATION_MS,
    LOGO_SIZE_CENTERED,
    LOGO_SIZE_DOCKED,
    NETWORK_POLLING_DELAY_MS,
    PANEL_FADE_DURATION_MS,
    SCREEN_FADE_IN_MS,
    SCREEN_FADE_OUT_MS,
    USB_POLLING_DELAY_MS,
    WINDOW_SIZE,
)
from vacuula_installer.core.firmware_detector import FirmwareDetector
from vacuula_installer.core.firmware_updater import FirmwareUpdater
from vacuula_installer.core.gen4_provisioner import Gen4Provisioner
from vacuula_installer.core.gen23_ap_poller import Gen23ApPoller
from vacuula_installer.core.gen23_prewifi_fix import Gen23WiFiFixer
from vacuula_installer.core.gen23_provisioner import Gen23Provisioner
from vacuula_installer.core.robot_detector import RobotDetector
from vacuula_installer.core.server_detector import ServerDetector
from vacuula_installer.core.session import SessionData
from vacuula_installer.i18n import Translator
from vacuula_installer.logger import download_logs
from vacuula_installer.screens.connect_robot import ConnectRobotScreen
from vacuula_installer.screens.disclaimer import DisclaimerScreen
from vacuula_installer.screens.error import ErrorScreen
from vacuula_installer.screens.find_server import FindServerScreen
from vacuula_installer.screens.finished import FinishedScreen
from vacuula_installer.screens.firmware import FirmwareUpdateScreen
from vacuula_installer.screens.gen4_provision import Gen4ProvisionScreen
from vacuula_installer.screens.gen23_provision import Gen23ProvisionScreen
from vacuula_installer.screens.welcome import WelcomeScreen
from vacuula_installer.screens.wifi import WifiScreen
from vacuula_installer.widgets.back_button import BackButton
from vacuula_installer.widgets.clickable_label import ClickableLabel
from vacuula_installer.widgets.logo import LogoWidget

logger = logging.getLogger(__name__)

def _clear_graphics_effect(widget: QWidget) -> None:
    # Pyside has annoying stub, this gets rid of errors shown by linter
    # QT documents None as proper way to clear effect: https://doc.qt.io/qt-6/qgraphicsitem.html#setGraphicsEffect
    widget.setGraphicsEffect(None)  # ty: ignore[invalid-argument-type]


class MainWindow(QMainWindow):
    def __init__(self, translator: Translator) -> None:
        super().__init__()
        self._translator = translator
        self._session = SessionData()

        # Keep references to in-flight animations: QPropertyAnimation
        # doesn't guarantee its C++ side survives being garbage
        # collected mid-animation otherwise.
        self._active_animations: list[QPropertyAnimation | QParallelAnimationGroup] = []

        self.setFixedSize(*WINDOW_SIZE)
        self._translator.languageChanged.connect(self._retranslate)

        central = QWidget(self)
        central.setObjectName("central")
        self.setCentralWidget(central)

        self._left_panel = QWidget(central)
        self._left_panel.setObjectName("leftPanel")
        self._left_panel.setGeometry(self._left_panel_rect())

        self._back_action: Callable[[], None] | None = None
        self._back_button = BackButton(self._left_panel)
        self._back_button.move(BACK_BUTTON_MARGIN, BACK_BUTTON_MARGIN)
        self._back_button.clicked.connect(self._go_back)

        self._right_panel = QWidget(central)
        self._right_panel.setObjectName("rightPanel")
        self._right_panel.setGeometry(self._right_panel_rect())
        self._right_panel_opacity = QGraphicsOpacityEffect(self._right_panel)
        self._right_panel_opacity.setOpacity(0.0)
        self._right_panel.setGraphicsEffect(self._right_panel_opacity)

        right_layout = QVBoxLayout(self._right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self._screen_stack = QStackedLayout()
        right_layout.addLayout(self._screen_stack)

        self._welcome_screen = WelcomeScreen(self._translator, self._right_panel)
        self._disclaimer_screen = DisclaimerScreen(self._translator, self._right_panel)
        self._connect_screen = ConnectRobotScreen(self._translator, self._right_panel)
        self._screen_stack.addWidget(self._welcome_screen)
        self._screen_stack.addWidget(self._connect_screen)
        self._screen_stack.addWidget(self._disclaimer_screen)

        self._error_screen = ErrorScreen(self._translator, self._right_panel)
        self._screen_stack.addWidget(self._error_screen)

        self._firmware_update_screen = FirmwareUpdateScreen(self._translator, self._right_panel)
        self._screen_stack.addWidget(self._firmware_update_screen)

        self._server_search_screen = FindServerScreen(
            self._translator, self._right_panel
        )
        self._screen_stack.addWidget(self._server_search_screen)

        self._connect_to_wifi_screen = WifiScreen(self._translator, self._right_panel)
        self._screen_stack.addWidget(self._connect_to_wifi_screen)

        self._provision_screen_gen23 = Gen23ProvisionScreen(self._translator, self._right_panel)
        self._screen_stack.addWidget(self._provision_screen_gen23)

        self._gen4_provision_screen = Gen4ProvisionScreen(self._translator, self._right_panel)
        self._screen_stack.addWidget(self._gen4_provision_screen)

        self._finished_screen = FinishedScreen(self._translator, self._right_panel)
        self._screen_stack.addWidget(self._finished_screen)

        # Logo starts centered on the whole window, on top of everything,
        # then animates into its resting spot in the left panel.
        self._logo = LogoWidget(central)
        self._logo.setGeometry(self._logo_centered_rect())
        self._logo.raise_()

        # Version label - TODO: expand later to include more status etc
        logo_rect = self._logo_docked_rect()
        self._version_label = QLabel(self._translator.tr("app.version", version=APP_VERSION), central)
        self._version_label.setObjectName("statusLabel")
        self._version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._version_label.setGeometry(0, logo_rect.y() + logo_rect.height() + 8, self._left_panel_rect().width(), 24)
        self._version_label.hide()

        self._download_logs = ClickableLabel(self._translator.tr("app.download_logs"), central)
        self._download_logs.clicked.connect(download_logs)
        self._download_logs.setObjectName("statusLabel")
        self._download_logs.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._download_logs.setGeometry(0, self._version_label.y() + self._version_label.height(), self._left_panel_rect().width(), 24)
        self._download_logs.hide()

        self._robot_detector = RobotDetector(self)
        self._server_detector = ServerDetector(self)
        self._firmware_detector = FirmwareDetector(self)
        self._firmware_updater = FirmwareUpdater(self)
        self._gen23_wifi_fixer = Gen23WiFiFixer(self)
        self._ap_poller = Gen23ApPoller(self)
        self._provisioner = Gen23Provisioner(self, self._session)
        self._gen4_provisioner: Gen4Provisioner | None = None

        self._connect_signals()
        self._retranslate()

        QTimer.singleShot(INTRO_DELAY_MS, self._play_intro_animation)

    # -- geometry helpers -----------------------------------------------------

    @staticmethod
    def _left_panel_rect() -> QRect:
        width, height = WINDOW_SIZE
        return QRect(0, 0, int(width * LEFT_PANEL_RATIO), height)

    @staticmethod
    def _right_panel_rect() -> QRect:
        width, height = WINDOW_SIZE
        left_width = int(width * LEFT_PANEL_RATIO)
        return QRect(left_width, 0, width - left_width, height)

    @staticmethod
    def _logo_centered_rect() -> QRect:
        width, height = WINDOW_SIZE
        size = LOGO_SIZE_CENTERED
        return QRect((width - size) // 2, (height - size) // 2, size, size)

    def _logo_docked_rect(self) -> QRect:
        left_rect = self._left_panel_rect()
        size = LOGO_SIZE_DOCKED
        x = left_rect.x() + (left_rect.width() - size) // 2
        y = left_rect.y() + (left_rect.height() - size) // 2
        return QRect(x, y, size, size)

    # -- intro animation -------------------------------------------------------

    def _play_intro_animation(self) -> None:
        animation = QPropertyAnimation(self._logo, b"geometry", self)
        animation.setDuration(LOGO_MOVE_DURATION_MS)
        animation.setStartValue(self._logo.geometry())
        animation.setEndValue(self._logo_docked_rect())
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        animation.finished.connect(self._reveal_right_panel)
        self._run(animation)

    def _reveal_right_panel(self) -> None:
        self._version_label.show()
        self._download_logs.show()
        animation = QPropertyAnimation(self._right_panel_opacity, b"opacity", self)
        animation.setDuration(PANEL_FADE_DURATION_MS)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        # A QGraphicsOpacityEffect left attached keeps compositing every
        # repaint so remove when finished
        animation.finished.connect(lambda: _clear_graphics_effect(self._right_panel))
        self._run(animation)

    # -- screen transitions -----------------------------------------------------

    def _crossfade_to(self, target: QWidget) -> None:
        """Fade the current right-panel screen out, then the target in."""
        current = self._screen_stack.currentWidget()
        if current is None or current is target:
            return

        fade_out_effect = QGraphicsOpacityEffect(current)
        current.setGraphicsEffect(fade_out_effect)
        fade_out = QPropertyAnimation(fade_out_effect, b"opacity", self)
        fade_out.setDuration(SCREEN_FADE_OUT_MS)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.finished.connect(lambda: self._switch_and_fade_in(current, target))
        self._run(fade_out)

    def _switch_and_fade_in(self, previous: QWidget, target: QWidget) -> None:
        _clear_graphics_effect(previous)

        self._screen_stack.setCurrentWidget(target)

        fade_in_effect = QGraphicsOpacityEffect(target)
        target.setGraphicsEffect(fade_in_effect)
        fade_in = QPropertyAnimation(fade_in_effect, b"opacity", self)
        fade_in.setDuration(SCREEN_FADE_IN_MS)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.finished.connect(lambda: _clear_graphics_effect(target))
        self._run(fade_in)

    def _run(self, animation: QPropertyAnimation) -> None:
        """Start an animation and keep it alive until it finishes."""
        self._active_animations.append(animation)
        animation.finished.connect(lambda: self._active_animations.remove(animation))
        animation.start()

    # -- back navigation ---------------------------------------------------------

    def _set_back_action(self, action: Callable[[], None] | None) -> None:
        """Set what clicking "back" does right now (or hide the button)."""
        # TODO: initial release we disable back button, will make it work later
        self._back_action = action
        self._back_button.setVisible(action is not None)

    def _go_back(self) -> None:
        if self._back_action is not None:
            self._back_action()

    # -- signal wiring & handlers ------------------------------------------------
    # TODO rename from handle_event to go_to_page, let signal be descriptor what event happened and function what is to happen

    def _connect_signals(self) -> None:
        # TODO: conditionally skip pages if session is already populated? Or recheck?
        self._welcome_screen.continueRequested.connect(
            self._select_dev_or_server_screen
        )
        self._disclaimer_screen.understandRequested.connect(self._goto_server_search_screen)

        self._server_detector.serverDetected.connect(self._on_server_detected)
        self._server_detector.manualCheckFailed.connect(self._on_manual_check_failed)
        self._server_detector.invalidServerVersion.connect(self._show_server_version_error)

        self._error_screen.restartRequested.connect(self._restart_wizard)

        self._robot_detector.gen23VersionText.connect(lambda text: setattr(self._session, "firmware_version", text))
        self._robot_detector.robotDetected.connect(self._start_firmware_detect)
        self._robot_detector.multipleRobotsDetected.connect(
            self._handle_multiple_robots
        )
        self._robot_detector.robotDisconnected.connect(
            self._handle_robot_disconnected
        )

        self._firmware_detector.firmwareDetected.connect(self._on_firmware)

        self._ap_poller.infoReceived.connect(self._on_robot_ap_reached)
        self._ap_poller.requestFailed.connect(
            lambda: self._connect_to_wifi_screen.set_prewifi_checking(False)
        )
        self._connect_to_wifi_screen.prewifiConnectedClicked.connect(self._on_prewifi_connected_clicked)


        self._ap_poller.networksReceived.connect(self._connect_to_wifi_screen.set_gen23_wifi_options)
        self._ap_poller.networksFailed.connect(self._connect_to_wifi_screen.set_gen23_wifi_failed)

        self._connect_to_wifi_screen.wifiAdded.connect(self._start_provisioning)
        self._provisioner.progressChanged.connect(self._provision_screen_gen23.set_step)
        self._provisioner.provisioningFailed.connect(self._on_provision_failed)
        self._provisioner.provisioningFinished.connect(lambda: setattr(self._session, "install_done", True))
        self._connect_to_wifi_screen.rescanRequested.connect(self._rescan_networks)

        self._gen23_wifi_fixer.fixFailed.connect(lambda msg: self._show_error(msg, detailed="error.generic.help"))

        self._firmware_update_screen.downloadRequested.connect(self._firmware_updater.download_firmware)
        self._firmware_update_screen.installRequested.connect(self._on_firmware_install_requested)

        self._firmware_updater.downloadProgress.connect(self._firmware_update_screen.set_download_progress)
        self._firmware_updater.downloadFinished.connect(self._firmware_update_screen.set_download_finished)
        self._firmware_updater.downloadFailed.connect(self._firmware_update_screen.set_download_failed)

        self._firmware_updater.installStepChanged.connect(self._firmware_update_screen.set_install_step)
        self._firmware_updater.installProgress.connect(self._firmware_update_screen.set_install_progress)
        self._firmware_updater.installFailed.connect(self._firmware_update_screen.set_install_failed)
        self._firmware_updater.installFinished.connect(self._on_firmware_install_finished)

        self._server_search_screen.manualConnectionTestRequested.connect(
            self._server_detector.check_manual
        )

        self._server_search_screen.enterIpManuallyRequested.connect(
            self._server_detector.stop
        )

    def _on_server_detected(self, ip: str, cert: str, port: int, gen3_port: int, gen4_port: int, manual: bool, timezone: str) -> None:
        self._session.server_ip_manual = manual
        if manual:
            self._server_search_screen.set_manual_ip_test_result(True)
        self._goto_connect_robot_screen(ip, cert, port, gen3_port, gen4_port, timezone)

    def _on_manual_check_failed(self, kind: str) -> None:
        self._server_search_screen.set_manual_ip_test_result(False, self._translator.tr(f"serversearch.manual.{kind}"))

    def _show_server_version_error(self) -> None:
        self._show_error("error.server.version", detailed=True)

    def _on_firmware_install_finished(self, key: str) -> None:
        self._firmware_update_screen.set_install_finished(key)

    def _on_firmware_install_requested(self, key: str) -> None:
        gen = key.split("-", 1)[0]
        if gen == "gen3":
            mac = self._gen23_wifi_fixer.gen23_get_mac_from_version(self._session.firmware_version)
            if mac is None:
                self._show_error("error.gen23.firmware", detailed="error.gen23.generic.detailed")
                return
            self._firmware_updater.start_gen3_update(self._session.robot_usb_device, key, mac)
        else:
            self._firmware_updater.start_gen4_update(self._session.robot_usb_device, key)

    def _show_error(self, message: str, *, detailed: bool | str = False, restart_btn: str | None = None) -> None:
        logger.error(f"Error: {message}, detailed: {detailed}, restart_btn: {restart_btn}")
        self._robot_detector.stop()
        self._server_detector.stop()
        self._ap_poller.stop()
        self._provisioner.stop()
        self._gen23_wifi_fixer.stop()
        self._firmware_detector.stop()
    
        self._firmware_update_screen.page = "" # TODO: hack to not make disconnect, might not be needed actually? dont know, look into after initial release

        self._error_screen.show_error(message, detailed=detailed, restart_btn=restart_btn)
        self._crossfade_to(self._error_screen)
        self._set_back_action(None)

    def _restart_wizard(self) -> None:
        self._session = SessionData()  # drop everything learned so far
        self._connect_screen.reset_searching()
        self._server_search_screen.reset_searching()
        self._gen23_wifi_fixer_screen = None  # if you keep any per-run objects like this
        self._crossfade_to(self._welcome_screen)
        self._set_back_action(None)

    def _rescan_networks(self) -> None:
        self._connect_to_wifi_screen.set_gen23_wifi_loading(True)
        self._ap_poller.fetch_networks()

    def _on_prewifi_connected_clicked(self) -> None:
        self._connect_to_wifi_screen.set_prewifi_checking(True)
        self._ap_poller.check_now()

    def _on_robot_ap_reached(self, info: dict) -> None:
        self._connect_to_wifi_screen.set_prewifi_checking(False)
        self._connect_to_wifi_screen.set_gen23_page()
        self._connect_to_wifi_screen.set_gen23_wifi_loading(True)
        self._ap_poller.fetch_networks()

    def _start_provisioning(self, ssid: str, password: str) -> None:
        self._session.wifi_ssid = ssid
        self._session.wifi_pass = password

        # TODO: clean up this to select generation
        match self.get_gen():
            case "gen4":
                self._start_gen4_provisioning()
            case "gen3":
                self._provision_screen_gen23.reset()
                self._crossfade_to(self._provision_screen_gen23)
                self._set_back_action(None)
                if not self._session.robot_usb_device:
                    self._handle_robot_disconnected()
                else:
                    mac = self._gen23_wifi_fixer.gen23_get_mac_from_version(self._session.firmware_version)
                    if mac is None:
                        self._show_error("error.gen23.firmware", detailed="error.gen23.generic.detailed")
                        return
                    self._provisioner.start(self._session.robot_usb_device, ssid, password, mac)
            case "gen2":
                self._show_error("error.gen2.unsupported", detailed=True)
            case _:
                self._show_error("error.generic.unexpected", detailed="error.generic.help")

    def _start_gen4_provisioning(self) -> None:
        self._gen4_provision_screen.reset()
        self._crossfade_to(self._gen4_provision_screen)
        self._set_back_action(None)

        self._gen4_provisioner = Gen4Provisioner(
            vacuula_server="vacuula.local",
            vacuula_server_ip=self._session.server_ip or "",
            vacuula_cert=self._session.server_certificate or "",
            wifi_ssid=self._session.wifi_ssid,
            wifi_psk=self._session.wifi_pass,
            gen4_port=self._session.gen4_port or 3443,
            vacuula_port=self._session.vacuula_port or 8050,
            manual_ip=self._session.server_ip_manual,
            parent=self,
        )
        self._gen4_provisioner.stepChanged.connect(self._gen4_provision_screen.set_step)
        self._gen4_provisioner.provisioningFailed.connect(lambda err: self._show_error(err, detailed="error.generic.help"))
        self._gen4_provisioner.provisioningFinished.connect(self._gen4_set_provision_finished)
        if not self._session.robot_usb_device:
            self._handle_robot_disconnected()
        else:
            self._gen4_provisioner.start(self._session.robot_usb_device)

    def _gen4_set_provision_finished(self) -> None:
        self._session.install_done = True
        self._gen4_provision_screen.set_finished()

    def _on_provision_failed(self, stage: str) -> None:
        logger.error(f"Provisioning failed at: {stage}, step: {self._provision_screen_gen23._step}")
        # self._provision_screen_gen23.set_failed()
        # TODO: clean this up
        if (self._provision_screen_gen23._step == 1):
            self._show_error("error.provision.gen23.wifi_password", detailed="error.generic.help")
        elif (self._provision_screen_gen23._step == 2):
            self._show_error("error.provision.gen23.no_internet", detailed="error.generic.help") # need ntp and 8.8.8.8 check
        else:
            self._show_error(f"error.provision.{stage}", detailed="error.generic.help")
        # self._set_back_action(self._back_to_wifi)

    def _goto_finished_screen(self) -> None:
        self._robot_detector.stop()
        if self._session.server_ip_manual:
            url = f"{self._session.server_ip}:{self._session.vacuula_port}"
        else:
            url = f"vacuula.local:{self._session.vacuula_port}"
        self._finished_screen.set_vacuula_url(url)
        self._crossfade_to(self._finished_screen)

    def _on_firmware(self, valid: bool, msg: str) -> None:
        if valid:
            self._goto_wifi_screen()
        elif msg == "error.firmware.invalid":
            self._crossfade_to(self._firmware_update_screen)
            self._firmware_update_screen.set_generation(self.get_gen())
        else:
            #TODO: check if link is clickable here (error.firmware.help)
            self._show_error(msg, detailed="error.firmware.help" if msg == "error.firmware.invalid" else "error.generic.help")

    def _select_dev_or_server_screen(self) -> None:
        if not getattr(sys, "frozen", False):
            self._goto_notice_screen()
            #self._crossfade_to(self._connect_to_wifi_screen)
            #self._connect_to_wifi_screen.set_gen23_page()
            
            # self._goto_dev_only_screen() # Temporary
            #self._crossfade_to(self._firmware_update_screen)
            #self._firmware_update_screen.set_generation('gen3')
            # self._show_error("firmware.gen3.factory_reset.disconnected", detailed=True, restart_btn="firmware.gen3.factory_reset.restart")
            # self._goto_connect_robot_screen('123', '123', 123, 123)  # Not implemented yet
            
            # self._goto_connect_robot_screen('', '')  # Not implemented yet
            # self._crossfade_to(self._connect_to_wifi_screen)
            # self._connect_to_wifi_screen.set_gen23_prewifi_page()
            # self._on_robot_ap_reached({})
        else:
            self._goto_notice_screen()

    def _goto_notice_screen(self) -> None:
        self._set_back_action(self._back_to_welcome)
        self._crossfade_to(self._disclaimer_screen)

    def _goto_dev_only_screen(self) -> None:
        # Shortcut place!
        pass

    def _goto_server_search_screen(self) -> None:
        self._crossfade_to(self._server_search_screen)
        self._server_detector.start(NETWORK_POLLING_DELAY_MS)
        self._set_back_action(self._back_to_welcome)

    def _goto_connect_robot_screen(self, ip: str, cert: str, vacuula_port: int, gen3_port: int, gen4_port: int, timezone: str) -> None:
        anim = self._server_search_screen.show_server_detected(ip)
        self._active_animations.append(anim)
        self._session.server_ip = ip
        self._session.server_certificate = cert
        self._session.vacuula_port = vacuula_port
        self._session.gen3_port = gen3_port
        self._session.gen4_port = gen4_port
        self._session.timezone = timezone
        # Dont @ me
        anim.finished.connect(
            lambda: QTimer.singleShot(
                2000,
                lambda: {
                    self._crossfade_to(self._connect_screen),
                    self._robot_detector.start(USB_POLLING_DELAY_MS),
                },
            )
        )
        anim.finished.connect(lambda: self._active_animations.remove(anim))
        anim.start()
        self._connect_screen.reset_searching()
        self._set_back_action(self._back_to_welcome)

    def _start_firmware_detect(self, display_name: str, device: usb.core.Device) -> None:
        self._session.robot_model_display_name = display_name
        self._session.robot_usb_device = device
        self._connect_screen.show_robot_detected(display_name)
        # self._robot_detector.stop()  # keep this running to detect disconnects!
        self._firmware_detector.detect(device, self._session.firmware_version) # TODO: clean this up, pass because of the gen23 variants

    def _handle_multiple_robots(self) -> None:
        self._show_error("error.multiple_robots", detailed=True)

    def _handle_robot_disconnected(self) -> None:
        if self._session.install_done:
            self._goto_finished_screen()
        elif self._firmware_update_screen.page == "factory_reset":
            self._show_error("firmware.gen3.factory_reset.disconnected", detailed=True, restart_btn="firmware.gen3.factory_reset.restart")
        elif self._firmware_update_screen.page == "done":
            self._show_error(f"firmware.install.done.disconnected.{self.get_gen()}", detailed=True, restart_btn="firmware.install.done.restart")
        else:
            self._show_error("error.robot_disconnected", detailed=True)

    def _goto_wifi_screen(self) -> None:
        match self.get_gen():
            case "gen4":
                self._crossfade_to(self._connect_to_wifi_screen)
            case "gen3":
                mac = self._gen23_wifi_fixer.gen23_get_mac_from_version(self._session.firmware_version)
                if mac is None:
                    self._show_error("error.gen23.firmware", detailed="error.gen23.generic.detailed")
                    return

                self._crossfade_to(self._connect_to_wifi_screen)
                self._connect_to_wifi_screen.set_gen23_prewifi_page(mac)
                if not self._session.robot_usb_device or not self._session.server_certificate:
                    self._show_error("error.generic.unexpected", detailed="error.generic.help")
                    return
                self._gen23_wifi_fixer.fix_robot(self._session.robot_usb_device, mac, self._session)
                self._ap_poller.start()
            case "gen2":
                self._show_error("error.gen2.unsupported", detailed=True)
            case _:
                # this could never happen normally
                self._show_error("error.generic.unexpected", detailed="error.generic.help")

    def get_gen(self) -> "gen2" | "gen3" | "gen4" | None:
        match self._session.robot_model_display_name:
            case "Neato D10" | "Neato D9" | "Neato D8" | "Neato D800":
                return "gen4"
            case (
                "Neato Botvac D7"
                | "Neato Botvac D6"
                | "Neato Botvac D5"
                | "Neato Botvac D4"
                | "Neato Botvac D3"
            ):
                return "gen3"
            case "Neato Botvac Connected":
                return "gen2"
            case _:
                return None

    def _goto_install_screen(self, ssid: str, password: str) -> None:
        self._session.wifi_ssid = ssid
        self._session.wifi_pass = password
        self._robot_detector.start(USB_POLLING_DELAY_MS)  # Temp placeholder
        self._crossfade_to(self._connect_screen)
        self._set_back_action(self._back_to_wifi)

    def _back_to_welcome(self) -> None:
        self._robot_detector.stop()
        self._server_detector.stop()
        self._server_search_screen.reset_searching()
        self._connect_screen.reset_searching()
        self._crossfade_to(self._welcome_screen)
        self._set_back_action(None)

    def _back_to_wifi(self) -> None:
        self._robot_detector.stop()  # Temp placeholder
        self._crossfade_to(self._connect_to_wifi_screen)
        self._set_back_action(self._back_to_welcome)
        self._connect_to_wifi_screen.wifi_revalidate_input()

    def _retranslate(self) -> None:
        self.setWindowTitle(self._translator.tr("app.window_title"))
        self._version_label.setText(self._translator.tr("app.version", version=APP_VERSION))
        self._download_logs.setText(self._translator.tr("app.download_logs"))
