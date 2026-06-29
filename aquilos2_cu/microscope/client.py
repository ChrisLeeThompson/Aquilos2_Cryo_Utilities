"""Real microscope client — wraps ``autoscript_sdb_microscope_client``."""
from __future__ import annotations

import logging
from typing import Any, Optional

from .electron_beam_ops import ElectronBeamOps
from .gis_ops import GISOps
from .ion_beam_ops import IonBeamOps
from .sputter_ops import SputterOps
from .stage_ops import StageOps
from .vacuum_ops import VacuumOps

logger = logging.getLogger(__name__)


class MicroscopeClient:
    """Wraps :class:`SdbMicroscopeClient` with a narrower, app-friendly interface.

    The underlying ``SdbMicroscopeClient`` is kept private (``_sdb``) because
    activity services and hardware-ops wrappers should go through narrow,
    intention-revealing methods — not reach into the raw SDB tree.

    Hardware-ops accessors (``gis``, ``stage``, ``electron_beam``, ``ion_beam``,
    ``sputter_coater``, ``vacuum``) are constructed lazily on first access. Each
    ops object holds a reference to ``_sdb``, so they're valid only while this
    client is connected. Calling an ops method after :meth:`disconnect` raises
    whatever AutoScript raises.

    ``autoscript_sdb_microscope_client`` is imported lazily in
    ``__init__`` so the package can still load in environments where
    AutoScript is not installed (simulation-only dev machines).
    """

    def __init__(self) -> None:
        # Lazy import — see class docstring.
        from autoscript_sdb_microscope_client import SdbMicroscopeClient

        self._sdb: Any = SdbMicroscopeClient()
        self._connected: bool = False
        self._host: str = ""

        # Hardware-ops cache. Populated on first access. Cleared on disconnect.
        self._gis: Optional[GISOps] = None
        self._stage: Optional[StageOps] = None
        self._electron_beam: Optional[ElectronBeamOps] = None
        self._ion_beam: Optional[IonBeamOps] = None
        self._sputter_coater: Optional[SputterOps] = None
        self._vacuum: Optional[VacuumOps] = None

    # --- State -------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def server_host(self) -> str:
        return self._host

    # --- Hardware-ops accessors -------------------------------------------

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("MicroscopeClient is not connected")

    @property
    def gis(self) -> GISOps:
        self._require_connected()
        if self._gis is None:
            self._gis = GISOps(self._sdb)
        return self._gis

    @property
    def stage(self) -> StageOps:
        self._require_connected()
        if self._stage is None:
            self._stage = StageOps(self._sdb)
        return self._stage

    @property
    def electron_beam(self) -> ElectronBeamOps:
        self._require_connected()
        if self._electron_beam is None:
            self._electron_beam = ElectronBeamOps(self._sdb)
        return self._electron_beam

    @property
    def ion_beam(self) -> IonBeamOps:
        self._require_connected()
        if self._ion_beam is None:
            self._ion_beam = IonBeamOps(self._sdb)
        return self._ion_beam

    @property
    def sputter_coater(self) -> SputterOps:
        self._require_connected()
        if self._sputter_coater is None:
            self._sputter_coater = SputterOps(self._sdb)
        return self._sputter_coater

    @property
    def vacuum(self) -> VacuumOps:
        self._require_connected()
        if self._vacuum is None:
            self._vacuum = VacuumOps(self._sdb)
        return self._vacuum

    # --- Lifecycle --------------------------------------------------------

    def connect(self) -> None:
        if self._connected:
            logger.warning("Already connected; ignoring connect() call")
            return
        self._sdb.connect()
        self._host = getattr(self._sdb, "server_host", "") or "<unknown>"
        self._connected = True
        logger.info("Connected to microscope at %s", self._host)

        # Use RAW (encoder) stage coordinates by default, not AutoScript's
        # default "Specimen" frame. Specimen Z is tied to the free working
        # distance (and its axis flips with link state), so saved stage
        # positions in that frame drift in Z; RAW always returns the stage
        # to the exact same physical position. Best-effort: a failure here
        # must not abort the connection (which would fall back to
        # simulation) — log it and proceed on the legacy behavior.
        try:
            from autoscript_sdb_microscope_client.enumerations import (
                CoordinateSystem,
            )

            self.stage.set_default_coordinate_system(CoordinateSystem.RAW)
        except Exception:
            logger.warning(
                "Could not set the stage default coordinate system to RAW; "
                "saved positions may drift in Z (legacy Specimen behavior). ",
                exc_info=True,
            )

    def disconnect(self) -> None:
        if not self._connected:
            return

        # Drop ops references first; they hold references to self._sdb
        # that would become stale post-disconnect.
        self._gis = None
        self._stage = None
        self._electron_beam = None
        self._ion_beam = None
        self._sputter_coater = None
        self._vacuum = None

        try:
            self._sdb.disconnect()
            logger.info("Disconnected from microscope")
        except Exception:
            logger.exception("Error during microscope disconnect (non-fatal)")
        finally:
            self._connected = False
            self._host = ""