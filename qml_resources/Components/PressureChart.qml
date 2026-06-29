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
// start of each run. Both ends of both axes auto-range to the data (round
// "nice" tick steps) so the trace fills the plot; only axis spines and
// short tick marks are drawn (no gridlines). Repaints on resize from the
// retained buffer, so no Python-side data copy is needed.

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

    // --- Auto-computed axis bounds (data space) ---
    // Both ends of each axis float to the data (via ChartFunctions.niceAxis
    // in _rescale) so the trace fills the plot rather than hugging a pinned
    // (0, 0) origin. step is the tick spacing (a "nice" round number).
    // Min-span guards (AppConfig) keep an empty/flat chart from collapsing.
    property real _xMin: 0
    property real _xMax: AppConfig.pressureChartXMinSpanS
    property real _xStep: AppConfig.pressureChartXMinSpanS
    property real _yMin: 0
    property real _yMax: AppConfig.pressureChartYMinSpanPa
    property real _yStep: AppConfig.pressureChartYMinSpanPa

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
        _rescale()                    // empty buffer -> default axes
        plotCanvas.requestPaint()
    }

    // --- Internal: recompute axis bounds from the buffer ---
    // Floats both ends of each axis to the data so the trace fills the
    // plot, snapping to "nice" round tick steps. An empty buffer yields a
    // sensible default (min-span) range.
    function _rescale() {
        var ticks = AppConfig.pressureChartTickCount
        var xlo = 0, xhi = 0, ylo = 0, yhi = 0
        if (_xs.length > 0) {
            xlo = xhi = _xs[0]
            ylo = yhi = _ys[0]
            for (var i = 1; i < _xs.length; ++i) {
                if (_xs[i] < xlo) xlo = _xs[i]
                if (_xs[i] > xhi) xhi = _xs[i]
                if (_ys[i] < ylo) ylo = _ys[i]
                if (_ys[i] > yhi) yhi = _ys[i]
            }
        }
        var ax = ChartFunctions.niceAxis(xlo, xhi, ticks,
                                         AppConfig.pressureChartXMinSpanS,
                                         AppConfig.pressureChartXPad)
        var ay = ChartFunctions.niceAxis(ylo, yhi, ticks,
                                         AppConfig.pressureChartYMinSpanPa,
                                         AppConfig.pressureChartYPad)
        _xMin = ax.min; _xMax = ax.max; _xStep = ax.step
        _yMin = ay.min; _yMax = ay.max; _yStep = ay.step
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

        // Data -> pixel transforms. Both axes are offset by their floated
        // minimum (not pinned at 0); y is inverted (canvas y grows down).
        // niceAxis guarantees max > min, so the spans never divide by zero.
        var xMin = root._xMin, xMax = root._xMax
        var yMin = root._yMin, yMax = root._yMax
        function sx(t) { return plotX + ((t - xMin) / (xMax - xMin)) * plotW }
        function sy(p) { return plotY + plotH - ((p - yMin) / (yMax - yMin)) * plotH }

        // Snap to half-pixel centers so 1px spines/ticks stay crisp.
        function crisp(v) { return Math.round(v) + 0.5 }

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
        // Ticks sit on "nice" round multiples of the step that fall inside
        // the padded range, so labels stay round while the spines keep
        // their headroom margin (start at the first multiple >= yMin).
        ctx.fillStyle = labelColor
        ctx.textAlign = "right"
        ctx.textBaseline = "middle"
        var yFirst = Math.ceil(yMin / root._yStep - 1e-9) * root._yStep
        var yN = Math.floor((yMax - yFirst) / root._yStep + 1e-9)
        for (var i = 0; i <= yN; ++i) {
            var pv = yFirst + i * root._yStep
            var py = crisp(sy(pv))
            ChartFunctions.drawLine(ctx, crisp(plotX) - tickLen, py,
                                    crisp(plotX), py, axisColor, 1)
            ctx.fillText(ChartFunctions.fmt(pv),
                         plotX - tickLen - tickGap, sy(pv))
        }

        // --- X tick marks + labels ---
        ctx.textAlign = "center"
        ctx.textBaseline = "top"
        var xFirst = Math.ceil(xMin / root._xStep - 1e-9) * root._xStep
        var xN = Math.floor((xMax - xFirst) / root._xStep + 1e-9)
        for (var j = 0; j <= xN; ++j) {
            var tv = xFirst + j * root._xStep
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
