"""Microscope-domain bounds, exposed to QML.

This module is the QML-facing surface for hardware-domain values that
live in :mod:`aquilos2_cu.defaults`. The pattern is read-only:

* **Source of truth** is Python (``defaults.py``).
* **QML reads** these values through this controller, registered as
  the ``MicroscopeBounds`` QML singleton in module
  ``Aquilos2.Microscope`` 1.0 (via ``qmlRegisterSingletonInstance``
  in the entry point).

Everything here is a ``@Property(..., constant=True)`` — the values
never change at runtime, so QML caches them after the first read and
no notify signal is needed. Currently this exposes the Stage / Scan
page's tilt-after-rotation numeric bounds
(``tiltAfterRotationMin/Max/Default``); the same bounds are also
consumed Python-side by ``SettingsController`` for clamping, so both
consumers resolve through the same constant.

The magnetron Sputter Coat parameter bounds (current / pressure /
duration) are exposed separately by :class:`CryoActivitiesController`
— they're cryo-activity scoped rather than microscope-domain values.

Unlike :class:`MicroscopeClient`, this controller has no microscope
client dependency and is constructed eagerly at engine startup,
before any connection attempt. It is safe to read from QML the
moment the engine loads.

There is no simulated counterpart. The values are static constants
identical for both real and simulated paths; one controller serves
both modes.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Property, QObject

from .. import defaults


class MicroscopeBoundsController(QObject):
    """Read-only QObject exposing hardware-domain bounds.

    Registered as the ``MicroscopeBounds`` QML singleton in module
    ``Aquilos2.Microscope`` 1.0 (via ``qmlRegisterSingletonInstance``
    in the application entry point). QML reads each Property at binding-
    evaluation time; ``constant=True`` tells the engine the value
    never changes and binding evaluation can be cached.
    """

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

    # --- Stage / Scan page bounds -----------------------------------------

    @Property(int, constant=True)
    def tiltAfterRotationMin(self) -> int:
        """Lower bound (degrees) for the tilt-after-rotation SpinBox.

        The same value clamps the persisted
        ``tiltAfterRotationAngleDeg`` setting in
        :class:`SettingsController` — both consumers resolve through
        :data:`defaults.TILT_AFTER_ROTATION_ANGLE_DEG_MIN`.
        """
        return defaults.TILT_AFTER_ROTATION_ANGLE_DEG_MIN

    @Property(int, constant=True)
    def tiltAfterRotationMax(self) -> int:
        """Upper bound (degrees) for the tilt-after-rotation SpinBox."""
        return defaults.TILT_AFTER_ROTATION_ANGLE_DEG_MAX

    @Property(int, constant=True)
    def tiltAfterRotationDefault(self) -> int:
        """Default value (degrees) for the tilt-after-rotation SpinBox."""
        return defaults.TILT_AFTER_ROTATION_ANGLE_DEG_DEFAULT