<template>
  <aside
    v-if="visible"
    id="drawer"
    class="fixed inset-y-0 right-0 z-40 flex w-full max-w-sm flex-col border-l border-amber-500/20 bg-white/95 p-6 text-slate-900 shadow-2xl shadow-slate-950/20 backdrop-blur dark:bg-slate-950/95 dark:text-slate-100"
  >
    <div class="text-overline">nested vue component</div>
    <h2 class="q-my-sm text-h5">Drawer</h2>
    <p id="drawer-message" class="text-caption">{{ message }}</p>
    <button
      id="drawer-close"
      type="button"
      class="mt-auto rounded-xl bg-slate-700 px-5 py-3 font-extrabold text-white"
      @click="close"
    >
      Close
    </button>
  </aside>
</template>

<script>
export default {
  name: "drawer",
  data() {
    return {
      visible: false,
      message: "",
    };
  },
  methods: {
    open(message = "Opened") {
      this.message = message;
      this.visible = true;
    },
    close() {
      this.visible = false;
    },
  },
};
</script>
