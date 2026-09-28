/**
 * Lightweight <canvas> chart with no external dependency — switches between
 * bar / pie / line for the same dataset [{label, value}].
 *
 * Used in the financial panel (Red Zone) and the admin's Data Analytics view
 * — see the `data-chart` attributes in the HTML.
 *
 * 6d (2026-09-28, Daniel: "numbers and names are overlapping"): same colours,
 * but readable at any width —
 *  - the canvas follows its container's width (and is sharp on HiDPI screens),
 *    redrawn on resize;
 *  - axis labels: horizontal when they fit, otherwise vertical; numbers (hours,
 *    days) are thinned instead (00, 03, 06 …) so they stay horizontal;
 *  - value labels only where they fit (never on top of each other);
 *  - the pie gets a legend (label · value · %) under the chart.
 */
(function () {
    var PALETTE = ["#3f6b62", "#4d7a8c", "#8c6a4d", "#7a5c8c", "#5c8c4d", "#8c4d5c", "#4d5c8c", "#8c7a4d"];
    var FONT = "11px sans-serif";
    var LINE_H = 13;  // px per label line (font size + gap)

    function textColor(canvas) {
        return window.getComputedStyle(canvas).color || "#17283F";
    }

    function formatValue(v) {
        var r = Math.round(v * 10) / 10;
        return r === Math.round(r) ? String(Math.round(r)) : r.toFixed(1);
    }

    /* Layout for axis labels in slots of `slot` px:
       {rotate, step: show every step-th label, bottom: px needed below the plot}. */
    function axisLayout(ctx, labels, slot) {
        var widest = labels.reduce(function (m, l) { return Math.max(m, ctx.measureText(l).width); }, 0);
        if (widest + 6 <= slot) return { rotate: false, step: 1, bottom: LINE_H + 8 };
        var numeric = labels.every(function (l) { return /^[\d:.\/\s-]+$/.test(l); });
        if (numeric) {
            var steps = [2, 3, 4, 5, 6, 8, 10, 12];
            for (var i = 0; i < steps.length; i++) {
                if (widest + 6 <= slot * steps[i]) return { rotate: false, step: steps[i], bottom: LINE_H + 8 };
            }
        }
        var step = Math.max(1, Math.ceil(LINE_H / Math.max(slot, 1)));
        return { rotate: true, step: step, bottom: Math.min(widest, 110) + 12 };
    }

    function drawAxisLabels(ctx, data, xs, h, layout, color) {
        ctx.fillStyle = color;
        ctx.font = FONT;
        data.forEach(function (d, i) {
            if (i % layout.step !== 0) return;
            var label = String(d.label);
            if (layout.rotate) {
                ctx.save();
                ctx.translate(xs[i], h - layout.bottom + 6);
                ctx.rotate(-Math.PI / 2);
                ctx.textAlign = "right";
                ctx.textBaseline = "middle";
                ctx.fillText(label.length > 18 ? label.slice(0, 17) + "…" : label, 0, 0);
                ctx.restore();
            } else {
                ctx.textAlign = "center";
                ctx.textBaseline = "alphabetic";
                ctx.fillText(label, xs[i], h - layout.bottom + LINE_H + 2);
            }
        });
    }

    function drawBar(ctx, w, h, data, color) {
        var max = Math.max.apply(null, data.map(function (d) { return d.value; }).concat([1]));
        var left = 12, right = 12, top = 18;
        ctx.font = FONT;
        var slot = (w - left - right) / Math.max(data.length, 1);
        var layout = axisLayout(ctx, data.map(function (d) { return String(d.label); }), slot);
        var plotH = h - top - layout.bottom;
        var xs = [];
        data.forEach(function (d, i) {
            var barHeight = (plotH * d.value) / max;
            var x = left + i * slot;
            var y = top + plotH - barHeight;
            var gap = Math.min(8, slot * 0.25);
            ctx.fillStyle = PALETTE[i % PALETTE.length];
            ctx.fillRect(x + gap / 2, y, Math.max(slot - gap, 1), barHeight);
            xs.push(x + slot / 2);
            var text = formatValue(d.value);  // value on top only when it fits over its own bar
            if (d.value > 0 && ctx.measureText(text).width + 4 <= slot) {
                ctx.fillStyle = color;
                ctx.textAlign = "center";
                ctx.textBaseline = "alphabetic";
                ctx.fillText(text, x + slot / 2, y - 4);
            }
        });
        drawAxisLabels(ctx, data, xs, h, layout, color);
    }

    function drawLine(ctx, w, h, data, color) {
        var max = Math.max.apply(null, data.map(function (d) { return d.value; }).concat([1]));
        var left = 16, right = 16, top = 18;
        ctx.font = FONT;
        var stepX = (w - left - right) / Math.max(data.length - 1, 1);
        var layout = axisLayout(ctx, data.map(function (d) { return String(d.label); }), stepX);
        var plotH = h - top - layout.bottom;
        var xs = data.map(function (d, i) { return left + i * stepX; });
        var ys = data.map(function (d) { return top + plotH - (plotH * d.value) / max; });
        ctx.beginPath();
        ctx.strokeStyle = PALETTE[0];
        ctx.lineWidth = 2;
        xs.forEach(function (x, i) { if (i === 0) ctx.moveTo(x, ys[i]); else ctx.lineTo(x, ys[i]); });
        ctx.stroke();
        // Values only on points whose axis label is shown, and only if they fit.
        var widest = data.reduce(function (m, d) { return Math.max(m, ctx.measureText(formatValue(d.value)).width); }, 0);
        var valueStep = Math.max(layout.step, Math.ceil((widest + 6) / Math.max(stepX, 1)));
        data.forEach(function (d, i) {
            ctx.fillStyle = PALETTE[0];
            ctx.beginPath();
            ctx.arc(xs[i], ys[i], 3, 0, Math.PI * 2);
            ctx.fill();
            if (i % valueStep === 0 && d.value > 0) {
                ctx.fillStyle = color;
                ctx.textAlign = "center";
                ctx.textBaseline = "alphabetic";
                ctx.fillText(formatValue(d.value), xs[i], ys[i] - 7);
            }
        });
        drawAxisLabels(ctx, data, xs, h, layout, color);
    }

    function drawPie(ctx, w, h, data) {
        var total = data.reduce(function (sum, d) { return sum + d.value; }, 0) || 1;
        var cx = w / 2, cy = h / 2, radius = Math.max(Math.min(w, h) / 2 - 12, 10);
        var start = -Math.PI / 2;
        data.forEach(function (d, i) {
            if (d.value <= 0) return;
            var slice = (d.value / total) * Math.PI * 2;
            ctx.beginPath();
            ctx.moveTo(cx, cy);
            ctx.arc(cx, cy, radius, start, start + slice);
            ctx.closePath();
            ctx.fillStyle = PALETTE[i % PALETTE.length];
            ctx.fill();
            start += slice;
        });
    }

    var RENDERERS = { bar: drawBar, pizza: drawPie, linha: drawLine };

    function legendFor(container) {
        var legend = container.querySelector(".chart-legend");
        if (!legend) {
            legend = document.createElement("ul");
            legend.className = "chart-legend";
            container.appendChild(legend);
        }
        return legend;
    }

    function renderChart(container, canvas, data, type) {
        // Width follows the container; height keeps the canvas's own ratio (min 200px).
        if (!canvas.dataset.ratio) {
            var w0 = parseFloat(canvas.getAttribute("width")) || 360;
            var h0 = parseFloat(canvas.getAttribute("height")) || 220;
            canvas.dataset.ratio = String(h0 / w0);
        }
        var style = window.getComputedStyle(container);
        var inner = container.clientWidth - parseFloat(style.paddingLeft || 0) - parseFloat(style.paddingRight || 0);
        var cssW = Math.max(Math.floor(inner) || 360, 200);
        var cssH = Math.max(Math.round(cssW * parseFloat(canvas.dataset.ratio)), 200);
        var dpr = window.devicePixelRatio || 1;
        canvas.style.width = cssW + "px";
        canvas.style.height = cssH + "px";
        canvas.width = Math.round(cssW * dpr);
        canvas.height = Math.round(cssH * dpr);
        var ctx = canvas.getContext("2d");
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, cssW, cssH);
        (RENDERERS[type] || drawBar)(ctx, cssW, cssH, data, textColor(canvas));

        var legend = legendFor(container);
        legend.hidden = type !== "pizza";
        if (type === "pizza") {
            var total = data.reduce(function (sum, d) { return sum + d.value; }, 0) || 1;
            legend.innerHTML = "";
            data.forEach(function (d, i) {
                if (d.value <= 0) return;
                var li = document.createElement("li");
                var swatch = document.createElement("span");
                swatch.className = "chart-legend-swatch";
                swatch.style.background = PALETTE[i % PALETTE.length];
                li.appendChild(swatch);
                li.appendChild(document.createTextNode(
                    String(d.label) + " · " + formatValue(d.value) + " · " + Math.round((d.value / total) * 100) + "%"));
                legend.appendChild(li);
            });
        }
    }

    function initChart(container) {
        var canvas = container.querySelector("canvas");
        if (!canvas) return;
        var data = JSON.parse(container.getAttribute("data-chart"));
        var buttons = container.querySelectorAll("[data-chart-type]");
        var current = container.getAttribute("data-chart-default") || "bar";

        function update() {
            renderChart(container, canvas, data, current);
            buttons.forEach(function (b) {
                var active = b.getAttribute("data-chart-type") === current;
                b.classList.toggle("active", active);
                b.setAttribute("aria-pressed", active ? "true" : "false");
            });
        }

        buttons.forEach(function (b) {
            b.addEventListener("click", function () {
                current = b.getAttribute("data-chart-type");
                update();
            });
        });
        var timer = null;
        window.addEventListener("resize", function () {
            clearTimeout(timer);
            timer = setTimeout(update, 150);
        });
        update();
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-chart]").forEach(initChart);
    });
})();
