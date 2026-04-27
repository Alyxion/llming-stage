<template>
  <main class="min-h-screen bg-gradient-to-br from-slate-50 to-indigo-50 pb-8 text-slate-900 dark:from-slate-950 dark:to-indigo-950 dark:text-slate-100">
    <nav class="flex flex-wrap items-center gap-5 border-b border-slate-500/20 px-7 py-4">
      <div class="mr-4 flex items-center gap-3">
        <div class="text-3xl font-black text-indigo-500">◎</div>
        <div>
          <div class="cap-brand-name font-extrabold">Capstone</div>
          <div class="text-xs opacity-60">llming-stage · sample 10</div>
        </div>
      </div>
      <a data-stage-link href="/" class="cap-nav-item font-bold text-indigo-500 no-underline">Home</a>
      <a data-stage-link href="/metric" class="cap-nav-item font-bold text-inherit no-underline opacity-70">Metrics</a>
      <a data-stage-link href="/uploads" class="cap-nav-item font-bold text-inherit no-underline opacity-70">Uploads</a>
      <a data-stage-link href="/chat" class="cap-nav-item font-bold text-inherit no-underline opacity-70">Chat</a>
    </nav>

    <section class="mx-auto my-8 max-w-6xl rounded-[30px] bg-white/80 p-8 shadow-2xl shadow-slate-900/10 dark:bg-slate-900/80">
      <div>
        <div class="text-overline">one session · one socket · four views</div>
        <h1 class="text-h3 q-my-sm">One session. Everything live.</h1>
        <p class="text-subtitle1">
          Streaming metrics, cookie-authed upload, and chat compose into a
          production-shaped FastAPI + llming-com app.
        </p>
      </div>
      <div class="mt-5 font-mono text-xs opacity-70">{{ sessionId }}</div>
      <div class="mt-5 flex flex-wrap items-center gap-3">
        <button type="button" class="rounded-xl bg-indigo-500 px-5 py-3 font-extrabold text-white" @click="broadcast">
          App broadcast
        </button>
        <span class="text-sm opacity-70">{{ broadcastMessage }}</span>
      </div>
    </section>

    <section class="mx-auto grid max-w-6xl gap-5 px-4 md:grid-cols-3">
      <a data-stage-link href="/metric" class="min-h-48 rounded-3xl border-t-4 border-indigo-500 bg-white/80 p-6 text-inherit no-underline shadow-2xl shadow-slate-900/10 dark:bg-slate-900/80">
        <span class="text-xs font-black tracking-widest text-indigo-500">MT</span>
        <h2>Live metrics</h2>
        <p>Plotly chart fed by a server-side asyncio task.</p>
      </a>
      <a data-stage-link href="/uploads" class="min-h-48 rounded-3xl border-t-4 border-emerald-500 bg-white/80 p-6 text-inherit no-underline shadow-2xl shadow-slate-900/10 dark:bg-slate-900/80">
        <span class="text-xs font-black tracking-widest text-emerald-500">UP</span>
        <h2>File upload</h2>
        <p>HTTP carries bytes; WebSocket reports progress.</p>
      </a>
      <a data-stage-link href="/chat" class="min-h-48 rounded-3xl border-t-4 border-purple-500 bg-white/80 p-6 text-inherit no-underline shadow-2xl shadow-slate-900/10 dark:bg-slate-900/80">
        <span class="text-xs font-black tracking-widest text-purple-500">CH</span>
        <h2>Streaming chat</h2>
        <p>Token deltas append live while history stays on the session.</p>
      </a>
    </section>
  </main>
</template>

<script>
export default {
  data() {
    return { sessionId: "", broadcastMessage: "No app broadcast yet" };
  },
  async mounted() {
    const session = await this.$stage.session();
    await this.$stage.connect();
    this.sessionId = session.sessionId;
  },
  methods: {
    broadcast() {
      this.$stage.send("admin.broadcast", { message: "Hello from AppRouter" });
    },
    setBroadcast(message) {
      this.broadcastMessage = message;
    },
  },
};
</script>
