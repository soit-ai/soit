import { expect, test, type Page } from '@playwright/test'
import { writeFile } from 'node:fs/promises'
import { mockShellApi } from '../helpers'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
  localStorage.setItem('i18nextLng', 'en-US')
}

const plugins = [
  {
    id: 'plugin-github',
    name: 'GitHub MCP',
    version: '0.9.2',
    publisher: 'SOIT Official',
    plugin_type: 'mcp',
    status: 'active',
    description: 'Operate GitHub repositories, issues, and pull requests.',
    spec_json: {},
    metadata_json: {
      tags: ['Agent', 'Workflow', 'Task'],
      permissions: ['Read repository content', 'Manage issues and pull requests'],
      dependencies: ['mcp-core >= 1.2.0', 'github-api >= 5.1.0'],
      risk: 'high',
      source: 'official',
    },
    publish_status: 'published',
    installed_count: 12,
    installed: true,
    enabled: true,
    created_at: '2026-06-01T09:00:00.000Z',
    updated_at: '2026-06-02T09:00:00.000Z',
  },
  {
    id: 'plugin-doc-summary',
    name: 'Document Summary',
    version: '1.3.5',
    publisher: 'Community Lab',
    plugin_type: 'skill',
    status: 'active',
    description: 'Summarize and extract key points from long documents.',
    spec_json: {},
    metadata_json: {
      tags: ['Agent', 'Workflow'],
      risk: 'low',
      source: 'community',
    },
    publish_status: 'published',
    installed_count: 5,
    installed: false,
    enabled: false,
    created_at: '2026-05-20T09:00:00.000Z',
    updated_at: '2026-05-30T09:00:00.000Z',
  },
]

const capabilities = [
  {
    ref: 'tool:http:github_issue_search',
    kind: 'tool',
    name: 'GitHub MCP',
    source_kind: 'plugin',
    source_id: 'plugin-github',
    source_version: '0.9.2',
    artifact_kind: 'tool',
    plugin_id: 'plugin-github',
    plugin_version_id: 'plugin-github-v1',
    installation_id: 'installation-github',
    metadata_json: {
      tags: ['Agent', 'Workflow', 'Task'],
      permissions: ['Read repository content', 'Manage issues and pull requests'],
      dependencies: ['mcp-core >= 1.2.0', 'github-api >= 5.1.0'],
      risk: 'high',
    },
  },
  {
    ref: 'plugin:summary:skill',
    kind: 'skill',
    name: 'Document Summary',
    source_kind: 'plugin',
    source_id: 'plugin-doc-summary',
    source_version: '1.3.5',
    artifact_kind: 'skill',
    plugin_id: 'plugin-doc-summary',
    plugin_version_id: 'plugin-doc-summary-v1',
    installation_id: null,
    metadata_json: {
      tags: ['Agent', 'Workflow'],
      risk: 'low',
    },
  },
]

const envelope = <T,>(data: T) => ({
  success: true,
  code: 'OK',
  message: 'OK',
  data,
})

