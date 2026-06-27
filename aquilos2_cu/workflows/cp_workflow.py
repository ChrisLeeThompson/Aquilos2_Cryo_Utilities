"""Cryo Prep workflow runner.

Runs a user-composed list of Cryo activities (Sputter Coat, GIS
Deposition) plus an optional Home Stage at the end. The activity list
and per-activity parameters are owned by :class:`CryoActivitiesController`;
this runner reads them as the workflow runner asks for the next
pending activity.

Iterative-fetch architecture
----------------------------
Activities are fetched one at a time via
:meth:`_next_pending_activity` rather than snapshotted at start. This
lets the user mutate the activity list while a workflow is running:

* **Adding** an activity mid-run (and switching it on) makes it
  pending — the runner picks it up on the next fetch, after the
  current activity finishes.
* **Toggling** a switch off mid-run on a not-yet-started activity
  makes it invisible to the next fetch and so it isn't run. (The QML
  binding locks switches on activities past idle, so toggling never
  affects activities that are already running, complete, or in
  exception.)
* **Deleting** a not-yet-started activity is similarly transparent —
  it's no longer in the model on the next fetch.

Per-activity enabled state
--------------------------
Each cryo activity has an associated UI switch. The switches are
session-only (not persisted) and default to off — the user explicitly
opts in to which activities run on each workflow.

The runner tracks enabled state in two structures:

* ``_enabled_instance_ids: set[str]`` — instance ids of cryo activities
  whose switches are on. QML pushes to this via
  :meth:`set_activity_enabled`.
* ``_home_stage_enabled: bool`` — independent flag for Home Stage.
  QML pushes via :meth:`set_home_stage_enabled`.

The :attr:`canStart` Property derives reactively from these — true
iff at least one cryo activity is enabled OR Home Stage is enabled,
*and* the workflow isn't already running.

Validation
----------
Three passes:

* **Parameter validation at start** — :meth:`_validate_pre_start`
  walks every currently-enabled activity and validates each one.
  On any failure, emits :attr:`validationFailed` for each offending
  activity (collected in one pass so the user sees every problem at
  once) and refuses the start. All-or-nothing so the user can fix
  every problem before retrying.

* **Pre-start check at start** — :meth:`_validate_pre_start` then
  gathers the pre-start checks declared by each enabled activity
  class and runs them through the orchestrator
  (:mod:`aquilos2_cu.pre_start_checks`). A REFUSE outcome (e.g.
  GIS Deposition enabled but Z not linked) refuses the start with
  the :attr:`preStartCheckRefused` signal; an ASK_CONFIRM outcome
  (e.g. stage in an unusual position) pauses the start pending
  user confirmation via the runner's two-step Start state machine.

* **Mid-run validation** — :meth:`_next_pending_activity` validates
  each activity it's about to return. On a mid-run validation
  failure (e.g. a GIS Deposition added mid-run with no position
  selected), the workflow aborts: emit :attr:`validationFailed` for
  that activity, return ``None`` so the runner ends the loop.
  Aborting rather than skipping reflects the layered-deposition
  physics — successive Sputter Coat / GIS Deposition activities lay
  down dependent material layers, so a missing intermediate layer
  would produce an incomplete sample worse than running fewer
  activities. (A mid-run pre-start check pass is planned alongside
  this — see :attr:`WorkflowRunner._confirmed_check_types` for the
  carry-forward of types the user already confirmed at Start.)

Stage position
--------------
If :attr:`SettingsController.moveStageToOriginalPosition` is true, the
runner captures the stage position once at the start of the workflow
and restores it at the end *on a successful run only*. Capture/restore
happens via :class:`StageRecorder` in the workflow's
:meth:`_before_run` / :meth:`_after_run` hooks (so they execute on the
worker thread, not the GUI thread). The recorder is constructed in
:meth:`_on_commit_to_run` — only when the runner has committed to
actually starting the run and the setting is on.

(The Aquilos 2 magnetron Sputter Coat does not touch the ion beam, so
there is no ion-beam state to capture or restore around a Cryo run.)
"""
from __future__ import annotations

