"""Ion beam hardware ops.

Wraps AutoScript's ``microscope.beams.ion_beam`` with a narrow,
intention-revealing surface. Two implementations live side by side:

* :class:`IonBeamOps` — real, backed by ``SdbMicroscopeClient.beams.ion_beam``.
* :class:`SimulatedIonBeamOps` — in-memory simulation for offline UI development.

The Aquilos 2 ion source is a **gallium LMIS**. The exposed surface
covers generic ion-beam state (on/off, high voltage, beam current) plus
scan rotation. The active consumer today is the Stage / Scan page's
"Scan Rotate SEM and FIB 180°" operation, via :attr:`scan_rotation_rad`.

Note: unlike a plasma FIB, a gallium LMIS has no selectable plasma gas,
so no ``plasma_gas`` accessor is exposed here. The Aquilos 2 magnetron
Sputter Coat is driven by :mod:`aquilos2_cu.microscope.sputter_ops` and
the vacuum system — it does not touch the ion beam.
"""
from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


class IonBeamOps:
    """Real ion beam ops backed by ``SdbMicroscopeClient.beams.ion_beam``."""

    def __init__(self, sdb: Any) -> None:
        self._sdb = sdb

    @property
    def is_on(self) -> bool:
        return bool(self._sdb.beams.ion_beam.is_on)

    def turn_on(self) -> None:
        logger.info("Ion beam: turn_on")
        self._sdb.beams.ion_beam.turn_on()

    def turn_off(self) -> None:
        logger.info("Ion beam: turn_off")
        self._sdb.beams.ion_beam.turn_off()

    @property
    def high_voltage(self) -> float:
        return float(self._sdb.beams.ion_beam.high_voltage.value)

    @high_voltage.setter
    def high_voltage(self, value: float) -> None:
        logger.info("Ion beam: setting high voltage to %.0f V", value)
        self._sdb.beams.ion_beam.high_voltage.value = float(value)

    @property
    def beam_current(self) -> float:
        return float(self._sdb.beams.ion_beam.beam_current.value)

    @beam_current.setter
    def beam_current(self, value: float) -> None:
        logger.info("Ion beam: setting beam current to %.3e A", value)
        self._sdb.beams.ion_beam.beam_current.value = float(value)

    @property
    def scan_rotation_rad(self) -> float:
        """Current scan rotation, in radians.

        Used by the Stage / Scan page's "Scan Rotate SEM and FIB
        180°" operation, which canonically toggles between 0 and π.
        """
        return float(self._sdb.beams.ion_beam.scanning.rotation.value)

    @scan_rotation_rad.setter
    def scan_rotation_rad(self, value: float) -> None:
        logger.info("Ion beam: setting scan rotation to %.4f rad", value)
        self._sdb.beams.ion_beam.scanning.rotation.value = float(value)


# --- Simulated implementation -------------------------------------------


class SimulatedIonBeamOps:
    """Simulated ion beam ops for offline development.

    Tracks state in memory so subsequent reads reflect prior writes.
    """

    def __init__(self) -> None:
        self._is_on: bool = False
        # 30 kV — a plausible gallium LMIS accelerating voltage.
        self._high_voltage: float = 30000.0
        self._beam_current: float = 1.0e-9
        # Scan rotation starts at 0 rad — the canonical "untoggled"
        # state expected by the Stage / Scan page's flip operation.
        self._scan_rotation_rad: float = 0.0

    @property
    def is_on(self) -> bool:
        return self._is_on

    def turn_on(self) -> None:
        logger.info("Simulated ion beam: turn_on")
        self._is_on = True

    def turn_off(self) -> None:
        logger.info("Simulated ion beam: turn_off")
        self._is_on = False

    @property
    def high_voltage(self) -> float:
        return self._high_voltage

    @high_voltage.setter
    def high_voltage(self, value: float) -> None:
        logger.info("Simulated ion beam: setting high voltage to %.0f V", value)
        self._high_voltage = float(value)

    @property
    def beam_current(self) -> float:
        return self._beam_current

    @beam_current.setter
    def beam_current(self, value: float) -> None:
        logger.info("Simulated ion beam: setting beam current to %.3e A", value)
        self._beam_current = float(value)

    @property
    def scan_rotation_rad(self) -> float:
        return self._scan_rotation_rad

    @scan_rotation_rad.setter
    def scan_rotation_rad(self, value: float) -> None:
        value = float(value)
        # Mirror the real hardware's input domain. AutoScript's
        # scanning.rotation rejects writes outside [0, 2π) — observed
        # on hardware, where a write of exactly 2π raised "specified
        # value is out of range". Enforcing the same domain here makes
        # out-of-range writes fail in simulation instead of passing
        # silently.
        if not 0.0 <= value < math.tau:
            raise ValueError(
                f"Specified value is out of range: {value!r} rad "
                "(scan rotation accepts [0, 2*pi))"
            )
        logger.info(
            "Simulated ion beam: setting scan rotation to %.4f rad", value,
        )
        self._scan_rotation_rad = value


# Type alias for callers that accept either implementation.
IonBeamOpsLike = IonBeamOps | SimulatedIonBeamOps