async function mockPluginApi(page: Page) {
  await page.route('**/api/v1/plugins**', async (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (!pathname.endsWith('/api/v1/plugins')) {
      await route.fallback()
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(envelope({
        items: plugins,
        page_size: 100,
        next_page_token: null,
      })),
    })
  })

  await page.route('**/api/v1/plugins/runtime/reload', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(envelope({ loaded_count: 1 })),
    })
  })

  await page.route('**/api/v1/plugins/*/enabled', async (route) => {
    const parts = new URL(route.request().url()).pathname.split('/')
    const pluginId = parts[parts.length - 2]
    const body = JSON.parse(route.request().postData() || '{}')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(envelope({
        id: `installation-${pluginId}`,
        plugin_id: pluginId,
        tenant_id: 'tenant-1',
        workspace_id: 'workspace-1',
        enabled: Boolean(body.enabled),
        state: 'installed',
        created_at: '2026-06-01T09:00:00.000Z',
        updated_at: '2026-06-02T10:00:00.000Z',
      })),
    })
  })

  await page.route('**/api/v1/plugins/*/install', async (route) => {
    const method = route.request().method()
    const parts = new URL(route.request().url()).pathname.split('/')
    const pluginId = parts[parts.length - 2]
    if (method === 'DELETE') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(envelope({})) })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(envelope({
        id: `installation-${pluginId}`,
        plugin_id: pluginId,
        installed_at: '2026-06-02T10:00:00.000Z',
      })),
    })
  })

  await page.route('**/api/v1/plugins/capabilities**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(envelope({
        items: capabilities,
        page_size: 100,
        next_page_token: null,
      })),
    })
  })

  await page.route('**/api/v1/agents/*/bindings', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: [
          {
            id: 'binding-1',
            agent_id: 'agent-1',
            binding_type: 'tool',
            target_key: 'tool:http:github_issue_search',
            config_json: {},
            sort_order: 1,
            created_at: '2026-06-01T09:00:00.000Z',
            updated_at: '2026-06-01T09:00:00.000Z',
          },
        ],
      }),
    })
  })

  await page.route('**/api/v1/agents**', async (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (!pathname.endsWith('/api/v1/agents')) {
      await route.fallback()
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          items: [
            {
              id: 'agent-1',
              tenant_id: 'tenant-1',
              workspace_id: 'workspace-1',
              name: 'Repository Agent',
              status: 'active',
              visibility: 'private',
              is_public: false,
              featured: false,
              downloads_count: 0,
              reviews_count: 0,
              created_at: '2026-06-01T09:00:00.000Z',
              updated_at: '2026-06-01T09:00:00.000Z',
            },
          ],
          page_size: 100,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/runs**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          items: [
            {
              id: 'run-1',
              mode: 'agent',
              subject_kind: 'agent',
              subject_id: 'agent-1',
              status: 'succeeded',
              started_at: '2026-06-02T09:30:00.000Z',
              created_at: '2026-06-02T09:30:00.000Z',
              updated_at: '2026-06-02T09:31:00.000Z',
            },
          ],
          page_size: 3,
          next_page_token: null,
        },
      }),
    })
  })
}

async function uploadPluginPackageFile(page: Page, dialogName: string, packagePath: string) {
  const dialog = page.getByRole('dialog', { name: dialogName })
  await expect(dialog).toBeVisible()
  await dialog.getByLabel('Plugin package file').setInputFiles(packagePath)
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockShellApi(page)
  await mockPluginApi(page)
})

test('plugin workbench opens capability details in a side panel', async ({ page }) => {
  await page.goto('/plugins', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Capability Workbench')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('Plugin Library')).toBeVisible()
  await expect(page.getByRole('table').getByText('GitHub MCP', { exact: true })).toBeVisible()
  await expect(page.getByRole('table').getByText('tool:http:github_issue_search')).toBeVisible()
  await expect(page.getByText('Read repository content')).toBeHidden()

  await page.getByRole('row', { name: /GitHub MCP/ }).click()
  const details = page.getByRole('dialog', { name: 'GitHub MCP' })
  await expect(details).toBeVisible()
  await expect(details.getByText('Read repository content')).toBeVisible()
  await expect(details.getByText('Repository Agent')).toBeVisible()

  await page.keyboard.press('Escape')
  await page.getByPlaceholder('Search capability name, tag, publisher').fill('summary')
  await expect(page.getByRole('table').getByText('Document Summary', { exact: true })).toBeVisible()
  await expect(page.getByRole('table').getByText('GitHub MCP')).toBeHidden()

  await page.getByText('MCP', { exact: true }).click()
  await expect(page.getByText('No plugin capabilities found.')).toBeVisible()
})

test('plugin workbench actions call plugin lifecycle api', async ({ page }) => {
  const enabledRequests: boolean[] = []
  await page.route('**/api/v1/plugins/*/enabled', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}')
    enabledRequests.push(Boolean(body.enabled))
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(envelope({
        id: 'installation-plugin-github',
        plugin_id: 'plugin-github',
        tenant_id: 'tenant-1',
        workspace_id: 'workspace-1',
        enabled: Boolean(body.enabled),
        state: 'installed',
        created_at: '2026-06-01T09:00:00.000Z',
        updated_at: '2026-06-02T10:00:00.000Z',
      })),
    })
  })

  await page.goto('/plugins', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('table').getByText('GitHub MCP', { exact: true })).toBeVisible({ timeout: 15_000 })

  await page.getByRole('row', { name: /GitHub MCP/ }).click()
  await page.getByRole('dialog', { name: 'GitHub MCP' }).getByRole('button', { name: 'Disable' }).click()
  await expect.poll(() => enabledRequests).toEqual([false])

  await page.keyboard.press('Escape')
  await page.getByRole('table').getByRole('button', { name: 'Install' }).click()
  await expect(page.getByText('Plugin installed')).toBeVisible()
})

