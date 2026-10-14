import { useEffect, useRef, useState } from 'react'
import { FiClock, FiDownload, FiEye, FiFileText, FiPrinter, FiRefreshCw, FiX } from 'react-icons/fi'
import { api, ApiError, errorMessage } from '../../api/client'

interface Report {
  id: number
  name: string
  slug: string
  category: string
  period: string
  file_size_kb: number
  generated_at: string | null
  file_available: boolean
}

/** Save a generated report to the user's computer. Throws if the file isn't available. */
async function saveReportFile(report: Pick<Report, 'id' | 'slug'>) {
  const url = URL.createObjectURL(await api.blob(`/api/reports/${report.id}/download/`))
  const link = document.createElement('a')
  link.href = url
  link.download = `${report.slug}.html`
  link.click()
  URL.revokeObjectURL(url)
}

const CATEGORIES = ['All', 'Sales', 'Finance', 'Inventory', 'HR', 'IT']

const CATEGORY_COLOR: Record<string, string> = {
  Sales: 'text-blue-500',
  Finance: 'text-purple-500',
  Inventory: 'text-orange-400',
  HR: 'text-green-500',
  IT: 'text-yellow-500',
}

function formatSize(kb: number): string {
  if (kb >= 1000) return `${(kb / 1024).toFixed(1)} MB`
  return `${kb} KB`
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

type GenerateState = 'idle' | 'loading' | 'done' | 'error'

function GenerateModal({
  reports,
  onClose,
  onSuccess,
}: {
  reports: Report[]
  onClose: () => void
  onSuccess: () => void
}) {
  const [slug, setSlug] = useState(reports[0]?.slug ?? '')
  const [directives, setDirectives] = useState('')
  const [state, setState] = useState<GenerateState>('idle')
  const [agentResponse, setAgentResponse] = useState('')
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (overlayRef.current === e.target) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  const handleSubmit = async () => {
    if (!slug || state === 'loading') return
    setState('loading')
    setAgentResponse('')
    try {
      const data = await api.post<{ response?: string }>(`/api/reports/generate/${slug}/`, { directives })
      setAgentResponse(data.response ?? '')
      setState('done')
      onSuccess()
    } catch (err) {
      setAgentResponse(err instanceof ApiError ? errorMessage(err, 'Generation failed.') : 'An unexpected error occurred.')
      setState('error')
    }
  }

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
    >
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
          <span className="font-semibold text-sm">Generate Report</span>
          <button type="button" onClick={onClose} className="text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors">
            <FiX className="w-4 h-4" />
          </button>
        </div>

        <div className="px-5 py-4 flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[var(--muted-foreground)]">Report</label>
            <select
              value={slug}
              onChange={e => setSlug(e.target.value)}
              disabled={state === 'loading' || state === 'done'}
              className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--border)] bg-[var(--input-background)] text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)] disabled:opacity-50"
            >
              {reports.map(r => (
                <option key={r.slug} value={r.slug}>{r.name}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[var(--muted-foreground)]">
              Directives <span className="font-normal opacity-60">(optional)</span>
            </label>
            <textarea
              value={directives}
              onChange={e => setDirectives(e.target.value)}
              disabled={state === 'loading' || state === 'done'}
              placeholder="e.g. Focus on Q1, include year-over-year comparison…"
              rows={3}
              className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--border)] bg-[var(--input-background)] text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)] resize-none disabled:opacity-50"
            />
          </div>

          {agentResponse && (
            <div className={`text-xs rounded-lg px-3 py-2.5 leading-relaxed ${state === 'error' ? 'bg-rose-500/10 text-rose-500' : 'bg-green-500/10 text-green-600'}`}>
              {agentResponse}
            </div>
          )}
        </div>

        <div className="px-5 py-3.5 border-t border-[var(--border)] flex justify-end gap-2">
          {state !== 'done' && (
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-1.5 text-sm rounded-lg border border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
            >
              Cancel
            </button>
          )}
          {state === 'done' ? (
            <button type="button" onClick={onClose} className="px-4 py-1.5 text-sm rounded-lg bg-[var(--primary)] text-white font-medium">
              Close
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!slug || state === 'loading'}
              className="flex items-center gap-2 px-4 py-1.5 text-sm rounded-lg bg-[var(--primary)] text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
            >
              {state === 'loading' && <FiRefreshCw className="w-3.5 h-3.5 animate-spin" />}
              {state === 'loading' ? 'Generating…' : 'Generate'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function ReportViewerModal({ report, onClose }: { report: Report; onClose: () => void }) {
  const [html, setHtml] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    api.get<{ html?: string }>(`/api/reports/${report.id}/view/`)
      .then(data => {
        if (data.html) setHtml(data.html)
        else setError('Report content unavailable.')
      })
      .catch(() => setError('Failed to load report.'))
      .finally(() => setLoading(false))
  }, [report.id])

  const handleDownload = () => {
    saveReportFile(report).catch(() => undefined)
  }

  const handlePrint = () => {
    iframeRef.current?.contentWindow?.print()
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[var(--background)]">
      <div className="h-12 px-4 flex items-center justify-between border-b border-[var(--border)] bg-[var(--card)] shrink-0">
        <div className="flex items-center gap-2.5">
          <FiFileText className="text-[var(--muted-foreground)] w-4 h-4" />
          <span className="font-semibold text-sm">{report.name}</span>
          <span className="text-xs text-[var(--muted-foreground)]">· {report.period}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handlePrint}
            disabled={loading || !!error}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors disabled:opacity-40"
          >
            <FiPrinter className="w-3.5 h-3.5" /> Print
          </button>
          <button
            type="button"
            onClick={handleDownload}
            disabled={loading || !!error}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors disabled:opacity-40"
          >
            <FiDownload className="w-3.5 h-3.5" /> Download
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-[var(--primary)] text-white"
          >
            <FiX className="w-3.5 h-3.5" /> Close
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        {loading && (
          <div className="h-full flex items-center justify-center text-sm text-[var(--muted-foreground)]">
            Loading report…
          </div>
        )}
        {error && (
          <div className="h-full flex items-center justify-center text-sm text-rose-500">{error}</div>
        )}
        {!loading && !error && (
          <iframe
            ref={iframeRef}
            srcDoc={html}
            title={report.name}
            className="w-full h-full border-0 bg-white"
            sandbox="allow-popups allow-modals"
          />
        )}
      </div>
    </div>
  )
}

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([])
  const [activeCategory, setActiveCategory] = useState('All')
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState<number | null>(null)
  const [showGenerateModal, setShowGenerateModal] = useState(false)
  const [viewingReport, setViewingReport] = useState<Report | null>(null)

  const fetchReports = () => {
    setLoading(true)
    const params = activeCategory !== 'All' ? `?category=${activeCategory}` : ''
    api.get<Report[]>(`/api/reports/${params}`)
      .then(setReports)
      .catch(() => setReports([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchReports() }, [activeCategory])

  const handleDownload = async (report: Report) => {
    if (!report.file_available || downloading === report.id) return
    setDownloading(report.id)
    try {
      await saveReportFile(report)
    } catch {
      alert('File not available yet. Generate the report first.')
    } finally {
      setDownloading(null)
    }
  }

  return (
    <>
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex gap-2 flex-wrap">
            {CATEGORIES.map(cat => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors cursor-pointer ${
                  activeCategory === cat
                    ? 'bg-[var(--primary)] text-white border-[var(--primary)]'
                    : 'bg-[var(--card)] text-[var(--foreground)] border-[var(--border)] hover:border-[var(--primary)] hover:text-[var(--primary)]'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setShowGenerateModal(true)}
            className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-[var(--primary)] text-white text-sm font-medium hover:opacity-90 transition-opacity"
          >
            <FiRefreshCw className="w-3.5 h-3.5" />
            Generate Report
          </button>
        </div>

        <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-4 border-b border-[var(--border)]">
            <FiClock className="text-[var(--muted-foreground)] w-4 h-4" />
            <span className="font-semibold text-sm">Available Reports</span>
          </div>

          {loading ? (
            <div className="py-16 text-center text-sm text-[var(--muted-foreground)]">Loading…</div>
          ) : reports.length === 0 ? (
            <div className="py-16 text-center text-sm text-[var(--muted-foreground)]">No reports found.</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  {['Report Name', 'Category', 'Period', 'Size', 'Generated', 'Actions'].map(col => (
                    <th key={col} className="px-5 py-3 text-left text-xs font-medium text-[var(--muted-foreground)]">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {reports.map(report => (
                  <tr key={report.id} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--muted)]/40 transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <FiFileText className="text-[var(--muted-foreground)] w-4 h-4 shrink-0" />
                        <span className="font-medium text-[var(--foreground)]">{report.name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={`text-xs font-semibold ${CATEGORY_COLOR[report.category] ?? 'text-[var(--muted-foreground)]'}`}>
                        {report.category}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-[var(--muted-foreground)]">{report.period}</td>
                    <td className="px-5 py-3.5 text-[var(--muted-foreground)]">{formatSize(report.file_size_kb)}</td>
                    <td className="px-5 py-3.5 text-[var(--muted-foreground)]">{formatDate(report.generated_at)}</td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => setViewingReport(report)}
                          disabled={!report.file_available}
                          className={`flex items-center gap-1.5 text-xs font-semibold transition-colors ${
                            report.file_available
                              ? 'text-[var(--primary)] hover:opacity-70 cursor-pointer'
                              : 'text-[var(--muted-foreground)] opacity-30 cursor-not-allowed'
                          }`}
                        >
                          <FiEye className="w-3.5 h-3.5" /> View
                        </button>
                        <button
                          onClick={() => handleDownload(report)}
                          disabled={!report.file_available || downloading === report.id}
                          className={`flex items-center gap-1.5 text-xs font-semibold transition-colors ${
                            report.file_available
                              ? 'text-[var(--muted-foreground)] hover:text-[var(--foreground)] cursor-pointer'
                              : 'text-[var(--muted-foreground)] opacity-30 cursor-not-allowed'
                          }`}
                        >
                          <FiDownload className="w-3.5 h-3.5" />
                          {downloading === report.id ? 'Downloading…' : 'Download'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {showGenerateModal && (
        <GenerateModal
          reports={reports}
          onClose={() => setShowGenerateModal(false)}
          onSuccess={() => {
            setShowGenerateModal(false)
            fetchReports()
          }}
        />
      )}

      {viewingReport && (
        <ReportViewerModal
          report={viewingReport}
          onClose={() => setViewingReport(null)}
        />
      )}
    </>
  )
}
