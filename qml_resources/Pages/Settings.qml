import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../Config"
import "../Components"
import "../Dialogs"

// Settings page
//
// All controls bind to appController.settings.* (PySide SettingsController).
// Two-way binding is achieved by:
//   1. Reading the property as the initial value (.checked / .value / .text).
//   2. Writing back on the appropriate change signal.
// The SettingsController's setters are no-ops when the incoming value matches
// the stored value, so there is no feedback loop when a control echoes a
// value back to its source.
//
// Persistence is handled inside SettingsController — every successful set
// writes to QSettings immediately, no explicit save action required.

Item {

    id: root

    TapHandler {
        onTapped: root.forceActiveFocus()
    }

    ColumnLayout {

        anchors.fill: parent
        anchors.margins: AppConfig.pageMargin
        spacing: AppConfig.pageSectionSpacing

        Label {

            text: "Settings"
            font.pixelSize: AppConfig.pageHeadingFontSize
            font.bold: true

        }

        Label {

            text: "Persistent script settings."
            font.pixelSize: AppConfig.pageBodyFontSize
            Layout.fillWidth: true
            wrapMode: Label.WordWrap

        }

        Item { Layout.preferredHeight: AppConfig.pageHeadingSpacerHeight }

        GridLayout {

            id: mainGridLayout
            Layout.fillWidth: true
            Layout.maximumWidth: AppConfig.settingsPageMaxWidth
            columns: 2
            rowSpacing: AppConfig.settingsFormRowSpacing
            columnSpacing: AppConfig.settingsFormColumnSpacing

            // ---- Row 0: Always On Top ----

            ToolTippedLabel {

                id: alwaysOnTopLabel
                Layout.row: 0
                Layout.column: 0
                text: "Always On Top"
                toolTipText: Strings.alwaysOnTopLabelTooltip

            }

            CheckBox {

                id: alwaysOnTopCheckBox
                Layout.row: 0
                Layout.column: 1
                Layout.alignment: Qt.AlignRight
                checked: appController.settings.alwaysOnTop
                onToggled: appController.settings.alwaysOnTop = checked

            }

            // ---- Row 1: GIS Gas Port Name ----

            ToolTippedLabel {

                id: gisGasPortNameLabel
                Layout.row: 1
                Layout.column: 0
                text: "GIS Gas Port Name"
                toolTipText: Strings.gisGasPortNameLabelTooltip

            }

            TextField {

                id: gisGasPortNameTextEdit
                Layout.row: 1
                Layout.column: 1
                Layout.preferredWidth: 120
                Layout.alignment: Qt.AlignRight
                enabled: !appController.anyWorkflowRunning
                // Initial value pulled from settings on load. We avoid a
                // declarative `text: appController.settings.gisGasPortName`
                // binding so user typing isn't fought by the binding while
                // the field is focused.
                text: appController.settings.gisGasPortName
                onAccepted: focus = false
                onEditingFinished: appController.settings.gisGasPortName = text

            }

            // ---- Row 2: Zero Tilt Before GIS Deposition ----
            //
            // When checked, each GIS Deposition activity tilts the stage
            // to zero degrees before moving to its deposition position,
            // so the XY/Z translation happens from a flat orientation.
            // Adds an extra stage move per deposition — leave off for
            // workflows that hop between nearby positions (e.g. grid 1 to
            // grid 2) where the tilt is just dead time.

            ToolTippedLabel {

                id: zeroTiltBeforeGisDepositionLabel
                Layout.row: 2
                Layout.column: 0
                text: "Zero Tilt Before GIS Deposition"
                toolTipText: Strings.zeroTiltBeforeGisDepositionLabelTooltip
            }

            CheckBox {

                id: zeroTiltBeforeGisDepositionCheckBox
                Layout.row: 2
                Layout.column: 1
                Layout.alignment: Qt.AlignRight
                enabled: !appController.anyWorkflowRunning
                checked: appController.settings.zeroTiltBeforeGisDeposition
                onToggled: appController.settings.zeroTiltBeforeGisDeposition = checked

            }

            // ---- Row 3: Move Stage To Original Position ----

            ToolTippedLabel {

                id: moveStageToOriginalPositionLabel
                Layout.row: 3
                Layout.column: 0
                text: "Move Stage To Original Position"
                toolTipText: Strings.moveStageToOriginalPositionLabelTooltip
            }

            CheckBox {

                id: moveStageToOriginalPositionCheckBox
                Layout.row: 3
                Layout.column: 1
                Layout.alignment: Qt.AlignRight
                enabled: !appController.anyWorkflowRunning
                checked: appController.settings.moveStageToOriginalPosition
                onToggled: appController.settings.moveStageToOriginalPosition = checked

            }

            // ---- Row 4: Reset Parameters For RT Prep Page ----

            ToolTippedLabel {

                id: resetRTPrepParametersLabel
                Layout.row: 4
                Layout.column: 0
                text: "Reset RT Prep Parameters"
                toolTipText: Strings.resetRTPrepParametersLabelTooltip

            }

            RoundButton {

                id: resetRTPrepParametersButton
                Layout.row: 4
                Layout.column: 1
                Layout.alignment: Qt.AlignRight
                text: "Reset RT Prep Parameters"
                radius: AppConfig.buttonRadius

                ToolTip.text: Strings.resetRTPrepParametersLabelTooltip
                ToolTip.delay: AppConfig.toolTipDelayMs
                ToolTip.timeout: AppConfig.toolTipTimeoutMs
                ToolTip.visible: hovered

                // Disable while ANY workflow is running (not just RT) —
                // restoring defaults mid-run is confusing and the
                // parameters are baked in to the running activity anyway.
                // Matches the page-wide anyWorkflowRunning lock used by
                // the other workflow-affecting controls. rtWorkflow must
                // be non-null because reset_parameters lives on it (unlike
                // the always-present cryoActivities).
                enabled: appController.rtWorkflow
                         && !appController.anyWorkflowRunning

                onClicked: {
                    if (appController.rtWorkflow) {
                        appController.rtWorkflow.reset_parameters()
                    }
                }

            }

            // ---- Row 5: Reset Parameters For Cryo Prep Page ----

            ToolTippedLabel {

                id: resetCryoPrepParametersLabel
                Layout.row: 5
                Layout.column: 0
                text: "Reset Cryo Prep Parameters"
                toolTipText: Strings.resetCryoPrepParametersLabelTooltip

            }

            RoundButton {

                id: resetCryoPrepParametersButton
                Layout.row: 5
                Layout.column: 1
                Layout.alignment: Qt.AlignRight
                text: "Reset Cryo Prep Parameters"
                radius: AppConfig.buttonRadius

                ToolTip.text: Strings.resetCryoPrepParametersLabelTooltip
                ToolTip.delay: AppConfig.toolTipDelayMs
                ToolTip.timeout: AppConfig.toolTipTimeoutMs
                ToolTip.visible: hovered

                // Disable while ANY workflow is running — matches the
                // page-wide anyWorkflowRunning lock. This acts on
                // cryoActivities, which is always present (no microscope
                // required), so the gate must NOT require cpWorkflow to be
                // non-null: cpWorkflow is null until the client is
                // constructed, and anyWorkflowRunning is false while
                // offline/idle, so the button stays enabled during
                // offline setup. The (cpWorkflow-absent OR not-running)
                // clause keeps that offline-enable explicit even though
                // anyWorkflowRunning already covers the run case.
                enabled: (!appController.cpWorkflow
                          || !appController.cpWorkflow.isRunning)
                         && !appController.anyWorkflowRunning

                onClicked: appController.cryoActivities.reset_parameters()
            }

            // ---- Row 6: Session Log Size ----

            ToolTippedLabel {

                id: sessionLogSizeLabel
                Layout.row: 6
                Layout.column: 0
                text: "Session Log File Size"
                toolTipText: Strings.sessionLogSizeLabelTooltip

            }

            Label {

                id: sessionLogSizeValueLabel
                Layout.row: 6
                Layout.column: 1
                Layout.alignment: Qt.AlignRight
                text: appController.sessionLog.formatFileSize(
                          appController.sessionLog.fileSize
                      )
                font.pixelSize: AppConfig.pageBodyFontSize

            }

            // ---- Row 7: Clear Session Log ----

            ToolTippedLabel {

                id: clearSessionLogLabel
                Layout.row: 7
                Layout.column: 0
                text: "Clear Session Log"
                toolTipText: Strings.clearSessionLogLabelTooltip

            }

            RoundButton {

                id: clearSessionLogButton
                Layout.row: 7
                Layout.column: 1
                Layout.alignment: Qt.AlignRight
                text: "Clear Session Log"
                radius: AppConfig.buttonRadius

                ToolTip.text: Strings.clearSessionLogLabelTooltip
                ToolTip.delay: AppConfig.toolTipDelayMs
                ToolTip.timeout: AppConfig.toolTipTimeoutMs
                ToolTip.visible: hovered

                // Disable while a workflow is running. Same protection
                // pattern as the Reset Parameters buttons above, but
                // load-bearing here: ``clearAll()`` mid-workflow would
                // orphan the in-flight session — the controller's
                // current-session pointer becomes stale and subsequent
                // ``on_activity_recorded`` events get dropped per its
                // defense-in-depth check. Disabling at the UI prevents
                // that footgun without special-casing in the
                // controller. Also disabled when there's nothing to
                // clear (file size is 0).
                enabled: !appController.anyWorkflowRunning
                         && appController.sessionLog.fileSize > 0

                onClicked: clearSessionLogConfirmDialog.open()

            }

        }

        Item { Layout.fillHeight: true }

    }

    // Destructive Clear Session Log confirmation. Lives as a sibling
    // of the ColumnLayout (not inside it) so the dialog overlays the
    // page correctly. Triggered from the Row 7 Clear Session Log
    // button's onClicked; the dialog itself does the actual work via
    // ``onAccepted`` (the standard Qt Dialog signal — ConfirmDialog
    // doesn't expose a custom ``confirmed`` signal).
    //
    // ``destructive: true`` puts the focus default on Cancel rather
    // than OK — a non-reflexive gate the user has to deliberately
    // step past. Matches the design convention we agreed for any
    // irreversible action.
    //
    // Button labels are hardcoded inside ConfirmDialog ("Cancel" /
    // "Ok") rather than parameterized — the title and message carry
    // the intent.

    ConfirmDialog {

        id: clearSessionLogConfirmDialog
        title: Strings.clearSessionLogTitle
        message: Strings.clearSessionLogMessage
        destructive: true

        onAccepted: appController.sessionLog.clearAll()

    }

}
