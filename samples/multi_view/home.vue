<template>
  <main class="min-h-screen flex items-center justify-center p-8 text-slate-900 bg-gradient-to-br from-amber-50 to-slate-50 dark:text-slate-100 dark:from-amber-950 dark:to-slate-950">
    <section class="w-full max-w-xl rounded-[28px] border border-amber-700/20 bg-white/80 p-8 shadow-2xl shadow-amber-700/10 dark:border-amber-300/20 dark:bg-amber-950/50">
      <div class="text-overline">shared session</div>
      <h1 class="text-h4 q-mt-xs q-mb-sm">Multi-view SPA</h1>
      <p class="text-caption q-mb-lg">
        Two routes, one WebSocket. Navigating does not reconnect; the
        server-side timer keeps running.
      </p>
      <div class="flex flex-wrap gap-3">
        <a data-stage-link href="/timer" class="inline-block rounded-xl bg-amber-600 px-5 py-3 font-extrabold text-white no-underline">Open timer</a>
        <button id="open-drawer" type="button" class="rounded-xl bg-slate-800 px-5 py-3 font-extrabold text-white" @click="openDrawer">Open drawer</button>
      </div>
    </section>
    <NavDrawer stage-id="drawer" />
  </main>
</template>

<script>
import NavDrawer from "./NavDrawer.vue";

export default {
  components: { NavDrawer },
  async mounted() {
    await this.$stage.connect();
  },
  methods: {
    openDrawer() {
      this.$stage.send("drawer.open");
    },
  },
};
</script>
