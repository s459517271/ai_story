<template>
  <div
    class="asset-extraction-node"
    :class="`status-${effectiveStatus}`"
    :style="nodeStyle"
  >
    <div class="node-top">
      <div class="card-top">
        <div class="card-title-wrap">
          <span class="card-title">资产抽取</span>
          <span class="card-subtitle">来源：{{ sourceTypeText }}</span>
        </div>
        <button
          class="pill-action"
          :disabled="isExecuting || status === 'processing'"
          @click.stop="handleExecute"
        >
          <span v-if="isExecuting" class="loading loading-spinner loading-xs" />
          <span v-else>执行抽取</span>
        </button>
      </div>

      <div class="card-meta">
        <span class="meta-chip">{{ itemCount }} 项待处理</span>
        <span v-if="data && data.updated_at" class="meta-chip">{{ formatDate(data.updated_at) }}</span>
      </div>
    </div>

    <div class="card-body prevent-canvas-wheel" @wheel.stop @mousedown.stop>
      <div v-if="data && data.summary" class="summary-box">
        {{ data.summary }}
      </div>

      <div v-if="localItems.length" class="item-list">
        <div v-for="item in localItems" :key="item.temp_id" class="item-card">
          <div class="item-head">
            <div>
              <div class="item-key-row">
                <code class="item-key">{{ item.key }}</code>
                <span class="item-group">{{ item.group || '未分组' }}</span>
              </div>
              <div class="item-label">{{ item.label || '未命名资产' }}</div>
            </div>
            <span class="item-confidence">{{ confidenceText(item.confidence) }}</span>
          </div>

          <pre class="item-value">{{ formatValue(item.value) }}</pre>

          <div class="item-controls">
            <select v-model="item.selected_action" class="select select-sm asset-select">
              <option value="">请选择动作</option>
              <option value="bind_existing">关联已有</option>
              <option value="create_new">生成新资产</option>
              <option value="overwrite_existing">覆盖已有</option>
              <option value="skip">跳过</option>
            </select>

            <select
              v-model="item.selected_asset_id"
              class="select select-sm asset-select"
              :disabled="!requiresAssetSelection(item.selected_action)"
            >
              <option value="">请选择资产</option>
              <option
                v-for="asset in resolveAssetOptions(item)"
                :key="asset.id || asset.asset_id"
                :value="asset.id || asset.asset_id"
              >
                {{ (asset.key || '未命名') + (asset.group ? ` · ${asset.group}` : '') }}
              </option>
            </select>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <div class="empty-title">暂未抽取到资产</div>
        <div class="empty-desc">执行后会解析文案并给出可关联或可生成的资产项</div>
      </div>
    </div>

    <div class="card-footer">
      <button
        class="pill-action secondary"
        :disabled="isApplying || !canApply"
        @click.stop="handleApply"
      >
        <span v-if="isApplying" class="loading loading-spinner loading-xs" />
        <span v-else>应用选择</span>
      </button>
    </div>
  </div>
</template>

<script>
import projectsAPI from '@/api/projects';
import { formatDate } from '@/utils/helpers';

export default {
  name: 'AssetExtractionNode',
  props: {
    status: {
      type: String,
      default: 'pending'
    },
    position: {
      type: Object,
      default: () => ({ x: 0, y: 0 })
    },
    data: {
      type: Object,
      default: null
    },
    projectId: {
      type: [String, Number],
      required: true
    },
    availableAssets: {
      type: Array,
      default: () => []
    }
  },
  data() {
    return {
      isExecuting: false,
      isApplying: false,
      localItems: [],
    };
  },
  computed: {
    nodeStyle() {
      return {
        position: 'absolute',
        left: `${this.position.x}px`,
        top: `${this.position.y}px`,
      };
    },
    effectiveStatus() {
      if (this.isExecuting || this.isApplying) {
        return 'processing';
      }
      return this.status;
    },
    sourceTypeText() {
      const map = {
        rewritten_text: '改写文案',
        original_text: '原始文案',
        original_topic: '原始文案',
      };
      return map[this.data?.source_type] || '原始文案';
    },
    itemCount() {
      return this.localItems.length;
    },
    canApply() {
      return this.localItems.some(item => item.selected_action);
    },
  },
  watch: {
    'data.items': {
      immediate: true,
      deep: true,
      handler(value) {
        this.localItems = (value || []).map(item => ({ ...item }));
      }
    }
  },
  methods: {
    formatDate,
    confidenceText(value) {
      const number = Number(value || 0);
      return `置信度 ${Math.round(number * 100)}%`;
    },
    formatValue(value) {
      if (value == null) {
        return '暂无值';
      }
      if (typeof value === 'string') {
        return value;
      }
      try {
        return JSON.stringify(value, null, 2);
      } catch (error) {
        return String(value);
      }
    },
    requiresAssetSelection(action) {
      return action === 'bind_existing' || action === 'overwrite_existing';
    },
    resolveAssetOptions(item) {
      const candidateMap = new Map();
      (item.candidates || []).forEach(candidate => {
        candidateMap.set(candidate.asset_id, {
          id: candidate.asset_id,
          key: candidate.key,
          group: candidate.group,
        });
      });
      this.availableAssets.forEach(asset => {
        candidateMap.set(asset.id, asset);
      });
      return Array.from(candidateMap.values());
    },
    handleExecute() {
      this.isExecuting = true;
      try {
        this.$emit('execute', { stageType: 'asset_extraction', inputData: {} });
      } finally {
        this.isExecuting = false;
      }
    },
    buildApplyPayload(item) {
      const payload = {
        temp_id: item.temp_id,
        action: item.selected_action,
      };

      if (this.requiresAssetSelection(item.selected_action)) {
        payload.asset_id = item.selected_asset_id;
      }

      if (item.selected_action === 'create_new') {
        payload.asset = {
          key: item.key,
          group: item.group,
          variable_type: item.variable_type,
          value: item.value,
          description: `从资产抽取节点生成：${item.label || item.key}`,
        };
      }

      if (item.selected_action === 'overwrite_existing') {
        payload.asset = {
          key: item.key,
          group: item.group,
          variable_type: item.variable_type,
          value: item.value,
          description: `从资产抽取节点更新：${item.label || item.key}`,
        };
      }

      return payload;
    },
    async handleApply() {
      const payload = this.localItems
        .filter(item => item.selected_action)
        .map(item => this.buildApplyPayload(item));

      if (!payload.length) {
        this.$message?.warning('请先选择要应用的资产项');
        return;
      }

      this.isApplying = true;
      try {
        await projectsAPI.applyAssetExtraction(this.projectId, payload);
        this.$message?.success('资产已更新并绑定到项目');
        this.$emit('asset-bindings-updated');
      } catch (error) {
        console.error('[AssetExtractionNode] 应用资产失败:', error);
        this.$message?.error(error.response?.data?.error || error.message || '应用资产失败');
      } finally {
        this.isApplying = false;
      }
    },
  }
};
</script>

