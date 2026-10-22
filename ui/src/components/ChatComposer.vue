<script setup>
import { ref } from 'vue'

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false,
  },
  model: {
    type: String,
    default: '',
  },
  effort: {
    type: String,
    default: 'default',
  },
  repo: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['send', 'stop', 'update:repo'])
const draft = ref('')

function send() {
  const content = draft.value.trim()
  if (!content || props.disabled) return
  draft.value = ''
  emit('send', content)
}

function onKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    send()
  }
}
</script>

<template>
  <footer class="composer">
    <label class="repo-field">
      <span>Gitee 仓库</span>
      <input
        :value="repo"
        :disabled="disabled"
        placeholder="https://gitee.com/owner/repo"
        @input="$emit('update:repo', $event.target.value)"
      />
    </label>

    <textarea
      v-model="draft"
      :disabled="disabled"
      placeholder="继续输入指令"
      @keydown="onKeydown"
    />

    <div class="composer-footer">
      <span>{{ model || 'deepseek-v4-pro' }} {{ effort || 'default' }}</span>
      <button v-if="disabled" class="stop-button" @click="$emit('stop')">停止</button>
      <button v-else class="send-button" :disabled="!draft.trim()" @click="send">发送</button>
    </div>
  </footer>
</template>
