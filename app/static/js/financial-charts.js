/**
 * Gráfico leve em <canvas>, sem dependência externa — alterna entre
 * barra / pizza / linha pro mesmo conjunto de dados [{label, value}].
 *
 * Usado no painel financeiro (Zona Vermelha) e retrofitado na
 * Análise de Dados do admin — ver os `data-chart` no HTML.
 */
(function () {
    var PALETTE = ["#3f6b62", "#4d7a8c", "#8c6a4d", "#7a5c8c", "#5c8c4d", "#8c4d5c", "#4d5c8c", "#8c7a4d"];

    function drawBar(ctx, w, h, data) {
        var max = Math.max.apply(null, data.map(function (d) { return d.value; }).concat([1]));
        var padding = 30;
        var barWidth = (w - padding * 2) / data.length;
        ctx.clearRect(0, 0, w, h);
        data.forEach(function (d, i) {
            var barHeight = ((h - padding * 2) * d.value) / max;
            var x = padding + i * barWidth;
            var y = h - padding - barHeight;
            ctx.fillStyle = PALETTE[i % PALETTE.length];
            ctx.fillRect(x + 4, y, barWidth - 8, barHeight);
            ctx.fillStyle = "currentColor";
            ctx.font = "11px sans-serif";
            ctx.textAlign = "center";
            ctx.fillText(String(d.value), x + barWidth / 2, y - 4);
            ctx.fillText(String(d.label).slice(0, 10), x + barWidth / 2, h - padding + 14);
        });
    }

    function drawLine(ctx, w, h, data) {
        var max = Math.max.apply(null, data.map(function (d) { return d.value; }).concat([1]));
        var padding = 30;
        var stepX = (w - padding * 2) / Math.max(data.length - 1, 1);
        ctx.clearRect(0, 0, w, h);
        ctx.beginPath();
        ctx.strokeStyle = PALETTE[0];
        ctx.lineWidth = 2;
        data.forEach(function (d, i) {
            var x = padding + i * stepX;
            var y = h - padding - ((h - padding * 2) * d.value) / max;
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.stroke();
        data.forEach(function (d, i) {
            var x = padding + i * stepX;
            var y = h - padding - ((h - padding * 2) * d.value) / max;
            ctx.fillStyle = PALETTE[0];
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = "currentColor";
            ctx.font = "11px sans-serif";
            ctx.textAlign = "center";
            ctx.fillText(String(d.label).slice(0, 10), x, h - padding + 14);
        });
    }

    function drawPie(ctx, w, h, data) {
        var total = data.reduce(function (sum, d) { return sum + d.value; }, 0) || 1;
        var cx = w / 2, cy = h / 2, radius = Math.min(w, h) / 2 - 30;
        var start = -Math.PI / 2;
        ctx.clearRect(0, 0, w, h);
        data.forEach(function (d, i) {
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

    function renderChart(canvas, data, type) {
        var ctx = canvas.getContext("2d");
        var renderer = RENDERERS[type] || drawBar;
        renderer(ctx, canvas.width, canvas.height, data);
    }

    function initChart(container) {
        var canvas = container.querySelector("canvas");
        var data = JSON.parse(container.getAttribute("data-chart"));
        var buttons = container.querySelectorAll("[data-chart-type]");
        var current = container.getAttribute("data-chart-default") || "bar";

        function update() {
            renderChart(canvas, data, current);
            buttons.forEach(function (b) {
                b.classList.toggle("active", b.getAttribute("data-chart-type") === current);
            });
        }

        buttons.forEach(function (b) {
            b.addEventListener("click", function () {
                current = b.getAttribute("data-chart-type");
                update();
            });
        });
        update();
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-chart]").forEach(initChart);
    });
})();
