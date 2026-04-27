<template>
  <main class="min-h-screen flex items-center justify-center p-8 text-slate-900 bg-gradient-to-br from-orange-50 to-rose-50 dark:text-slate-100 dark:from-orange-950 dark:to-rose-950">
    <section class="w-full max-w-md rounded-[28px] border border-red-600/20 bg-white/80 p-10 text-center shadow-2xl shadow-red-700/10 dark:bg-orange-950/50">
      <div class="text-overline">server-driven countdown</div>
      <div id="val" class="my-6 text-[clamp(72px,14vw,104px)] font-black leading-none text-transparent bg-clip-text bg-gradient-to-br from-amber-500 to-red-500">
        {{ label }}
      </div>
      <div class="flex justify-center gap-2">
        <button type="button" class="rounded-xl bg-red-600 px-5 py-3 font-extrabold text-white" @click="start">Start 10 s</button>
        <button type="button" class="rounded-xl bg-slate-600 px-5 py-3 font-extrabold text-white" @click="cancel">Cancel</button>
      </div>
      <div class="q-mt-lg">
        <a data-stage-link href="/" class="text-inherit no-underline opacity-75">Back home</a>
      </div>
    </section>
  </main>
</template>

<script>
export default {
  data() {
    return { label: "—" };
  },
  async mounted() {
    await this.$stage.connect();
  },
  methods: {
    setTimer(remaining) {
      this.label = remaining + "s";
    },
    finishTimer() {
      this.label = "✓ done";
    },
    start() {
      this.$stage.send("timer.start", { seconds: 10 });
    },
    cancel() {
      this.$stage.send("timer.cancel");
    },
  },
};
</script>
