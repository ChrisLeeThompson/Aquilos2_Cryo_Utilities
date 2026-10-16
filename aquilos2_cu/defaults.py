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

from typing import Dict, List, Tuple


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

# --- Stage move safety ---
# When True, every move the app makes to a saved or captured position
# (GIS Deposition's target, Move To, and Move Stage To Original
# Position) is a staged move: tilt to 0°, move X/Y/Z/R together, then
# tilt to the position's tilt. Rotation therefore happens flat and the
# tilt is applied only once the stage is at the target rotation; a
# single five-axis move gives no control over the order in which xT
# applies rotation and tilt. When the move also changes the holder (GIS
# Deposition, Move To), the stage tilts to 0° under the current holder
# and the position's holder is selected while the stage is flat. Costs
# up to two extra tilt moves per position, so it's a setting: workflows
# that hop between nearby positions (e.g. grid 1 -> grid 2) can leave
# it off. See microscope/stage_moves.py.
ZERO_TILT_BEFORE_STAGE_MOVES: bool = True

# Arrival check. xT clamps a move that leaves the selected holder's
# limits without raising an error (absolute_move returns and the stage
# stops short), so every stage of a move is read back. The axes listed
# in STAGE_MOVE_ARRIVAL_CHECK_AXES are compared with their targets; a
# miss (a shortfall) fails the move: GIS Deposition stops before the
# needle moves, Move To reports it, and the stage restore is reported
# as not restored. Rotation and tilt are the default: those are the
# axes the holder limits clamp, and their encoders read back exactly.
# X/Y/Z deviations are logged with every check but not enforced: on
# the instrument a Y miss of about 170 µm appeared after a tilt with
# nothing clamped, so a hard X/Y/Z check would stop good runs. Add an
# axis letter (x, y, z, r, t) once the logged deviations show it is
# stable. STAGE_MOVE_ARRIVAL_CHECK off: log only, never fail. The
# angle tolerance is in degrees because the UI steps tilt in 0.1°.
STAGE_MOVE_ARRIVAL_CHECK: bool = True
STAGE_MOVE_ARRIVAL_CHECK_AXES: str = "rt"
STAGE_MOVE_TOLERANCE_XYZ_M: float = 20e-6
STAGE_MOVE_TOLERANCE_ANGLE_DEG: float = 0.05

# --- Holders ---
# The xT holder (microscope.specimen.stage.holder) is the selected
# specimen holder, chosen by the operator in Sample Exchange. It governs
# which stage positions Microscope Control permits: with the AutoGrid
# shuttle holder selected, xT refuses moves to some positions that the
# standard shuttle holder allows, and the reverse.
#
# A saved stage position records the holder selected when it was saved
# (or last updated). GIS Deposition and Move To select that holder
# before moving there; a position with no recorded holder is reached
# under the holder already selected. Sputter Coat and Home Stage select
# a fixed holder (SPUTTER_COAT_HOLDER, HOME_STAGE_HOLDER). A Cryo Prep
# run remembers the holder selected at Start (the Start holder): GIS
# Deposition reaches an untagged position under it, and the run selects
# it again when it ends — on every exit path, unlike the stage restore
# (see CPWorkflow._after_run). Move To leaves the position's holder
# selected.
#
# Names are exactly as xT lists them in ``stage.holder.available_values``.

# Holders a position can be saved with, and the tag the Stage Positions
# list shows for each. Saving under any other holder is refused.
SUPPORTED_HOLDERS: Dict[str, str] = {
    "AutoGridShuttle35": "AG",
    "CryoTEMStubShuttle": "ST",
    "HPFCarrierShuttle3mm35": "HPF",
    "HPFCarrierShuttle6mm35": "HPF",
    "HPFSapphireShuttle3mm35": "HPF",
    "HPFSapphireShuttle6mm35": "HPF",
    "LeicaShuttle35": "LS",
    "SpinMillHolder": "SM",
}

