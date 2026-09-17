const $ = (id) => document.getElementById(id);

function params() {
    return new URLSearchParams({
        start: $("start-date").value,
        end: $("end-date").value,
        machine: $("machine-select").value,
    });
}

// Zeichenlimit pro Spalte - Name muss exakt dem Spaltennamen aus dem Backend
// entsprechen. Nicht gelistete Spalten werden nicht gekürzt.
// Voller Wert bleibt als Tooltip (title-Attribut) abrufbar.
const COLUMN_CHAR_LIMITS = {
    tools_removed: 40,
    tools_added: 40,
    tools_in_revolver: 40,
    ToolName_x: 30,
    ToolName_y: 30,
};

const isDarkMode = () =>
    window.matchMedia("(prefers-color-scheme: dark)").matches;


// ---------------- Theming ----------------

function themedLayout(layout) {
    const dark = isDarkMode();

    return {
        ...layout,

        title: {
            ...(layout.title || {}),
            x: 0,
            xanchor: "left",
        },

        margin: {
            l: 55,
            r: 40,
            t: 40,
            b: 60,
            ...(layout.margin || {}),
        },

        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",

        font: {
            color: dark ? "#e6e6e6" : "#1a1a1a",
            ...(layout.font || {}),
        },

        xaxis: {
            gridcolor: dark ? "#444" : "#ddd",
            zerolinecolor: dark ? "#666" : "#bbb",
            automargin: true,
            ticklabelstandoff: 8,
            ...(layout.xaxis || {}),
        },

        yaxis: {
            gridcolor: dark ? "#444" : "#ddd",
            zerolinecolor: dark ? "#666" : "#bbb",
            automargin: true,
            ticklabelstandoff: 8,
            ...(layout.yaxis || {}),
        },
    };
}


// ---------------- Charts ----------------

// machine ist optional.
// Ohne machine bleibt der Titel unverändert.
// Mit machine wird "auf {machine}" ergänzt.
function renderChart(elId, figJson, machine = null) {
    const layout = structuredClone(figJson.layout || {});

    if (
        machine &&
        layout.title?.text &&
        !layout.title.text.includes(machine)
    ) {
        layout.title.text += ` auf ${machine}`;
    }

    Plotly.newPlot(
        $(elId),
        figJson.data,
        themedLayout(layout),
        { responsive: true }
    );
}


// Rerendert alle sichtbaren Charts mit dem aktuellen Farbschema
// (z.B. wenn der Nutzer während der Session zwischen hell/dunkel wechselt).
function rethemeAllCharts() {
    document.querySelectorAll(".chart").forEach(el => {
        if (el.data) {
            Plotly.relayout(el, themedLayout(el.layout));
        }
    });
}

window.matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", rethemeAllCharts);


// ---------------- Tables ----------------

function truncate(col, value) {
    if (value === null || value === undefined) {
        return { text: "", full: null };
    }

    const limit = COLUMN_CHAR_LIMITS[col];
    const str = String(value);

    if (!limit || str.length <= limit) {
        return { text: str, full: null };
    }

    return {
        text: str.slice(0, limit) + "…",
        full: str,
    };
}


function isNumericCol(records, col) {
    return records.every(r =>
        r[col] === null || typeof r[col] === "number"
    );
}


