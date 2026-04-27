<template>
  <main class="min-h-screen space-y-5 bg-slate-50 p-6 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
    <header class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="dash-title text-3xl font-black tracking-tight">Analytics Dashboard</h1>
        <p class="text-sm text-slate-500 dark:text-slate-400">{{ timestamp }}</p>
      </div>
      <div class="flex gap-2">
        <button class="rounded-xl bg-blue-600 px-4 py-2 font-bold text-white" type="button" @click="refresh">Refresh</button>
        <button class="rounded-xl border border-slate-300 px-4 py-2 font-bold dark:border-slate-700" type="button" @click="showComparison = !showComparison">
          {{ showComparison ? "Hide YoY" : "Compare YoY" }}
        </button>
      </div>
    </header>

    <section class="grid gap-4 rounded-2xl border border-slate-200 bg-white/80 p-4 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900/80 lg:grid-cols-[1fr_auto_1.5fr_auto]">
      <div>
        <p class="text-xs font-bold uppercase tracking-widest text-slate-500">Regions</p>
        <div class="mt-2 flex flex-wrap gap-2">
          <button
            v-for="region in regions"
            :key="region"
            :class="chipClass(selectedRegions.includes(region))"
            type="button"
            @click="toggle(selectedRegions, region)"
          >
            {{ region }}
          </button>
        </div>
      </div>
      <label class="block">
        <span class="text-xs font-bold uppercase tracking-widest text-slate-500">Date range</span>
        <select v-model="dateRange" class="mt-2 rounded-xl border border-slate-300 bg-transparent px-3 py-2 text-inherit dark:border-slate-700" @change="drawAll">
          <option v-for="range in dateRanges" :key="range">{{ range }}</option>
        </select>
      </label>
      <div>
        <p class="text-xs font-bold uppercase tracking-widest text-slate-500">Products</p>
        <div class="mt-2 flex flex-wrap gap-2">
          <button
            v-for="product in products"
            :key="product"
            :class="chipClass(selectedProducts.includes(product))"
            type="button"
            @click="toggle(selectedProducts, product)"
          >
            {{ product }}
          </button>
        </div>
      </div>
      <label class="block">
        <span class="text-xs font-bold uppercase tracking-widest text-slate-500">Search</span>
        <input v-model="searchText" class="mt-2 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 text-inherit outline-none dark:border-slate-700" placeholder="laptop" @input="drawAll">
      </label>
    </section>

    <section class="grid gap-4 md:grid-cols-4">
      <article v-for="item in kpis" :key="item.key" class="rounded-2xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
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
      <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900 xl:col-span-2">
        <h2 class="mb-3 font-bold">Revenue & Orders Trend</h2>
        <div id="chart-line" ref="line" class="h-72 w-full"></div>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="mb-3 font-bold">Product Sales</h2>
        <div id="chart-bar" ref="bar" class="h-72 w-full"></div>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="mb-3 font-bold">Sales Distribution</h2>
        <div id="chart-pie" ref="pie" class="h-64 w-full"></div>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="mb-3 font-bold">Regional Performance</h2>
        <div id="chart-radar" ref="radar" class="h-64 w-full"></div>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="mb-3 font-bold">System Health</h2>
        <div class="grid grid-cols-2 gap-2">
          <div id="chart-cpu" ref="cpu" class="h-56 w-full"></div>
          <div id="chart-mem" ref="mem" class="h-56 w-full"></div>
        </div>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="mb-3 font-bold">Weekly Activity</h2>
        <div id="chart-heat" ref="heat" class="h-64 w-full"></div>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="mb-3 font-bold">Customer Segments</h2>
        <div id="chart-scatter" ref="scatter" class="h-64 w-full"></div>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-xl shadow-slate-900/5 dark:border-slate-800 dark:bg-slate-900">
        <h2 class="mb-3 font-bold">Stock Performance</h2>
        <div id="chart-candle" ref="candle" class="h-64 w-full"></div>
      </article>
    </section>
  </main>
</template>

<script>
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const PRODUCT_COLORS = {
  Laptops: '#3b82f6',
  Phones: '#10b981',
  Tablets: '#f59e0b',
  Watches: '#ef4444',
  Headphones: '#8b5cf6',
};

