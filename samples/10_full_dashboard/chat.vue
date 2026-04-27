<template>
  <main class="min-h-screen bg-gradient-to-br from-fuchsia-50 to-slate-50 text-slate-900 dark:from-fuchsia-950 dark:to-slate-950 dark:text-slate-100">
    <nav class="flex flex-wrap items-center gap-5 border-b border-slate-500/20 px-7 py-4">
      <div class="mr-4 flex items-center gap-3"><div class="text-3xl font-black text-indigo-500">◎</div><div><div class="cap-brand-name font-extrabold">Capstone</div><div class="text-xs opacity-60">sample 10</div></div></div>
      <a data-stage-link href="/" class="cap-nav-item font-bold text-inherit no-underline opacity-70">Home</a><a data-stage-link href="/metric" class="cap-nav-item font-bold text-inherit no-underline opacity-70">Metrics</a><a data-stage-link href="/uploads" class="cap-nav-item font-bold text-inherit no-underline opacity-70">Uploads</a><a data-stage-link href="/chat" class="cap-nav-item font-bold text-purple-500 no-underline">Chat</a>
    </nav>
    <section class="mx-auto flex min-h-[calc(100vh-78px)] max-w-3xl flex-col gap-4 p-6">
      <header>
        <h1 class="text-h5 q-my-xs">Chat</h1>
        <p class="text-caption">Streamed replies over the same session socket.</p>
      </header>
      <div class="flex-1 overflow-auto rounded-3xl border border-purple-500/20 bg-white/80 p-5 dark:bg-purple-950/30">
        <div v-for="(msg, index) in messages" :key="index" :class="['msg', msg.role, 'my-3 flex gap-3']">
          <div :class="['grid h-8 w-8 shrink-0 place-items-center rounded-full font-extrabold text-white', msg.role === 'assistant' ? 'bg-gradient-to-br from-indigo-500 to-purple-500' : 'bg-slate-500']">{{ msg.role === "user" ? "U" : "A" }}</div>
          <div class="flex-1 rounded-2xl bg-slate-500/10 px-4 py-3">{{ msg.text }}</div>
        </div>
      </div>
      <div class="flex items-center gap-3 rounded-3xl border border-purple-500/20 bg-white/80 p-3 dark:bg-purple-950/30">
        <input id="q" v-model="text" class="min-w-0 flex-1 bg-transparent px-3 py-3 text-inherit outline-none" placeholder="Ask anything" @keydown.enter="send">
        <button id="send" type="button" class="rounded-xl bg-purple-500 px-5 py-3 font-extrabold text-white" @click="send">Send</button>
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
    this.$stage.send("chat.history");
  },
  methods: {
    setHistory(messages) {
      this.messages = messages.slice();
    },
    startReply(id) {
      const item = { role: "assistant", text: "" };
      this.messages.push(item);
      this.pending.set(id, item);
    },
    appendReply(id, delta) {
      const item = this.pending.get(id);
      if (item) item.text += delta;
    },
    finishReply(id) {
      this.pending.delete(id);
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
