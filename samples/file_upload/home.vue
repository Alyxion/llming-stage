<template>
  <main class="min-h-screen px-6 py-8 text-slate-900 bg-gradient-to-br from-emerald-50 to-green-50 dark:text-slate-100 dark:from-emerald-950 dark:to-slate-950">
    <section class="mx-auto flex w-full max-w-2xl flex-col gap-5">
      <header>
        <div class="text-overline">HTTP bytes + WebSocket progress</div>
        <h1 class="text-h4 q-my-xs">File upload</h1>
        <p class="text-caption q-mb-none">
          HTTP POST carries the file; progress and completion stream back over
          the session socket.
        </p>
      </header>

      <div class="rounded-3xl border border-emerald-600/20 bg-white/80 p-6 shadow-2xl shadow-emerald-700/10 dark:bg-emerald-950/40">
        <input id="file" ref="file" type="file" class="mb-4 block text-inherit">
        <div class="flex flex-wrap items-center gap-3">
          <button id="go" type="button" class="rounded-xl bg-emerald-600 px-5 py-3 font-extrabold text-white" @click="upload">Upload</button>
          <div id="progress" class="min-h-6 tabular-nums text-slate-500 dark:text-slate-300">{{ progress }}</div>
        </div>
      </div>

      <div class="rounded-3xl border border-emerald-600/20 bg-white/80 p-6 shadow-2xl shadow-emerald-700/10 dark:bg-emerald-950/40">
        <div class="text-overline q-mb-sm">history · this session</div>
        <ul id="history" class="m-0 list-disc pl-5 font-mono text-sm leading-7">
          <li v-if="!uploads.length" class="list-none opacity-55">no uploads yet</li>
          <li v-for="item in uploads" :key="item.sha256">
            {{ item.name }} — {{ item.bytes.toLocaleString() }} bytes —
            {{ item.sha256.slice(0, 12) }}...
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
      this.progress = `${record.name}: done · sha256 ${record.sha256.slice(0, 12)}...`;
      this.$stage.send("uploads.list");
    },
    async upload() {
      const file = this.$refs.file.files[0];
      if (!file) return;
      const form = new FormData();
      form.append("file", file);
      this.progress = `${file.name}: starting...`;
      await fetch("/api/upload", {
        method: "POST",
        body: form,
        credentials: "include",
      });
    },
  },
};
</script>
