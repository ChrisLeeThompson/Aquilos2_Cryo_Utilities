"""Application-wide default values and bounds.

Single source of truth for behavioral constants: the values the app
falls back to when no user-saved override exists, and the bounds used
both for clamping setters and for QML SpinBox ``from`` / ``to``
properties (exposed via controller Q_INVOKABLE getters).

Sections are organized by feature area. Settings and workflow modules
import from this module rather than holding their own ``defaults.py``
files — there are few enough values that one file is easier to edit
and to grep.

What's *not* here: pure UI / visual constants (margins, colors,
spacing, animation durations) live in ``qml_resources/Config/AppConfig.qml``.
"""
from __future__ import annotations

from typing import List, Tuple


# =========================================================================
# Persistence schema namespace
# =========================================================================

# Prefix for every QSettings key the app persists (activity lists, saved
# stage positions, RT workflow params, user settings). Bump this on a
# breaking change to any persisted format to start from a clean namespace.
# Every module composes its keys from this constant rather than hardcoding
# the literal, so a single edit re-namespaces all persisted state at once.
SCHEMA_PREFIX: str = "v3/"


# =========================================================================
# Settings (user preferences — application-wide)
# =========================================================================

# --- Always On Top ---
ALWAYS_ON_TOP: bool = False

# --- GIS gas port name (used by GIS Purge activity) ---
GIS_GAS_PORT_NAME: str = "Pt dep"

# --- Sputter duration bounds ---
# Bounds for the Sputter Coat activity's duration parameter, exposed to
# QML via CryoActivitiesController as sputterDurationMin / sputterDurationMax.
SPUTTER_DURATION_MIN_S: int = 1
SPUTTER_DURATION_MAX_S: int = 999

# --- Workflow completion behavior ---
# MOVE_STAGE_TO_ORIGINAL_POSITION drives the stage-position recorder:
# return the stage to where the session began, on a successful run.
# (The Aquilos 2 magnetron Sputter Coat doesn't touch the ion beam, so
# there is no ion-beam state to capture and restore around a run.)
MOVE_STAGE_TO_ORIGINAL_POSITION: bool = True

# --- GIS Deposition stage safety ---
# When True, each GIS Deposition activity tilts the stage to zero
# degrees before moving to its deposition position, so the XY/Z
# translation happens from a flat orientation — reducing collision
# risk when approaching positions that are awkward from a steep tilt.
# Costs an extra stage move per deposition, so it's a setting:
# workflows that hop between nearby positions (e.g. grid 1 -> grid 2)
# can leave it off to skip the tilt.
ZERO_TILT_BEFORE_GIS_DEPOSITION: bool = True


# =========================================================================
# RT Prep workflow
# =========================================================================

# --- Argon Purge ---
#
# Cycles the chamber vacuum through argon pressure steps to purge the
# argon lines / reduce ice contamination. The user controls the cycle
# count and the post-run chamber recovery; the pressure setpoints and
# poll windows are fixed (they define the procedure) and mirror v2.5.

ARGON_PURGE_CYCLES_DEFAULT: int = 2
ARGON_PURGE_CYCLES_MIN: int = 1
ARGON_PURGE_CYCLES_MAX: int = 20
ARGON_PURGE_CHAMBER_RECOVERY_DEFAULT_S: int = 120

