import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../Config"

// Sputter Coat activity (Aquilos 2 magnetron plasma coater).
//
// Magnetron parameters:
//   • current (mA)
//   • target chamber pressure (Pa)
//   • sputter duration (s)
//   • chamber recovery (s)
//
// It does NOT use the ion beam, an ion species, grids, or a high
// voltage — those were Hydra Bio MicroSputter concepts.
//
// Per-instance state model: same pattern as GISDeposition.qml. Multiple
// Sputter Coat instances can exist on the Cryo page; each is keyed by
// `instanceId` and binds two-way to its model row through the
// CryoActivitiesController. The spin-box setters call
// appController.cryoActivities.set_sputter_*(instanceId, value), which
// clamps, updates the model row, and persists.

GroupBox {

    id: root

    // --- Per-instance binding ---
    property string instanceId: ""

    // Model-row sourced parameter values.
    property int current: 0          // mA
    property int pressure: 0         // Pa
    property int duration: 0         // s
    property int chamberRecovery: 0  // s

    // --- Activity header summary ---
    readonly property string parameterSummary:
        current + " mA, " + pressure + " Pa, " + duration + "s"

    // Uniform spin box width: widest measured member in this group. Each
    // CustomSpinBox still self-measures its own implicitWidth (range/decimals/
    // font/locale/arrows); we just bind every box to the group max so they
    // line up. Reading implicitWidth to size preferredWidth is loop-safe
    // because implicitWidth doesn't depend on preferredWidth/width.
    readonly property real _spinBoxWidth: Math.max(
        currentSpinBox.implicitWidth,
        pressureSpinBox.implicitWidth,
        durationSpinBox.implicitWidth,
        chamberRecoverySpinBox.implicitWidth)

    Layout.fillWidth: true
    focusPolicy: Qt.StrongFocus
    background: Rectangle {
        anchors.fill: parent
        color: "transparent"
    }

    GridLayout {

        anchors.fill: parent
        columns: 2
        rowSpacing: AppConfig.activityFormRowSpacing
        columnSpacing: AppConfig.activityFormColumnSpacing

        // ---- Row 1: Current (mA) ----

        ToolTippedLabel {
            id: currentLabel
            text: "Current (mA)"
            toolTipText: Strings.sputterCoatCurrentLabelTooltip
        }

        CustomSpinBox {
            id: currentSpinBox
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            Layout.preferredWidth: root._spinBoxWidth
            from: appController.cryoActivities.sputterCurrentMin
            to: appController.cryoActivities.sputterCurrentMax
            value: root.current
            editable: true
            showArrows: true
            onValueModified: {
                if (root.instanceId) {
                    appController.cryoActivities.set_sputter_current_ma(
                        root.instanceId, value
                    )
                }
            }
        }

        // ---- Row 2: Pressure (Pa) ----

        ToolTippedLabel {
            id: pressureLabel
            text: "Pressure (Pa)"
            toolTipText: Strings.sputterCoatPressureLabelTooltip
        }

        CustomSpinBox {
            id: pressureSpinBox
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            Layout.preferredWidth: root._spinBoxWidth
            from: appController.cryoActivities.sputterPressureMin
            to: appController.cryoActivities.sputterPressureMax
            stepSize: appController.cryoActivities.sputterPressureStep
            value: root.pressure
            editable: true
            showArrows: true
            onValueModified: {
                if (root.instanceId) {
                    appController.cryoActivities.set_sputter_pressure_pa(
                        root.instanceId, value
                    )
                }
            }
        }

        // ---- Row 3: Duration (s) ----

        ToolTippedLabel {
            id: durationLabel
            text: "Duration (s)"
            toolTipText: Strings.sputterCoatDurationLabelTooltip
        }

        CustomSpinBox {
            id: durationSpinBox
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            Layout.preferredWidth: root._spinBoxWidth
            from: appController.cryoActivities.sputterDurationMin
            to: appController.cryoActivities.sputterDurationMax
            value: root.duration
            editable: true
            showArrows: true
            onValueModified: {
                if (root.instanceId) {
                    appController.cryoActivities.set_sputter_duration(
                        root.instanceId, value
                    )
                }
            }
        }

        // ---- Row 4: Chamber recovery (s) ----

        ToolTippedLabel {
            id: chamberRecoveryLabel
            text: "Chamber Recovery (s)"
            toolTipText: Strings.chamberRecoveryLabelTooltip
        }

        CustomSpinBox {
            id: chamberRecoverySpinBox
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            Layout.preferredWidth: root._spinBoxWidth
            from: appController.cryoActivities.chamberRecoveryMin
            to: appController.cryoActivities.chamberRecoveryMax
            value: root.chamberRecovery
            editable: true
            showArrows: true
            onValueModified: {
                if (root.instanceId) {
                    appController.cryoActivities.set_sputter_chamber_recovery(
                        root.instanceId, value
                    )
                }
            }
        }

    }

}
