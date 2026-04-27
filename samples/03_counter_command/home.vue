<template>
  <main class="min-h-screen flex items-center justify-center p-8 text-slate-900 bg-gradient-to-br from-sky-50 to-cyan-50 dark:text-slate-100 dark:from-slate-950 dark:to-cyan-950">
    <section class="w-full max-w-md rounded-[28px] border border-cyan-700/20 bg-white/80 p-10 text-center shadow-2xl shadow-cyan-700/10 dark:border-cyan-300/20 dark:bg-slate-900/80">
      <div class="text-overline">server-held counter</div>
      <div id="val" class="my-6 text-[clamp(82px,16vw,128px)] font-black leading-none tabular-nums text-transparent bg-clip-text bg-gradient-to-br from-cyan-600 to-blue-600">
        {{ value }}
      </div>
      <div class="flex justify-center gap-2">
        <button type="button" class="rounded-xl bg-slate-600 px-5 py-3 font-extrabold text-white" @click="inc(-1)">-</button>
        <button type="button" class="rounded-xl bg-cyan-600 px-5 py-3 font-extrabold text-white" @click="inc(1)">+</button>
        <button type="button" class="rounded-xl bg-red-600 px-5 py-3 font-extrabold text-white" @click="reset">reset</button>
      </div>
      <p class="text-caption q-mt-lg q-mb-none">
        Open two tabs. Each tab gets its own session and server-side count.
      </p>
    </section>
  </main>
</template>

<script>
export default {
  data() {
    return { value: 0 };
  },
  async mounted() {
    await this.$stage.connect();
  },
  methods: {
    setCounter(value) {
      this.value = value;
    },
    inc(by) {
      this.$stage.send("counter.inc", { by });
    },
    reset() {
      this.$stage.send("counter.reset");
    },
  },
};
</script>