export default {
  data() {
    return {
      charts: {},
      dateRange: 'Last 12 months',
      dateRanges: ['Last 7 days', 'Last 30 days', 'Last 3 months', 'Last 12 months', 'Year to date'],
      products: ['Laptops', 'Phones', 'Tablets', 'Watches', 'Headphones'],
      regions: ['North', 'South', 'East', 'West', 'Central'],
      searchText: '',
      selectedProducts: ['Laptops', 'Phones', 'Tablets', 'Watches', 'Headphones'],
      selectedRegions: ['North', 'South', 'East', 'West', 'Central'],
      showComparison: false,
      timestamp: '—',
      themeObserver: null,
      metricTimer: null,
      cpuUsage: 45,
      memoryUsage: 62,
    };
  },
  computed: {
    kpis() {
      const scale = this.scale();
      return [
        { key: 'revenue', label: 'Revenue', value: '$' + Math.floor(124500 * scale).toLocaleString(), delta: '+12.5%', badge: 'UP', color: 'text-blue-500' },
        { key: 'orders', label: 'Orders', value: Math.floor(1847 * scale).toLocaleString(), delta: '+8.2%', badge: 'ORD', color: 'text-emerald-500' },
        { key: 'customers', label: 'Customers', value: Math.floor(892 * scale).toLocaleString(), delta: '+15.3%', badge: 'USR', color: 'text-purple-500' },
        { key: 'conversion', label: 'Conversion', value: '3.24%', delta: '+0.8%', badge: 'CVR', color: 'text-amber-500' },
      ];
    },
  },
  async mounted() {
    await window.__stage.load('echarts');
    this.refreshTimestamp();
    await this.$nextTick();
    this.drawAll();
    this.metricTimer = setInterval(() => {
      this.cpuUsage = Math.max(10, Math.min(95, this.cpuUsage + (Math.random() * 10 - 5)));
      this.memoryUsage = Math.max(20, Math.min(90, this.memoryUsage + (Math.random() * 6 - 3)));
      this.drawGauges();
    }, 2000);
    this.resizeObserver = new ResizeObserver(() => Object.values(this.charts).forEach((c) => c.resize()));
    this.resizeObserver.observe(this.$el);
    this.themeObserver = new MutationObserver(() => this.drawAll());
    this.themeObserver.observe(document.body, { attributes: true, attributeFilter: ['class'] });
  },
  beforeUnmount() {
    clearInterval(this.metricTimer);
    this.resizeObserver?.disconnect();
    this.themeObserver?.disconnect();
    Object.values(this.charts).forEach((c) => c.dispose());
  },
  methods: {
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
    dataSet() {
      const ranges = {
        'Last 7 days': ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],
        'Last 30 days': Array.from({length: 30}, (_, i) => `Day ${i + 1}`),
        'Last 3 months': Array.from({length: 12}, (_, i) => `Week ${i + 1}`),
        'Last 12 months': MONTHS,
        'Year to date': MONTHS,
      };
      const labels = ranges[this.dateRange];
      const base = labels.map((_, i) => 9000 + Math.round(Math.sin(i * 0.8) * 2200 + Math.random() * 1800));
      const orders = labels.map((_, i) => 120 + Math.round(Math.cos(i * 0.7) * 35 + Math.random() * 40));
      const products = Object.fromEntries(this.products
        .filter((p) => this.selectedProducts.includes(p))
        .filter((p) => !this.searchText || p.toLowerCase().includes(this.searchText.toLowerCase()))
        .map((p, i) => [p, Math.floor((9000 + i * 3100) * this.scale())]));
      return { labels, revenue: base.map((v) => Math.floor(v * this.scale())), orders, products };
    },
    drawAll() {
      if (!window.echarts) return;
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
      const data = this.dataSet();
      const series = [
        { name: 'Revenue', type: 'line', smooth: true, areaStyle: { opacity: 0.25 }, data: data.revenue, itemStyle: { color: '#3b82f6' } },
        { name: 'Orders', type: 'line', smooth: true, yAxisIndex: 1, data: data.orders, itemStyle: { color: '#10b981' } },
      ];
      if (this.showComparison) {
        series.push({ name: 'Revenue LY', type: 'line', smooth: true, lineStyle: { type: 'dashed' }, data: data.revenue.map((v) => Math.floor(v * 0.86)), itemStyle: { color: '#60a5fa' } });
      }
      this.charts.line = echarts.init(this.$refs.line);
      this.charts.line.setOption({
        ...this.common(),
        tooltip: { ...this.common().tooltip, trigger: 'axis' },
        legend: { ...this.common().legend, top: 5 },
        grid: { left: 50, right: 40, top: 42, bottom: 30 },
        xAxis: { type: 'category', data: data.labels, axisLine: { lineStyle: { color: c.muted } } },
        yAxis: [
          { type: 'value', axisLine: { lineStyle: { color: c.muted } }, splitLine: { lineStyle: { color: c.border } } },
          { type: 'value', axisLine: { lineStyle: { color: c.muted } }, splitLine: { show: false } },
        ],
        series,
      });
    },
    drawBar() {
      const c = this.colors();
      const data = this.dataSet();
      this.charts.bar = echarts.init(this.$refs.bar);
      this.charts.bar.setOption({
        ...this.common(),
        tooltip: { ...this.common().tooltip, trigger: 'axis' },
        grid: { left: 50, right: 20, top: 20, bottom: 30 },
        xAxis: { type: 'category', data: Object.keys(data.products), axisLine: { lineStyle: { color: c.muted } } },
        yAxis: { type: 'value', splitLine: { lineStyle: { color: c.border } } },
        series: [{ type: 'bar', data: Object.entries(data.products).map(([k, v]) => ({ value: v, itemStyle: { color: PRODUCT_COLORS[k], borderRadius: [4, 4, 0, 0] } })) }],
      });
    },
    drawPie() {
      const data = this.dataSet();
      this.charts.pie = echarts.init(this.$refs.pie);
      this.charts.pie.setOption({
        ...this.common(),
        tooltip: { ...this.common().tooltip, trigger: 'item' },
        series: [{ type: 'pie', radius: ['42%', '72%'], label: { show: false }, data: Object.entries(data.products).map(([name, value]) => ({ name, value })) }],
      });
    },
    drawRadar() {
      this.charts.radar = echarts.init(this.$refs.radar);
      this.charts.radar.setOption({
        ...this.common(),
        radar: { indicator: ['Sales', 'Marketing', 'Support', 'Dev', 'Ops'].map((name) => ({ name, max: 100 })), splitLine: { lineStyle: { color: this.colors().border } } },
        series: [{ type: 'radar', areaStyle: { opacity: 0.2 }, data: this.selectedRegions.slice(0, 3).map((name, i) => ({ name, value: [70 + i * 4, 44 + i * 8, 62, 80 - i * 5, 55 + i * 6] })) }],
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
      const hours = Array.from({length: 24}, (_, h) => `${h}:00`);
      const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
      const data = [];
      for (let d = 0; d < 7; d++) for (let h = 0; h < 24; h++) data.push([h, d, Math.floor(Math.random() * 100)]);
      this.charts.heat = echarts.init(this.$refs.heat);
      this.charts.heat.setOption({
        ...this.common(),
        grid: { left: 48, right: 20, top: 20, bottom: 45 },
        xAxis: { type: 'category', data: hours },
        yAxis: { type: 'category', data: days },
        visualMap: { min: 0, max: 100, orient: 'horizontal', left: 'center', bottom: 0, textStyle: { color: this.colors().text } },
        series: [{ type: 'heatmap', data }],
      });
    },
    drawScatter() {
      const cloud = (cx, cy) => Array.from({length: 36}, () => [cx + Math.random() * 24 - 12, cy + Math.random() * 24 - 12]);
      this.charts.scatter = echarts.init(this.$refs.scatter);
      this.charts.scatter.setOption({
        ...this.common(),
        xAxis: { type: 'value', splitLine: { lineStyle: { color: this.colors().border } } },
        yAxis: { type: 'value', splitLine: { lineStyle: { color: this.colors().border } } },
        series: [
          { name: 'Enterprise', type: 'scatter', data: cloud(70, 70) },
          { name: 'SMB', type: 'scatter', data: cloud(50, 45) },
          { name: 'Consumer', type: 'scatter', data: cloud(30, 60) },
        ],
      });
    },
    drawCandle() {
      let price = 100;
      const data = Array.from({length: 30}, () => {
        const close = price + Math.random() * 10 - 5;
        const item = [price, close, Math.min(price, close) - 2, Math.max(price, close) + 2];
        price = close;
        return item;
      });
      this.charts.candle = echarts.init(this.$refs.candle);
      this.charts.candle.setOption({
        ...this.common(),
        xAxis: { type: 'category', data: data.map((_, i) => `D${i + 1}`) },
        yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { color: this.colors().border } } },
        series: [{ type: 'candlestick', data }],
      });
    },
    refresh() {
      this.refreshTimestamp();
      this.drawAll();
    },
    refreshTimestamp() {
      const d = new Date();
      this.timestamp = d.toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' }) + ' · ' + d.toLocaleTimeString();
    },
    scale() {
      return (this.selectedRegions.length / this.regions.length) * (this.selectedProducts.length / this.products.length);
    },
    toggle(list, value) {
      const i = list.indexOf(value);
      if (i >= 0) list.splice(i, 1);
      else list.push(value);
      this.drawAll();
    },
  },
};
</script>