# Holders whose positions ask for confirmation: the Start dialog lists
# the GIS Deposition positions saved with them, and the Move To dialog
# says the holder changes. The other supported holders are switched
# without a dialog.
HOLDERS_TO_CONFIRM: Tuple[str, ...] = (
    "CryoTEMStubShuttle",
    "SpinMillHolder",
)

# The holders Sputter Coat and Home Stage run under. Each activity tilts
# the stage to 0° under the holder selected at that moment, selects its
# holder, then goes on (Sputter Coat hands the stage to the coater
# routine; Home Stage homes), whatever holder a preceding GIS
# Deposition left selected. Start is refused when Microscope Control
# does not list the holder an enabled activity selects.
SPUTTER_COAT_HOLDER: str = "AutoGridShuttle35"
HOME_STAGE_HOLDER: str = "AutoGridShuttle35"

# Holder-switch verification. Microscope Control may silently override
# a holder selection it does not permit (the command is accepted, the
# holder is then changed back), so every switch reads the holder back:
# poll until it matches (up to HOLDER_SWITCH_TIMEOUT_S, every
# HOLDER_SWITCH_POLL_S), then wait HOLDER_SWITCH_SETTLE_S and re-read
# to catch a delayed override. See microscope/holder.py.
HOLDER_SWITCH_TIMEOUT_S: float = 10.0
HOLDER_SWITCH_POLL_S: float = 0.5
HOLDER_SWITCH_SETTLE_S: float = 2.0


# =========================================================================
# RT Prep workflow
# =========================================================================

# --- Argon Purge ---
#
# Cycles the chamber vacuum through argon pressure steps to purge the
# argon lines / reduce ice contamination. The user controls the cycle
# count and the post-run chamber recovery; the pressure setpoints and
# poll windows are fixed (they define the procedure).

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
# Safety cap on the "wait until 15 Pa settles" loop. On reaching the
# cap the activity logs a warning and proceeds rather than hanging.
ARGON_PURGE_MID_MAX_POLLS: int = 300
ARGON_PURGE_LOW_PRESSURE_PA: float = 10.0
ARGON_PURGE_LOW_PRESSURE_POLLS: int = 30
# The live chart suppresses samples until the chamber has actually reached
# low (sputter) vacuum, so the trace isn't dominated by the initial
# high-vacuum climb. A sample is charted only once the chamber reports
# "Pumped" and the pressure has risen above this threshold — well above
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
# target chamber pressure (Pa), and a duration (s). It does not use the
# ion beam, an ion species, a grid selection, or a high voltage — those
# are Hydra Bio MicroSputter concepts (see activities/sputter_coat.py).

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
# (SPUTTER_PRESSURE_MAX_POLLS) is exhausted — 240 × 2 s = 480 s.
SPUTTER_PRESSURE_POLL_INTERVAL_S: float = 2.0
SPUTTER_PRESSURE_MAX_POLLS: int = 240
SPUTTER_PRESSURE_TOLERANCE_PA: int = 2

# Sputter duration default (seconds). The bounds are shared with the
# Settings page Bulk / Lamella preset durations
# (SPUTTER_DURATION_MIN/MAX_S above), so the broad 1–999 range is kept
# — the preset feature relies on it.
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
# (Sputter, GIS) activities. Each entry is
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
# Stage Positions page
# =========================================================================