# Fixed sequence parameters (not user-exposed). Pressures in pascals;
# poll windows in counts of ARGON_PURGE_POLL_INTERVAL_S-second reads.
ARGON_PURGE_INITIAL_WAIT_S: int = 5
ARGON_PURGE_POLL_INTERVAL_S: float = 2.0
ARGON_PURGE_HIGH_PRESSURE_PA: float = 30.0
ARGON_PURGE_HIGH_PRESSURE_POLLS: int = 60
ARGON_PURGE_MID_PRESSURE_PA: float = 15.0
ARGON_PURGE_MID_TOLERANCE_LO_PA: float = 14.75
ARGON_PURGE_MID_TOLERANCE_HI_PA: float = 15.5
# Safety cap on the "wait until 15 Pa settles" loop (v2.5 looped
# unbounded). On reaching the cap the activity logs a warning and
# proceeds rather than hanging.
ARGON_PURGE_MID_MAX_POLLS: int = 300
ARGON_PURGE_LOW_PRESSURE_PA: float = 10.0
ARGON_PURGE_LOW_PRESSURE_POLLS: int = 30
# The live chart suppresses samples until the chamber has actually reached
# low (sputter) vacuum, so the trace isn't dominated by the initial
# high-vacuum climb. A sample is charted only once the chamber reports
# "Pumped" AND the pressure has risen above this threshold — well above
# high vacuum (~1e-3 Pa), below every setpoint (10/15/30 Pa) — which rules
# out the chamber's at-rest "Pumped" state at run start.
ARGON_PURGE_CHART_GATE_MIN_PA: float = 5.0

# --- GIS Purge ---
GIS_PURGE_DURATION_S: int = 120
GIS_PURGE_CHAMBER_RECOVERY_S: int = 30

GIS_PURGE_DURATION_MIN_S: int = 1
GIS_PURGE_DURATION_MAX_S: int = 999

# Home Stage has no per-activity parameters — its only configuration
# is MOVE_STAGE_TO_ORIGINAL_POSITION above.


# =========================================================================
# Cryo Prep workflow
# =========================================================================

# --- Sputter Coat (magnetron plasma) ---
#
# The Aquilos 2 magnetron sputter coater is driven by current (mA), a
# target chamber pressure (Pa), and a duration (s). It does NOT use the
# ion beam, an ion species, a grid selection, or a high voltage — those
# were Hydra Bio MicroSputter concepts. Values mirror the proven v2.5
# Aquilos sequence (see activities/sputter_coat.py).

# Sputter current (milliamperes). The activity converts to amperes
# (× 1e-3) before writing to sputter_coater.current. Exposed to QML via
# cryo/controller.py's sputterCurrentMin/Max Properties.
SPUTTER_CURRENT_DEFAULT_MA: int = 30
SPUTTER_CURRENT_MIN_MA: int = 2
SPUTTER_CURRENT_MAX_MA: int = 30

# Sputter target chamber pressure (pascals), stepped in 10 Pa
# increments in the UI. The activity pumps the chamber (argon) to this
# pressure and waits for it to settle before striking the plasma.
SPUTTER_PRESSURE_DEFAULT_PA: int = 10
SPUTTER_PRESSURE_MIN_PA: int = 10
SPUTTER_PRESSURE_MAX_PA: int = 30
SPUTTER_PRESSURE_STEP_PA: int = 10

# Pressure-equilibration poll loop tunables. After pumping to the
# target pressure, the activity polls chamber_pressure every
# SPUTTER_PRESSURE_POLL_INTERVAL_S seconds until it is within
# SPUTTER_PRESSURE_TOLERANCE_PA of the target, or the poll budget
# (SPUTTER_PRESSURE_MAX_POLLS) is exhausted — v2.5's 240 × 2 s = 480 s.
SPUTTER_PRESSURE_POLL_INTERVAL_S: float = 2.0
SPUTTER_PRESSURE_MAX_POLLS: int = 240
SPUTTER_PRESSURE_TOLERANCE_PA: int = 2

# Sputter duration default (seconds). The bounds are shared with the
# Settings page Bulk / Lamella preset durations
# (SPUTTER_DURATION_MIN/MAX_S above), so the broad 1–999 range is kept
# rather than v2.5's narrower 1–60 — the preset feature relies on it.
SPUTTER_COAT_DURATION_DEFAULT_S: int = 120

# Chamber recovery after the sputter run (seconds)
SPUTTER_COAT_CHAMBER_RECOVERY_DEFAULT_S: int = 120

# --- GIS Deposition ---
# Empty string = no position selected; the workflow refuses to start
# an activity with an unselected position. Stale ids (referring to
# deleted positions) are detected at workflow Start, not eagerly.
GIS_DEPOSITION_POSITION_ID_DEFAULT: str = ""

