'use client'

import { useEffect, useMemo, useState } from 'react'
import ProductShell from '@/components/layout/ProductShell'
import {
  clearRuntimeSettings,
  getRuntimeSettings,
  updateRuntimeSettings,
  type RuntimeSettingsField,
  type RuntimeSettingsResponse,
  type RuntimeSettingsUpdateValue,
} from '@/lib/settingsApi'

const RESTART_LABELS: Record<string, string> = {
  immediate: '立即生效',
  api: '需重启 API',
  worker: '需重启 worker',
  api_worker: '需重启 API + worker',
}

const PROVIDER_ORDER_PRESETS = ['fixture,pexels,youtube', 'pexels,youtube', 'youtube,pexels']
const EXPECTED_GROUP_TITLES = ['AI 配置', '素材源配置', 'YouTube 高级配置', '基础设施配置']

function stringifyFieldValue(field: RuntimeSettingsField) {
  if (field.sensitive) {
    return ''
  }
  if (typeof field.value === 'boolean') {
    return field.value ? 'true' : 'false'
  }
  return field.value === undefined || field.value === null ? '' : String(field.value)
}

function parseDraftValue(field: RuntimeSettingsField, value: string): RuntimeSettingsUpdateValue {
  if (field.kind === 'boolean') {
    return value === 'true'
  }
  return value
}

function getStatusLabel(saveState: 'saved' | 'dirty' | 'saving' | 'failed') {
  if (saveState === 'dirty') {
    return '有未保存修改'
  }
  if (saveState === 'saving') {
    return '保存中'
  }
  if (saveState === 'failed') {
    return '保存失败'
  }
  return '已保存'
}

function sourceBadgeClass(source: RuntimeSettingsField['source']) {
  if (source === 'runtime') {
    return 'border-accent bg-accent/20 text-accentink'
  }
  if (source === 'missing') {
    return 'border-rose-200 bg-rose-50 text-rose-700'
  }
  return 'border-border bg-subtle text-secondary'
}

