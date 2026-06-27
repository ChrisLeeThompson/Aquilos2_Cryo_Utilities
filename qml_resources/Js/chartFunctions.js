.pragma library

// =============================================================================
// CHART FUNCTIONS
//
// Small, generic helpers for the Canvas-based line charts (e.g. the Argon
// Purge chamber-pressure chart in PressureChart.qml). Kept separate from
// diagramFunctions.js so the charts don't depend on the milling-diagram
// drawing library. No instrument geometry lives here.
// =============================================================================

// Generic line drawing (axis spines, tick marks, trace segments).
// Mirrors DiagramFunctions.drawLine; duplicated here to keep the chart
// self-contained.
function drawLine(ctx, startX, startY, endX, endY, strokeStyle, lineWidth) {
    ctx.strokeStyle = strokeStyle;
    ctx.lineWidth = lineWidth;
    ctx.beginPath();
    ctx.moveTo(startX, startY);
    ctx.lineTo(endX, endY);
    ctx.stroke();
}

// Round an axis maximum UP to a "nice" round number (1, 2, or 5 times a
// power of ten) so tick labels read cleanly: 27 -> 30, 12 -> 20, 0.7 -> 1.
// Guards non-positive input (an empty/zero buffer) by returning 1.
function niceCeil(v) {
    if (v <= 0)
        return 1;
    var exp = Math.floor(Math.log(v) / Math.LN10);
    var base = Math.pow(10, exp);
    var f = v / base;                 // in [1, 10)
    var nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
    return nice * base;
}

// Format a tick value: integers print without a decimal point; small
// non-integer values get a single decimal so sub-unit ticks stay legible.
function fmt(v) {
    if (Math.abs(v - Math.round(v)) < 1e-6)
        return String(Math.round(v));
    return v.toFixed(1);
}