GIS_DEPOSITION_DURATION_DEFAULT_S: int = 90
GIS_DEPOSITION_DURATION_MIN_S: int = 1
GIS_DEPOSITION_DURATION_MAX_S: int = 999

GIS_DEPOSITION_CHAMBER_RECOVERY_DEFAULT_S: int = 30


# --- Chamber recovery bounds (shared) ---
# Both sputter and GIS deposition use the same recovery range.
CHAMBER_RECOVERY_MIN_S: int = 0
CHAMBER_RECOVERY_MAX_S: int = 999


# --- First-launch / Restore-Defaults activity list ----------------------

# Default Cryo workflow shipped with the app: two pairs of
# (Sputter, GIS) activities, matching v2.1's default. Each entry is
# a tuple of (activity_type, params_dict). Empty params dicts mean
# "use all defaults from the constants above" — passed to the matching
# Record dataclass's ``from_dict``, which fills missing fields.
DEFAULT_CRYO_ACTIVITY_LIST: List[Tuple[str, dict]] = [
    ("sputter_coat", {}),
    ("gis_deposition", {}),
    ("gis_deposition", {}),
    ("sputter_coat", {}),
]


# =========================================================================
# Stage / Scan page
# =========================================================================
#
# The Stage / Scan page is a manual-assist surface (not a workflow):
# the user clicks Rotate / Scan-Rotate or drags the Z slider, and
# operations execute as direct gestures with no per-activity records.
# The constants below configure those gestures' bounds and defaults.

# --- Tilt-after-rotation angle (degrees) ---
# Bounds are exposed to QML via microscope/bounds.py for the SpinBox's
# ``from`` / ``to``, and used by SettingsController to clamp the
# persisted ``tiltAfterRotationAngleDeg`` setting on write. The default
# is the SpinBox's initial value when no user-saved override exists.
TILT_AFTER_ROTATION_ANGLE_DEG_MIN: int = -10
TILT_AFTER_ROTATION_ANGLE_DEG_MAX: int = 60
TILT_AFTER_ROTATION_ANGLE_DEG_DEFAULT: int = 17

# --- Stage rotation checkbox factory defaults ---
# Initial values for the three Stage / Scan page checkboxes when no
# user-saved override exists. SettingsController persists the user's
# edits across sessions; these are the values that ship.
#
# Match the v2.1 default behaviour:
#   * Scan rotate after rotation: ON by default — the typical
#     workflow rotates the stage and flips the scan rotation in
#     one gesture.
#   * Zero tilt before rotation: OFF — users tilt manually if they
#     need it.
#   * Tilt after rotation: OFF — paired with the angle SpinBox; the
#     user opts in explicitly.
SCAN_ROTATE_AFTER_ROTATION_DEFAULT: bool = True
ZERO_TILT_BEFORE_ROTATION_DEFAULT: bool = False
TILT_AFTER_ROTATION_DEFAULT: bool = False

# --- Stage Z slider worker tunables ---
# The Z slider's worker thread issues a ``relative_move`` every tick
# while the slider value is non-zero. The dz argument (in metres) is
# computed as ``slider_value × STAGE_Z_STEP_SIZE_M``; the wait between
# ticks is ``STAGE_Z_TICK_INTERVAL_S`` (seconds).
#
# Step size matches v2.1 (2.5 µm/step). Tick interval (50 ms) keeps
# the slider responsive without spamming the AutoScript input queue.
# At slider = ±25 (the AppConfig.qml limits) and these defaults, the
# worker produces ~1.25 mm/s of effective Z velocity at the extremes.
#
# Reduce STAGE_Z_STEP_SIZE_M for finer manual control; increase
# STAGE_Z_TICK_INTERVAL_S to slow the slider down. Both are kept as
# constants here rather than user settings — promote either to
# SettingsController if users ask for fine-control / fast-travel
# modes.
STAGE_Z_STEP_SIZE_M: float = 2.5e-6
STAGE_Z_TICK_INTERVAL_S: float = 0.05