test('plugin workbench uploads packages and confirms same-version reinstall', async ({ page }, testInfo) => {
  const packagePath = testInfo.outputPath('local-plugin.zip')
  await writeFile(packagePath, Buffer.from('fake zip payload'))
  const uploadModes: string[] = []

  await page.route('**/api/v1/plugins/package**', async (route) => {
    const url = new URL(route.request().url())
    const mode = url.searchParams.get('mode') || 'auto'
    uploadModes.push(mode)
    if (uploadModes.length === 2 && mode === 'auto') {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          code: 'CONFLICT',
          message: 'Plugin package version already exists',
          details: { reason: 'same_version_exists', name: 'Local Skill', version: '1.0.0' },
        }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(envelope({
        action: mode === 'reinstall' ? 'reinstalled' : 'created',
        plugin: {
          id: 'plugin-local-skill',
          name: 'Local Skill',
          version: '1.0.0',
          publisher: 'soit',
          plugin_type: 'skill',
          status: 'active',
          description: 'Local skill package.',
          spec_json: {},
          metadata_json: { tags: ['Local'], source: 'private' },
          publish_status: 'published',
          installed_count: 1,
          installed: true,
          enabled: true,
          created_at: '2026-06-03T09:00:00.000Z',
          updated_at: '2026-06-03T09:00:00.000Z',
        },
        install: {
          install_dir: '/tmp/plugins/local-skill',
          package_path: '/tmp/plugins/local-skill/package.zip',
          manifest_path: '/tmp/plugins/local-skill/manifest.json',
          spec_path: '/tmp/plugins/local-skill/spec.json',
        },
      })),
    })
  })

  await page.goto('/plugins', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Capability Workbench')).toBeVisible({ timeout: 15_000 })

  await page.getByRole('button', { name: 'Upload package' }).click()
  await uploadPluginPackageFile(page, 'Upload plugin package', packagePath)
  await page.getByRole('dialog', { name: 'Upload plugin package' }).getByRole('button', { name: 'Upload' }).click()
  await expect(page.getByText('Plugin package created')).toBeVisible()
  await expect(page.getByRole('table').getByText('Local Skill', { exact: true })).toBeVisible()
  await expect(page.getByRole('dialog', { name: 'Upload plugin package' })).toBeHidden()

  await page.getByRole('button', { name: 'Upload package' }).click()
  await uploadPluginPackageFile(page, 'Upload plugin package', packagePath)
  await page.getByRole('dialog', { name: 'Upload plugin package' }).getByRole('button', { name: 'Upload' }).click()
  await expect(page.getByRole('alertdialog', { name: 'Reinstall plugin package?' })).toBeVisible()
  await page.getByRole('button', { name: 'Reinstall' }).click()
  await expect(page.getByText('Plugin package reinstalled')).toBeVisible()
  await expect.poll(() => uploadModes).toEqual(['auto', 'auto', 'reinstall'])
})

