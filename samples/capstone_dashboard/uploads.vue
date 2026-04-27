<template>
  <main class="min-h-screen bg-gradient-to-br from-emerald-50 to-slate-50 text-slate-900 dark:from-emerald-950 dark:to-slate-950 dark:text-slate-100">
    <nav class="flex flex-wrap items-center gap-5 border-b border-slate-500/20 px-7 py-4">
      <div class="mr-4 flex items-center gap-3"><div class="text-3xl font-black text-indigo-500">◎</div><div><div class="cap-brand-name font-extrabold">Capstone</div><div class="text-xs opacity-60">sample 10</div></div></div>
      <a data-stage-link href="/" class="cap-nav-item font-bold text-inherit no-underline opacity-70">Home</a><a data-stage-link href="/metric" class="cap-nav-item font-bold text-inherit no-underline opacity-70">Metrics</a><a data-stage-link href="/uploads" class="cap-nav-item font-bold text-emerald-500 no-underline">Uploads</a><a data-stage-link href="/chat" class="cap-nav-item font-bold text-inherit no-underline opacity-70">Chat</a>
    </nav>
    <section class="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <h1 class="text-h5 q-my-xs">Uploads</h1>
      <p class="text-caption">Cookie-authed HTTP POST; progress streams on the shared WebSocket.</p>
      <div class="rounded-3xl border border-emerald-500/20 bg-white/80 p-5 dark:bg-emerald-950/30">
        <input id="file" ref="file" type="file" class="mb-4 block text-inherit">
        <div class="flex flex-wrap items-center gap-3">
          <button id="go" type="button" class="rounded-xl bg-emerald-500 px-5 py-3 font-extrabold text-white" @click="upload">Upload</button>
          <div id="progress" class="text-caption">{{ progress }}</div>
        </div>
      </div>
      <div class="rounded-3xl border border-emerald-500/20 bg-white/80 p-5 dark:bg-emerald-950/30">
        <div class="text-overline q-mb-sm">history</div>
        <ul id="history" class="m-0 list-disc pl-5 font-mono text-sm leading-7">
          <li v-if="!uploads.length" class="list-none opacity-55">no uploads yet</li>
          <li v-for="item in uploads" :key="item.sha256">
            {{ item.name }} — {{ item.bytes.toLocaleString() }} bytes — {{ item.sha256.slice(0, 12) }}...
          </li>
        </ul>
      </div>
    </section>
  </main>
</template>

<script>
export default {
  data() {
    return { uploads: [], progress: "" };
  },
  async mounted() {
    await this.$stage.connect();
    this.$stage.send("uploads.list");
  },
  methods: {
    setUploads(items) {
      this.uploads = items;
    },
    setProgress(name, bytes) {
      this.progress = `${name}: ${bytes.toLocaleString()} bytes...`;
    },
    finishUpload(record) {
      this.progress = `${record.name}: done`;
      this.$stage.send("uploads.list");
    },
    async upload() {
      const file = this.$refs.file.files[0];
      if (!file) return;
      const form = new FormData();
      form.append("file", file);
      this.progress = `${file.name}: starting...`;
      await fetch("/api/upload", { method: "POST", body: form, credentials: "include" });
    },
  },
};
</script>
