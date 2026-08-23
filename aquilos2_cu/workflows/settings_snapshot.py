"""Workflow settings snapshot.

A frozen, immutable capture of the user-preferences fields that drive
workflow behavior. Constructed in :meth:`WorkflowRunner._on_commit_to_run`
(which fires once the workflow commits to running, after validation
passes) and consumed by per-activity ``_build_*`` methods during the
run.

Why a snapshot
--------------
Activities are constructed just-in-time inside
:meth:`WorkflowRunner._next_pending_activity` rather than at workflow
Start. Without a snapshot, a setting read inside a ``_build_*`` method
would be re-read live each iteration — meaning a user editing the
Settings page mid-run would silently change the behavior of an
activity that hadn't been built yet (e.g. a new GIS port name taking
effect on the next GIS Deposition, or toggling
``moveStageToOriginalPosition`` flipping the Home Stage's restore
behavior moments before it runs).

Capturing the values once at commit time means the running workflow
uses the values that were in effect when the run started, regardless
of what the user does in the Settings page during the run.

The Settings page UI also disables the workflow-affecting controls
during a run as a UX cue (see :attr:`AppController.anyWorkflowRunning`).
The snapshot is the load-bearing safety mechanism; the UI lock is
clarity layered on top.

Shared between RT and CP
------------------------
Both :class:`RTWorkflow` and :class:`CPWorkflow` capture the same
dataclass. RT doesn't read every field (e.g. the GIS-deposition
zero-tilt flag is CP-only), but a single shape avoids divergence if a
future RT activity grows the same dependency.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..settings.settings_controller import SettingsController


@dataclass(frozen=True)
class WorkflowSettingsSnapshot:
    """Immutable capture of workflow-driving SettingsController fields.

    Constructed via :meth:`from_settings` at the moment a workflow
    commits to running. Read by ``_build_*`` methods on the workflow
    runner during the iterative-fetch loop.

    Field naming follows Python snake_case; the corresponding
    QObject Property names on :class:`SettingsController` are listed
    in :meth:`from_settings` for traceability.
    """

    gis_gas_port_name: str
    move_stage_to_original: bool
    zero_tilt_before_gis_deposition: bool

    @classmethod
    def from_settings(
        cls, settings: SettingsController,
    ) -> "WorkflowSettingsSnapshot":
        """Capture the workflow-driving fields from a SettingsController."""
        return cls(
            gis_gas_port_name=settings.gisGasPortName,
            move_stage_to_original=settings.moveStageToOriginalPosition,
            zero_tilt_before_gis_deposition=(
                settings.zeroTiltBeforeGisDeposition
            ),
        )