# Longest saved-position name accepted by add_from_current / rename.
# Names are interpolated into status-bar text ("Moving stage to ..."),
# so the cap keeps those lines readable. The name dialog enforces the
# same limit at input time via AppConfig.qml's positionNameMaxLength —
# keep the two in step.
STAGE_POSITION_NAME_MAX_CHARS: int = 40


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
#   * Scan rotate after rotation: on by default — the typical
#     workflow rotates the stage and flips the scan rotation in
#     one gesture.
#   * Zero tilt before rotation: off — users tilt manually if they
#     need it.
#   * Tilt after rotation: off — paired with the angle SpinBox; the
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
# Step size is 2.5 µm/step. Tick interval (50 ms) keeps
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
# Tilt is deliberately not part of the check: legitimate operating
# positions (e.g., the GIS deposition default at 60°) routinely
# exceed any conservative tilt threshold, and the radial XY check
# already catches the operationally unusual positions. The snapshot
# still carries ``stage_t_rad`` for checks that may need it.

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
# Reader contexts differ — these are not all read in the same place:
#   * DEV_FORCE_SIMULATION is read by the entry point
#     (aquilos2_cryo_utilities.py); it has no effect once a client
#     (real or simulated) exists.
#   * DEV_FORCE_UNLINKED / DEV_FORCE_STAGE_OUT_OF_RANGE /
#     DEV_FORCE_HOLDER_OVERRIDE / DEV_FORCE_STAGE_SHORTFALL /
#     DEV_SIMULATED_HOLDERS / DEV_SIMULATED_INITIAL_HOLDER are read only
#     by SimulatedStageOps (microscope/stage_ops.py) and have no effect
#     on the real StageOps facade.
#
# DEV_FORCE_SIMULATION:
#   Skip the microscope connection attempt entirely and start in
#   simulation mode (equivalent to passing --simulation on the command
#   line). The entry point combines this with the --simulation flag and logs a
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
#
# DEV_FORCE_HOLDER_OVERRIDE:
#   Make the simulated stage behave like Microscope Control overriding
#   a holder selection: set_holder() is accepted and the first readback
#   shows the new holder, but the next readback reverts to the previous
#   one. Exercises the "reverted" failure path of
#   microscope/holder.py's select_holder() (GIS Deposition then fails
#   with "holder selection failed"; the end-of-run holder restore
#   reports "holder not restored"; Move To reports "Holder selection
#   failed").
#
# DEV_FORCE_STAGE_SHORTFALL:
#   Make every simulated absolute_move land short of its command (X by
#   50 µm, tilt by 1°), the way xT clamps a move that leaves the
#   selected holder's limits. Exercises the arrival check in
#   microscope/stage_moves.py: GIS Deposition ends with "stage did not
#   reach position", Move To with "Stage stopped short of ...", and the
#   stage restore reports "stage not restored". The X miss shows up in
#   the deviation log line; the tilt miss trips the check.
#
# DEV_SIMULATED_HOLDERS:
#   The simulated stage's ``available_holders`` list: every supported
#   holder plus an unsupported generic entry, so the "Holder Not
#   Supported" path can be exercised by selecting it.
#
# DEV_SIMULATED_INITIAL_HOLDER:
#   The holder the simulated stage starts with.
DEV_FORCE_SIMULATION: bool = False
DEV_FORCE_UNLINKED: bool = False
DEV_FORCE_STAGE_OUT_OF_RANGE: bool = False
DEV_FORCE_HOLDER_OVERRIDE: bool = False
DEV_FORCE_STAGE_SHORTFALL: bool = False
DEV_SIMULATED_HOLDERS: List[str] = [*SUPPORTED_HOLDERS, "GenericHolder"]
DEV_SIMULATED_INITIAL_HOLDER: str = "AutoGridShuttle35"

# Radial distance (metres) used to seed the stage position when
# DEV_FORCE_STAGE_OUT_OF_RANGE is set. Chosen comfortably past
# STAGE_SAFE_RADIAL_RANGE_M so the check trips unambiguously; the value
# also shows up in the dialog text ("9.0 mm from center (0, 0)"). Keep
# this at least ~1 mm beyond STAGE_SAFE_RADIAL_RANGE_M whenever that
# limit changes, or DEV_FORCE_STAGE_OUT_OF_RANGE stops seeding an
# out-of-range position and the ASK_CONFIRM path can no longer be
# exercised in simulation.
DEV_FORCED_OUT_OF_RANGE_RADIAL_M: float = 9e-3