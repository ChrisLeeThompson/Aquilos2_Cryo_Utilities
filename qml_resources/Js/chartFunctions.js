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

// Nearest "nice" number (1/2/5 times a power of ten) to x. With round
// true it snaps to the closest nice value (1.5/3/7 thresholds, used to
// pick a tick step); with round false it rounds up (used to size a span).
// Guards non-positive input by returning 1.
function niceNum(x, round) {
    if (x <= 0)
        return 1;
    var exp = Math.floor(Math.log(x) / Math.LN10);
    var f = x / Math.pow(10, exp);    // in [1, 10)
    var nf = round ? (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10)
                   : (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10);
    return nf * Math.pow(10, exp);
}

// Compute an axis {min, max, step} for the data range [lo, hi] with about
// `ticks` intervals. Unlike niceCeil (which pins min at 0), both ends float
// to the data so the trace fills the plot. The bounds are the data range
// plus `pad` fractional headroom at each end (e.g. 0.05 = 5% of the span),
// so the trace doesn't touch the spines — in particular keeping a gap
// between a low trace and the x-axis. `minSpan` widens a degenerate range
// (one sample, or a flat trace) so it can't collapse to zero width/height.
// The bounds themselves are NOT rounded; instead the caller draws ticks at
// "nice" round multiples of `step` that fall inside [min, max] (see
// PressureChart._paint), so tick labels stay round while the fit stays tight.
function niceAxis(lo, hi, ticks, minSpan, pad) {
    if (hi - lo < minSpan) {          // widen a degenerate range
        var mid = 0.5 * (lo + hi);
        lo = mid - 0.5 * minSpan;
        hi = mid + 0.5 * minSpan;
    }
    var span = hi - lo;
    lo -= span * pad;                 // fractional headroom each end
    hi += span * pad;
    if (lo < 0)                       // time and pressure are non-negative
        lo = 0;
    return {
        min: lo,
        max: hi,
        step: niceNum((hi - lo) / Math.max(1, ticks), true)
    };
}

// Format a tick value: integers print without a decimal point; small
// non-integer values get a single decimal so sub-unit ticks stay legible.
function fmt(v) {
    if (Math.abs(v - Math.round(v)) < 1e-6)
        return String(Math.round(v));
    return v.toFixed(1);
}
