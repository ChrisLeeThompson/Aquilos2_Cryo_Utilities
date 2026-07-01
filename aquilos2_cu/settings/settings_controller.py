"""User-preference controller, exposed to QML as ``appController.settings``.

The controller wraps ``QSettings`` and presents each preference as a
PySide ``Property`` with a notify signal. QML two-way bindings work because
each setter is a no-op when the incoming value matches the stored value —
this breaks the QML→Python→QML feedback loop that would otherwise occur
when a control echoes a value back to its source.

Every property is also persisted on assignment, so user edits survive a
restart without an explicit save step.
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Property, QObject, QSettings, Signal

from .. import defaults

logger = logging.getLogger(__name__)


# Settings-key namespace for this version of the app. The single source
# of truth is ``defaults.SCHEMA_PREFIX`` — bumping it there (e.g. to
# "v4/") partitions new keys from old ones across every module during a
# future breaking change without forcing a migration.
_PREFIX = defaults.SCHEMA_PREFIX
_K_ALWAYS_ON_TOP = _PREFIX + "alwaysOnTop"
_K_COMPACT_MODE = _PREFIX + "compactMode"
_K_GIS_GAS_PORT_NAME = _PREFIX + "gisGasPortName"
_K_MOVE_STAGE_TO_ORIGINAL = _PREFIX + "moveStageToOriginalPosition"
_K_ZERO_TILT_BEFORE_GIS_DEPOSITION = _PREFIX + "zeroTiltBeforeGisDeposition"
_K_SCAN_ROTATE_AFTER_ROTATION = _PREFIX + "scanRotateAfterRotation"
_K_ZERO_TILT_BEFORE_ROTATION = _PREFIX + "zeroTiltBeforeRotation"
_K_TILT_AFTER_ROTATION = _PREFIX + "tiltAfterRotation"
_K_TILT_AFTER_ROTATION_ANGLE_DEG = _PREFIX + "tiltAfterRotationAngleDeg"


class SettingsController(QObject):
    """User preferences, persisted via :class:`QSettings`."""

    # --- Notify signals ----------------------------------------------------

    alwaysOnTopChanged = Signal()
    compactModeChanged = Signal()
    gisGasPortNameChanged = Signal()
    moveStageToOriginalPositionChanged = Signal()
    zeroTiltBeforeGisDepositionChanged = Signal()
    scanRotateAfterRotationChanged = Signal()
    zeroTiltBeforeRotationChanged = Signal()
    tiltAfterRotationChanged = Signal()
    tiltAfterRotationAngleDegChanged = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        # QSettings picks up Organization/Application names set on
        # QCoreApplication by the entry point, so no path arguments needed.
        self._qs = QSettings()

        # Load current values into private fields. We avoid re-emitting
        # change signals during the initial load (no consumers are bound yet).
        self._always_on_top = self._read_bool(
            _K_ALWAYS_ON_TOP, defaults.ALWAYS_ON_TOP
        )
        self._compact_mode = self._read_bool(
            _K_COMPACT_MODE, defaults.COMPACT_MODE
        )
        self._gis_gas_port_name = self._read_str(
            _K_GIS_GAS_PORT_NAME, defaults.GIS_GAS_PORT_NAME
        )
        self._move_to_original = self._read_bool(
            _K_MOVE_STAGE_TO_ORIGINAL, defaults.MOVE_STAGE_TO_ORIGINAL_POSITION
        )
        self._zero_tilt_before_gis_deposition = self._read_bool(
            _K_ZERO_TILT_BEFORE_GIS_DEPOSITION,
            defaults.ZERO_TILT_BEFORE_GIS_DEPOSITION,
        )
        self._scan_rotate_after_rotation = self._read_bool(
            _K_SCAN_ROTATE_AFTER_ROTATION,
            defaults.SCAN_ROTATE_AFTER_ROTATION_DEFAULT,
        )
        self._zero_tilt_before_rotation = self._read_bool(
            _K_ZERO_TILT_BEFORE_ROTATION,
            defaults.ZERO_TILT_BEFORE_ROTATION_DEFAULT,
        )
        self._tilt_after_rotation = self._read_bool(
            _K_TILT_AFTER_ROTATION,
            defaults.TILT_AFTER_ROTATION_DEFAULT,
        )
        self._tilt_after_rotation_angle_deg = self._read_int_clamped(
            _K_TILT_AFTER_ROTATION_ANGLE_DEG,
            defaults.TILT_AFTER_ROTATION_ANGLE_DEG_DEFAULT,
            defaults.TILT_AFTER_ROTATION_ANGLE_DEG_MIN,
            defaults.TILT_AFTER_ROTATION_ANGLE_DEG_MAX,
        )

    # --- Always On Top -----------------------------------------------------

    @Property(bool, notify=alwaysOnTopChanged)
    def alwaysOnTop(self) -> bool:
        return self._always_on_top

    @alwaysOnTop.setter
    def alwaysOnTop(self, value: bool) -> None:
        value = bool(value)
        if value == self._always_on_top:
            return
        self._always_on_top = value
        self._qs.setValue(_K_ALWAYS_ON_TOP, value)
        self.alwaysOnTopChanged.emit()

    # --- Compact Mode ------------------------------------------------------

    @Property(bool, notify=compactModeChanged)
    def compactMode(self) -> bool:
        return self._compact_mode

    @compactMode.setter
    def compactMode(self, value: bool) -> None:
        value = bool(value)
        if value == self._compact_mode:
            return
        self._compact_mode = value
        self._qs.setValue(_K_COMPACT_MODE, value)
        self.compactModeChanged.emit()

    # --- GIS Gas Port Name -------------------------------------------------

    @Property(str, notify=gisGasPortNameChanged)
    def gisGasPortName(self) -> str:
        return self._gis_gas_port_name

    @gisGasPortName.setter
    def gisGasPortName(self, value: str) -> None:
        value = str(value)
        if value == self._gis_gas_port_name:
            return
        self._gis_gas_port_name = value
        self._qs.setValue(_K_GIS_GAS_PORT_NAME, value)
        self.gisGasPortNameChanged.emit()

    # --- Move stage to original position ----------------------------------

    @Property(bool, notify=moveStageToOriginalPositionChanged)
    def moveStageToOriginalPosition(self) -> bool:
        return self._move_to_original

    @moveStageToOriginalPosition.setter
    def moveStageToOriginalPosition(self, value: bool) -> None:
        value = bool(value)
        if value == self._move_to_original:
            return
        self._move_to_original = value
        self._qs.setValue(_K_MOVE_STAGE_TO_ORIGINAL, value)
        self.moveStageToOriginalPositionChanged.emit()

    # --- Zero tilt before GIS deposition -----------------------------------
    #
    # When True, each GIS Deposition activity tilts the stage to zero
    # degrees before moving to its deposition position (the XY/Z move
    # then happens from a flat orientation). Read into the workflow
    # settings snapshot at Start and passed to each GISDepositionService.

    @Property(bool, notify=zeroTiltBeforeGisDepositionChanged)
    def zeroTiltBeforeGisDeposition(self) -> bool:
        return self._zero_tilt_before_gis_deposition

    @zeroTiltBeforeGisDeposition.setter
    def zeroTiltBeforeGisDeposition(self, value: bool) -> None:
        value = bool(value)
        if value == self._zero_tilt_before_gis_deposition:
            return
        self._zero_tilt_before_gis_deposition = value
        self._qs.setValue(_K_ZERO_TILT_BEFORE_GIS_DEPOSITION, value)
        self.zeroTiltBeforeGisDepositionChanged.emit()

    # --- Scan Rotate After Rotation ---------------------------------------

    @Property(bool, notify=scanRotateAfterRotationChanged)
    def scanRotateAfterRotation(self) -> bool:
        return self._scan_rotate_after_rotation

    @scanRotateAfterRotation.setter
    def scanRotateAfterRotation(self, value: bool) -> None:
        value = bool(value)
        if value == self._scan_rotate_after_rotation:
            return
        self._scan_rotate_after_rotation = value
        self._qs.setValue(_K_SCAN_ROTATE_AFTER_ROTATION, value)
        self.scanRotateAfterRotationChanged.emit()

    # --- Zero Tilt Before Rotation ----------------------------------------

    @Property(bool, notify=zeroTiltBeforeRotationChanged)
    def zeroTiltBeforeRotation(self) -> bool:
        return self._zero_tilt_before_rotation

    @zeroTiltBeforeRotation.setter
    def zeroTiltBeforeRotation(self, value: bool) -> None:
        value = bool(value)
        if value == self._zero_tilt_before_rotation:
            return
        self._zero_tilt_before_rotation = value
        self._qs.setValue(_K_ZERO_TILT_BEFORE_ROTATION, value)
        self.zeroTiltBeforeRotationChanged.emit()

    # --- Tilt After Rotation ----------------------------------------------

    @Property(bool, notify=tiltAfterRotationChanged)
    def tiltAfterRotation(self) -> bool:
        return self._tilt_after_rotation

    @tiltAfterRotation.setter
    def tiltAfterRotation(self, value: bool) -> None:
        value = bool(value)
        if value == self._tilt_after_rotation:
            return
        self._tilt_after_rotation = value
        self._qs.setValue(_K_TILT_AFTER_ROTATION, value)
        self.tiltAfterRotationChanged.emit()

    # --- Tilt After Rotation Angle (degrees) ------------------------------

    @Property(int, notify=tiltAfterRotationAngleDegChanged)
    def tiltAfterRotationAngleDeg(self) -> int:
        return self._tilt_after_rotation_angle_deg

    @tiltAfterRotationAngleDeg.setter
    def tiltAfterRotationAngleDeg(self, value: int) -> None:
        value = self._clamp(
            int(value),
            defaults.TILT_AFTER_ROTATION_ANGLE_DEG_MIN,
            defaults.TILT_AFTER_ROTATION_ANGLE_DEG_MAX,
        )
        if value == self._tilt_after_rotation_angle_deg:
            return
        self._tilt_after_rotation_angle_deg = value
        self._qs.setValue(_K_TILT_AFTER_ROTATION_ANGLE_DEG, value)
        self.tiltAfterRotationAngleDegChanged.emit()

    # --- QSettings type-coercion helpers -----------------------------------
    #
    # QSettings on Windows (the common deployment target) stores everything
    # through the registry, which round-trips numbers and bools as strings.
    # These helpers normalize that back to Python types and apply the default
    # if a key is missing or unparseable.

    def _read_bool(self, key: str, default: bool) -> bool:
        raw = self._qs.value(key)
        if raw is None:
            return default
        if isinstance(raw, bool):
            return raw
        # A bool persisted as a plain int (0/1) — accept it. Must come
        # after the bool check: bool is a subclass of int, so testing int
        # first would swallow genuine bools and lose their identity.
        if isinstance(raw, int):
            return bool(raw)
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in ("true", "1", "yes", "on"):
                return True
            if lowered in ("false", "0", "no", "off"):
                return False
        logger.warning(
            "Could not parse bool from QSettings key %r (got %r); using default %r",
            key, raw, default,
        )
        return default

    def _read_str(self, key: str, default: str) -> str:
        raw = self._qs.value(key)
        if raw is None:
            return default
        return str(raw)

    def _read_int_clamped(
        self, key: str, default: int, lo: int, hi: int
    ) -> int:
        raw = self._qs.value(key)
        if raw is None:
            return default
        try:
            value = int(raw)
        except (TypeError, ValueError):
            logger.warning(
                "Could not parse int from QSettings key %r (got %r); using default %r",
                key, raw, default,
                exc_info=True,
            )
            return default
        return self._clamp(value, lo, hi)

    @staticmethod
    def _clamp(value: int, lo: int, hi: int) -> int:
        if value < lo:
            return lo
        if value > hi:
            return hi
        return value