function renderFieldInput(
  field: RuntimeSettingsField,
  value: string,
  onChange: (value: string) => void,
) {
  if (field.kind === 'boolean') {
    return (
      <label className="inline-flex min-h-10 items-center gap-3 text-sm font-medium text-ink">
        <input
          className="h-4 w-4 rounded border-border text-accentstrong focus:ring-accentstrong"
          type="checkbox"
          checked={value === 'true'}
          onChange={(event) => onChange(event.target.checked ? 'true' : 'false')}
        />
        {value === 'true' ? '已启用' : '已关闭'}
      </label>
    )
  }

  if (field.kind === 'provider_order') {
    return (
      <div className="grid gap-2">
        <select
          className="h-10 rounded-md border border-border bg-white px-3 text-sm text-ink outline-none transition focus:border-accentstrong focus:ring-2 focus:ring-accentstrong/20"
          value={PROVIDER_ORDER_PRESETS.includes(value) ? value : 'custom'}
          onChange={(event) => {
            if (event.target.value !== 'custom') {
              onChange(event.target.value)
            }
          }}
        >
          {PROVIDER_ORDER_PRESETS.map((preset) => (
            <option key={preset} value={preset}>
              {preset}
            </option>
          ))}
          <option value="custom">自定义</option>
        </select>
        <input
          className="h-10 rounded-md border border-border bg-white px-3 text-sm text-ink outline-none transition placeholder:text-mutedtext focus:border-accentstrong focus:ring-2 focus:ring-accentstrong/20"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="fixture,pexels,youtube"
        />
      </div>
    )
  }

  return (
    <input
      className="h-10 w-full rounded-md border border-border bg-white px-3 text-sm text-ink outline-none transition placeholder:text-mutedtext focus:border-accentstrong focus:ring-2 focus:ring-accentstrong/20"
      type={field.sensitive ? 'password' : 'text'}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={field.sensitive ? '输入新值以替换当前配置' : '输入本地 runtime override'}
    />
  )
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<RuntimeSettingsResponse | null>(null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [dirtyKeys, setDirtyKeys] = useState<string[]>([])
  const [errorText, setErrorText] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<'saved' | 'dirty' | 'saving' | 'failed'>('saved')

  useEffect(() => {
    void loadSettings()
  }, [])

  const fieldByKey = useMemo(() => {
    const fields: Record<string, RuntimeSettingsField> = {}
    settings?.groups.forEach((group) => {
      group.fields.forEach((field) => {
        fields[field.key] = field
      })
    })
    return fields
  }, [settings])

  async function loadSettings() {
    try {
      const nextSettings = await getRuntimeSettings()
      setSettings(nextSettings)
      setDrafts({})
      setDirtyKeys([])
      setSaveState('saved')
      setErrorText(null)
    } catch {
      setErrorText('设置服务暂时不可用。')
      setSaveState('failed')
    }
  }

  function updateDraft(field: RuntimeSettingsField, value: string) {
    setDrafts((prev) => ({ ...prev, [field.key]: value }))
    setDirtyKeys((prev) => (prev.includes(field.key) ? prev : [...prev, field.key]))
    setSaveState('dirty')
  }

  async function saveChanges() {
    const updates: Record<string, RuntimeSettingsUpdateValue> = {}
    dirtyKeys.forEach((key) => {
      const field = fieldByKey[key]
      if (field) {
        updates[key] = parseDraftValue(field, drafts[key] ?? '')
      }
    })

    if (Object.keys(updates).length === 0) {
      return
    }

    try {
      setSaveState('saving')
      const nextSettings = await updateRuntimeSettings(updates)
      setSettings(nextSettings)
      setDrafts({})
      setDirtyKeys([])
      setSaveState('saved')
      setErrorText(null)
    } catch (error) {
      setSaveState('failed')
      setErrorText(error instanceof Error ? error.message : '保存失败，请检查字段。')
    }
  }

  async function clearField(field: RuntimeSettingsField) {
    try {
      const nextSettings = await clearRuntimeSettings([field.key])
      setSettings(nextSettings)
      setDrafts((prev) => {
        const next = { ...prev }
        delete next[field.key]
        return next
      })
      setDirtyKeys((prev) => prev.filter((key) => key !== field.key))
      setSaveState('saved')
      setErrorText(null)
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : '清除失败，请稍后重试。')
    }
  }

  function resetDrafts() {
    setDrafts({})
    setDirtyKeys([])
    setSaveState('saved')
    setErrorText(null)
  }

  return (
    <ProductShell>
      <div className="grid min-w-0 gap-4 lg:gap-5">
        <section className="rounded-lg border border-border bg-white p-5 shadow-soft sm:p-6" aria-label="运行设置">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <span className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">Settings</span>
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">运行设置</h1>
                <p className="max-w-3xl text-sm leading-6 text-secondary sm:text-base">
                  编辑本地 runtime 配置，管理 AI、素材源、YouTube 高级参数和基础设施连接。
                </p>
              </div>
            </div>

            <div className="grid gap-3 rounded-md border border-border bg-subtle p-3 text-sm lg:min-w-[280px]">
              <div className="flex items-center justify-between gap-3">
                <span className="text-secondary">保存状态</span>
                <strong className="text-ink">{getStatusLabel(saveState)}</strong>
              </div>
              <div className="grid gap-1">
                <span className="text-secondary">当前模式</span>
                <strong className="text-ink">{settings?.mode.label ?? '读取中'}</strong>
                <p className="text-xs leading-5 text-mutedtext">{settings?.mode.description ?? '正在读取设置服务。'}</p>
              </div>
            </div>
          </div>
        </section>

        {errorText ? (
          <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {errorText}
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <button
            className="rounded-md bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-50"
            type="button"
            onClick={saveChanges}
            disabled={dirtyKeys.length === 0 || saveState === 'saving'}
          >
            保存修改
          </button>
          <button
            className="rounded-md border border-border bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:border-accentstrong disabled:cursor-not-allowed disabled:opacity-50"
            type="button"
            onClick={resetDrafts}
            disabled={dirtyKeys.length === 0 || saveState === 'saving'}
          >
            放弃修改
          </button>
        </div>

        {settings ? (
          settings.groups.map((group) => (
            <section key={group.id} className="grid gap-3" aria-label={group.title}>
              <div className="space-y-1">
                <h2 className="text-xl font-semibold text-ink">{group.title}</h2>
                <p className="text-sm text-secondary">{group.description}</p>
              </div>

              <div className="grid gap-3">
                {group.fields.map((field) => {
                  const value = drafts[field.key] ?? stringifyFieldValue(field)
                  const isDirty = dirtyKeys.includes(field.key)
                  const showClear = field.source === 'runtime' || field.sensitive

                  return (
                    <div
                      key={field.key}
                      className="grid gap-3 rounded-lg border border-border bg-white p-4 shadow-soft lg:grid-cols-[minmax(220px,0.85fr)_minmax(260px,1.1fr)_auto] lg:items-start"
                    >
                      <div className="grid gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-sm font-semibold text-ink">{field.label}</h3>
                          {field.configured ? (
                            <span className="rounded border border-border bg-muted px-2 py-0.5 text-[11px] font-semibold text-secondary">
                              已配置
                            </span>
                          ) : null}
                          {isDirty ? (
                            <span className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
                              已修改
                            </span>
                          ) : null}
                        </div>
                        <code className="text-xs text-mutedtext">{field.key}</code>
                        <p className="text-xs leading-5 text-secondary">{field.help}</p>
                      </div>

                      <div className="grid gap-2">
                        <div className="flex flex-wrap gap-2">
                          <span
                            className={`rounded border px-2 py-0.5 text-[11px] font-semibold ${sourceBadgeClass(
                              field.source,
                            )}`}
                          >
                            {field.source}
                          </span>
                          <span className="rounded border border-border bg-subtle px-2 py-0.5 text-[11px] font-semibold text-secondary">
                            {RESTART_LABELS[field.restart] ?? field.restart}
                          </span>
                        </div>
                        {renderFieldInput(field, value, (nextValue) => updateDraft(field, nextValue))}
                      </div>

                      <div className="flex items-center justify-end">
                        {showClear ? (
                          <button
                            className="rounded-md border border-border bg-white px-3 py-2 text-sm font-semibold text-ink transition hover:border-accentstrong disabled:cursor-not-allowed disabled:opacity-50"
                            type="button"
                            onClick={() => void clearField(field)}
                            disabled={saveState === 'saving'}
                          >
                            清除
                          </button>
                        ) : null}
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>
          ))
        ) : (
          <div className="grid gap-3" aria-label="设置分组加载中">
            {EXPECTED_GROUP_TITLES.map((title) => (
              <section key={title} className="rounded-lg border border-border bg-white p-5 shadow-soft" aria-label={title}>
                <h2 className="text-xl font-semibold text-ink">{title}</h2>
                <p className="mt-2 text-sm text-secondary">正在读取运行设置。</p>
              </section>
            ))}
          </div>
        )}
      </div>
    </ProductShell>
  )
}
