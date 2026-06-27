"""Recorders — capture and restore microscope state.

A *recorder* is a single-responsibility object that snapshots a
specific aspect of microscope state into an opaque value, and
restores that value back to the microscope on demand. Activities
that mutate microscope state can use a recorder to hold the
"before" state and reapply it on completion, giving the user the
option to leave the microscope as they found it.

This package currently contains:

* :mod:`stage_position` — captures the full stage position (all
  five axes) and replays it verbatim. Used by the workflow runners
  when the "Move Stage To Original Position" setting is enabled, to
  return the stage to where the session began after a successful
  run.

Recorders are constructed with the narrow ops Protocol they
operate on (e.g. :class:`StageOps`), not the full microscope
client — this keeps them testable in isolation and explicit about
what state they touch.

Snapshots
---------
Each recorder defines its own snapshot dataclass. Snapshots are
:class:`dataclasses.dataclass(frozen=True)` so they can't be
mutated after capture, and they ``__repr__`` cleanly for log
output. Activities should treat snapshots as opaque — capture,
hold the value, restore — without inspecting individual fields.
"""