# How often the Z worker re-reads the stage position to refresh the
# Z-slider safety gate, while the page is active and the slider is idle.
# Much slower than the tick above — the safe/blocked decision doesn't
# move fast. The worker polls every
# ``round(STAGE_SAFE_RANGE_POLL_INTERVAL_S / STAGE_Z_TICK_INTERVAL_S)``
# idle ticks, and skips the read entirely while the slider is driving Z
# (radial distance is invariant under Z motion, and it keeps all stage
# client I/O on the one worker thread).
STAGE_SAFE_RANGE_POLL_INTERVAL_S: float = 0.5

# --- Stage safety threshold for StagePositionWithinSafeRangeCheck ---
#
# A stage position whose radial distance from chamber center
# exceeds this threshold triggers an ASK_CONFIRM dialog at
# workflow Start (and at the start of direct Stage Rotation
# and Move To gestures). The threshold is intentionally
# conservative — it catches operationally unusual positions,
# not physically dangerous ones — the user can still confirm
# and proceed. Bump this as real hardware experience accrues.
#
# Tilt was previously included as a third axis-wise component
# and was dropped: legitimate operating positions (e.g., the
# GIS deposition default at 60°) routinely exceed any
# conservative tilt threshold, and the radial XY check already
# catches the operationally unusual positions where tilt would
# correlate with concern. The snapshot still carries
# ``stage_t_rad`` for future checks that may need it.

STAGE_SAFE_RADIAL_RANGE_M: float = 8e-3   # 8 mm from chamber center


# =========================================================================
# Developer / testing overrides
# =========================================================================
#
# Local development toggles, consolidated here so a single glance before
# distributing catches any flag left on. Keep them all at their committed
# defaults in shipped code; flip one locally to exercise a path, then flip
# it back.
#
# Reader contexts differ — these are NOT all read in the same place:
#   * DEV_FORCE_SIMULATION is read by the entry point
#     (aquilos2_cryo_utilities.py); it has no effect once a client
#     (real or simulated) exists.
#   * DEV_FORCE_UNLINKED / DEV_FORCE_STAGE_OUT_OF_RANGE are read ONLY by
#     SimulatedStageOps (microscope/stage_ops.py) and have NO effect on
#     the real StageOps facade.
#
# DEV_FORCE_SIMULATION:
#   Skip the microscope connection attempt entirely and start in
#   simulation mode (equivalent to passing --simulation on the command
#   line). The entry point ORs this with the --simulation flag and logs a
#   warning when it is set. Set back to False before distributing.
#
# The two stage-state seeds below let the pre-start check dialogs be
# exercised in simulation without editing the simulated initial position
# or the is_linked default by hand.
#
# DEV_FORCE_UNLINKED:
#   Start the simulated stage unlinked, so GIS Deposition's
#   ZLinkedToFreeWorkingDistanceCheck returns REFUSE on Start.
#
# DEV_FORCE_STAGE_OUT_OF_RANGE:
#   Start the simulated stage at DEV_FORCED_OUT_OF_RANGE_RADIAL_M from
#   chamber center, so StagePositionWithinSafeRangeCheck returns
#   ASK_CONFIRM for any gated gesture (GIS Deposition, Sputter Coat,
#   Home Stage, direct Stage Rotation). home() also resets to this
#   position while the flag is set, so the state persists across Homes
#   for repeated triggering.
DEV_FORCE_SIMULATION: bool = False
DEV_FORCE_UNLINKED: bool = False
DEV_FORCE_STAGE_OUT_OF_RANGE: bool = False

# Radial distance (metres) used to seed the stage position when
# DEV_FORCE_STAGE_OUT_OF_RANGE is set. Chosen comfortably past
# STAGE_SAFE_RADIAL_RANGE_M so the check trips unambiguously; the value
# also shows up in the dialog text ("9.0 mm from center (0, 0)"). Keep
# this at least ~1 mm beyond STAGE_SAFE_RADIAL_RANGE_M whenever that
# limit changes, or DEV_FORCE_STAGE_OUT_OF_RANGE stops seeding an
# out-of-range position and the ASK_CONFIRM path can no longer be
# exercised in simulation.
DEV_FORCED_OUT_OF_RANGE_RADIAL_M: float = 9e-3