import logging
from typing import List, Optional, Set

from PySide6.QtCore import (
    Property,
    QObject,
    Signal,
    Slot,
)

from .. import defaults
from ..activities.base import ActivityService, StatusCallback
from ..activities.gis_deposition import GISDepositionService
from ..activities.home_stage import HomeStageService
from ..activities.sputter_coat import SputterCoatService
from ..cryo.activity_records import (
    ACTIVITY_TYPE_GIS_DEPOSITION,
    ACTIVITY_TYPE_SPUTTER_COAT,
    GISDepositionRecord,
    SputterCoatRecord,
)
from ..cryo.controller import CryoActivitiesController
from ..microscope import MicroscopeClientLike
from ..microscope.recorders.stage_position import (
    StagePositionSnapshot,
    StageRecorder,
)
from ..pre_start_checks import (
    PreStartCheck,
    gather_snapshot,
    run_pre_start_checks,
    to_dialog_items,
)
from ..settings.settings_controller import SettingsController
from ..stage_positions.controller import StagePositionsController
from .runner import PreStartValidationResult, WorkflowRunner
from .settings_snapshot import WorkflowSettingsSnapshot

logger = logging.getLogger(__name__)


class CPWorkflow(WorkflowRunner):
    """Cryo Prep workflow runner."""

    # Validation failure for a specific activity instance. Emitted
    # before start when an activity's parameters are invalid (e.g. a
    # GIS Deposition referencing a deleted position). The QML page
    # uses these to set the offending row's activityState to
    # "exception" and the error as the statusMessage tooltip.
    #
    # Args: instance_id (string), message (string).
    validationFailed = Signal(str, str)

    # canStart notify. Emitted whenever a switch toggles or the
    # underlying state changes such that canStart's value flips.
    canStartChanged = Signal()

    def __init__(
        self,
        microscope: MicroscopeClientLike,
        cryo_activities: CryoActivitiesController,
        stage_positions: StagePositionsController,
        settings: SettingsController,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._microscope = microscope
        self._cryo_activities = cryo_activities
        self._stage_positions = stage_positions
        self._settings = settings

        # Session-only enabled state. Not persisted across app launches —
        # at every fresh start, every switch is off. Toggling a switch
        # in the UI calls set_activity_enabled / set_home_stage_enabled.
        self._enabled_instance_ids: Set[str] = set()
        self._home_stage_enabled: bool = False

        # Stage-position recorder state — constructed in
        # :meth:`_on_commit_to_run`, captured in :meth:`_before_run`,
        # and restored in :meth:`_after_run` (gated on a successful
        # run). Used when the "Move Stage To Original Position" setting
        # is on.
        self._stage_recorder: Optional[StageRecorder] = None
        self._stage_snapshot: Optional[StagePositionSnapshot] = None

        # Workflow-settings snapshot — captured in
        # :meth:`_on_commit_to_run` once the runner has committed to
        # the run, consumed by per-activity ``_build_*`` methods,
        # cleared in :meth:`_after_run`. Mirrors the stage recorder
        # lifecycle.
        self._settings_snapshot: Optional[WorkflowSettingsSnapshot] = None

        # canStart depends on isRunning (inherited) — re-emit when it
        # transitions so QML's Start-button binding refreshes. Same
        # pattern as RTWorkflow.
        self.isRunningChanged.connect(self.canStartChanged)

    # --- QML-visible properties -------------------------------------------

    @Property(bool, notify=canStartChanged)
    def canStart(self) -> bool:
        """True when Start is meaningful right now.

        Conditions:
            * at least one cryo activity OR home stage is enabled
            * the workflow isn't already running

        Microscope-connected and other-page-not-running checks are
        handled at the QML page level, mirroring RTWorkflow's pattern.
        """
        if self.isRunning:
            return False
        return bool(self._enabled_instance_ids) or self._home_stage_enabled

    # --- Enabled-state setters --------------------------------------------

    @Slot(str, bool)
    def set_activity_enabled(self, instance_id: str, value: bool) -> None:
        """Toggle a cryo activity's switch state by instance id.

        Called by the QML delegate when its switch toggles. Storing
        as a set rather than a per-instance flag means a removed
        activity's id naturally goes stale — no entry, no enabled.
        On removal, the QML calls :meth:`forget_activity` to clean up
        the set explicitly.
        """
        had_any = self.canStart
        if value:
            self._enabled_instance_ids.add(instance_id)
        else:
            self._enabled_instance_ids.discard(instance_id)
        if self.canStart != had_any:
            self.canStartChanged.emit()

    @Slot(str, result=bool)
    def is_activity_enabled(self, instance_id: str) -> bool:
        """Read a cryo activity's current switch state."""
        return instance_id in self._enabled_instance_ids

    @Slot(bool)
    def set_home_stage_enabled(self, value: bool) -> None:
        """Toggle the Home Stage switch state."""
        had_any = self.canStart
        self._home_stage_enabled = bool(value)
        if self.canStart != had_any:
            self.canStartChanged.emit()

    @Slot(result=bool)
    def is_home_stage_enabled(self) -> bool:
        """Read the Home Stage switch state."""
        return self._home_stage_enabled

    @Slot(str)
    def forget_activity(self, instance_id: str) -> None:
        """Remove an instance id from the enabled set.

        Called by QML when an activity is deleted from the model so
        the set doesn't accumulate stale entries. No-op if the id
        was never enabled.
        """
        had_any = self.canStart
        self._enabled_instance_ids.discard(instance_id)
        if self.canStart != had_any:
            self.canStartChanged.emit()

    # --- WorkflowRunner overrides -----------------------------------------
    #
    # Mid-run switch toggles are honored automatically: each iteration,
    # the runner calls _next_pending_activity, which reads the current
    # _enabled_instance_ids and _home_stage_enabled. A switch toggled
    # off after Start makes the activity invisible to the next fetch.
    # No separate skip-callback needed.
    #
    # The QML binding locks switches on activities past the idle state,
    # so toggles only ever fire for activities the user can still
    # meaningfully change.

    def _validate_pre_start(self) -> PreStartValidationResult:
        """All-or-nothing validation pass at start.

        Three-stage pipeline. Each stage refuses the start outright
        on failure; stages run in order so cheap GUI-state checks
        precede expensive hardware reads.

        Stage 1 — :attr:`canStart` guard. Defensive: QML should have
        the Start button disabled if no activity is enabled, but if
        :meth:`start` is called anyway, refuse cleanly.

        Stage 2 — parameter validation. Walks every currently-enabled
        cryo activity and validates each one (e.g. GIS Deposition
        references a stale position). On any failure, emits
        :attr:`validationFailed` per offending activity (collected in
        one pass so the user sees every problem at once) and a
        generic StatusBar message; returns ``"refused"``.

        Stage 3 — pre-start checks. Gathers the checks declared by
        each enabled activity class (Z linked, stage position within
        safe range, ...), runs them through the orchestrator, and
        routes the outcome:

        * REFUSE → emit :attr:`preStartCheckRefused` with the
          check-result items, status breadcrumb ``"Pre-start check
          failed"``, return ``"refused"``.
        * ASK_CONFIRM → emit :attr:`preStartCheckNeedsConfirmation`,
          return ``"needs_confirmation"`` with the set of check types
          the user is being asked to confirm (carried forward into
          :attr:`WorkflowRunner._confirmed_check_types` on accept).
        * PASS → fall through.

        On stage-3 PASS (and only then), return
        ``PreStartValidationResult(outcome="ok")``. State capture
        (workflow settings snapshot, stage recorder) does NOT happen
        here — it moves to :meth:`_on_commit_to_run`, which fires
        only when the runner has actually committed to the run
        (either an outright OK or an accepted confirmation).

        Why all-or-nothing here, vs. abort-on-fetch in
        :meth:`_next_pending_activity`: at start, the user has the
        chance to fix every problem before committing to a run. After
        the run begins, deposition layers are already being laid
        down, and aborting at the first mid-run failure preserves the
        layered-sample integrity (see module docstring).
        """
        # --- Stage 1: canStart guard ---
        if not self.canStart:
            logger.info(
                "CPWorkflow: no activities enabled; refusing to start"
            )
            self.statusUpdated.emit(
                "Cannot start: no activities enabled"
            )
            return PreStartValidationResult(outcome="refused")

        # Prune enabled instance ids that no longer exist in the live model.
        # _enabled_instance_ids is otherwise pruned only on forget_activity,
        # so after enabling an activity and then loading a template (which
        # mints fresh instance ids — templates.py omits instance_id), the
        # set holds stale ids matching zero records. Without this, Stage 2/3
        # below and _next_pending_activity all skip every record and the run
        # reports "Workflow complete" having done nothing. Intersect against
        # the live ids here, at Start, to close that gap.
        live_ids = {
            record.instance_id
            for record in self._cryo_activities.model.all_records()
        }
        if not self._enabled_instance_ids <= live_ids:
            stale_count = len(self._enabled_instance_ids - live_ids)
            self._enabled_instance_ids &= live_ids
            logger.info(
                "CPWorkflow: pruned %d stale enabled instance id(s) at start",
                stale_count,
            )
            self.canStartChanged.emit()
            # Pruning may have emptied the set; if Home Stage isn't enabled
            # either, there's now nothing to run.
            if not self.canStart:
                self.statusUpdated.emit(
                    "Cannot start: no activities enabled"
                )
                return PreStartValidationResult(outcome="refused")

        # --- Stage 2: parameter validation (collect-all pass) ---
        validation_errors: List[tuple[str, str]] = []
        for record in self._cryo_activities.model.all_records():
            if record.instance_id not in self._enabled_instance_ids:
                continue
            error = self._validate_record(record)
            if error is not None:
                validation_errors.append((record.instance_id, error))
                logger.warning(
                    "CPWorkflow: pre-start validation failed for "
                    "instance=%r: %s",
                    record.instance_id, error,
                )

        if validation_errors:
            for instance_id, message in validation_errors:
                self.validationFailed.emit(instance_id, message)
            count = len(validation_errors)
            self.statusUpdated.emit(
                f"Cannot start: {count} "
                f"activit{'y' if count == 1 else 'ies'} need attention"
            )
            logger.info(
                "CPWorkflow: refusing to start (%d validation error%s)",
                count, "" if count == 1 else "s",
            )
            return PreStartValidationResult(outcome="refused")

        # --- Stage 3: pre-start checks ---
        checks = self._gather_pre_start_checks()
        if checks:
            try:
                snapshot = gather_snapshot(self._microscope)
                summary = run_pre_start_checks(checks, snapshot)
            except Exception:
                # gather_snapshot reads live hardware; a transient glitch
                # must not propagate out of this @Slot-invoked path and
                # leave Start enabled with only a console traceback. Refuse
                # cleanly with a user-facing breadcrumb instead.
                logger.exception(
                    "CPWorkflow: pre-start hardware read failed; refusing "
                    "to start"
                )
                self.statusUpdated.emit("Cannot start: hardware read failed")
                return PreStartValidationResult(outcome="refused")

            if summary.refused:
                items = to_dialog_items(summary.refused)
                self.preStartCheckRefused.emit(items)
                self.statusUpdated.emit("Pre-start check failed")
                logger.info(
                    "CPWorkflow: refusing to start "
                    "(%d pre-start check%s failed)",
                    len(summary.refused),
                    "" if len(summary.refused) == 1 else "s",
                )
                return PreStartValidationResult(outcome="refused")

            if summary.needs_confirmation:
                items = to_dialog_items(summary.needs_confirmation)
                self.preStartCheckNeedsConfirmation.emit(items)
                logger.info(
                    "CPWorkflow: awaiting user confirmation "
                    "(%d pre-start check%s ask for confirmation)",
                    len(summary.needs_confirmation),
                    "" if len(summary.needs_confirmation) == 1 else "s",
                )
                return PreStartValidationResult(
                    outcome="needs_confirmation",
                    pending_confirmed_check_types=(
                        summary.needs_confirmation_types
                    ),
                )

        # All clear. State capture happens in _on_commit_to_run, not
        # here — see the method docstring for the rationale.
        return PreStartValidationResult(outcome="ok")

    def _gather_pre_start_checks(self) -> List[PreStartCheck]:
        """Walk enabled cryo activities + Home Stage, collect their checks.

        Returns a flat list of :class:`PreStartCheck` instances
        contributed by each currently-enabled activity. The
        orchestrator deduplicates by type, so contributing the same
        check from multiple activities (e.g. both Sputter Coat and
        Home Stage want :class:`StagePositionWithinSafeRangeCheck`)
        is fine and produces one evaluation per type.

        Inline dispatch on record type mirrors the pattern in
        :meth:`_next_pending_activity` — no separate registry class.
        Unknown record types are silently skipped (also mirroring
        the fetch behavior).
        """
        checks: List[PreStartCheck] = []
        for record in self._cryo_activities.model.all_records():
            if record.instance_id not in self._enabled_instance_ids:
                continue
            if isinstance(record, SputterCoatRecord):
                checks.extend(SputterCoatService.pre_start_checks())
            elif isinstance(record, GISDepositionRecord):
                checks.extend(GISDepositionService.pre_start_checks())
            # Unknown record types: silently skip. _next_pending_activity
            # will also skip them at fetch time and log a warning then;
            # no point logging twice for the same record.
        if self._home_stage_enabled:
            checks.extend(HomeStageService.pre_start_checks())
        return checks

    def _validate_record(self, record) -> Optional[str]:
        """Validate a single cryo activity record.

        Returns an error message describing the issue, or ``None`` if
        the record is valid. Currently checks GIS Deposition records
        for stale or empty position references; SputterCoatRecord
        has no cross-reference validation needs.

        Used by both :meth:`_validate_pre_start` (start-time pass) and
        :meth:`_next_pending_activity` (mid-run pass), so the
        validation logic stays in one place.
        """
        if isinstance(record, GISDepositionRecord):
            resolved = self._stage_positions.get_record_by_id(
                record.position_id
            )
            if resolved is None:
                return (
                    "GIS Deposition references an unknown stage "
                    "position. Please choose a position from the list."
                )
        return None

    def _on_commit_to_run(self) -> None:
        """Capture workflow settings + set up the stage recorder.

        Fires on every path that commits to a run — either an
        outright ``"ok"`` from :meth:`_validate_pre_start` or an
        accepted confirmation via
        :meth:`WorkflowRunner.respondToConfirmation`. Never fires on
        refused or cancelled paths, so the captured state always
        binds to a run that's about to start.

        Why state capture moved here from ``_validate_pre_start``:
        with the two-step Start, ``_validate_pre_start`` may return
        ``"needs_confirmation"`` and pause for an arbitrary amount
        of time before the user accepts or rejects. Capturing
        settings/recorder there would either:

        * Capture too early — locking the user out of editing
          Settings during the dialog wait, which is surprising and
          out of step with the workflow-not-yet-started state.
        * Capture potentially stale state — by the time the user
          accepts, the captured settings might no longer match what
          they intended.

        Capturing at the commit point matches the snapshot's
        "values as of commit" intent. See also
        :class:`WorkflowSettingsSnapshot`'s module docstring.
        """
        self._settings_snapshot = WorkflowSettingsSnapshot.from_settings(
            self._settings
        )

        if self._settings_snapshot.move_stage_to_original:
            self._stage_recorder = StageRecorder(self._microscope.stage)
            logger.info(
                "CPWorkflow: move-stage-to-original is enabled"
            )
        else:
            self._stage_recorder = None

    def _next_pending_activity(
        self, executed_keys: Set[str],
    ) -> Optional[ActivityService]:
        """Return the next enabled activity not yet executed in this run.

        Walks the cryo activity model in current order, skipping
        disabled activities and activities already executed (or
        aborted). For each candidate, validates and returns the
        corresponding :class:`ActivityService`.

        Mid-run toggle-off folds in here for free: if the user toggles
        an activity off after Start, it's no longer in
        :attr:`_enabled_instance_ids` and isn't returned. Mid-run
        additions appear automatically — when the user adds and
        switches on a new activity, the next fetch sees it in the
        model.

        Two-stage failure on each candidate:

        * **Parameter validation** — :meth:`_validate_record`. On
          failure, emits :attr:`validationFailed` and aborts.
        * **Pre-start check** — :meth:`_mid_run_pre_start_check_passes`.
          On failure, the helper emits its own diagnostics; we just
          return ``None`` to abort.

        Both abort the workflow per the layered-deposition contract:
        dependent layers (Sputter Coat, GIS Deposition) build on
        each other, so silently skipping a failed activity would
        leave gaps in the sample worse than running fewer activities
        cleanly.

        Home Stage is always considered last, mirroring the previous
        snapshot order. Its key is ``"home_stage/"`` (single-instance,
        empty instance_id). It gets the same mid-run pre-start check
        treatment as the cryo activities.

        Unknown record types are skipped silently — we mark them in
        ``executed_keys`` to avoid retrying on every iteration.
        """
        for record in self._cryo_activities.model.all_records():
            # Skip if not switched on (handles mid-run toggle-off).
            if record.instance_id not in self._enabled_instance_ids:
                continue

            # Determine the activity class from the record type. Used
            # for both the executed-key formatting and the mid-run
            # pre-start check call. Unknown record types are skipped;
            # we mark them so we don't retry on every iteration.
            # Choosing a synthetic prefix ("unknown/") avoids any
            # collision with real activity ids.
            if isinstance(record, SputterCoatRecord):
                activity_class = SputterCoatService
            elif isinstance(record, GISDepositionRecord):
                activity_class = GISDepositionService
            else:
                logger.warning(
                    "CPWorkflow: unknown activity record type %s; skipping",
                    type(record).__name__,
                )
                executed_keys.add(f"unknown/{record.instance_id}")
                continue

            activity_id = activity_class.activity_id
            key = f"{activity_id}/{record.instance_id}"
            if key in executed_keys:
                continue

            # Stage 1: parameter validation. Failure aborts the
            # workflow (see method docstring for the layered-
            # deposition rationale).
            error = self._validate_record(record)
            if error is not None:
                self.validationFailed.emit(record.instance_id, error)
                self.statusUpdated.emit(
                    "Workflow aborted: an activity failed validation"
                )
                logger.warning(
                    "CPWorkflow: aborting workflow — activity %r "
                    "(instance=%r) failed mid-run validation: %s",
                    activity_id, record.instance_id, error,
                )
                return None

            # Stage 2: mid-run pre-start check. ASK_CONFIRM outcomes
            # whose type was pre-confirmed at workflow Start proceed
            # silently; everything else aborts. Helper emits its own
            # diagnostics (preStartCheckRefused + status breadcrumb).
            if not self._mid_run_pre_start_check_passes(
                activity_class, self._microscope,
            ):
                return None

            # Build the service. Construction reads the record's
            # current parameter values; edits made between Start and
            # this fetch are picked up.
            if isinstance(record, SputterCoatRecord):
                return self._build_sputter_coat(record)
            # Must be GISDepositionRecord (we'd have continued above
            # for any other type).
            resolved = self._stage_positions.get_record_by_id(
                record.position_id
            )
            return self._build_gis_deposition(record, resolved)

        # Home Stage is always last, opt-in. Mid-run pre-start
        # check applies here too.
        home_stage_key = f"{HomeStageService.activity_id}/"
        if (self._home_stage_enabled
                and home_stage_key not in executed_keys):
            if not self._mid_run_pre_start_check_passes(
                HomeStageService, self._microscope,
            ):
                return None
            return self._build_home_stage()

        return None

    # --- Worker hooks (run on the worker thread) --------------------------

    def _before_run(self, on_status: StatusCallback) -> None:
        """Capture restore-state before any activity runs.

        Captures the stage position when the recorder was set up in
        :meth:`_on_commit_to_run`. Best-effort: a capture failure is
        logged and the snapshot left None (so its restore is skipped),
        without aborting the run.
        """
        if self._stage_recorder is not None:
            on_status("Capturing stage position...")
            try:
                self._stage_snapshot = self._stage_recorder.capture()
            except Exception:
                logger.exception(
                    "CPWorkflow: stage capture failed; proceeding without restore"
                )
                self._stage_snapshot = None

    def _after_run(self, on_status: StatusCallback, completed: bool) -> None:
        """Restore captured state after the activity loop exits.

        The stage position is restored only on a fully successful run
        (``completed`` is True). After a stop or exception we leave the
        stage where it is: commanding further motion after an abnormal
        exit is unsafe (a stop may be a reaction to a collision risk; an
        exception may mean the stage isn't where we think it is).

        The restore is best-effort. If the capture failed (snapshot is
        None), the restore is skipped. All recorder / snapshot /
        settings-snapshot references are cleared unconditionally at the
        end so nothing leaks into a subsequent run.
        """
        # Stage position — success only.
        if completed:
            if (self._stage_recorder is not None
                    and self._stage_snapshot is not None):
                on_status("Returning stage to original position...")
                try:
                    self._stage_recorder.restore(self._stage_snapshot)
                except Exception:
                    logger.exception(
                        "CPWorkflow: stage restore failed; stage may not be "
                        "at its original position"
                    )
        elif self._stage_recorder is not None:
            logger.info(
                "CPWorkflow: skipping stage restore (run did not complete "
                "successfully)"
            )

        # Drop all references — next run creates fresh ones.
        self._stage_snapshot = None
        self._stage_recorder = None
        self._settings_snapshot = None

    # --- Activity builders -------------------------------------------------

    def _build_sputter_coat(
        self, record: SputterCoatRecord,
    ) -> SputterCoatService:
        """Construct a SputterCoatService from a record.

        The Aquilos 2 magnetron coater is driven by the sputter, vacuum,
        and stage ops — it does not touch the ion beam.
        """
        return SputterCoatService(
            sputter_ops=self._microscope.sputter_coater,
            vacuum_ops=self._microscope.vacuum,
            stage_ops=self._microscope.stage,
            current_ma=record.current_ma,
            pressure_pa=record.pressure_pa,
            duration_s=record.duration_s,
            chamber_recovery_s=record.chamber_recovery_s,
            instance_id=record.instance_id,
        )

    def _build_gis_deposition(
        self,
        record: GISDepositionRecord,
        resolved_position,
    ) -> GISDepositionService:
        """Construct a GISDepositionService from a record + resolved position.

        ``resolved_position`` is the :class:`SavedStagePosition` looked
        up from :class:`StagePositionsController` by id. We use its
        coordinates to construct the AutoScript-shape position object
        passed to the activity.
        """
        target_position = self._microscope.stage.make_position(
            x=resolved_position.x,
            y=resolved_position.y,
            z=resolved_position.z,
            r=resolved_position.r,
            t=resolved_position.t,
        )
        return GISDepositionService(
            gis_ops=self._microscope.gis,
            stage_ops=self._microscope.stage,
            gis_port_name=self._settings_snapshot.gis_gas_port_name,
            target_position=target_position,
            position_name=resolved_position.name,
            duration_s=record.duration_s,
            chamber_recovery_s=record.chamber_recovery_s,
            zero_tilt_first=(
                self._settings_snapshot.zero_tilt_before_gis_deposition
            ),
            instance_id=record.instance_id,
        )

    def _build_home_stage(self) -> HomeStageService:
        """Construct a HomeStageService for the end-of-workflow home.

        Home Stage takes no parameters — the former
        ``move_to_original`` arg was removed when stage restore became
        a workflow-level concern (handled by this runner's
        :class:`StageRecorder`, gated on a successful run).
        """
        return HomeStageService(
            stage=self._microscope.stage,
        )