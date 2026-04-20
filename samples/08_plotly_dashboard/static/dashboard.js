window.__stageViews = window.__stageViews || {};
window.__stageViews.dashboard = {
  async mount(target) {
    await window.__stage.load('echarts');

    const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const PRODUCTS = ['Laptops', 'Phones', 'Tablets', 'Watches', 'Headphones'];
    const REGIONS = ['North', 'South', 'East', 'West', 'Central'];
    const PRODUCT_COLORS = {
      Laptops:    '#3b82f6',
      Phones:     '#10b981',
      Tablets:    '#f59e0b',
      Watches:    '#ef4444',
      Headphones: '#8b5cf6',
    };
    const DATE_RANGES = {
      'Last 7 days':     { points: 7,  labels: ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'] },
      'Last 30 days':    { points: 30, labels: Array.from({length: 30}, (_, i) => `Day ${i+1}`) },
      'Last 3 months':   { points: 12, labels: Array.from({length: 12}, (_, i) => `Week ${i+1}`) },
      'Last 12 months':  { points: 12, labels: MONTHS },
      'Year to date':    { points: 12, labels: MONTHS },
    };

    const rand = (seed) => {
      let s = seed >>> 0;
      return () => { s = (s * 1103515245 + 12345) & 0x7fffffff; return s / 0x7fffffff; };
    };

    const data = {
      revenue: 124500,
      orders: 1847,
      customers: 892,
      conversionRate: 3.24,
      cpuUsage: 45,
      memoryUsage: 62,
      monthlySales:  Array.from({length: 12}, () => Math.floor(8000 + Math.random() * 7000)),
      monthlyOrders: Array.from({length: 12}, () => Math.floor(100 + Math.random() * 200)),
      productSales:  Object.fromEntries(PRODUCTS.map((p) => [p, Math.floor(5000 + Math.random() * 20000)])),
      regionalMetrics: Object.fromEntries(REGIONS.map((r) => [r, {
        sales: Math.floor(10000 + Math.random() * 20000),
        marketing: Math.floor(5000 + Math.random() * 10000),
        support: Math.floor(3000 + Math.random() * 7000),
        development: Math.floor(8000 + Math.random() * 12000),
        operations: Math.floor(4000 + Math.random() * 8000),
      }])),
      selectedRegions: [...REGIONS],
      selectedProducts: [...PRODUCTS],
      dateRange: 'Last 12 months',
      showComparison: false,
      searchText: '',
    };

    const isDark = () => document.body.classList.contains('body--dark');
    const bg      = () => isDark() ? '#0f172a' : '#f8fafc';
    const surface = () => isDark() ? '#1e293b' : '#ffffff';
    const border  = () => isDark() ? '#334155' : '#e2e8f0';
    const txt     = () => isDark() ? '#f8fafc' : '#1e293b';
    const muted   = () => isDark() ? '#94a3b8' : '#64748b';

    target.innerHTML = `
      <div id="dash-root" class="dash-root">
        <div class="dash-head">
          <div>
            <div class="dash-title">Analytics Dashboard</div>
            <div class="dash-sub" id="dash-timestamp">—</div>
          </div>
          <div class="dash-head-right">
            <button class="dash-iconbtn" id="btn-refresh" title="Refresh">
              <q-icon name="refresh" size="20px"></q-icon>
            </button>
            <button class="dash-iconbtn" id="btn-settings" title="Settings">
              <q-icon name="settings" size="20px"></q-icon>
            </button>
          </div>
        </div>

        <div class="dash-filters">
          <div class="f-col">
            <div class="f-label">Regions</div>
            <div class="chips" id="region-chips"></div>
          </div>
          <div class="f-col">
            <div class="f-label">Date Range</div>
            <select class="f-select" id="date-range"></select>
          </div>
          <div class="f-col f-grow">
            <div class="f-label">Products</div>
            <div class="chips" id="product-chips"></div>
          </div>
          <div class="f-col">
            <div class="f-label">Options</div>
            <label class="f-switch">
              <input type="checkbox" id="compare-yoy"><span>Compare YoY</span>
            </label>
          </div>
          <div class="f-col">
            <div class="f-label">Search</div>
            <input type="text" class="f-input" id="search-input" placeholder="e.g. laptop…">
          </div>
        </div>

        <div class="dash-kpis">
          ${kpi('revenue',    'Revenue',    'trending_up',  '#60a5fa', '+12.5%')}
          ${kpi('orders',     'Orders',     'shopping_cart','#34d399', '+8.2%')}
          ${kpi('customers',  'Customers',  'people',       '#c084fc', '+15.3%')}
          ${kpi('conversion', 'Conversion', 'speed',        '#fbbf24', '+0.8%')}
        </div>

        <div class="dash-row">
          <div class="dash-card grow-2">
            <div class="card-title">Revenue & Orders Trend</div>
            <div id="chart-line" class="chart-box"></div>
          </div>
          <div class="dash-card grow-1">
            <div class="card-title">Product Sales</div>
            <div id="chart-bar" class="chart-box"></div>
          </div>
        </div>

        <div class="dash-row">
          <div class="dash-card grow-1">
            <div class="card-title">Sales Distribution</div>
            <div id="chart-pie" class="chart-box"></div>
          </div>
          <div class="dash-card grow-1">
            <div class="card-title">Regional Performance</div>
            <div id="chart-radar" class="chart-box"></div>
          </div>
          <div class="dash-card grow-1 gauge-card">
            <div class="card-title">System Health</div>
            <div class="gauge-row">
              <div id="chart-cpu" class="gauge-box"></div>
              <div id="chart-mem" class="gauge-box"></div>
            </div>
          </div>
        </div>

        <div class="dash-row">
          <div class="dash-card grow-1">
            <div class="card-title">Weekly Activity</div>
            <div id="chart-heat" class="chart-box"></div>
          </div>
          <div class="dash-card grow-1">
            <div class="card-title">Customer Segments</div>
            <div id="chart-scatter" class="chart-box"></div>
          </div>
        </div>

        <div class="dash-row">
          <div class="dash-card grow-1">
            <div class="card-title">Stock Performance</div>
            <div id="chart-candle" class="chart-box"></div>
          </div>
        </div>

        <div id="settings-dialog" class="dialog-backdrop hidden">
          <div class="dialog-card">
            <div class="dialog-title">Dashboard Settings</div>
            <div class="dialog-body">
              <label class="d-field">
                <span>Alert Threshold (%)</span>
                <input type="range" id="alert-threshold" min="50" max="100" value="80">
                <output id="alert-threshold-out">80</output>
              </label>
              <label class="d-field">
                <span>Refresh interval (s)</span>
                <input type="number" id="refresh-interval" min="1" max="60" value="5" step="1">
              </label>
              <div class="d-field">
                <span>Default chart</span>
                <div class="d-radio">
                  <label><input type="radio" name="ct" value="line" checked>line</label>
                  <label><input type="radio" name="ct" value="bar">bar</label>
                  <label><input type="radio" name="ct" value="area">area</label>
                </div>
              </div>
            </div>
            <div class="dialog-actions">
              <button id="settings-cancel">Cancel</button>
              <button id="settings-apply" class="primary">Apply</button>
            </div>
          </div>
        </div>
      </div>
      <style>
        .dash-root { padding: 20px 24px; display: flex; flex-direction: column; gap: 18px;
          min-height: 100%; color: var(--dash-text); }
        .dash-head { display: flex; align-items: center; justify-content: space-between; }
        .dash-title { font-size: 26px; font-weight: 700; letter-spacing: -0.01em; }
        .dash-sub { font-size: 13px; opacity: 0.55; margin-top: 2px; }
        .dash-head-right { display: flex; gap: 6px; }
        .dash-iconbtn { width: 38px; height: 38px; border-radius: 50%; border: 0;
          background: transparent; color: inherit; cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          transition: background .1s; }
        .dash-iconbtn:hover { background: rgba(128,128,128,.12); }

        .dash-filters { display: flex; flex-wrap: wrap; gap: 22px; padding: 14px 18px;
          border-radius: 10px; background: var(--surface);
          border: 1px solid var(--border); }
        .f-col { display: flex; flex-direction: column; gap: 6px; }
        .f-grow { flex: 1; min-width: 260px; }
        .f-label { font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
          opacity: 0.55; }
        .f-select, .f-input { padding: 6px 10px; font-size: 13px;
          background: transparent; color: inherit;
          border: 1px solid var(--border); border-radius: 6px; outline: none;
          min-width: 160px; }
        .f-switch { display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer; }
        .f-switch input { accent-color: #3b82f6; }
        .chips { display: flex; flex-wrap: wrap; gap: 6px; }
        .chip { padding: 4px 10px; border-radius: 999px; font-size: 12px; cursor: pointer;
          border: 1px solid var(--border); user-select: none; transition: all .1s; }
        .chip.sel { background: rgba(59, 130, 246, 0.18); color: #3b82f6;
          border-color: rgba(59, 130, 246, 0.6); }

        .dash-kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
        .kpi { padding: 16px 18px; border-radius: 10px; background: var(--surface);
          border: 1px solid var(--border); display: flex; align-items: start;
          justify-content: space-between; }
        .kpi-label { font-size: 12px; opacity: 0.6; text-transform: uppercase; letter-spacing: .05em; }
        .kpi-value { font-size: 26px; font-weight: 700; margin-top: 4px;
          font-variant-numeric: tabular-nums; }
        .kpi-delta { font-size: 12px; color: #10b981; margin-top: 2px; }
        .kpi-icon { font-size: 28px; opacity: 0.8; }

        .dash-row { display: flex; gap: 14px; }
        .dash-card { background: var(--surface); border: 1px solid var(--border);
          border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; }
        .card-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; opacity: 0.85; }
        .chart-box { width: 100%; height: 240px; }
        .grow-1 { flex: 1; }
        .grow-2 { flex: 2; }
        .gauge-card .gauge-row { display: flex; gap: 8px; }
        .gauge-box { flex: 1; height: 200px; }

        .dialog-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.5);
          display: flex; align-items: center; justify-content: center; z-index: 50; }
        .dialog-backdrop.hidden { display: none; }
        .dialog-card { width: 420px; background: var(--surface); border: 1px solid var(--border);
          border-radius: 12px; padding: 20px; }
        .dialog-title { font-size: 17px; font-weight: 600; margin-bottom: 14px; }
        .dialog-body { display: flex; flex-direction: column; gap: 14px; }
        .d-field { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 8px;
          font-size: 13px; }
        .d-field input[type=range] { width: 100%; grid-column: 1 / -1; accent-color: #3b82f6; }
        .d-field input[type=number] { padding: 5px 8px; background: transparent; color: inherit;
          border: 1px solid var(--border); border-radius: 5px; outline: none; width: 80px; }
        .d-radio { display: flex; gap: 10px; grid-column: 1 / -1; font-size: 13px; }
        .d-radio label { display: flex; gap: 4px; align-items: center; cursor: pointer; }
        .dialog-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
        .dialog-actions button { padding: 6px 14px; border: 1px solid var(--border);
          background: transparent; color: inherit; border-radius: 6px; cursor: pointer;
          font-size: 13px; }
        .dialog-actions button.primary { background: #3b82f6; border-color: #3b82f6;
          color: #fff; }

        .dash-root {
          --surface: #ffffff; --border: #e2e8f0; --dash-text: #1e293b;
        }
        .body--dark .dash-root {
          --surface: #1e293b; --border: #334155; --dash-text: #f8fafc;
        }
      </style>`;

    function kpi(key, title, icon, color, delta) {
      return `
        <div class="kpi">
          <div>
            <div class="kpi-label">${title}</div>
            <div class="kpi-value" id="kpi-${key}">—</div>
            <div class="kpi-delta">${delta}</div>
          </div>
          <q-icon name="${icon}" size="28px" style="color:${color}"></q-icon>
        </div>`;
    }

    const charts = {};
    const themeOpts = () => ({
      textStyle: { color: txt(), fontFamily: '-apple-system, system-ui, sans-serif' },
      legend:  { textStyle: { color: txt() } },
      tooltip: { backgroundColor: surface(), borderColor: border(), textStyle: { color: txt() } },
    });

    function filtered() {
      const cfg = DATE_RANGES[data.dateRange];
      const points = cfg.points, labels = cfg.labels;
      const rnd = rand(points);
      let baseSales, baseOrders;
      if (data.dateRange === 'Last 7 days')        { baseSales = Array.from({length: points}, () => Math.floor(800 + rnd() * 700)); baseOrders = Array.from({length: points}, () => Math.floor(10 + rnd() * 30)); }
      else if (data.dateRange === 'Last 30 days')  { baseSales = Array.from({length: points}, () => Math.floor(600 + rnd() * 600)); baseOrders = Array.from({length: points}, () => Math.floor(8 + rnd() * 22)); }
      else if (data.dateRange === 'Last 3 months') { baseSales = Array.from({length: points}, () => Math.floor(2000 + rnd() * 2000)); baseOrders = Array.from({length: points}, () => Math.floor(25 + rnd() * 55)); }
      else { baseSales = data.monthlySales.slice(); baseOrders = data.monthlyOrders.slice(); }

      const regionScale  = data.selectedRegions.length  / REGIONS.length;
      const productScale = data.selectedProducts.length / PRODUCTS.length;
      const combined = regionScale * productScale;

      const sales  = baseSales.map((s) => Math.floor(s * combined));
      const orders = baseOrders.map((o) => Math.floor(o * combined));
      const products = {};
      for (const [k, v] of Object.entries(data.productSales)) {
        if (!data.selectedProducts.includes(k)) continue;
        if (data.searchText && !k.toLowerCase().includes(data.searchText.toLowerCase())) continue;
        products[k] = Math.floor(v * regionScale);
      }
      return { labels, sales, orders, products };
    }

    function lineSeries(f) {
      const s = [
        { name: 'Revenue', type: 'line', smooth: true, areaStyle: { opacity: 0.25 },
          data: f.sales, itemStyle: { color: '#3b82f6' } },
        { name: 'Orders',  type: 'line', smooth: true, yAxisIndex: 1,
          data: f.orders, itemStyle: { color: '#10b981' } },
      ];
      if (data.showComparison) {
        const rnd = rand(42);
        s.push(
          { name: 'Revenue (LY)', type: 'line', smooth: true, lineStyle: { type: 'dashed' },
            data: f.sales.map((v) => Math.floor(v * (0.80 + rnd() * 0.15))),
            itemStyle: { color: '#60a5fa' } },
          { name: 'Orders (LY)', type: 'line', smooth: true, yAxisIndex: 1, lineStyle: { type: 'dashed' },
            data: f.orders.map((v) => Math.floor(v * (0.80 + rnd() * 0.15))),
            itemStyle: { color: '#34d399' } },
        );
      }
      return s;
    }

    function createLine() {
      const f = filtered();
      const el = target.querySelector('#chart-line');
      const c = echarts.init(el, null, { renderer: 'canvas' });
      c.setOption({
        ...themeOpts(),
        tooltip: { ...themeOpts().tooltip, trigger: 'axis' },
        legend: { ...themeOpts().legend, top: 5 },
        grid: { left: 50, right: 40, top: 40, bottom: 30 },
        xAxis: { type: 'category', data: f.labels, axisLine: { lineStyle: { color: muted() } } },
        yAxis: [
          { type: 'value', name: 'Revenue ($)', position: 'left',  axisLine: { lineStyle: { color: muted() } }, splitLine: { lineStyle: { color: border() } } },
          { type: 'value', name: 'Orders',      position: 'right', axisLine: { lineStyle: { color: muted() } }, splitLine: { show: false } },
        ],
        series: lineSeries(f),
      });
      charts.line = c;
    }

    function createBar() {
      const f = filtered();
      const el = target.querySelector('#chart-bar');
      const c = echarts.init(el, null, { renderer: 'canvas' });
      c.setOption({
        ...themeOpts(),
        tooltip: { ...themeOpts().tooltip, trigger: 'axis' },
        grid: { left: 50, right: 20, top: 20, bottom: 30 },
        xAxis: { type: 'category', data: Object.keys(f.products), axisLine: { lineStyle: { color: muted() } } },
        yAxis: { type: 'value', name: 'Sales ($)', axisLine: { lineStyle: { color: muted() } }, splitLine: { lineStyle: { color: border() } } },
        series: [{
          type: 'bar', barWidth: '60%',
          data: Object.entries(f.products).map(([k, v]) => ({
            value: v, itemStyle: { color: PRODUCT_COLORS[k] || '#888', borderRadius: [4, 4, 0, 0] },
          })),
        }],
      });
      charts.bar = c;
    }

    function createPie() {
      const f = filtered();
      const el = target.querySelector('#chart-pie');
      const c = echarts.init(el, null, { renderer: 'canvas' });
      c.setOption({
        ...themeOpts(),
        tooltip: { ...themeOpts().tooltip, trigger: 'item', formatter: '{b}: ${c} ({d}%)' },
        legend: { ...themeOpts().legend, orient: 'vertical', right: 10, top: 'center' },
        series: [{
          type: 'pie', radius: ['40%', '70%'], center: ['40%', '50%'],
          itemStyle: { borderRadius: 8, borderColor: surface(), borderWidth: 2 },
          label: { show: false },
          emphasis: { label: { show: true, fontSize: 14 } },
          data: Object.entries(f.products).map(([name, value]) => ({ value, name })),
        }],
      });
      charts.pie = c;
    }

    function createRadar() {
      const el = target.querySelector('#chart-radar');
      const c = echarts.init(el, null, { renderer: 'canvas' });
      const indicators = [
        { name: 'Sales',       max: 35000 },
        { name: 'Marketing',   max: 20000 },
        { name: 'Support',     max: 15000 },
        { name: 'Development', max: 25000 },
        { name: 'Operations',  max: 15000 },
      ];
      const entries = Object.entries(data.regionalMetrics).slice(0, 3);
      c.setOption({
        ...themeOpts(),
        tooltip: { ...themeOpts().tooltip, trigger: 'item' },
        legend: { ...themeOpts().legend, data: entries.map(([r]) => r), top: 5 },
        radar: { indicator: indicators, center: ['50%', '55%'], radius: '60%',
          axisName: { color: txt() },
          splitLine: { lineStyle: { color: border() } },
          axisLine: { lineStyle: { color: border() } },
          splitArea: { show: false },
        },
        series: [{
          type: 'radar', areaStyle: { opacity: 0.2 },
          data: entries.map(([r, m]) => ({
            name: r, value: [m.sales, m.marketing, m.support, m.development, m.operations],
          })),
        }],
      });
      charts.radar = c;
    }

    function gaugeOpt(value, title, color) {
      return {
        series: [{
          type: 'gauge', startAngle: 200, endAngle: -20, min: 0, max: 100,
          itemStyle: { color },
          progress: { show: true, width: 18 },
          pointer: { show: false },
          axisLine: { lineStyle: { width: 18, color: [[1, border()]] } },
          axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
          title: { show: true, offsetCenter: [0, '70%'], fontSize: 12, color: muted() },
          detail: {
            valueAnimation: true, fontSize: 24, fontWeight: 'bold',
            offsetCenter: [0, '0%'], formatter: '{value}%', color: txt(),
          },
          data: [{ value, name: title }],
        }],
      };
    }

    function createGauges() {
      charts.cpu = echarts.init(target.querySelector('#chart-cpu'), null, { renderer: 'canvas' });
      charts.cpu.setOption(gaugeOpt(data.cpuUsage, 'CPU', '#3b82f6'));
      charts.mem = echarts.init(target.querySelector('#chart-mem'), null, { renderer: 'canvas' });
      charts.mem.setOption(gaugeOpt(data.memoryUsage, 'Memory', '#10b981'));
    }

    function createHeatmap() {
      const el = target.querySelector('#chart-heat');
      const c = echarts.init(el, null, { renderer: 'canvas' });
      const rnd = rand(123);
      const hours = Array.from({length: 24}, (_, h) => `${h}:00`);
      const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
      const heatData = [];
      for (let d = 0; d < 7; d++) for (let h = 0; h < 24; h++) heatData.push([h, d, Math.floor(rnd() * 100)]);
      c.setOption({
        ...themeOpts(),
        tooltip: { ...themeOpts().tooltip, position: 'top' },
        grid: { left: 50, right: 20, top: 20, bottom: 50 },
        xAxis: { type: 'category', data: hours, axisLine: { lineStyle: { color: muted() } } },
        yAxis: { type: 'category', data: days, axisLine: { lineStyle: { color: muted() } } },
        visualMap: {
          min: 0, max: 100, orient: 'horizontal', left: 'center', bottom: 0,
          textStyle: { color: txt() },
          inRange: { color: ['#1e3a5f', '#3b82f6', '#60a5fa'] },
        },
        series: [{ type: 'heatmap', data: heatData }],
      });
      charts.heat = c;
    }

    function createScatter() {
      const el = target.querySelector('#chart-scatter');
      const c = echarts.init(el, null, { renderer: 'canvas' });
      const rnd = rand(456);
      const gauss = (m, s) => m + (rnd() + rnd() + rnd() + rnd() + rnd() + rnd() - 3) * s;
      c.setOption({
        ...themeOpts(),
        tooltip: { ...themeOpts().tooltip, trigger: 'item' },
        legend: { ...themeOpts().legend, data: ['Enterprise', 'SMB', 'Consumer'], top: 5 },
        grid: { left: 50, right: 20, top: 40, bottom: 30 },
        xAxis: { type: 'value', name: 'Engagement', axisLine: { lineStyle: { color: muted() } }, splitLine: { lineStyle: { color: border() } } },
        yAxis: { type: 'value', name: 'Satisfaction', axisLine: { lineStyle: { color: muted() } }, splitLine: { lineStyle: { color: border() } } },
        series: [
          { name: 'Enterprise', type: 'scatter', symbolSize: 10, data: Array.from({length: 50}, () => [gauss(50, 15), gauss(50, 15)]) },
          { name: 'SMB',        type: 'scatter', symbolSize: 10, data: Array.from({length: 40}, () => [gauss(70, 10), gauss(30, 10)]) },
          { name: 'Consumer',   type: 'scatter', symbolSize: 10, data: Array.from({length: 30}, () => [gauss(30, 10), gauss(70, 10)]) },
        ],
      });
      charts.scatter = c;
    }

    function createCandle() {
      const el = target.querySelector('#chart-candle');
      const c = echarts.init(el, null, { renderer: 'canvas' });
      const now = new Date();
      const dates = Array.from({length: 30}, (_, i) => {
        const d = new Date(now); d.setDate(d.getDate() - (30 - i));
        return `${(d.getMonth() + 1).toString().padStart(2, '0')}/${d.getDate().toString().padStart(2, '0')}`;
      });
      const candleData = [];
      let price = 100;
      for (let i = 0; i < 30; i++) {
        const close = price + (Math.random() * 10 - 5);
        const low  = Math.min(price, close) - Math.random() * 3;
        const high = Math.max(price, close) + Math.random() * 3;
        candleData.push([price, close, low, high]);
        price = close;
      }
      c.setOption({
        ...themeOpts(),
        tooltip: { ...themeOpts().tooltip, trigger: 'axis', axisPointer: { type: 'cross' } },
        grid: { left: 50, right: 20, top: 20, bottom: 30 },
        xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: muted() } } },
        yAxis: { type: 'value', scale: true, axisLine: { lineStyle: { color: muted() } }, splitLine: { lineStyle: { color: border() } } },
        series: [{
          type: 'candlestick', data: candleData,
          itemStyle: {
            color: '#10b981', color0: '#ef4444',
            borderColor: '#10b981', borderColor0: '#ef4444',
          },
        }],
      });
      charts.candle = c;
    }

    function updateAll() {
      updateKPIs();
      const f = filtered();
      if (charts.line) charts.line.setOption({
        xAxis: { data: f.labels },
        series: lineSeries(f),
      });
      if (charts.bar) charts.bar.setOption({
        xAxis: { data: Object.keys(f.products) },
        series: [{ data: Object.entries(f.products).map(([k, v]) => ({
          value: v, itemStyle: { color: PRODUCT_COLORS[k] || '#888', borderRadius: [4, 4, 0, 0] },
        })) }],
      });
      if (charts.pie) charts.pie.setOption({
        series: [{ data: Object.entries(f.products).map(([name, value]) => ({ value, name })) }],
      });
    }

    function scale() {
      return (data.selectedRegions.length / REGIONS.length) *
             (data.selectedProducts.length / PRODUCTS.length);
    }

    function updateKPIs() {
      const s = scale();
      target.querySelector('#kpi-revenue').textContent    = '$' + Math.floor(data.revenue * s).toLocaleString();
      target.querySelector('#kpi-orders').textContent     = Math.floor(data.orders * s).toLocaleString();
      target.querySelector('#kpi-customers').textContent  = Math.floor(data.customers * s).toLocaleString();
      target.querySelector('#kpi-conversion').textContent = data.conversionRate.toFixed(2) + '%';
    }

    const regionChipsEl = target.querySelector('#region-chips');
    REGIONS.forEach((r) => {
      const el = document.createElement('div');
      el.className = 'chip sel'; el.textContent = r;
      el.addEventListener('click', () => {
        const i = data.selectedRegions.indexOf(r);
        if (i >= 0) { data.selectedRegions.splice(i, 1); el.classList.remove('sel'); }
        else        { data.selectedRegions.push(r);        el.classList.add('sel'); }
        updateAll();
      });
      regionChipsEl.appendChild(el);
    });

    const productChipsEl = target.querySelector('#product-chips');
    PRODUCTS.forEach((p) => {
      const el = document.createElement('div');
      el.className = 'chip sel'; el.textContent = p;
      el.addEventListener('click', () => {
        const i = data.selectedProducts.indexOf(p);
        if (i >= 0) { data.selectedProducts.splice(i, 1); el.classList.remove('sel'); }
        else        { data.selectedProducts.push(p);        el.classList.add('sel'); }
        updateAll();
      });
      productChipsEl.appendChild(el);
    });

    const dateSel = target.querySelector('#date-range');
    Object.keys(DATE_RANGES).forEach((k) => {
      const o = document.createElement('option'); o.value = k; o.textContent = k;
      if (k === data.dateRange) o.selected = true;
      dateSel.appendChild(o);
    });
    dateSel.addEventListener('change', (e) => { data.dateRange = e.target.value; updateAll(); });

    target.querySelector('#compare-yoy').addEventListener('change',
      (e) => { data.showComparison = e.target.checked; updateAll(); });
    target.querySelector('#search-input').addEventListener('input',
      (e) => { data.searchText = e.target.value; updateAll(); });

    const dialog = target.querySelector('#settings-dialog');
    target.querySelector('#btn-settings').addEventListener('click', () => dialog.classList.remove('hidden'));
    target.querySelector('#settings-cancel').addEventListener('click', () => dialog.classList.add('hidden'));
    target.querySelector('#settings-apply').addEventListener('click',  () => dialog.classList.add('hidden'));
    target.querySelector('#alert-threshold').addEventListener('input', (e) => {
      target.querySelector('#alert-threshold-out').value = e.target.value;
    });

    target.querySelector('#btn-refresh').addEventListener('click', () => updateAll());

    const stamp = () => {
      const d = new Date();
      target.querySelector('#dash-timestamp').textContent =
        d.toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' }) +
        ' · ' + d.toLocaleTimeString();
    };
    stamp();

    // Defer chart init to the next frame so flex layout has settled
    // and each chart box reports its final size (ECharts uses width/height
    // at init time; a 0-height container yields a 0-height canvas).
    await new Promise((r) => requestAnimationFrame(r));
    createLine(); createBar(); createPie(); createRadar();
    createGauges(); createHeatmap(); createScatter(); createCandle();
    updateKPIs();

    const metricsTimer = setInterval(() => {
      data.cpuUsage    = Math.max(10, Math.min(95, data.cpuUsage + (Math.random() * 10 - 5)));
      data.memoryUsage = Math.max(20, Math.min(90, data.memoryUsage + (Math.random() * 6 - 3)));
      if (charts.cpu) charts.cpu.setOption(gaugeOpt(Math.round(data.cpuUsage * 10) / 10, 'CPU', '#3b82f6'));
      if (charts.mem) charts.mem.setOption(gaugeOpt(Math.round(data.memoryUsage * 10) / 10, 'Memory', '#10b981'));
    }, 2000);

    const resize = () => Object.values(charts).forEach((c) => c && c.resize());
    const ro = new ResizeObserver(resize);
    ro.observe(target);

    const themeObs = new MutationObserver(() => {
      Object.values(charts).forEach((c) => c && c.dispose());
      Object.keys(charts).forEach((k) => delete charts[k]);
      createLine(); createBar(); createPie(); createRadar();
      createGauges(); createHeatmap(); createScatter(); createCandle();
    });
    themeObs.observe(document.body, { attributes: true, attributeFilter: ['class'] });

    return {
      unmount() {
        clearInterval(metricsTimer);
        ro.disconnect();
        themeObs.disconnect();
        Object.values(charts).forEach((c) => c && c.dispose());
        target.innerHTML = '';
      },
    };
  },
};