// title ist optional.
// machine ist optional.
// Beispiel:
// renderTable("table-werkzeugverlauf", records, "Werkzeugverlauf", machine)
function renderTable(elId, records, title = null, machine = null) {
    const el = $(elId);

    let finalTitle = title;

    if (
        machine &&
        finalTitle &&
        !finalTitle.includes(machine)
    ) {
        finalTitle += ` auf ${machine}`;
    }

    if (!records || records.length === 0) {
        el.innerHTML = `
            ${finalTitle ? `<h3>${finalTitle}</h3>` : ""}
            <p><i>Keine Daten.</i></p>
        `;
        return;
    }

    const cols = Object.keys(records[0]);

    const numericCols = new Set(
        cols.filter(c => isNumericCol(records, c))
    );

    let html = finalTitle
        ? `<h3>${finalTitle}</h3>`
        : "";

    html += `
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
    `;

    html += cols.map(c =>
        `<th class="${numericCols.has(c) ? "num" : ""}">${c}</th>`
    ).join("");

    html += `
                    </tr>
                </thead>
                <tbody>
    `;

    for (const row of records) {
        html += "<tr>" + cols.map(c => {
            const { text, full } = truncate(c, row[c]);

            const cls = numericCols.has(c)
                ? ' class="num"'
                : "";

            return full
                ? `<td${cls} title="${full.replace(/"/g, "&quot;")}">${text}</td>`
                : `<td${cls}>${text}</td>`;
        }).join("") + "</tr>";
    }

    html += `
                </tbody>
            </table>
        </div>
    `;

    el.innerHTML = html;
}


// ---------------- Tabs ----------------

document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn")
            .forEach(b => b.classList.remove("active"));

        document.querySelectorAll(".tab-panel")
            .forEach(p => p.classList.remove("active"));

        btn.classList.add("active");

        const panel = $("tab-" + btn.dataset.tab);
        panel.classList.add("active");

        // Charts, die geladen wurden während ihr Tab unsichtbar war
        // (display:none), haben eine falsche (meist zu kleine) Breite
        // gemessen. Nach dem Sichtbarwerden neu einpassen lassen.
        requestAnimationFrame(() => {
            panel.querySelectorAll(".chart").forEach(el => {
                if (el.data) {
                    Plotly.Plots.resize(el);
                }
            });
        });
    });
});


// ---------------- Loaders pro Tab ----------------


// TAB 1: Übersicht
// Keine Maschine an Chart-Titel anhängen.

async function loadUebersicht() {
    const res = await fetch("api/uebersicht?" + params());
    const d = await res.json();

    // Kein machine-Parameter: Titel bleibt unverändert.
    renderChart(
        "chart-top-tools-all",
        d.top_tools_all_chart
    );

    const wbox = $("warnings-box");

    if (d.warnings.count > 0) {
        wbox.innerHTML = `
            <div class="warning-box">
                ${d.warnings.count}
                Arbeitsschritte benötigen mehr Tools als die
                Revolver-Kapazität der jeweiligen Maschine zulässt.
            </div>
            <div id="table-warnings"></div>
        `;

        renderTable(
            "table-warnings",
            d.warnings.table
        );
    } else {
        wbox.innerHTML = "";
    }

    // Kein machine-Parameter: Titel bleibt unverändert.
    renderChart(
        "chart-ruestzeit-all",
        d.ruestzeit_vs_toolwechsel_all_chart
    );

    $("kategorisierung").textContent =
        d.kategorisierung_lines.join("\n");

    renderTable(
        "table-vergleich-all",
        d.vergleich_all_table
    );
}


// TAB 2: Revolver
// Bei allen Charts und Tabellen Maschine ergänzen.

async function loadRevolver() {
    const machine = $("machine-select").value;

    $("werkzeugverlauf-title").textContent =
        `Werkzeugverlauf auf ${machine}`;

    $("top10-title").textContent =
        `Top 10 Tools auf ${machine}`;

    $("combos-title").textContent =
        `Top Toolkombinationen auf ${machine}`;

    const p = params();

    p.set(
        "top_n_combos",
        $("combo-slider").value
    );

    const res = await fetch("api/revolver?" + p);
    const d = await res.json();

    renderTable(
        "table-werkzeugverlauf",
        d.werkzeugverlauf_table,
        "Werkzeugverlauf",
        machine
    );

    renderChart(
        "chart-top10",
        d.top10_machine_chart,
        machine
    );

    renderChart(
        "chart-top-combos",
        d.top_combos_chart,
        machine
    );

    renderChart(
        "chart-revolver-sim",
        d.revolver_simulation_chart,
        machine
    );
}