<style scoped>
.asset-extraction-node {
  width: 620px;
  min-height: 320px;
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
  overflow: hidden;
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
}

.asset-extraction-node::before {
  content: '';
  display: block;
  height: 3px;
  background: linear-gradient(90deg, #22d3ee 0%, #38bdf8 55%, #818cf8 100%);
}

.asset-extraction-node:hover {
  transform: translateY(-4px);
  box-shadow: 0 24px 52px rgba(15, 23, 42, 0.14);
}

.layout-shell.theme-dark .asset-extraction-node {
  background: rgba(15, 23, 42, 0.92);
  border-color: rgba(148, 163, 184, 0.2);
  box-shadow: 0 18px 40px rgba(2, 6, 23, 0.4);
}

.node-top,
.card-footer {
  padding: 16px 18px;
}

.card-top,
.card-meta,
.card-footer,
.item-head,
.item-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-title,
.empty-title,
.item-label {
  font-weight: 700;
  color: #0f172a;
}

.card-subtitle,
.empty-desc,
.item-group,
.item-confidence,
.summary-box {
  color: #64748b;
}

.layout-shell.theme-dark .card-title,
.layout-shell.theme-dark .empty-title,
.layout-shell.theme-dark .item-label,
.layout-shell.theme-dark .item-key {
  color: #e2e8f0;
}

.layout-shell.theme-dark .card-subtitle,
.layout-shell.theme-dark .empty-desc,
.layout-shell.theme-dark .item-group,
.layout-shell.theme-dark .item-confidence,
.layout-shell.theme-dark .summary-box {
  color: #94a3b8;
}

.pill-action {
  border: 1px solid rgba(148, 163, 184, 0.3);
  background: rgba(255, 255, 255, 0.92);
  color: #0f172a;
  border-radius: 999px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.25s ease;
}

.pill-action:hover:not(:disabled) {
  border-color: rgba(34, 211, 238, 0.5);
  box-shadow: 0 10px 24px rgba(56, 189, 248, 0.18);
  transform: translateY(-1px);
}

.pill-action.secondary {
  width: 100%;
}

.pill-action:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.layout-shell.theme-dark .pill-action {
  background: rgba(30, 41, 59, 0.92);
  color: #e2e8f0;
}

.card-meta {
  justify-content: flex-start;
  padding-top: 0;
}

.meta-chip,
.item-group {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 10px;
  background: rgba(148, 163, 184, 0.12);
  font-size: 12px;
}

.card-body {
  padding: 0 18px 18px;
  max-height: 360px;
  overflow: auto;
}

.summary-box,
.item-card,
.empty-state {
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(248, 250, 252, 0.75);
}

.layout-shell.theme-dark .summary-box,
.layout-shell.theme-dark .item-card,
.layout-shell.theme-dark .empty-state {
  background: rgba(15, 23, 42, 0.72);
  border-color: rgba(148, 163, 184, 0.18);
}

.summary-box,
.empty-state {
  padding: 14px 16px;
  margin-bottom: 14px;
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.item-card {
  padding: 14px 16px;
}

.item-key-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.item-key {
  font-size: 12px;
}

.item-value {
  margin: 12px 0;
  padding: 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.16);
  font-size: 12px;
  line-height: 1.5;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
}

.layout-shell.theme-dark .item-value {
  background: rgba(2, 6, 23, 0.5);
  color: #cbd5e1;
}

.asset-select {
  flex: 1;
  min-width: 0;
}

.empty-state {
  text-align: center;
}

.status-processing {
  border-color: rgba(56, 189, 248, 0.45);
}

.status-completed {
  border-color: rgba(34, 197, 94, 0.35);
}

.status-failed {
  border-color: rgba(248, 113, 113, 0.42);
}
</style>
