/* Sales Performance Dashboard - Vue 3 (no build step) + Chart.js.
 * All numbers come from the FastAPI backend; this file only fetches and draws them. */
const { createApp } = Vue;

const API = window.API_BASE || "";            // same origin when served by FastAPI
const COLORS = { revenue: "#2f6db5", profit: "#f0a830", soft: "#9dbbe0", grid: "#e2e7ee" };
const gbp = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
const gbpShort = v => (Math.abs(v) >= 1e6 ? `£${(v / 1e6).toFixed(2)}m` : Math.abs(v) >= 1e3 ? `£${(v / 1e3).toFixed(0)}k` : `£${v.toFixed(0)}`);
const charts = {};                             // Chart.js objects kept outside Vue's reactivity on purpose

Chart.defaults.font.family = '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif';
Chart.defaults.color = "#637083";

createApp({
  data() {
    return {
      options: { regions: [], channels: [], categories: [], min_date: "", max_date: "" },
      f: { start: "", end: "", region: "", channel: "", category: "" },
      grain: "month",
      sort: "revenue",
      kpi: null,
      products: [],
      loading: true,
      error: "",
      updatedAt: "",
      activePreset: "All time",
      requestId: 0,
    };
  },
  computed: {
    presets() {
      const max = this.options.max_date;
      if (!max) return [];
      const y = Number(max.slice(0, 4));
      const minus = days => { const d = new Date(max); d.setDate(d.getDate() - days + 1); return d.toISOString().slice(0, 10); };
      return [
        { label: "All time", start: this.options.min_date, end: max },
        { label: String(y), start: `${y}-01-01`, end: `${y}-12-31` },
        { label: String(y - 1), start: `${y - 1}-01-01`, end: `${y - 1}-12-31` },
        { label: `Q4 ${y}`, start: `${y}-10-01`, end: `${y}-12-31` },
        { label: "Last 90 days", start: minus(90), end: max },
      ];
    },
    query() {
      const p = new URLSearchParams();
      Object.entries(this.f).forEach(([k, v]) => v && p.set(k, v));
      return p.toString();
    },
    exportUrl() { return `${API}/api/export/products.csv?${this.query}`; },
    periodLabel() { return this.f.start ? `${this.fmtDate(this.f.start)} – ${this.fmtDate(this.f.end)}` : ""; },
    prevLabel() {
      const p = this.kpi && this.kpi.previous_period;
      return p ? `${this.fmtDate(p.start)} – ${this.fmtDate(p.end)}` : "";
    },
    kpiCards() {
      const k = this.kpi;
      if (!k) return [];
      const c = k.change_pct;
      const card = (label, value, change, text) => ({
        label, value, change, changeText: text,
        cls: change === null ? "" : change > 0 ? "up" : change < 0 ? "down" : "",
      });
      const pct = v => (v === null ? "" : `${Math.abs(v).toFixed(1)}%`);
      return [
        card("Revenue", gbp.format(k.revenue), c.revenue, pct(c.revenue)),
        card("Profit", gbp.format(k.profit), c.profit, pct(c.profit)),
        card("Margin", `${k.margin_pct.toFixed(1)}%`, c.margin_pts, c.margin_pts === null ? "" : `${Math.abs(c.margin_pts).toFixed(1)} pts`),
        card("Orders", k.orders.toLocaleString("en-GB"), c.orders, pct(c.orders)),
        card("Avg order value", `£${k.avg_order_value.toFixed(2)}`, c.avg_order_value, pct(c.avg_order_value)),
      ];
    },
  },
  watch: {
    query() { this.load(); },
    grain() { this.loadTrend(this.requestId); },
    sort() { this.loadProducts(this.requestId); },
  },
  async mounted() {
    try {
      this.options = await this.get("/api/filters");
      this.f.start = this.options.min_date;     // triggers the first load via the watcher
      this.f.end = this.options.max_date;
    } catch (e) {
      this.fail(e);
    }
  },
  methods: {
    money: v => gbp.format(v),
    int: v => v.toLocaleString("en-GB"),
    fmtDate: s => new Date(s).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }),
    share(p) { return this.kpi && this.kpi.revenue ? Math.min(100, (100 * p.revenue) / this.kpi.revenue) : 0; },
    queryWithout(key) {
      const p = new URLSearchParams(this.query);
      p.delete(key);
      return p.toString();
    },
    async get(path, extra = "", omit = null) {
      // Region/category charts ignore their own filter, so the selected bar is highlighted among the others.
      const q = omit ? this.queryWithout(omit) : this.query;
      const res = await fetch(`${API}${path}?${q}${extra}`);
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
      return res.json();
    },
    fail(e) {
      this.error = `Could not load data: ${e.message}. Is the API running (uvicorn sales_dashboard.api:app)?`;
      this.loading = false;
    },
    applyPreset(p) { this.activePreset = p.label; this.f.start = p.start; this.f.end = p.end; },
    reset() {
      this.f = { start: this.options.min_date, end: this.options.max_date, region: "", channel: "", category: "" };
      this.activePreset = "All time";
    },
    async load() {
      const id = ++this.requestId;               // ignore responses from older, slower requests
      this.loading = true;
      this.error = "";
      try {
        const [kpi, regions, categories] = await Promise.all([
          this.get("/api/kpis"), this.get("/api/regions", "", "region"), this.get("/api/categories", "", "category"),
        ]);
        if (id !== this.requestId) return;
        this.kpi = kpi;
        this.drawRegions(regions);
        this.drawCategories(categories);
        await Promise.all([this.loadTrend(id), this.loadProducts(id)]);
        this.updatedAt = new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
        this.loading = false;
      } catch (e) {
        if (id === this.requestId) this.fail(e);
      }
    },
    async loadTrend(id) {
      const rows = await this.get("/api/revenue-trend", `&grain=${this.grain}`);
      if (id === this.requestId) this.drawTrend(rows);
    },
    async loadProducts(id) {
      const rows = await this.get("/api/top-products", `&limit=10&sort=${this.sort}`);
      if (id === this.requestId) this.products = rows;
    },

    upsert(name, canvas, config) {
      if (charts[name]) {
        charts[name].data = config.data;
        charts[name].options = config.options;
        charts[name].update();
      } else {
        charts[name] = new Chart(canvas, config);
      }
    },
    moneyAxis() {
      return { beginAtZero: true, grid: { color: COLORS.grid }, ticks: { callback: v => gbpShort(v) } };
    },
    drawTrend(rows) {
      this.upsert("trend", this.$refs.trendCanvas, {
        type: "line",
        data: {
          labels: rows.map(r => r.period),
          datasets: [
            { label: "Revenue", data: rows.map(r => r.revenue), borderColor: COLORS.revenue,
              backgroundColor: "rgba(47,109,181,0.10)", fill: true, tension: 0.25, pointRadius: rows.length > 40 ? 0 : 3 },
            { label: "Profit", data: rows.map(r => r.profit), borderColor: COLORS.profit,
              backgroundColor: COLORS.profit, tension: 0.25, pointRadius: rows.length > 40 ? 0 : 3 },
          ],
        },
        options: {
          maintainAspectRatio: false, animation: false, interaction: { mode: "index", intersect: false },
          plugins: { tooltip: { callbacks: { label: c => `${c.dataset.label}: ${gbp.format(c.parsed.y)}` } } },
          scales: { y: this.moneyAxis(), x: { grid: { display: false }, ticks: { maxTicksLimit: 14 } } },
        },
      });
    },
    drawRegions(rows) {
      this.upsert("region", this.$refs.regionCanvas, {
        type: "bar",
        data: {
          labels: rows.map(r => r.region),
          datasets: [{ label: "Revenue", data: rows.map(r => r.revenue), borderRadius: 4,
                       backgroundColor: rows.map(r => (this.f.region && r.region !== this.f.region ? COLORS.soft : COLORS.revenue)) }],
        },
        options: {
          indexAxis: "y", maintainAspectRatio: false, animation: false,
          plugins: { legend: { display: false }, tooltip: { callbacks: {
            label: c => { const r = rows[c.dataIndex]; return [`Revenue: ${gbp.format(r.revenue)} (${r.share_pct}%)`, `Margin: ${r.margin_pct}%`, `Orders: ${r.orders.toLocaleString("en-GB")}`]; } } } },
          scales: { x: this.moneyAxis(), y: { grid: { display: false } } },
          onClick: (_, els) => { if (els.length) { const r = rows[els[0].index].region; this.f.region = this.f.region === r ? "" : r; } },
          onHover: (e, els) => { e.native.target.style.cursor = els.length ? "pointer" : "default"; },
        },
      });
    },
    drawCategories(rows) {
      this.upsert("category", this.$refs.categoryCanvas, {
        type: "bar",
        data: {
          labels: rows.map(r => r.category),
          datasets: [
            { type: "bar", label: "Revenue", data: rows.map(r => r.revenue), yAxisID: "y", borderRadius: 4, order: 2,
              backgroundColor: rows.map(r => (this.f.category && r.category !== this.f.category ? COLORS.soft : COLORS.revenue)) },
            { type: "line", label: "Margin %", data: rows.map(r => r.margin_pct), yAxisID: "y1",
              borderColor: "#ffffff", backgroundColor: COLORS.profit, pointRadius: 7, pointBorderWidth: 2,
              showLine: false, order: 1 },
          ],
        },
        options: {
          maintainAspectRatio: false, animation: false,
          plugins: { tooltip: { callbacks: { label: c => (c.dataset.yAxisID === "y1" ? `Margin: ${c.parsed.y}%` : `Revenue: ${gbp.format(c.parsed.y)} (${rows[c.dataIndex].share_pct}%)`) } } },
          scales: {
            y: this.moneyAxis(),
            y1: { position: "right", min: 0, max: 70, grid: { display: false }, ticks: { callback: v => `${v}%` } },
            x: { grid: { display: false } },
          },
          onClick: (_, els) => { if (els.length) { const c = rows[els[0].index].category; this.f.category = this.f.category === c ? "" : c; } },
          onHover: (e, els) => { e.native.target.style.cursor = els.length ? "pointer" : "default"; },
        },
      });
    },
  },
}).mount("#app");
