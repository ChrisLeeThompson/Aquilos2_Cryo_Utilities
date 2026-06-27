"""Sputter Coat activity service (Aquilos 2 magnetron plasma coater).

Hardware-side implementation of the Sputter Coat activity used in
Cryo Prep workflows. Drives the **magnetron plasma sputter coater** —
a self-contained device that does NOT use the ion beam. (The Aquilos 2
ion source is a gallium LMIS, which has no plasma-gas selection; the
Hydra Bio MicroSputter's ion-beam-driven sequence does not apply here.)
Mirrors the proven v2.5 Aquilos sequence.

Sequence
--------

1. Verify the sputter coater is installed (else fail early with
   :class:`ActivityResult.EXCEPTION`).
2. ``sputter_coater.prepare()`` — moves the stage to the sputter
   position, switches the chamber to sputter (argon) vacuum, and saves
   the prior state (uninterruptible; a short settle follows).
3. Pump the chamber to the target pressure and poll
   ``vacuum.chamber_pressure`` until it equilibrates within tolerance
   (interruptible per poll; capped poll budget).
4. Set the magnetron current (mA → A) and let it settle.
5. Lock the specimen stage axes (x, y, r, t) so the specimen can't
   drift during plasma ignition.
6. ``sputter_coater.run(duration)`` — strikes the plasma and sputters
   for the duration (uninterruptible; no grid argument on the
   Aquilos magnetron).
7. Unlock the axes, ``sputter_coater.recover()`` (restores the
   pre-prepare vacuum / state), then wait out the chamber recovery
   (interruptible per-second loop).

Reliability
-----------
The pump → equilibrate → set-current → lock → run block is retried
once on any failure, matching v2.5 (reset and try again before giving
up). A ``try``/``finally`` guarantees that, however the activity exits
(complete, stop, or exception), the stage axes are unlocked and the
coater is recovered — the specimen is never left with locked axes or
the magnetron prepared.

Cancellation
------------
Stop checks are issued before every uninterruptible call and on every
iteration of the pressure-poll and chamber-recovery loops. The two
operations that can't be interrupted mid-call are
``sputter_coater.prepare()`` and ``sputter_coater.run()``; the stop
event is checked immediately after each returns.

Progress reporting
------------------
The opaque phases (prepare, run) ride in indeterminate mode. The two
phases with a knowable total report determinate progress: the
pressure-equilibration poll (against its poll budget) and the chamber
recovery (its own ``time.sleep`` loop).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from .. import defaults
from ..microscope.sputter_ops import SputterOpsLike
from ..microscope.stage_ops import StageOpsLike
from ..microscope.vacuum_ops import VacuumOpsLike
from ..pre_start_checks import PreStartCheck
from ..pre_start_checks.checks import StagePositionWithinSafeRangeCheck
from .base import (
    ActivityResult,
    ActivityService,
    ProgressCallback,
    StatusCallback,
    report_activity_exception,
    report_indeterminate,
)

logger = logging.getLogger(__name__)


# Stage axes locked during plasma ignition to prevent specimen drift.
# Matches the v2.5 magnetron sequence.
_AXES_TO_LOCK = ("x", "y", "r", "t")

# Post-call settle times (seconds) after the opaque prepare() and the
# current write, matching v2.5's defensive 2 s delays.
_PREPARE_SETTLE_S = 2.0
_CURRENT_SETTLE_S = 2.0

# Number of times to attempt the pump → run block before giving up.
# v2.5 retries once (two total attempts) on a magnetron startup failure.
_SPUTTER_ATTEMPTS = 2


class SputterCoatService(ActivityService):
    """Magnetron plasma sputter-coat of the specimen on an Aquilos 2."""

    activity_id = "sputter_coat"

    def __init__(
        self,
        sputter_ops: SputterOpsLike,
        vacuum_ops: VacuumOpsLike,
        stage_ops: StageOpsLike,
        current_ma: int,
        pressure_pa: int,
        duration_s: int,
        chamber_recovery_s: int,
        instance_id: str,
    ) -> None:
        """Construct the activity.

        Parameters mirror the :class:`SputterCoatRecord` fields. The
        ``instance_id`` is forwarded so log messages can disambiguate
        multiple Sputter Coat instances in the same workflow.
        """
        super().__init__()
        self._sputter = sputter_ops
        self._vacuum = vacuum_ops
        self._stage = stage_ops

        self._current_ma = int(current_ma)
        self._pressure_pa = int(pressure_pa)
        self._duration_s = int(duration_s)
        self._chamber_recovery_s = int(chamber_recovery_s)
        # Override the class default with this instance's id. Read by
        # the workflow runner for per-instance status routing.
        self.instance_id = str(instance_id)

    def run(
        self,
        stop_event: threading.Event,
        on_progress: ProgressCallback,
        on_status: StatusCallback,
    ) -> ActivityResult:
        log_prefix = f"Sputter Coat [{self.instance_id}]"
        status_prefix = "Sputter coat"

        logger.info(
            "%s: starting (current=%d mA, pressure=%d Pa, duration=%ds, "
            "recovery=%ds)",
            log_prefix, self._current_ma, self._pressure_pa,
            self._duration_s, self._chamber_recovery_s,
        )

        if not self._sputter.is_installed:
            logger.error("%s: sputter coater not installed", log_prefix)
            on_status("Sputter coat: sputter coater not installed")
            return ActivityResult.EXCEPTION

        return self._run_inner(
            stop_event, on_progress, on_status, log_prefix, status_prefix,
        )

    def _run_inner(
        self,
        stop_event: threading.Event,
        on_progress: ProgressCallback,
        on_status: StatusCallback,
        log_prefix: str,
        status_prefix: str,
    ) -> ActivityResult:
        # The whole hardware sequence is opaque from our side until the
        # pressure poll, so start the bar in indeterminate mode.
        report_indeterminate(on_progress)

        # --- Prepare (uninterruptible; stop-checked around it) ---
        if stop_event.is_set():
            return ActivityResult.STOP
        on_status("Preparing sputter coater...")
        try:
            self._sputter.prepare()
        except Exception as exc:
            report_activity_exception(
                on_status, log_prefix, status_prefix, "prepare", exc,
            )
            return ActivityResult.EXCEPTION

        # prepare() succeeded — recover() must now run on every exit
        # path, and any locked axes must be unlocked. The try/finally
        # below guarantees both.
        axes_locked = False
        recovered = False
        try:
            if self._sleep_interruptible(stop_event, _PREPARE_SETTLE_S):
                return ActivityResult.STOP

            # --- Pump → equilibrate → set current → lock → run ---
            # Retried once on any failure (v2.5 behavior).
            last_exc: Optional[BaseException] = None
            for attempt in range(1, _SPUTTER_ATTEMPTS + 1):
                if stop_event.is_set():
                    return ActivityResult.STOP
                try:
                    on_status(
                        f"Pumping chamber to {self._pressure_pa} Pa..."
                    )
                    self._vacuum.pump_pressure(self._pressure_pa)

                    if self._wait_for_pressure(
                        stop_event, on_progress, on_status, log_prefix,
                    ) == ActivityResult.STOP:
                        return ActivityResult.STOP

                    on_status(
                        f"Setting sputter current to {self._current_ma} mA..."
                    )
                    self._sputter.current = self._current_ma * 1e-3
                    if self._sleep_interruptible(stop_event, _CURRENT_SETTLE_S):
                        return ActivityResult.STOP

                    on_status("Locking stage axes...")
                    self._lock_axes()
                    axes_locked = True

                    report_indeterminate(on_progress)
                    on_status(
                        f"Sputtering for {self._duration_s} second"
                        f"{'' if self._duration_s == 1 else 's'}..."
                    )
                    self._sputter.run(self._duration_s)
                    last_exc = None
                    break  # success
                except Exception as exc:
                    last_exc = exc
                    logger.warning(
                        "%s: sputter attempt %d/%d failed: %s",
                        log_prefix, attempt, _SPUTTER_ATTEMPTS, exc,
                    )
                    # Unlock before retrying so the re-pump starts from a
                    # clean state; the loop re-locks before the next run.
                    if axes_locked:
                        self._safe_unlock_axes(log_prefix)
                        axes_locked = False
                    if attempt < _SPUTTER_ATTEMPTS:
                        on_status(
                            "Sputter coat: attempt failed, retrying..."
                        )

            if last_exc is not None:
                report_activity_exception(
                    on_status, log_prefix, status_prefix,
                    "sputter run", last_exc,
                )
                return ActivityResult.EXCEPTION

            # Stop requested during the (uninterruptible) run — skip
            # recovery countdown but still unlock/recover in the finally.
            if stop_event.is_set():
                logger.info(
                    "%s: cancelled after sputter run; skipping recovery",
                    log_prefix,
                )
                return ActivityResult.STOP

            # Success path: unlock axes and recover BEFORE the chamber-
            # recovery countdown, matching the v2.5 order. The finally is
            # the backstop for the stop/exception paths above.
            self._safe_unlock_axes(log_prefix)
            axes_locked = False
            on_status("Recovering sputter coater...")
            self._safe_recover(log_prefix)
            recovered = True

            # --- Chamber recovery (determinate per-second loop) ---
            if self._chamber_recovery_s > 0:
                on_status(
                    f"Chamber recovery for {self._chamber_recovery_s} second"
                    f"{'' if self._chamber_recovery_s == 1 else 's'}..."
                )
                on_progress(0, self._chamber_recovery_s)
                for i in range(1, self._chamber_recovery_s + 1):
                    if stop_event.is_set():
                        logger.info(
                            "%s: cancelled during recovery", log_prefix,
                        )
                        return ActivityResult.STOP
                    time.sleep(1)
                    on_progress(i, self._chamber_recovery_s)

            on_status("Sputter coat complete")
            logger.info("%s: complete", log_prefix)
            return ActivityResult.COMPLETE
        finally:
            # Backstop cleanup for the stop / exception exit paths. On
            # the success path these are no-ops (axes already unlocked,
            # recover already called).
            if axes_locked:
                self._safe_unlock_axes(log_prefix)
            if not recovered:
                self._safe_recover(log_prefix)

    # --- Pressure equilibration ------------------------------------------

    def _wait_for_pressure(
        self,
        stop_event: threading.Event,
        on_progress: ProgressCallback,
        on_status: StatusCallback,
        log_prefix: str,
    ) -> ActivityResult:
        """Poll chamber pressure until it settles to the target (or cap).

        Returns :attr:`ActivityResult.STOP` if the user stops mid-poll,
        :attr:`ActivityResult.COMPLETE` on equilibration. Raises if the
        poll budget is exhausted without equilibrating, or if reading the
        pressure fails — both are caught by the caller's retry logic.
        """
        target = self._pressure_pa
        tol = defaults.SPUTTER_PRESSURE_TOLERANCE_PA
        max_polls = defaults.SPUTTER_PRESSURE_MAX_POLLS
        interval = defaults.SPUTTER_PRESSURE_POLL_INTERVAL_S

        on_progress(0, max_polls)
        for poll in range(1, max_polls + 1):
            if stop_event.is_set():
                return ActivityResult.STOP
            pressure = self._vacuum.chamber_pressure
            on_status(
                f"Equilibrating: {pressure:.1f} Pa (target {target} Pa)..."
            )
            on_progress(poll, max_polls)
            if round(pressure, 2) <= target + tol:
                logger.info(
                    "%s: chamber equilibrated at %.2f Pa after %d poll(s)",
                    log_prefix, pressure, poll,
                )
                return ActivityResult.COMPLETE
            time.sleep(interval)

        raise TimeoutError(
            f"chamber pressure did not reach {target}+{tol} Pa within "
            f"{max_polls} polls"
        )

    # --- Stage axis lock / recover helpers -------------------------------

    def _lock_axes(self) -> None:
        for axis in _AXES_TO_LOCK:
            self._stage.lock_axis(axis)

    def _safe_unlock_axes(self, log_prefix: str) -> None:
        """Best-effort unlock of all locked axes; never raises.

        Tolerates a missing ``safety_settings`` (AttributeError) or any
        per-axis failure so cleanup can't mask the primary outcome.
        """
        for axis in _AXES_TO_LOCK:
            try:
                self._stage.unlock_axis(axis)
            except Exception:
                logger.exception(
                    "%s: error unlocking axis %r during cleanup (non-fatal)",
                    log_prefix, axis,
                )

    def _safe_recover(self, log_prefix: str) -> None:
        """Best-effort sputter-coater recover; never raises."""
        try:
            self._sputter.recover()
        except Exception:
            logger.exception(
                "%s: error during sputter recover cleanup (non-fatal)",
                log_prefix,
            )

    @staticmethod
    def _sleep_interruptible(
        stop_event: threading.Event, seconds: float,
    ) -> bool:
        """Sleep up to ``seconds``, checking the stop event each second.

        Returns True if the stop event is set (so the caller can return
        :attr:`ActivityResult.STOP`), False otherwise.
        """
        whole = int(seconds)
        for _ in range(whole):
            if stop_event.is_set():
                return True
            time.sleep(1)
        frac = seconds - whole
        if frac > 0:
            if stop_event.is_set():
                return True
            time.sleep(frac)
        return stop_event.is_set()

    @classmethod
    def pre_start_checks(cls) -> List[PreStartCheck]:
        """Sputter Coat verifies the stage is in a safe position
        before any of the activity's hardware steps.

        Advisory (ASK_CONFIRM on failure) — the operationally
        meaningful starting position is surfaced before the workflow's
        adjacent activities (GIS Deposition, Home Stage) move the stage.
        """
        return [StagePositionWithinSafeRangeCheck()]

    def parameter_summary(self) -> Dict[str, Any]:
        """Provenance summary — raw SI-ish values as configured.

        Current is recorded in milliamperes and pressure in pascals (the
        units the user sets and the record stores); the log delegate
        formats them for display.
        """
        return {
            "current_ma": self._current_ma,
            "pressure_pa": self._pressure_pa,
            "duration_s": self._duration_s,
            "chamber_recovery_s": self._chamber_recovery_s,
        }
