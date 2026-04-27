<template>
  <main class="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-10">
    <section class="mx-auto max-w-6xl space-y-6">
      <header class="rounded-[2rem] bg-gradient-to-br from-cyan-300 via-sky-500 to-slate-900 p-8 shadow-2xl">
        <p class="text-xs uppercase tracking-[0.35em] text-slate-900/70">sample 13</p>
        <h1 class="mt-3 text-4xl md:text-6xl font-black tracking-tight">Basic components</h1>
        <p class="mt-4 max-w-2xl text-lg text-slate-900/80">
          Tailwind layout classes, Quasar widgets, and the Stage shell loaded once.
        </p>
      </header>

      <div class="grid gap-6 lg:grid-cols-3">
        <q-card flat bordered class="rounded-3xl bg-white text-slate-900 shadow-xl">
          <q-card-section class="space-y-4">
            <div>
              <p class="text-xs uppercase tracking-[0.25em] text-slate-500">forms</p>
              <h2 class="text-2xl font-bold">Inputs and choices</h2>
            </div>
            <q-input v-model="name" filled label="Customer name" />
            <q-select v-model="segment" filled :options="segments" label="Segment" />
            <q-checkbox v-model="approved" label="Approved" />
            <q-toggle v-model="urgent" color="orange" label="Priority routing" />
            <div>
              <div class="mb-1 flex justify-between text-sm">
                <span>Confidence</span><strong>{{ confidence }}%</strong>
              </div>
              <q-slider v-model="confidence" :min="0" :max="100" color="cyan" />
            </div>
          </q-card-section>
        </q-card>

        <q-card flat bordered class="rounded-3xl bg-white text-slate-900 shadow-xl">
          <q-card-section class="space-y-4">
            <div>
              <p class="text-xs uppercase tracking-[0.25em] text-slate-500">actions</p>
              <h2 class="text-2xl font-bold">Buttons and overlays</h2>
            </div>
            <div class="flex flex-wrap gap-3">
              <q-btn color="primary" label="Notify" @click="notify" />
              <q-btn outline color="primary" label="Dialog" @click="dialog = true" />
              <q-btn color="dark" label="Menu">
                <q-menu>
                  <q-list class="min-w-44">
                    <q-item v-close-popup clickable><q-item-section>Assign</q-item-section></q-item>
                    <q-item v-close-popup clickable><q-item-section>Archive</q-item-section></q-item>
                    <q-item v-close-popup clickable><q-item-section>Export</q-item-section></q-item>
                  </q-list>
                </q-menu>
              </q-btn>
            </div>
            <q-linear-progress rounded size="14px" :value="confidence / 100" color="cyan" />
            <q-banner rounded class="bg-slate-100 text-slate-700">
              {{ summary }}
            </q-banner>
          </q-card-section>
        </q-card>

        <q-card flat bordered class="rounded-3xl bg-white text-slate-900 shadow-xl">
          <q-tabs v-model="tab" dense active-color="primary" indicator-color="primary">
            <q-tab name="table" label="Table" />
            <q-tab name="tree" label="Tree" />
          </q-tabs>
          <q-separator />
          <q-tab-panels v-model="tab" animated>
            <q-tab-panel name="table">
              <q-table flat dense row-key="account" :rows="rows" :columns="columns" :pagination="{ rowsPerPage: 4 }" />
            </q-tab-panel>
            <q-tab-panel name="tree">
              <q-tree :nodes="nodes" node-key="label" default-expand-all />
            </q-tab-panel>
          </q-tab-panels>
        </q-card>
      </div>
    </section>

    <q-dialog v-model="dialog">
      <q-card class="w-[420px] max-w-[90vw]">
        <q-card-section>
          <div class="text-h6">Review workflow</div>
          <p class="mt-2 text-slate-600">Dialogs, menus, and notifications are provided by the bundled Quasar runtime.</p>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn v-close-popup flat color="primary" label="Close" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </main>
</template>

<script>
export default {
  data() {
    return {
      approved: true,
      columns: [
        { name: 'account', label: 'Account', field: 'account', align: 'left' },
        { name: 'status', label: 'Status', field: 'status', align: 'left' },
        { name: 'value', label: 'Value', field: 'value', align: 'right' },
      ],
      confidence: 82,
      dialog: false,
      name: 'Ada Lovelace',
      nodes: [
        { label: 'Inbox', children: [{ label: 'Qualified' }, { label: 'Needs reply' }] },
        { label: 'Pipeline', children: [{ label: 'Proposal' }, { label: 'Won' }] },
      ],
      rows: [
        { account: 'Northwind', status: 'Active', value: '$42k' },
        { account: 'Globex', status: 'Review', value: '$18k' },
        { account: 'Initech', status: 'New', value: '$9k' },
        { account: 'Umbrella', status: 'Active', value: '$31k' },
      ],
      segment: 'Enterprise',
      segments: ['Startup', 'Mid-market', 'Enterprise'],
      tab: 'table',
      urgent: false,
    };
  },
  computed: {
    summary() {
      const priority = this.urgent ? 'priority' : 'standard';
      return `${this.name} is an ${this.segment} lead on ${priority} routing.`;
    },
  },
  methods: {
    notify() {
      this.$q.notify({ message: 'Notification sent', color: 'primary', icon: 'check_circle' });
    },
  },
};
</script>