test('plugin workbench keeps uploaded plugin visible after capabilities refresh', async ({ page }, testInfo) => {
  const packagePath = testInfo.outputPath('weather-plugin.zip')
  await writeFile(packagePath, Buffer.from('fake zip payload'))
  let uploaded = false
  const weatherPlugin = {
    id: 'plugin-weather-query',
    name: 'weather-query',
    version: '1.0.0',
    publisher: 'soit',
    plugin_type: 'mixed',
    status: 'active',
    description: 'Query current weather and short forecasts.',
    spec_json: {},
    metadata_json: { tags: ['Weather'], source: 'private' },
    publish_status: 'published',
    installed_count: 1,
    installed: true,
    enabled: true,
    created_at: '2026-06-03T09:00:00.000Z',
    updated_at: '2026-06-03T09:00:00.000Z',
  }

  await page.route('**/api/v1/plugins', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(envelope({
        items: uploaded ? [weatherPlugin, ...plugins] : plugins,
        page_size: 100,
        next_page_token: null,
      })),
    })
  })

  await page.route('**/api/v1/plugins/capabilities**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(envelope({
        items: uploaded
          ? [
              {
                ref: 'skill:weather_query',
                kind: 'skill',
                name: 'Weather Query Skill',
                source_kind: 'plugin',
                source_id: 'plugin-weather-query',
                source_version: '1.0.0',
                artifact_kind: 'skill',
                plugin_id: 'plugin-weather-query',
                plugin_version_id: 'plugin-weather-query-v1',
                installation_id: 'installation-weather-query',
                metadata_json: { tags: ['Weather'], risk: 'low' },
              },
              ...capabilities,
            ]
          : capabilities,
        page_size: 100,
        next_page_token: null,
      })),
    })
  })

  await page.route('**/api/v1/plugins/package**', async (route) => {
    uploaded = true
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(envelope({
        action: 'created',
        plugin: weatherPlugin,
        install: {
          install_dir: '/tmp/plugins/weather-query',
          package_path: '/tmp/plugins/weather-query/package.zip',
          manifest_path: '/tmp/plugins/weather-query/manifest.json',
          spec_path: '/tmp/plugins/weather-query/spec.json',
        },
      })),
    })
  })

  await page.goto('/plugins', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Capability Workbench')).toBeVisible({ timeout: 15_000 })

  await page.getByRole('button', { name: 'Upload package' }).click()
  await uploadPluginPackageFile(page, 'Upload plugin package', packagePath)
  await page.getByRole('dialog', { name: 'Upload plugin package' }).getByRole('button', { name: 'Upload' }).click()
  await expect(page.getByRole('table').getByText('skill:weather_query', { exact: true })).toBeVisible()
  await expect(page.getByRole('table').getByText('weather-query', { exact: true })).toBeVisible()
})

test('plugin workbench updates installed package and confirms uninstall', async ({ page }, testInfo) => {
  const packagePath = testInfo.outputPath('github-plugin.zip')
  await writeFile(packagePath, Buffer.from('fake zip payload'))
  const upgradeRequests: string[] = []
  const uninstallRequests: string[] = []

  await page.route('**/api/v1/plugins/*/upgrade-package', async (route) => {
    const parts = new URL(route.request().url()).pathname.split('/')
    upgradeRequests.push(parts[parts.length - 2])
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(envelope({
        plugin: {
          ...plugins[0],
          version: '1.0.0',
          updated_at: '2026-06-03T10:00:00.000Z',
        },
        install: {
          install_dir: '/tmp/plugins/github',
          package_path: '/tmp/plugins/github/package.zip',
          manifest_path: '/tmp/plugins/github/manifest.json',
          spec_path: '/tmp/plugins/github/spec.json',
        },
      })),
    })
  })

  await page.route('**/api/v1/plugins/*/install', async (route) => {
    const method = route.request().method()
    const parts = new URL(route.request().url()).pathname.split('/')
    const pluginId = parts[parts.length - 2]
    if (method === 'DELETE') {
      uninstallRequests.push(pluginId)
      await route.fulfill({ status: 204, contentType: 'application/json', body: '' })
      return
    }
    await route.fallback()
  })

  await page.goto('/plugins', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('table').getByText('GitHub MCP', { exact: true })).toBeVisible({ timeout: 15_000 })

  await page.getByRole('row', { name: /GitHub MCP/ }).click()
  const details = page.getByRole('dialog', { name: 'GitHub MCP' })
  await details.getByRole('button', { name: 'Update package' }).click()
  await uploadPluginPackageFile(page, 'Update plugin package', packagePath)
  await page.getByRole('dialog', { name: 'Update plugin package' }).getByRole('button', { name: 'Upload' }).click()
  await expect(page.getByText('Plugin package upgraded')).toBeVisible()
  await expect.poll(() => upgradeRequests).toEqual(['plugin-github'])

  await details.getByRole('button', { name: 'Uninstall' }).click()
  await expect(page.getByRole('alertdialog', { name: 'Uninstall plugin?' })).toBeVisible()
  await page.getByRole('button', { name: 'Uninstall' }).click()
  await expect(page.getByText('Plugin uninstalled')).toBeVisible()
  await expect.poll(() => uninstallRequests).toEqual(['plugin-github'])
})
