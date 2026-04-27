<template>
  <main class="min-h-screen p-6 text-slate-900 bg-gradient-to-br from-fuchsia-50 to-slate-50 dark:text-slate-100 dark:from-fuchsia-950 dark:to-slate-950">
    <section class="mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-3xl flex-col gap-4">
      <header>
        <div class="text-overline">server streamed deltas</div>
        <h1 class="text-h5 q-my-xs">Streaming chat</h1>
        <p class="text-caption q-mb-none">
          Server emits chat.start -> chat.delta -> chat.done; the client appends
          tokens live.
        </p>
      </header>

      <div id="log" class="flex-1 overflow-auto rounded-3xl border border-violet-600/20 bg-white/80 p-5 shadow-2xl shadow-violet-950/10 dark:bg-violet-950/40">
        <div v-for="(msg, index) in messages" :key="index" :class="['msg', msg.role, 'my-3 flex items-start gap-3']">
          <div :class="['grid h-8 w-8 shrink-0 place-items-center rounded-full font-extrabold text-white', msg.role === 'assistant' ? 'bg-gradient-to-br from-violet-600 to-cyan-500' : 'bg-slate-500']">
            {{ msg.role === "user" ? "U" : "A" }}
          </div>
          <div class="flex-1 rounded-2xl bg-slate-500/10 px-4 py-3 leading-relaxed">{{ msg.text }}</div>
        </div>
      </div>

      <div class="flex items-center gap-3 rounded-3xl border border-violet-600/20 bg-white/80 p-3 shadow-2xl shadow-violet-950/10 dark:bg-violet-950/40">
        <input id="q" v-model="text" class="min-w-0 flex-1 bg-transparent px-3 py-3 text-inherit outline-none" placeholder="Ask anything" @keydown.enter="send">
        <button id="send" type="button" class="rounded-xl bg-violet-600 px-5 py-3 font-extrabold text-white" @click="send">Send</button>
      </div>
    </section>
  </main>
</template>

<script>
export default {
  data() {
    return { text: "", messages: [], pending: new Map() };
  },
  async mounted() {
    await this.$stage.connect();
  },
  methods: {
    setHistory(messages) {
      this.messages = messages.slice();
    },
    startReply(id) {
      const item = { role: "assistant", text: "" };
      this.messages.push(item);
      this.pending.set(id, item);
      this.scrollLog();
    },
    appendReply(id, delta) {
      const item = this.pending.get(id);
      if (item) item.text += delta;
      this.scrollLog();
    },
    finishReply(id) {
      this.pending.delete(id);
    },
    scrollLog() {
      this.$nextTick(() => {
        const log = this.$el.querySelector("#log");
        log.scrollTop = log.scrollHeight;
      });
    },
    send() {
      const value = this.text.trim();
      if (!value) return;
      this.messages.push({ role: "user", text: value });
      this.text = "";
      this.$stage.send("chat.ask", { text: value });
    },
  },
};
</script>
