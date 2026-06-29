"""Argon Purge activity (Aquilos 2, RT prep).

Cycles the chamber vacuum through argon pressure steps to purge the
argon lines and reduce ice contamination before cryo work. Mirrors the
proven v2.5 Aquilos sequence:

    1. Initial wait.
    2. For each of N cycles: pump to the high setpoint (30 Pa) and hold
       a monitoring window, then pump to the mid setpoint (15 Pa) and
       wait until the pressure settles into tolerance.
    3. Pump to the low setpoint (10 Pa) and hold a monitoring window.
    4. Return the chamber to high vacuum.
    5. Chamber recovery (optional).

The pressure setpoints and poll windows are fixed in
:mod:`aquilos2_cu.defaults` — they define the procedure. Only the cycle
count and chamber-recovery time are user-controlled.

Stop semantics
--------------
Interruptible at every poll boundary (and during the initial wait and
chamber-recovery loops). On stop or exception, a ``finally`` returns
the chamber to high vacuum so it is never left in a low-vacuum argon
state.

Progress reporting
------------------
Each monitoring / equilibration phase reports determinate progress
against its poll budget; the chamber recovery uses its own per-second
loop. The opaque return-to-high-vacuum step rides in indeterminate mode.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from .. import defaults
from ..microscope.vacuum_ops import VacuumOpsLike
from ..pre_start_checks import PreStartCheck
from .base import (
    ActivityResult,
    ActivityService,
    ProgressCallback,
    StatusCallback,
    report_activity_exception,
    report_indeterminate,
)

logger = logging.getLogger(__name__)

# Optional telemetry sink for live charting: called once per pressure
# poll with (elapsed_seconds_since_run_start, chamber_pressure_pa). The
# RT workflow wires this to a Qt signal that a QML chart subscribes to;
# it is None in headless / test contexts.
SampleCallback = Callable[[float, float], None]

# VacuumState value (str) reported by the chamber once it has settled at
# the commanded vacuum. Matches both the real ``VacuumState.PUMPED`` enum
# (stringified) and ``SimulatedVacuumOps.chamber_state``.
_CHAMBER_STATE_PUMPED = "Pumped"


class ArgonPurgeService(ActivityService):
    """Argon-purge the chamber through a cycled pressure sequence."""

    activity_id = "argon_purge"

    def __init__(
        self,
        vacuum_ops: VacuumOpsLike,
        cycles: int,
        chamber_recovery_s: int,
        on_sample: Optional[SampleCallback] = None,
    ) -> None:
        super().__init__()
        self._vacuum = vacuum_ops
        self._cycles = int(cycles)
        self._chamber_recovery_s = int(chamber_recovery_s)
        # Optional (elapsed_s, pressure_pa) sink for live charting. None
        # in headless / test contexts; the run loop guards every call.
        self._on_sample = on_sample
        # Set at run() entry; the x-axis origin for emitted samples.
        self._t0 = 0.0
        # One-way latch: chart samples are suppressed until the chamber has
        # reached low (sputter) vacuum (see _emit_sample). Reset per run.
        self._chart_gate_open = False

    def run(
        self,
        stop_event: threading.Event,
        on_progress: ProgressCallback,
        on_status: StatusCallback,
    ) -> ActivityResult:
        log_prefix = "Argon Purge"
        status_prefix = "Argon purge"
        logger.info(
            "%s: starting (cycles=%d, recovery=%ds)",
            log_prefix, self._cycles, self._chamber_recovery_s,
        )
        # x-axis origin for chart samples — elapsed seconds are measured
        # from here. monotonic() (not time()) so a clock change mid-run
        # can't perturb the timeline, matching the runner's duration
        # measurement.
        self._t0 = time.monotonic()
        # Re-arm the chart gate for this run: suppress samples until the
        # chamber first reaches low (sputter) vacuum.
        self._chart_gate_open = False

        high_pa = defaults.ARGON_PURGE_HIGH_PRESSURE_PA
        mid_pa = defaults.ARGON_PURGE_MID_PRESSURE_PA
        low_pa = defaults.ARGON_PURGE_LOW_PRESSURE_PA

        # Tracks whether we've put the chamber into a low-vacuum (argon)
        # state that the cleanup must undo. Cleared once we return it to
        # high vacuum ourselves on the success path.
        chamber_disturbed = False
        try:
            report_indeterminate(on_progress)

            # --- Initial wait ---
            on_status("Argon purge: initial wait...")
            if self._sleep_interruptible(
                stop_event, defaults.ARGON_PURGE_INITIAL_WAIT_S,
            ):
                return ActivityResult.STOP

            # --- Cycles ---
            for cycle in range(1, self._cycles + 1):
                on_status(
                    f"Argon purge: cycle {cycle} of {self._cycles} — "
                    f"pumping to {int(high_pa)} Pa..."
                )
                self._vacuum.pump_sputter_vacuum(high_pa)
                chamber_disturbed = True
                if self._monitor_window(
                    stop_event, on_progress, on_status,
                    defaults.ARGON_PURGE_HIGH_PRESSURE_POLLS,
                    f"cycle {cycle} of {self._cycles}",
                ) == ActivityResult.STOP:
                    return ActivityResult.STOP

                on_status(
                    f"Argon purge: cycle {cycle} of {self._cycles} — "
                    f"pumping to {int(mid_pa)} Pa..."
                )
                self._vacuum.pump_sputter_vacuum(mid_pa)
                if self._wait_for_band(
                    stop_event, on_progress, on_status, log_prefix,
                ) == ActivityResult.STOP:
                    return ActivityResult.STOP

            # --- Final low-pressure monitoring window ---
            on_status(f"Argon purge: pumping to {int(low_pa)} Pa...")
            self._vacuum.pump_sputter_vacuum(low_pa)
            chamber_disturbed = True
            if self._monitor_window(
                stop_event, on_progress, on_status,
                defaults.ARGON_PURGE_LOW_PRESSURE_POLLS,
                "final pump-down",
            ) == ActivityResult.STOP:
                return ActivityResult.STOP

            # --- Return to high vacuum ---
            report_indeterminate(on_progress)
            on_status("Argon purge: returning to high vacuum...")
            self._vacuum.pump_high_vacuum()
            # We returned the chamber ourselves; the finally cleanup is
            # now a no-op.
            chamber_disturbed = False

            # --- Chamber recovery ---
            if self._chamber_recovery_s > 0:
                on_status(
                    f"Chamber recovery for {self._chamber_recovery_s} second"
                    f"{'' if self._chamber_recovery_s == 1 else 's'}..."
                )
                on_progress(0, self._chamber_recovery_s)
                for i in range(1, self._chamber_recovery_s + 1):
                    if stop_event.is_set():
                        on_status("Chamber recovery: stopped")
                        return ActivityResult.STOP
                    time.sleep(1)
                    on_progress(i, self._chamber_recovery_s)

            on_status("Argon purge: complete")
            logger.info("%s: complete", log_prefix)
            return ActivityResult.COMPLETE
        except Exception as exc:
            report_activity_exception(
                on_status, log_prefix, status_prefix, "argon purge", exc,
            )
            return ActivityResult.EXCEPTION
        finally:
            # Leave the chamber in a safe (high-vacuum) state if we
            # disturbed it and didn't already return it ourselves
            # (stop / exception paths).
            if chamber_disturbed:
                try:
                    self._vacuum.pump_high_vacuum()
                    logger.info(
                        "%s: cleanup returned chamber to high vacuum",
                        log_prefix,
                    )
                except Exception:
                    logger.exception(
                        "%s: error returning chamber to high vacuum during "
                        "cleanup (non-fatal)", log_prefix,
                    )

    # --- Phase helpers ----------------------------------------------------

    def _emit_sample(self, pressure: float) -> None:
        """Forward one (elapsed_s, pressure_pa) reading to the chart sink.

        Gated: samples are suppressed until the chamber has reached low
        (sputter) vacuum, so the chart shows the argon cycling rather than
        the initial high-vacuum climb. The gate opens once the chamber
        reports ``"Pumped"`` *and* the pressure has risen above
        :data:`defaults.ARGON_PURGE_CHART_GATE_MIN_PA` (the pressure term
        rejects the chamber's at-rest "Pumped" state at run start); once
        open it stays open for the rest of the run.

        No-op when no sink is wired (headless / tests). Guarded: a
        misbehaving sink — or a chamber-state read — must never abort a
        vacuum poll; telemetry is strictly best-effort.
        """
        if self._on_sample is None:
            return
        try:
            if not self._chart_gate_open:
                if not self._chamber_at_sputter_vacuum(pressure):
                    return
                self._chart_gate_open = True
            self._on_sample(time.monotonic() - self._t0, float(pressure))
        except Exception:
            logger.exception(
                "Argon Purge: chart sample sink raised (non-fatal)"
            )

    def _chamber_at_sputter_vacuum(self, pressure: float) -> bool:
        """True once the chamber has reached low (sputter) vacuum.

        Gate condition for the live chart: the chamber reports it is
        ``"Pumped"`` and the pressure has climbed out of high vacuum into
        the argon regime (above the gate threshold).
        """
        return (
            self._vacuum.chamber_state == _CHAMBER_STATE_PUMPED
            and float(pressure) >= defaults.ARGON_PURGE_CHART_GATE_MIN_PA
        )

    def _monitor_window(
        self,
        stop_event: threading.Event,
        on_progress: ProgressCallback,
        on_status: StatusCallback,
        polls: int,
        label: str,
    ) -> ActivityResult:
        """Hold for ``polls`` reads, displaying the pressure each tick.

        Returns :attr:`ActivityResult.STOP` if interrupted, else
        :attr:`ActivityResult.COMPLETE`.
        """
        interval = defaults.ARGON_PURGE_POLL_INTERVAL_S
        on_progress(0, polls)
        for i in range(1, polls + 1):
            if stop_event.is_set():
                return ActivityResult.STOP
            pressure = self._vacuum.chamber_pressure
            self._emit_sample(pressure)
            on_status(f"Argon purge: {label} — {pressure:.1f} Pa")
            on_progress(i, polls)
            time.sleep(interval)
        return ActivityResult.COMPLETE

    def _wait_for_band(
        self,
        stop_event: threading.Event,
        on_progress: ProgressCallback,
        on_status: StatusCallback,
        log_prefix: str,
    ) -> ActivityResult:
        """Poll until the pressure settles into the mid-pressure band.

        Returns :attr:`ActivityResult.STOP` if interrupted. On reaching
        the band, or the safety poll cap (logged), returns
        :attr:`ActivityResult.COMPLETE` — a purge proceeds rather than
        failing if the band is slow to settle.
        """
        lo = defaults.ARGON_PURGE_MID_TOLERANCE_LO_PA
        hi = defaults.ARGON_PURGE_MID_TOLERANCE_HI_PA
        target = defaults.ARGON_PURGE_MID_PRESSURE_PA
        max_polls = defaults.ARGON_PURGE_MID_MAX_POLLS
        interval = defaults.ARGON_PURGE_POLL_INTERVAL_S

        on_progress(0, max_polls)
        for poll in range(1, max_polls + 1):
            if stop_event.is_set():
                return ActivityResult.STOP
            pressure = self._vacuum.chamber_pressure
            self._emit_sample(pressure)
            on_status(
                f"Argon purge: equilibrating to {int(target)} Pa — "
                f"{pressure:.1f} Pa"
            )
            on_progress(poll, max_polls)
            if lo < pressure < hi:
                logger.info(
                    "%s: mid-pressure band reached at %.2f Pa after "
                    "%d poll(s)", log_prefix, pressure, poll,
                )
                return ActivityResult.COMPLETE
            time.sleep(interval)

        logger.warning(
            "%s: mid-pressure band not reached within %d polls; proceeding",
            log_prefix, max_polls,
        )
        return ActivityResult.COMPLETE

    @staticmethod
    def _sleep_interruptible(
        stop_event: threading.Event, seconds: float,
    ) -> bool:
        """Sleep up to ``seconds``, checking the stop event each second.

        Returns True if the stop event is set, False otherwise.
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
        """No preconditions — argon purge doesn't move the stage.

        Mirrors GIS Purge on the RT page.
        """
        return []

    def parameter_summary(self) -> Dict[str, Any]:
        return {
            "cycles": self._cycles,
            "chamber_recovery_s": self._chamber_recovery_s,
        }
