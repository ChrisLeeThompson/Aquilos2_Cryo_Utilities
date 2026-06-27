import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../Config"

// Argon Purge activity (Aquilos 2, RT prep).
//
// Cycles the chamber vacuum through argon pressure steps to purge the
// argon lines / reduce ice contamination before cryo work.
//
// Exposed parameters:
//   • cycles — number of 30 Pa → 15 Pa pressure cycles
//   • chamber recovery (s) — post-purge vacuum wait
//
// The pressure setpoints (30 / 15 / 10 Pa) are fixed in the backend
// (they define the procedure) and are not user-editable.
//
// Backend coupling: the spin boxes bind two-way to
// appController.rtWorkflow.* — values are sourced from the runner
// (loaded from QSettings on startup) and pushed back on every edit.
// The runner's setters are no-ops on equal values, breaking the
// binding feedback loop. The parent page ensures this component is
// only visible when the runner exists.

GroupBox {

    id: root

    // --- Activity enable state (set by the page from the container switch) ---
    // Forwarded to the pressure chart so it lights up when the activity is
    // armed and dims to gray when off. Bound to the visible toggle (not QML
    // `enabled`, which goes false during the run and would dim the live chart).
    property bool activityEnabled: false

    // --- Parameter values (read by the page / controller) ---
    readonly property int cycles: cyclesSpinBox.value
    readonly property int chamberRecovery: chamberRecoverySpinBox.value

    // --- Activity header summary ---
    readonly property string parameterSummary:
        cycles + (cycles === 1 ? " cycle" : " cycles")

    // Uniform spin box width: widest measured member in this group. Each
    // CustomSpinBox still self-measures its own implicitWidth (range/decimals/
    // font/locale/arrows — cyclesSpinBox's arrow padding is already included);
    // we just bind every box to the group max so they line up. Loop-safe
    // because implicitWidth doesn't depend on preferredWidth/width.
    readonly property real _spinBoxWidth: Math.max(
        cyclesSpinBox.implicitWidth,
        chamberRecoverySpinBox.implicitWidth)

    Layout.fillWidth: true
    focusPolicy: Qt.StrongFocus
    background: Rectangle {
        anchors.fill: parent
        color: "transparent"
    }

    GridLayout {

        id: paramsGrid
        anchors.fill: parent
        columns: 2
        rowSpacing: AppConfig.activityFormRowSpacing
        columnSpacing: AppConfig.activityFormColumnSpacing

        // ---- Row 1: Cycles ----

        ToolTippedLabel {
            id: cyclesLabel
            text: "Cycles"
            toolTipText: Strings.argonPurgeCyclesLabelTooltip
        }

        CustomSpinBox {
            id: cyclesSpinBox
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            Layout.preferredWidth: root._spinBoxWidth
            from: AppConfig.argonPurgeCyclesMin
            to: AppConfig.argonPurgeCyclesMax
            value: appController.rtWorkflow
                   ? appController.rtWorkflow.argonPurgeCycles
                   : AppConfig.argonPurgeCyclesDefault
            editable: true
            showArrows: true
            // onValueModified (user edits only), not onValueChanged, so
            // the binding above and the write-back here don't form a loop.
            onValueModified: {
                if (appController.rtWorkflow) {
                    appController.rtWorkflow.argonPurgeCycles = value
                }
            }
        }

        // ---- Row 2: Chamber recovery ----

        ToolTippedLabel {
            id: chamberRecoveryLabel
            text: "Chamber Recovery (s)"
            toolTipText: Strings.chamberRecoveryLabelTooltip
        }

        CustomSpinBox {
            id: chamberRecoverySpinBox
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            Layout.preferredWidth: root._spinBoxWidth
            from: AppConfig.chamberRecoverySpinBoxMin
            to: AppConfig.chamberRecoverySpinBoxMax
            value: appController.rtWorkflow
                   ? appController.rtWorkflow.argonPurgeChamberRecovery
                   : AppConfig.chamberRecoverySpinBoxMin
            editable: true
            showArrows: true
            onValueModified: {
                if (appController.rtWorkflow) {
                    appController.rtWorkflow.argonPurgeChamberRecovery = value
                }
            }
        }

        // ---- Row 3: Live chamber-pressure chart ----
        // Spans both columns, below the chamber-recovery row. Fed live by
        // the runner's pressureSampled(elapsed_s, pressure_pa) signal and
        // cleared at the start of each run via workflowStarted. The page
        // only shows this component while the runner exists, but
        // rtWorkflow can still be null briefly between runner lifecycles,
        // so Connections guards via ignoreUnknownSignals.
        PressureChart {

            id: pressureChart
            Layout.row: 2
            Layout.column: 0
            Layout.columnSpan: 2
            Layout.fillWidth: true
            Layout.topMargin: AppConfig.activityFormRowSpacing

            // Light/dim with the activity's enable toggle.
            active: root.activityEnabled

            Connections {
                target: appController.rtWorkflow
                ignoreUnknownSignals: true
                function onPressureSampled(t, p) {
                    pressureChart.addSample(t, p)
                }
                function onWorkflowStarted() {
                    pressureChart.clear()
                }
            }
        }

    }

}
