<template>
  <main class="min-h-screen space-y-5 bg-slate-50 p-6 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
    <header class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="dash-title text-3xl font-black tracking-tight">Analytics Dashboard</h1>
        <p class="text-sm text-slate-500 dark:text-slate-400">{{ timestamp }} · {{ connected ? 'live · server-driven' : 'connecting…' }}</p>
      </div>
      <div class="flex gap-2">
        <button class="rounded-xl bg-blue-600 px-4 py-2 font-bold text-white" type="button" :disabled="!connected" @click="refresh">Refresh</button>
        <button class="rounded-xl border border-slate-300 px-4 py-2 font-bold dark:border-slate-700" type="button" :disabled="!connected" @click="toggleComparison">
          {{ filters.show_comparison ? 'Hide YoY' : 'Compare YoY' }}
        </button>
      </div>
    </header>

    <section class="grid gap-4 rounded-2xl border border-slate-200 bg-white/80 p-4 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900/80 lg:grid-cols-[1fr_auto_1.5fr_auto]">
      <div>
        <p class="text-xs font-bold uppercase tracking-widest text-slate-500">Regions</p>
        <div class="mt-2 flex flex-wrap gap-2">
          <button
            v-for="region in options.regions"
            :key="region"
            :class="chipClass(filters.regions.includes(region))"
            type="button"
            :disabled="!connected"
            @click="toggle('regions', region)"
          >
            {{ region }}
          </button>
        </div>
      </div>
      <label class="block">
        <span class="text-xs font-bold uppercase tracking-widest text-slate-500">Date range</span>
        <select :value="filters.date_range" class="mt-2 rounded-xl border border-slate-300 bg-transparent px-3 py-2 text-inherit dark:border-slate-700" :disabled="!connected" @change="setDateRange($event.target.value)">
          <option v-for="range in options.date_ranges" :key="range">{{ range }}</option>
        </select>
      </label>
      <div>
        <p class="text-xs font-bold uppercase tracking-widest text-slate-500">Products</p>
        <div class="mt-2 flex flex-wrap gap-2">
          <button
            v-for="product in options.products"
            :key="product"
            :class="chipClass(filters.products.includes(product))"
            type="button"
            :disabled="!connected"
            @click="toggle('products', product)"
          >
            {{ product }}
          </button>
        </div>
      </div>
      <label class="block">
        <span class="text-xs font-bold uppercase tracking-widest text-slate-500">Search</span>
        <input :value="filters.search" class="mt-2 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 text-inherit outline-none dark:border-slate-700" placeholder="laptop" :disabled="!connected" @input="setSearch($event.target.value)">
      </label>
    </section>

    <section class="grid gap-4 md:grid-cols-4">
      <article v-for="item in kpis" :key="item.key" class="rounded-2xl border border-slate-200 bg-[#ffffff] p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p class="text-xs font-bold uppercase tracking-widest text-slate-500">{{ item.label }}</p>
            <p :id="'kpi-' + item.key" class="mt-2 text-3xl font-black tabular-nums">{{ item.value }}</p>
            <p class="mt-1 text-sm font-bold text-emerald-500">{{ item.delta }}</p>
          </div>
          <span class="text-xl font-black" :class="item.color">{{ item.badge }}</span>
        </div>
      </article>
    </section>

    <section class="grid gap-4 xl:grid-cols-3">
      <article class="rounded-2xl border border-slate-200 bg-[#ffffff] p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900 xl:col-span-2">
        <h2 class="mb-3 font-bold">Revenue & Orders Trend</h2>
        <div id="chart-line" ref="line" class="h-72 w-full"></div>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-[#ffffff] p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="mb-3 font-bold">Product Sales</h2>
        <div id="chart-bar" ref="bar" class="h-72 w-full"></div>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-[#ffffff] p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="mb-3 font-bold">Sales Distribution</h2>
        <div id="chart-pie" ref="pie" class="h-64 w-full"></div>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-[#ffffff] p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="mb-3 font-bold">Regional Performance</h2>
        <div id="chart-radar" ref="radar" class="h-64 w-full"></div>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-[#ffffff] p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="mb-3 font-bold">System Health</h2>
        <div class="grid grid-cols-2 gap-2">
          <div id="chart-cpu" ref="cpu" class="h-56 w-full"></div>
          <div id="chart-mem" ref="mem" class="h-56 w-full"></div>
        </div>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-[#ffffff] p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="mb-3 font-bold">Weekly Activity</h2>
        <div id="chart-heat" ref="heat" class="h-64 w-full"></div>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-[#ffffff] p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="mb-3 font-bold">Customer Segments</h2>
        <div id="chart-scatter" ref="scatter" class="h-64 w-full"></div>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-[#ffffff] p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="mb-3 font-bold">Stock Performance</h2>
        <div id="chart-candle" ref="candle" class="h-64 w-full"></div>
      </article>
    </section>
  </main>
</template>

<script>
const KPI_BADGES = {
  revenue:    { delta: '+12.5%', badge: 'UP',  color: 'text-blue-500',    label: 'Revenue',    prefix: '$' },
  orders:     { delta: '+8.2%',  badge: 'ORD', color: 'text-emerald-500', label: 'Orders',     prefix: ''  },
  customers:  { delta: '+15.3%', badge: 'USR', color: 'text-purple-500',  label: 'Customers',  prefix: ''  },
  conversion: { delta: '+0.8%',  badge: 'CVR', color: 'text-amber-500',   label: 'Conversion', prefix: ''  },
};

export default {
  data() {
    return {
      // Connection + server-pushed state.
      connected: false,
      timestamp: '—',
      options: { regions: [], products: [], date_ranges: [] },
      filters: {
        regions: [], products: [], date_range: '', search: '', show_comparison: false,
      },
      serverData: null,
      cpuUsage: 0,
      memoryUsage: 0,
      // ECharts instances + observers (not reactive but stored on `this` for cleanup).
      charts: {},
      resizeObserver: null,
      themeObserver: null,
      searchTimer: null,
    };
  },
  computed: {
    kpis() {
      const k = (this.serverData && this.serverData.kpis) || {};
      return Object.keys(KPI_BADGES).map((key) => {
        const meta = KPI_BADGES[key];
        const v = k[key];
        let value;
        if (v == null) {
          value = '—';
        } else if (key === 'conversion') {
          value = v.toFixed(2) + '%';
        } else {
          value = meta.prefix + Number(v).toLocaleString();
        }
        return { key, label: meta.label, value, delta: meta.delta, badge: meta.badge, color: meta.color };
      });
    },
  },
  async mounted() {
    await window.__stage.load('echarts');
    this.refreshTimestamp();
    // Open the WebSocket — this is what registers the per-tab session
    // visible in the runner's Sessions tab. Without it, no dashboard.
    await this.$stage.connect();
    // Ask the server to push initial state + start the metrics ticker.
    // The server replies via session.call("home.applyInitial", …).
    this.$stage.send('dashboard.subscribe');
    // Charts auto-redraw on Quasar dark-mode toggles.
    this.resizeObserver = new ResizeObserver(() => Object.values(this.charts).forEach((c) => c.resize()));
    this.resizeObserver.observe(this.$el);
    this.themeObserver = new MutationObserver(() => this.drawAll());
    this.themeObserver.observe(document.body, { attributes: true, attributeFilter: ['class'] });
  },
  beforeUnmount() {
    if (this.searchTimer) clearTimeout(this.searchTimer);
    this.resizeObserver?.disconnect();
    this.themeObserver?.disconnect();
    Object.values(this.charts).forEach((c) => c.dispose());
  },
  methods: {
    /* --- methods the server calls on this view ------------------------ */
    applyInitial(options, filters, data) {
      this.options = options;
      this.filters = filters;
      this.applyData(data);
      this.connected = true;
      this.refreshTimestamp();
    },
    applyDataset(filters, data) {
      this.filters = filters;
      this.applyData(data);
      this.refreshTimestamp();
    },
    applyMetrics(metrics) {
      this.cpuUsage = metrics.cpu;
      this.memoryUsage = metrics.memory;
      this.drawGauges();
    },

    /* --- user-driven filter changes ----------------------------------- */
    toggle(category, value) {
      // Compute the next list and ship the whole new value up; the
      // server is the source of truth for what's selected.
      const current = this.filters[category] || [];
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      this.$stage.send('dashboard.set_filters', { [category]: next });
    },
    setDateRange(date_range) {
      this.$stage.send('dashboard.set_filters', { date_range });
    },
    setSearch(search) {
      if (this.searchTimer) clearTimeout(this.searchTimer);
      // Debounce typing — don't slam the WS with one message per keystroke.
      this.searchTimer = setTimeout(() => {
        this.$stage.send('dashboard.set_filters', { search });
      }, 200);
    },
    toggleComparison() {
      this.$stage.send('dashboard.set_filters', { show_comparison: !this.filters.show_comparison });
    },
    refresh() {
      // Ask the server for a fresh dataset under the same filters.
      this.$stage.send('dashboard.set_filters', {});
    },

    /* --- data application + charts (rendering only, no data gen) ----- */
    applyData(data) {
      this.serverData = data;
      this.$nextTick(() => this.drawAll());
    },
    chipClass(active) {
      return [
        'chip rounded-full border px-3 py-1 text-sm font-bold transition',
        active
          ? 'border-blue-500 bg-blue-500/15 text-blue-500'
          : 'border-slate-300 text-slate-500 dark:border-slate-700',
      ];
    },
    colors() {
      const dark = document.body.classList.contains('body--dark');
      return {
        border: dark ? '#334155' : '#e2e8f0',
        muted: dark ? '#94a3b8' : '#64748b',
        surface: dark ? '#0f172a' : '#ffffff',
        text: dark ? '#f8fafc' : '#1e293b',
      };
    },
    common() {
      const c = this.colors();
      return {
        textStyle: { color: c.text, fontFamily: 'Roboto, sans-serif' },
        legend: { textStyle: { color: c.text } },
        tooltip: { backgroundColor: c.surface, borderColor: c.border, textStyle: { color: c.text } },
      };
    },
    drawAll() {
      if (!window.echarts || !this.serverData) return;
      Object.values(this.charts).forEach((c) => c.dispose());
      this.charts = {};
      this.drawLine();
      this.drawBar();
      this.drawPie();
      this.drawRadar();
      this.drawGauges();
      this.drawHeatmap();
      this.drawScatter();
      this.drawCandle();
    },
    drawLine() {
      const c = this.colors();
      const d = this.serverData;
      const series = [
        { name: 'Revenue', type: 'line', smooth: true, areaStyle: { opacity: 0.25 }, data: d.revenue,
          itemStyle: { color: '#3b82f6' } },
        { name: 'Orders',  type: 'line', smooth: true, yAxisIndex: 1, data: d.orders,
          itemStyle: { color: '#10b981' } },
      ];
      if (d.revenue_ly) {
        series.push({ name: 'Revenue LY', type: 'line', smooth: true,
          lineStyle: { type: 'dashed' }, data: d.revenue_ly, itemStyle: { color: '#60a5fa' } });
      }
      this.charts.line = echarts.init(this.$refs.line);
      this.charts.line.setOption({
        ...this.common(),
        tooltip: { ...this.common().tooltip, trigger: 'axis' },
        legend: { ...this.common().legend, top: 5 },
        grid: { left: 50, right: 40, top: 42, bottom: 30 },
        xAxis: { type: 'category', data: d.labels, axisLine: { lineStyle: { color: c.muted } } },
        yAxis: [
          { type: 'value', axisLine: { lineStyle: { color: c.muted } }, splitLine: { lineStyle: { color: c.border } } },
          { type: 'value', axisLine: { lineStyle: { color: c.muted } }, splitLine: { show: false } },
        ],
        series,
      });
    },
    drawBar() {
      const c = this.colors();
      const d = this.serverData;
      const colors = d.product_colors || {};
      this.charts.bar = echarts.init(this.$refs.bar);
      this.charts.bar.setOption({
        ...this.common(),
        tooltip: { ...this.common().tooltip, trigger: 'axis' },
        grid: { left: 50, right: 20, top: 20, bottom: 30 },
        xAxis: { type: 'category', data: Object.keys(d.products), axisLine: { lineStyle: { color: c.muted } } },
        yAxis: { type: 'value', splitLine: { lineStyle: { color: c.border } } },
        series: [{
          type: 'bar',
          data: Object.entries(d.products).map(([k, v]) => ({
            value: v,
            itemStyle: { color: colors[k] || '#6366f1', borderRadius: [4, 4, 0, 0] },
          })),
        }],
      });
    },
    drawPie() {
      const d = this.serverData;
      this.charts.pie = echarts.init(this.$refs.pie);
      this.charts.pie.setOption({
        ...this.common(),
        tooltip: { ...this.common().tooltip, trigger: 'item' },
        series: [{
          type: 'pie', radius: ['42%', '72%'], label: { show: false },
          data: Object.entries(d.products).map(([name, value]) => ({ name, value })),
        }],
      });
    },
    drawRadar() {
      const d = this.serverData;
      this.charts.radar = echarts.init(this.$refs.radar);
      this.charts.radar.setOption({
        ...this.common(),
        radar: {
          indicator: ['Sales', 'Marketing', 'Support', 'Dev', 'Ops'].map((name) => ({ name, max: 100 })),
          splitLine: { lineStyle: { color: this.colors().border } },
        },
        series: [{ type: 'radar', areaStyle: { opacity: 0.2 }, data: d.radar }],
      });
    },
    gaugeOption(value, title, color) {
      return {
        series: [{
          type: 'gauge', startAngle: 200, endAngle: -20, min: 0, max: 100,
          progress: { show: true, width: 18 }, pointer: { show: false },
          axisLine: { lineStyle: { width: 18, color: [[1, this.colors().border]] } },
          axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
          title: { offsetCenter: [0, '70%'], color: this.colors().muted, fontSize: 12 },
          detail: { formatter: '{value}%', color: this.colors().text, fontSize: 24, fontWeight: 'bold' },
          itemStyle: { color },
          data: [{ value: Math.round(value), name: title }],
        }],
      };
    },
    drawGauges() {
      this.charts.cpu ??= echarts.init(this.$refs.cpu);
      this.charts.mem ??= echarts.init(this.$refs.mem);
      this.charts.cpu.setOption(this.gaugeOption(this.cpuUsage, 'CPU', '#3b82f6'));
      this.charts.mem.setOption(this.gaugeOption(this.memoryUsage, 'Memory', '#10b981'));
    },
    drawHeatmap() {
      const d = this.serverData;
      const hours = Array.from({ length: 24 }, (_, h) => `${h}:00`);
      const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
      this.charts.heat = echarts.init(this.$refs.heat);
      this.charts.heat.setOption({
        ...this.common(),
        grid: { left: 48, right: 20, top: 20, bottom: 45 },
        xAxis: { type: 'category', data: hours },
        yAxis: { type: 'category', data: days },
        visualMap: { min: 0, max: 100, orient: 'horizontal', left: 'center', bottom: 0,
                     textStyle: { color: this.colors().text } },
        series: [{ type: 'heatmap', data: d.heat }],
      });
    },
    drawScatter() {
      const d = this.serverData;
      this.charts.scatter = echarts.init(this.$refs.scatter);
      this.charts.scatter.setOption({
        ...this.common(),
        xAxis: { type: 'value', splitLine: { lineStyle: { color: this.colors().border } } },
        yAxis: { type: 'value', splitLine: { lineStyle: { color: this.colors().border } } },
        series: Object.entries(d.scatter || {}).map(([name, points]) => ({ name, type: 'scatter', data: points })),
      });
    },
    drawCandle() {
      const d = this.serverData;
      this.charts.candle = echarts.init(this.$refs.candle);
      this.charts.candle.setOption({
        ...this.common(),
        xAxis: { type: 'category', data: d.candle.map((_, i) => `D${i + 1}`) },
        yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { color: this.colors().border } } },
        series: [{ type: 'candlestick', data: d.candle }],
      });
    },
    refreshTimestamp() {
      const d = new Date();
      this.timestamp = d.toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' })
        + ' · ' + d.toLocaleTimeString();
    },
  },
};
</script>
