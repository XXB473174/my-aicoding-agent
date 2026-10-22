<script setup>
defineProps({
  threads: {
    type: Array,
    default: () => [],
  },
  activeId: {
    type: String,
    default: null,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['new-thread', 'select-thread', 'delete-thread'])

function titleOf(thread) {
  return thread.title || thread.repoFullName || thread.repo || '未命名任务'
}

function confirmDelete(thread) {
  if (window.confirm('确认删除该会话吗？该操作会同时删除会话历史、checkpoint 和业务记录。')) {
    emit('delete-thread', thread.id)
  }
}
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <span class="brand-text">MY-AICODING</span>
    </div>

    <button class="new-button" :disabled="disabled" @click="$emit('new-thread')">
      + 新任务
    </button>

    <nav class="thread-list">
      <button
        v-for="thread in threads"
        :key="thread.id"
        class="thread-item"
        :class="{ active: thread.id === activeId }"
        @click="$emit('select-thread', thread.id)"
      >
        <span class="status-dot" :class="thread.status"></span>
        <span class="thread-content">
          <span class="thread-title">{{ titleOf(thread) }}</span>
          <small>{{ thread.repoFullName || thread.repo }}</small>
        </span>
        <span
          class="thread-delete"
          title="删除会话"
          role="button"
          tabindex="0"
          @click.stop="confirmDelete(thread)"
          @keydown.enter.stop.prevent="confirmDelete(thread)"
          @keydown.space.stop.prevent="confirmDelete(thread)"
        >
          ×
        </span>
      </button>
    </nav>
  </aside>
</template>
