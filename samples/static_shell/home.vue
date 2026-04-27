<template>
  <main class="min-h-screen flex flex-col items-center justify-center gap-6 px-6 py-12 text-center text-slate-900 bg-gradient-to-br from-slate-50 via-emerald-50 to-amber-50 dark:text-slate-100 dark:from-slate-950 dark:via-emerald-950 dark:to-amber-950">
    <div class="text-h2 !font-black !tracking-[-0.04em] text-transparent bg-clip-text bg-gradient-to-br from-teal-700 to-amber-600">
      Static shell
    </div>
    <p class="text-subtitle1 max-w-xl text-slate-600 dark:text-slate-300">
      One Vue view, no session, no WebSocket. This page can be hosted from a
      CDN bucket or mounted next to a FastAPI backend.
    </p>
    <div class="flex flex-wrap justify-center gap-2">
      <span class="rounded-full bg-teal-700 px-3 py-2 text-xs font-extrabold tracking-wide text-white">Vue + Quasar</span>
      <span class="rounded-full bg-cyan-700 px-3 py-2 text-xs font-extrabold tracking-wide text-white">No server reactivity</span>
      <span class="rounded-full bg-amber-700 px-3 py-2 text-xs font-extrabold tracking-wide text-white">Static deployable</span>
    </div>
  </main>
</template>
