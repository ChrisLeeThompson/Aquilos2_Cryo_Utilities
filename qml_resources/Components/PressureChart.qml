import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../Config"
import "../Js"

// Chamber-pressure chart (Argon Purge).
//
// A small, self-contained Canvas line chart: chamber pressure (Pa, y)
// vs elapsed time (s, x). No QtCharts — the house pattern is Canvas +
// getContext("2d") (see TiltIndicatorArc.qml / ShuttleGraphics.qml).
//
// The component OWNS its point buffer. The parent feeds it live via
// addSample(t, p) — wired in ArgonPurge.qml to
// appController.rtWorkflow.pressureSampled — and calls clear() at the
// start of each run. Both axes auto-scale from 0 (with a floor); only
// axis spines and short tick marks are drawn (no gridlines). Repaints on
// resize from the retained buffer, so no Python-side data copy is needed.

ColumnLayout {

    id: root

    // --- Public input: active (enabled) state ---
    // Driven by the Argon Purge enable toggle. When true the chart paints
    // "lit" (white chrome, blue trace); when false it dims to gray. The
    // palette is chosen imperatively in _paint, so repaint explicitly on
    // change (var/Canvas state changes don't auto-repaint).
    property bool active: true
    onActiveChanged: plotCanvas.requestPaint()

    // --- Owned data buffer (parent-driven) ---
    // Two parallel arrays avoid a per-sample object allocation;
    // (_xs[i], _ys[i]) is one sample.
    property var _xs: []          // elapsed seconds
    property var _ys: []          // chamber pressure, Pa

    // --- Auto-computed axis maxima (data space) ---
    // Origin is pinned at (0, 0) — both elapsed time and pressure are
    // non-negative — so only the maxima scale. Floors keep a fresh/empty
    // chart from collapsing to zero width/height.
    property real _xMax: AppConfig.pressureChartXFloorS
    property real _yMax: AppConfig.pressureChartYFloorPa

    spacing: AppConfig.activityFormRowSpacing

    // --- Public API ---

    // Append one sample and repaint. var-array push() does not emit a
    // change signal, so the repaint is requested explicitly (matching the
    // codebase's explicit requestPaint() discipline).
    function addSample(t, p) {
        _xs.push(t)
        _ys.push(p)
        _rescale()
        plotCanvas.requestPaint()
    }

    // Drop all samples and reset the axes — called at run start.
    function clear() {
        _xs = []
        _ys = []
        _xMax = AppConfig.pressureChartXFloorS
        _yMax = AppConfig.pressureChartYFloorPa
        plotCanvas.requestPaint()
    }

    // --- Internal: recompute axis maxima from the buffer ---
    function _rescale() {
        var xm = AppConfig.pressureChartXFloorS
        var ym = AppConfig.pressureChartYFloorPa
        for (var i = 0; i < _xs.length; ++i) {
            if (_xs[i] > xm)
                xm = _xs[i]
            if (_ys[i] > ym)
                ym = _ys[i]
        }
        // Round both maxima up to "nice" values so tick labels land on
        // round numbers (0, 10, 20, 30 — not arbitrary fractions).
        _xMax = ChartFunctions.niceCeil(xm)
        _yMax = ChartFunctions.niceCeil(ym)
    }

    // --- Plot surface ---
    Item {

        Layout.fillWidth: true
        Layout.preferredHeight: AppConfig.pressureChartHeight

        Canvas {

            id: plotCanvas
            anchors.fill: parent
            antialiasing: true
            smooth: true

            // Repaint on resize — the retained buffer is re-projected to
            // the new pixel size.
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()

            onPaint: root._paint(getContext("2d"))
        }
    }

    // --- Paint routine ---
    function _paint(ctx) {

        var W = plotCanvas.width
        var H = plotCanvas.height

        ctx.clearRect(0, 0, W, H)

        // Plot rectangle, inset by margins that leave room for the axis
        // tick labels and titles.
        var mL = AppConfig.pressureChartMarginLeft
        var mB = AppConfig.pressureChartMarginBottom
        var mT = AppConfig.pressureChartMarginTop
        var mR = AppConfig.pressureChartMarginRight
        var plotX = mL
        var plotY = mT
        var plotW = Math.max(1, W - mL - mR)
        var plotH = Math.max(1, H - mT - mB)

        // Plot background.
        ctx.fillStyle = AppConfig.pressureChartPlotBackground
        ctx.fillRect(plotX, plotY, plotW, plotH)

        // Data -> pixel transforms. y is inverted (canvas y grows down).
        var xMax = root._xMax
        var yMax = root._yMax
        function sx(t) { return plotX + (t / xMax) * plotW }
        function sy(p) { return plotY + plotH - (p / yMax) * plotH }

        // Snap to half-pixel centers so 1px spines/ticks stay crisp.
        function crisp(v) { return Math.round(v) + 0.5 }

        var ticks = AppConfig.pressureChartTickCount
        var tickLen = AppConfig.pressureChartTickLength
        var tickGap = AppConfig.pressureChartTickGap
        ctx.font = AppConfig.pressureChartTickFontPx + "px sans-serif"

        // Palette follows the activity enable state (see `active`): white
        // chrome + blue trace when armed, all gray when off.
        var chrome = root.active ? AppConfig.pressureChartChromeColorActive
                                 : AppConfig.pressureChartChromeColorInactive
        var traceColor = root.active ? AppConfig.pressureChartTraceColorActive
                                     : AppConfig.pressureChartTraceColorInactive
        var axisColor = chrome
        var labelColor = chrome

        // --- Axis spines (left + bottom only; no gridlines) ---
        ChartFunctions.drawLine(ctx, crisp(plotX), crisp(plotY),
                                crisp(plotX), crisp(plotY + plotH),
                                axisColor, 1)
        ChartFunctions.drawLine(ctx, crisp(plotX), crisp(plotY + plotH),
                                crisp(plotX + plotW), crisp(plotY + plotH),
                                axisColor, 1)

        // --- Y tick marks + labels ---
        ctx.fillStyle = labelColor
        ctx.textAlign = "right"
        ctx.textBaseline = "middle"
        for (var i = 0; i <= ticks; ++i) {
            var pv = yMax * i / ticks
            var py = crisp(sy(pv))
            ChartFunctions.drawLine(ctx, crisp(plotX) - tickLen, py,
                                    crisp(plotX), py, axisColor, 1)
            ctx.fillText(ChartFunctions.fmt(pv),
                         plotX - tickLen - tickGap, sy(pv))
        }

        // --- X tick marks + labels ---
        ctx.textAlign = "center"
        ctx.textBaseline = "top"
        for (var j = 0; j <= ticks; ++j) {
            var tv = xMax * j / ticks
            var px = crisp(sx(tv))
            ChartFunctions.drawLine(ctx, px, crisp(plotY + plotH),
                                    px, crisp(plotY + plotH) + tickLen,
                                    axisColor, 1)
            ctx.fillText(ChartFunctions.fmt(tv),
                         sx(tv), plotY + plotH + tickLen + tickGap)
        }

        // --- Axis titles ---
        ctx.fillStyle = labelColor
        ctx.textAlign = "center"
        ctx.textBaseline = "bottom"
        ctx.fillText(Strings.pressureChartXAxis, plotX + plotW / 2, H)

        ctx.save()
        ctx.translate(AppConfig.pressureChartTickFontPx, plotY + plotH / 2)
        ctx.rotate(-Math.PI / 2)
        ctx.textAlign = "center"
        ctx.textBaseline = "top"
        ctx.fillText(Strings.pressureChartYAxis, 0, 0)
        ctx.restore()

        // --- Chart title (centered above the plot) ---
        // Same family and color as the axis tick labels, a step larger.
        // Drawn inside save()/restore() so the larger font doesn't leak
        // into the placeholder text below.
        ctx.save()
        ctx.fillStyle = labelColor
        ctx.font = AppConfig.pressureChartTitleFontPx + "px sans-serif"
        ctx.textAlign = "center"
        ctx.textBaseline = "middle"
        ctx.fillText(Strings.pressureChartTitle, plotX + plotW / 2, mT / 2)
        ctx.restore()

        // --- Empty buffer: placeholder text, no trace ---
        if (root._xs.length === 0) {
            ctx.fillStyle = labelColor
            ctx.textAlign = "center"
            ctx.textBaseline = "middle"
            ctx.fillText(Strings.pressureChartWaiting,
                         plotX + plotW / 2, plotY + plotH / 2)
            return
        }

        // --- Pressure trace (polyline) ---
        ctx.strokeStyle = traceColor
        ctx.lineWidth = AppConfig.pressureChartTraceWidth
        ctx.lineJoin = "round"
        ctx.beginPath()
        ctx.moveTo(sx(root._xs[0]), sy(root._ys[0]))
        for (var k = 1; k < root._xs.length; ++k)
            ctx.lineTo(sx(root._xs[k]), sy(root._ys[k]))
        ctx.stroke()

        // A single sample has no segment to stroke — draw a dot so the
        // first reading is visible before the second arrives.
        if (root._xs.length === 1) {
            ctx.fillStyle = traceColor
            ctx.beginPath()
            ctx.arc(sx(root._xs[0]), sy(root._ys[0]),
                    AppConfig.pressureChartTraceWidth, 0, 2 * Math.PI)
            ctx.fill()
        }
    }
}