// TAB 3: Rüstzeit
// Maschine an Chart-Titel und Tabellentitel anhängen.

async function loadRuestzeit() {
    const machine = $("machine-select").value;

    $("ruestzeit-title").textContent =
        `Rüstzeit vs. Anzahl Werkzeugwechsel auf ${machine}`;

    const p = params();

    p.set(
        "exclude_zero_ruestzeit",
        $("exclude-zero-ruestzeit").checked
    );

    p.set(
        "exclude_zero_changes",
        $("exclude-zero-changes").checked
    );

    const res = await fetch("api/ruestzeit?" + p);
    const d = await res.json();

    const content = $("ruestzeit-content");

    if (d.empty) {
        content.innerHTML = `
            <p>
                <i>
                    Für den ausgewählten Zeitraum liegen keine
                    gültigen Rüstzeitdaten vor.
                </i>
            </p>
        `;

        return;
    }

    content.innerHTML = `
        <div class="metrics">
            <div class="metric">
                <div class="label">Arbeitsschritte</div>
                <div class="value">${d.metrics.count}</div>
            </div>

            <div class="metric">
                <div class="label">Pearson-Korrelation</div>
                <div class="value">${d.metrics.pearson ?? "-"}</div>
            </div>

            <div class="metric">
                <div class="label">Spearman-Korrelation</div>
                <div class="value">${d.metrics.spearman ?? "-"}</div>
            </div>
        </div>

        <div id="table-setup-summary"></div>
        <div id="chart-ruestzeit-scatter" class="chart"></div>
    `;

    renderTable(
        "table-setup-summary",
        d.setup_summary_table,
        "Durchschnittliche Rüstzeit je Werkzeugwechsel",
        machine
    );

    renderChart(
        "chart-ruestzeit-scatter",
        d.scatter_chart,
        machine
    );

    // Sicherstellen, dass die Breite stimmt,
    // egal ob der Tab gerade sichtbar ist.
    requestAnimationFrame(() => {
        Plotly.Plots.resize(
            $("chart-ruestzeit-scatter")
        );
    });
}


// TAB 4: Vergleich
// Maschine an den Tabellentitel anhängen.

async function loadVergleich() {
    const machine = $("machine-select").value;

    $("vergleich-title").textContent =
        `Vergleich auf ${machine}`;

    const res = await fetch("api/vergleich?" + params());
    const d = await res.json();

    renderTable(
        "table-vergleich",
        d.table,
        "Vergleich",
        machine
    );
}


// ---------------- Load All ----------------

async function loadAll() {
    await Promise.all([
        loadUebersicht(),
        loadRevolver(),
        loadRuestzeit(),
        loadVergleich()
    ]);
}


// ---------------- Event-Wiring ----------------

$("start-date").addEventListener("change", loadAll);

$("end-date").addEventListener("change", loadAll);

$("machine-select").addEventListener("change", loadAll);

$("exclude-zero-ruestzeit").addEventListener(
    "change",
    loadRuestzeit
);

$("exclude-zero-changes").addEventListener(
    "change",
    loadRuestzeit
);

$("combo-slider").addEventListener("input", () => {
    $("combo-count-label").textContent =
        $("combo-slider").value;
});

$("combo-slider").addEventListener("change", loadRevolver);


// ---------------- Init ----------------

(async function init() {
    const meta = await (
        await fetch("api/meta")
    ).json();

    $("start-date").value =
        meta.default_start;

    $("end-date").value =
        meta.default_end;

    $("start-date").min =
        meta.min_date;

    $("start-date").max =
        meta.max_date;

    $("end-date").min =
        meta.min_date;

    $("end-date").max =
        meta.max_date;

    const sel = $("machine-select");

    meta.machines.forEach(m => {
        const opt = document.createElement("option");

        opt.value = m;
        opt.textContent = m;

        sel.appendChild(opt);
    });

    sel.value =
        meta.default_machine;

    await loadAll();
})();